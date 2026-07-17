"""Écran de jeu : affichage du plateau et du chevalet (pywebview).

Première brique de l'écran de jeu (suite de l'écran d'accueil, issue #27).
Cet écran est **en lecture seule** : il affiche le plateau, les tuiles déjà
posées, les scores, le joueur courant et le nombre de jetons restants dans le
sac. Aucune pose de mot n'est encore possible ici (ce sera l'étape suivante).

Confidentialité du chevalet
---------------------------
Dans une partie à plusieurs joueurs humains sur le même écran, le chevalet du
joueur courant n'est **jamais** affiché automatiquement : il reste masqué par
défaut. Seul un clic explicite sur « voir mes lettres » le révèle, et « cacher
mes lettres » le remasque à tout moment (pas seulement au changement de tour).
Côté API, une seule règle structurelle garantit ce principe : :meth:`ApiJeu.
obtenir_chevalet` n'expose **que** le chevalet du joueur dont l'index est
demandé — il n'existe aucune méthode renvoyant tous les chevalets d'un coup, et
:func:`etat_public` ne contient aucune identité de lettre.

Lancement de l'écran pour test (mode démonstration) ::

    python -m scrabble.ui.jeu

Ce mode construit une :class:`~scrabble.moteur.partie.Partie` d'exemple à deux
joueurs, avec un plateau partiellement rempli (voir :func:`construire_partie_demo`),
et ouvre l'écran de jeu sans passer par l'écran d'accueil.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import webview

from scrabble import journal
from scrabble.config import THEMES_PLATEAU, charger_config
from scrabble.dictionnaire.dictionnaire import Trie, normaliser_mot
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import (
    ActionInvalide,
    EntreeHistorique,
    Joueur,
    Partie,
)
from scrabble.moteur.plateau_partie import (
    Coup,
    Direction,
    PlateauPartie,
    Tuile,
    dans_plateau,
)
from scrabble.moteur.score import DetailMot, DetailScore, detailler_score
from scrabble.persistance import (
    CHEMIN_DEFAUT,
    enregistrer_action,
    finaliser_partie,
)
from scrabble.moteur.validation import CoupInvalide, DictionnaireMots, valider_coup
from scrabble.regles.lettres import JOKER, valeur_lettre
from scrabble.regles.plateau import TAILLE, type_case

DOSSIER_WEB = Path(__file__).parent / "web"


# --------------------------------------------------------------------------- #
# Sérialisation de l'état de partie vers des structures JSON (logique non-UI)
# --------------------------------------------------------------------------- #
# Ces fonctions sont volontairement pures et sans dépendance à pywebview : elles
# sont testables directement (voir tests/test_jeu.py). Le type de chaque case
# provient de scrabble.regles.plateau.type_case — il n'est PAS redéfini côté JS.


def serialiser_case(plateau: PlateauPartie, ligne: int, colonne: int) -> dict[str, Any]:
    """Sérialise une case : son type de bonus et la tuile éventuellement posée.

    Le champ ``type`` est la valeur du :class:`~scrabble.regles.plateau.TypeCase`
    (``"MT"``, ``"MD"``, ``"LT"``, ``"LD"``, ``"centre"`` ou ``"normale"``). Si
    la case porte une tuile, ``lettre`` est la lettre affichée, ``joker`` dit si
    c'est un joker (valeur nulle) et ``valeur`` est le nombre de points de la
    tuile (0 pour un joker, cohérent avec le chevalet — voir
    :func:`serialiser_chevalet`) ; sinon ``lettre`` vaut ``None`` et ``valeur``
    vaut 0. Le JS affiche cette ``valeur`` en indice sur la tuile posée
    (classe CSS ``.tuile-valeur``), comme sur les lettres du chevalet/brouillon.
    """
    tuile = plateau.tuile(ligne, colonne)
    if tuile is None:
        valeur = 0
    elif tuile.joker:
        valeur = 0
    else:
        valeur = valeur_lettre(tuile.lettre)
    return {
        "type": type_case(ligne, colonne).value,
        "lettre": tuile.lettre if tuile is not None else None,
        "joker": bool(tuile.joker) if tuile is not None else False,
        "valeur": valeur,
    }


def serialiser_plateau(plateau: PlateauPartie) -> list[list[dict[str, Any]]]:
    """Sérialise les ``TAILLE`` × ``TAILLE`` cases du plateau en lignes de cases."""
    return [
        [serialiser_case(plateau, ligne, colonne) for colonne in range(TAILLE)]
        for ligne in range(TAILLE)
    ]


# Côtés du plateau occupés par les adversaires du joueur humain de référence,
# dans l'ordre de rotation imposé par l'issue #33 : le premier autre joueur va
# en haut (face à face avec le joueur du bas), puis à gauche, puis à droite.
COTES_ADVERSAIRES = ("haut", "gauche", "droite")


def calculer_positions(joueurs: list[Joueur]) -> list[str]:
    """Position spatiale de chaque joueur autour du plateau (index → côté).

    Renvoie une liste parallèle à ``joueurs`` où l'élément ``i`` est le côté
    (``"bas"``, ``"haut"``, ``"gauche"`` ou ``"droite"``) assigné au joueur
    d'index ``i``. Règle (issue #33), avec une seule source de vérité côté
    Python :

    * Le **joueur humain de référence** — le premier joueur ``humain`` de la
      liste ``joueurs`` — est toujours en ``"bas"`` (position naturelle face à
      l'écran). S'il n'y a aucun humain (cas théorique / test), le premier
      joueur tient ce rôle.
    * Tous les autres joueurs (humains et ordinateurs confondus) se répartissent
      sur les côtés restants dans l'ordre de la liste, en tournant :
      ``haut``, puis ``gauche``, puis ``droite``.

    Cas particuliers : liste vide → ``[]`` ; un seul joueur → ``["bas"]`` (aucune
    position latérale).
    """
    if not joueurs:
        return []
    reference = next(
        (index for index, joueur in enumerate(joueurs) if joueur.humain), 0
    )
    positions = [""] * len(joueurs)
    positions[reference] = "bas"
    rang = 0
    for index in range(len(joueurs)):
        if index == reference:
            continue
        positions[index] = COTES_ADVERSAIRES[rang % len(COTES_ADVERSAIRES)]
        rang += 1
    return positions


# Bibliothèque d'avatars SVG (issue #34). Chaque identifiant correspond à un
# fichier ``web/avatars/<id>.svg`` (portraits stylisés originaux, un jeu de
# traits distinctifs par avatar). Une quinzaine suffit largement à garantir
# l'absence de doublon avec au plus 4 joueurs par partie. L'ordre de cette liste
# fait partie du contrat déterministe : ne pas la réordonner sans raison.
AVATARS: tuple[str, ...] = tuple(f"avatar-{n:02d}" for n in range(1, 16))


def _graine_avatar(joueur: Joueur, index: int) -> int:
    """Graine stable (indépendante de l'exécution) pour le choix d'avatar.

    Dérivée du nom du joueur **et** de son index dans la partie : deux joueurs
    homonymes reçoivent ainsi des graines différentes. On passe par ``hashlib``
    plutôt que par ``hash()`` intégré, dont la valeur varie d'un processus à
    l'autre (``PYTHONHASHSEED``) — la reproductibilité inter-exécutions n'est pas
    exigée ici mais elle rend les tests et le débogage plus simples.
    """
    cle = f"{index}\x00{joueur.nom}".encode("utf-8")
    return int.from_bytes(hashlib.md5(cle).digest()[:8], "big")


def calculer_avatars(joueurs: list[Joueur]) -> list[str]:
    """Avatar attribué à chaque joueur autour du plateau (index → identifiant).

    Renvoie une liste parallèle à ``joueurs`` où l'élément ``i`` est l'identifiant
    d'avatar (voir :data:`AVATARS`) assigné au joueur d'index ``i``. Comme
    :func:`calculer_positions`, c'est **une seule source de vérité** côté Python,
    consommée telle quelle par l'UI (aucune logique d'attribution dupliquée en
    JS). Propriétés garanties (issue #34) :

    * **Déterminisme** : l'attribution ne dépend que de la liste ``joueurs`` (nom
      + rang), donc un même appel sur une même partie rend toujours le même
      résultat — pas de ré-tirage à chaque rafraîchissement d'écran.
    * **Absence de doublon** tant qu'il reste des avatars libres : chaque joueur
      vise l'avatar de sa graine puis, s'il est déjà pris, un sondage linéaire
      lui trouve le prochain avatar libre. Avec ≤ 4 joueurs et 15 avatars, aucun
      doublon n'est possible.
    * **Dégradation propre** si le nombre de joueurs dépassait celui des avatars
      (cas théorique, impossible avec ``MAX_JOUEURS`` = 4) : le sondage échoue,
      on retombe sur l'avatar préféré et un doublon est toléré plutôt que de
      planter.
    """
    nb = len(AVATARS)
    assignes: list[str] = []
    pris: set[int] = set()
    for index, joueur in enumerate(joueurs):
        prefere = _graine_avatar(joueur, index) % nb
        choix = prefere
        for pas in range(nb):
            candidat = (prefere + pas) % nb
            if candidat not in pris:
                choix = candidat
                break
        pris.add(choix)
        assignes.append(AVATARS[choix])
    return assignes


def serialiser_joueur_public(
    joueur: Joueur,
    index: int,
    courant: bool,
    position: str | None = None,
    avatar: str | None = None,
) -> dict[str, Any]:
    """Sérialise les infos **publiques** d'un joueur (sans révéler ses lettres).

    Contient le nombre de lettres du chevalet (``nb_lettres``) mais **jamais**
    leur identité : l'affichage masqué peut ainsi montrer le bon nombre de
    rectangles grisés sans rien dévoiler. ``position`` est le côté du plateau
    assigné au joueur (voir :func:`calculer_positions`) : l'UI place le panneau
    du joueur sur ce côté (une seule source de vérité, calculée côté Python).
    ``avatar`` est l'identifiant du portrait SVG attribué (voir
    :func:`calculer_avatars`), également calculé côté Python.
    """
    return {
        "index": index,
        "nom": joueur.nom,
        "humain": joueur.humain,
        "niveau": joueur.niveau.name if joueur.niveau is not None else None,
        "score": joueur.score,
        "nb_lettres": len(joueur.chevalet),
        "courant": courant,
        "position": position,
        "avatar": avatar,
    }


def serialiser_chevalet(joueur: Joueur) -> list[dict[str, Any]]:
    """Sérialise le chevalet d'un joueur : lettre, valeur et drapeau joker.

    Un joker (jeton :data:`~scrabble.regles.lettres.JOKER`) n'a pas encore de
    lettre attribuée sur le chevalet : il est renvoyé avec ``lettre`` = ``"*"``,
    ``valeur`` = 0 et ``joker`` = ``True``.
    """
    return [
        {
            "lettre": jeton,
            "valeur": valeur_lettre(jeton),
            "joker": jeton == JOKER,
        }
        for jeton in joueur.chevalet
    ]


def compter_humains(partie: Partie) -> int:
    """Nombre de joueurs **humains** dans la partie (champ ``Joueur.humain``).

    Sert à décider si le bouton « voir mes lettres » a un sens : avec un seul
    humain, il n'y a personne à qui cacher son chevalet, donc l'UI l'affiche
    directement sans bouton bascule ni état masqué. Avec deux humains ou plus,
    le chevalet reste masqué par défaut (confidentialité entre adversaires).
    """
    return sum(1 for joueur in partie.joueurs if joueur.humain)


def index_panneau_interactif(partie: Partie) -> int | None:
    """Index du joueur dont le panneau du bas expose le chevalet **interactif**.

    Correction du défaut d'exposition du tour IA (issue #35). Le panneau du bas
    (chevalet, brouillon, pose clic-clic, valider/annuler, échanger) ne doit
    jamais donner accès au chevalet d'un ordinateur :

    * Si le joueur **courant** est humain — que ce soit l'unique humain ou, en
      multi-humains, celui à qui c'est le tour — le panneau du bas le suit et
      renvoie son index : le panneau est interactif pour cet humain.
    * Si le joueur courant est un **ordinateur**, la fonction renvoie ``None`` :
      aucun chevalet n'est alors exposé ni manipulable ; l'UI passe en mode
      « attente » (message + bouton « Faire jouer l'ordinateur »).

    Garantie structurelle : la valeur renvoyée ne désigne **jamais** un
    ordinateur. C'est la seule source de vérité (côté Python) du choix « panneau
    interactif ou attente », consommée telle quelle par l'UI.
    """
    joueur = partie.joueur_courant()
    return partie.index_courant if joueur.humain else None


def etat_public(partie: Partie, id_partie: int | None) -> dict[str, Any]:
    """État complet de la partie **sans aucune identité de lettre de chevalet**.

    C'est la vue partagée affichable par tous : plateau, scores, joueur courant,
    jetons restants dans le sac et état de fin. Les chevalets n'y figurent que
    par leur taille (``nb_lettres``) ; leur contenu ne s'obtient que via
    :meth:`ApiJeu.obtenir_chevalet`, un joueur à la fois.

    ``nb_humains`` (nombre de joueurs humains) permet à l'UI de n'afficher le
    bouton « voir mes lettres » que lorsqu'il y a au moins deux humains.
    ``tour_humain`` dit si le joueur courant est humain (panneau interactif) ou
    un ordinateur (panneau en attente) ; ``index_panneau`` est l'index du joueur
    dont le chevalet est exposé, ou ``None`` pendant un tour d'ordinateur (voir
    :func:`index_panneau_interactif`, issue #35).

    ``historique`` (issue #37) est la portion récente de l'historique des
    actions (voir :func:`serialiser_historique`) : la plus récente en premier,
    plafonnée à ``min(nb_joueurs * 2, 8)`` lignes, chacune avec le détail du
    score inclus pour l'ouverture au clic — l'UI alimente son encart glissant à
    partir de ce seul champ, rafraîchi après chaque action (coup humain ou série
    de tours IA).
    """
    positions = calculer_positions(partie.joueurs)
    avatars = calculer_avatars(partie.joueurs)
    return {
        "id_partie": id_partie,
        "taille": TAILLE,
        "plateau": serialiser_plateau(partie.plateau),
        "joueurs": [
            serialiser_joueur_public(
                joueur,
                index,
                index == partie.index_courant,
                positions[index],
                avatars[index],
            )
            for index, joueur in enumerate(partie.joueurs)
        ],
        "index_courant": partie.index_courant,
        "jetons_sac": partie.sac.jetons_restants(),
        "nb_humains": compter_humains(partie),
        "tour_humain": partie.joueur_courant().humain,
        "index_panneau": index_panneau_interactif(partie),
        "terminee": partie.terminee,
        "gagnants": [j.nom for j in partie.gagnants] if partie.terminee else [],
        "historique": serialiser_historique(partie),
    }


#: Plafond du nombre de lignes de l'historique glissant affichées à l'écran.
MAX_LIGNES_HISTORIQUE = 8


def nb_lignes_historique(partie: Partie) -> int:
    """Nombre de lignes d'historique à afficher : ``min(nb_joueurs * 2, 8)``.

    Règle de l'issue #37 : on montre au plus les ``nb_joueurs * 2`` dernières
    actions (soit deux « tours de table »), plafonnées à
    :data:`MAX_LIGNES_HISTORIQUE`. En tout début de partie, il peut y avoir moins
    d'actions jouées que cette borne : :func:`serialiser_historique` n'en renvoie
    alors que ce qui existe (voir cette fonction).
    """
    return min(len(partie.joueurs) * 2, MAX_LIGNES_HISTORIQUE)


def serialiser_entree_historique(
    partie: Partie, entree: "EntreeHistorique", index: int
) -> dict[str, Any]:
    """Sérialise une :class:`~scrabble.moteur.partie.EntreeHistorique` pour l'UI.

    Expose de quoi afficher une ligne de l'historique glissant (issue #37) : le
    joueur (``nom_joueur``, ``index_joueur`` et ``humain`` — ce dernier permet la
    distinction visuelle bleu/violet cohérente avec le reste de l'écran), le
    ``type`` d'action (``"coup"``/``"passe"``/``"echange"``), le
    ``score_action`` gagné à cette action (le total du coup, ``0`` pour une passe
    ou un échange) et, pour un coup, le mot principal (``mot``).

    ``index`` est la position de l'entrée dans ``partie.historique`` : c'est
    l'identifiant stable de l'action, transmis tel quel pour retrouver le détail
    au clic. Choix documenté (issue #37) : le ``detail`` complet (réutilisant
    :func:`serialiser_detail_score`) est **inclus directement** dans la
    sérialisation quand l'action en a un — le clic n'a alors besoin d'aucun
    aller-retour supplémentaire vers Python. Une passe ou un échange n'a pas de
    détail : ``detail`` vaut ``None`` (l'UI signale « rien à détailler »).

    ``positions`` (issue #58) liste les cases ``{ligne, colonne}`` nouvellement
    posées par le coup, reprises telles quelles de
    :attr:`~scrabble.moteur.partie.EntreeHistorique.positions_posees` (calculées
    par le moteur, sans recalcul ici). L'UI s'en sert pour mettre brièvement en
    surbrillance le dernier coup d'un ordinateur sur le plateau. Liste vide pour
    une passe ou un échange.
    """
    joueur = partie.joueurs[entree.index_joueur]
    score_action = entree.detail.total if entree.detail is not None else 0
    mot = (
        entree.detail.mots[0].texte
        if entree.detail is not None and entree.detail.mots
        else None
    )
    return {
        "index": index,
        "index_joueur": entree.index_joueur,
        "nom_joueur": entree.nom_joueur,
        "humain": joueur.humain,
        "action": entree.action,
        "score_action": score_action,
        "mot": mot,
        "positions": [
            {"ligne": ligne, "colonne": colonne}
            for (ligne, colonne) in entree.positions_posees
        ],
        "detail": (
            serialiser_detail_score(entree.detail)
            if entree.detail is not None
            else None
        ),
    }


def serialiser_historique(partie: Partie) -> list[dict[str, Any]]:
    """Sérialise la portion récente de l'historique pour l'encart glissant.

    Renvoie les ``min(nb_joueurs * 2, 8)`` dernières actions de la partie (voir
    :func:`nb_lignes_historique`), **la plus récente en premier** (ordre décroissant
    d'ancienneté — choix documenté de l'issue #37 : le dernier coup apparaît en
    tête de l'encart). En début de partie, moins d'actions ont été jouées que la
    borne : on ne renvoie alors que ce qui existe (p. ex. 2 lignes seulement à
    1 humain + 1 ordinateur après un tour chacun).

    Chaque entrée est sérialisée par :func:`serialiser_entree_historique`, en
    conservant son index d'origine dans ``partie.historique`` (identifiant stable
    du coup, indépendant du fenêtrage).
    """
    limite = nb_lignes_historique(partie)
    recentes = partie.historique[-limite:] if limite > 0 else []
    debut = len(partie.historique) - len(recentes)
    entrees = [
        serialiser_entree_historique(partie, entree, debut + decalage)
        for decalage, entree in enumerate(recentes)
    ]
    entrees.reverse()  # plus récent en premier
    return entrees


def serialiser_detail_score(detail: DetailScore) -> dict[str, Any]:
    """Sérialise un :class:`~scrabble.moteur.score.DetailScore` pour la modale.

    Expose le détail déjà calculé par
    :func:`~scrabble.moteur.score.detailler_score` (issue #21) sans le
    recalculer côté JS (issue #35) : pour chaque mot formé son texte, son score
    individuel et les cases bonus **effectivement utilisées** (``ligne``,
    ``colonne`` et ``type`` de case, p. ex. ``"MD"``) ; puis le bonus
    « scrabble » et le total du coup. La liste ``mots`` commence par le mot
    principal, suivie des mots transversaux.
    """
    return {
        "mots": [
            {
                "texte": mot.texte,
                "score": mot.score,
                "cases_bonus": [
                    {"ligne": ligne, "colonne": colonne, "type": case.value}
                    for (ligne, colonne, case) in mot.cases_bonus
                ],
            }
            for mot in detail.mots
        ],
        "bonus_scrabble": detail.bonus_scrabble,
        "total": detail.total,
    }


# --------------------------------------------------------------------------- #
# Construction d'un Coup à partir de placements « clic-clic » (logique non-UI)
# --------------------------------------------------------------------------- #
# Le JavaScript accumule des « placements en attente » : pour chaque lettre
# déposée sur une case vide, un dict {ligne, colonne, lettre, joker}. Ces
# fonctions transforment cette liste en un :class:`Coup` prêt pour le moteur,
# sans aucune dépendance à pywebview : elles sont testables directement (voir
# tests/test_jeu.py). Elles ne valident PAS les règles du Scrabble (rôle de
# :mod:`scrabble.moteur.validation`) ; elles garantissent seulement que la
# structure du coup est cohérente (lettres alignées et contiguës).


def _lire_placement(placement: Any) -> tuple[int, int, str, bool]:
    """Valide et normalise un placement JS en ``(ligne, colonne, lettre, joker)``.

    :raises ValueError: si la position est absente/hors plateau ou si la lettre
        n'est pas une majuscule ``A``–``Z`` (un joker porte aussi la lettre
        qu'il représente).
    """
    if not isinstance(placement, dict):
        raise ValueError("Placement invalide : dictionnaire attendu.")
    ligne = placement.get("ligne")
    colonne = placement.get("colonne")
    lettre = placement.get("lettre")
    joker = bool(placement.get("joker", False))
    if not isinstance(ligne, int) or not isinstance(colonne, int):
        raise ValueError("Placement invalide : position (ligne, colonne) manquante.")
    if not dans_plateau(ligne, colonne):
        raise ValueError(
            f"Placement hors plateau en (ligne={ligne}, colonne={colonne})."
        )
    if isinstance(lettre, str):
        lettre = lettre.upper()
    if not (isinstance(lettre, str) and len(lettre) == 1 and "A" <= lettre <= "Z"):
        raise ValueError(f"Lettre de placement invalide : {lettre!r}.")
    return ligne, colonne, lettre, joker


def _deduire_direction(
    placements: list[tuple[int, int, str, bool]],
) -> Direction:
    """Déduit le sens du mot depuis les cases posées (ou l'impose si une seule).

    * Deux lettres ou plus : le sens se déduit de leur alignement (même ligne →
      horizontal, même colonne → vertical).
    * Une seule lettre en attente : le sens est fixé arbitrairement à
      l'horizontale. Ce choix est **sans conséquence** sur la validation ou le
      score (issue #43) : le moteur calcule de toute façon le mot dans le sens
      choisi ET le mot transversal autour de la lettre, les deux devant être
      valides et étant comptés à l'identique — quel que soit le sens fixé, le
      résultat (validité, score total) est rigoureusement le même. Aucun choix
      de sens n'est donc demandé au joueur pour une lettre unique.
    * Lève :class:`ValueError` si les lettres ne sont ni alignées en ligne ni en
      colonne.
    """
    lignes = {ligne for ligne, _, _, _ in placements}
    colonnes = {colonne for _, colonne, _, _ in placements}
    if len(placements) == 1:
        return Direction.HORIZONTALE
    meme_ligne = len(lignes) == 1
    meme_colonne = len(colonnes) == 1
    if meme_ligne and not meme_colonne:
        return Direction.HORIZONTALE
    if meme_colonne and not meme_ligne:
        return Direction.VERTICALE
    raise ValueError(
        "Les lettres posées ne sont ni alignées en ligne ni en colonne."
    )


def construire_coup(
    plateau: PlateauPartie,
    placements: list[Any],
) -> Coup:
    """Construit un :class:`Coup` à partir des placements en attente du JS.

    ``placements`` est la liste des lettres déposées (dicts
    ``{ligne, colonne, lettre, joker}``). Le coup renvoyé couvre le segment
    contigu du mot principal, de la première à la dernière lettre nouvelle, en
    **incluant les tuiles déjà présentes** que le mot enjambe (leur lettre est
    reprise telle quelle). Le sens se déduit de l'alignement des lettres ; pour
    une lettre unique il est fixé à l'horizontale en interne (issue #43 : ce
    choix n'a aucune conséquence sur la validation ou le score, voir
    :func:`_deduire_direction`) — aucun paramètre de sens n'est attendu du JS.

    :raises ValueError: liste vide, position hors plateau, lettre invalide, deux
        lettres sur la même case, pose sur une case déjà occupée, lettres non
        alignées, ou trou (case vide) au milieu du mot.
    """
    if not placements:
        raise ValueError("Aucune lettre à poser sur le plateau.")
    lus = [_lire_placement(placement) for placement in placements]

    poses: dict[tuple[int, int], Tuile] = {}
    for ligne, colonne, lettre, joker in lus:
        if (ligne, colonne) in poses:
            raise ValueError(
                f"Deux lettres posées sur la même case (ligne={ligne}, "
                f"colonne={colonne})."
            )
        if not plateau.case_vide(ligne, colonne):
            raise ValueError(
                f"Une lettre est posée sur une case déjà occupée (ligne={ligne}, "
                f"colonne={colonne})."
            )
        poses[(ligne, colonne)] = Tuile(lettre, joker=joker)

    sens = _deduire_direction(lus)
    if sens is Direction.HORIZONTALE:
        ligne = lus[0][0]
        colonnes = [colonne for _, colonne, _, _ in lus]
        depart = (ligne, min(colonnes))
        cases = [(ligne, colonne) for colonne in range(min(colonnes), max(colonnes) + 1)]
    else:
        colonne = lus[0][1]
        lignes = [ligne for ligne, _, _, _ in lus]
        depart = (min(lignes), colonne)
        cases = [(ligne, colonne) for ligne in range(min(lignes), max(lignes) + 1)]

    tuiles: list[Tuile] = []
    for position in cases:
        if position in poses:
            tuiles.append(poses[position])
        else:
            existante = plateau.tuile(*position)
            if existante is None:
                raise ValueError(
                    "Les lettres posées ne sont pas contiguës : il reste une case "
                    f"vide au milieu du mot (ligne={position[0]}, "
                    f"colonne={position[1]})."
                )
            tuiles.append(existante)

    return Coup(depart[0], depart[1], sens, tuple(tuiles))


def jouer_placements(
    partie: Partie,
    placements: list[Any],
) -> dict[str, Any]:
    """Construit le coup, le fait jouer par ``partie`` et renvoie succès/erreur.

    Cœur non-UI de :meth:`ApiJeu.poser_mot`. Tous les échecs prévisibles sont
    transformés en ``{"succes": False, "erreur": <message clair>}`` sans lever :

    * structure de coup incohérente (:class:`ValueError` de
      :func:`construire_coup`) ;
    * placement illégal (:class:`~scrabble.moteur.validation.CoupInvalide`) ;
    * lettres absentes du chevalet ou partie terminée
      (:class:`~scrabble.moteur.partie.ActionInvalide`).

    En cas de succès, l'appelant recharge l'état via :func:`etat_public` : rien
    n'est perdu côté attente puisque le moteur a consommé les lettres.
    """
    try:
        coup = construire_coup(partie.plateau, placements)
    except ValueError as err:
        return {"succes": False, "erreur": str(err)}
    try:
        entree = partie.jouer_coup(coup)
    except CoupInvalide as err:
        return {"succes": False, "erreur": str(err)}
    except ActionInvalide as err:
        return {"succes": False, "erreur": str(err)}
    points = entree.detail.total if entree.detail is not None else 0
    return {
        "succes": True,
        "points": points,
        "nom": entree.nom_joueur,
        "detail": (
            serialiser_detail_score(entree.detail)
            if entree.detail is not None
            else None
        ),
    }


def simuler_coup(
    partie: Partie,
    placements: list[Any],
) -> dict[str, Any]:
    """Valide un coup en attente et calcule son score **sans le jouer** (issue #69).

    Cœur non-UI de :meth:`ApiJeu.verifier_coup`. Contrairement à
    :func:`jouer_placements`, cette fonction ne modifie **rien** de la vraie
    partie : ni le plateau réel, ni le chevalet du joueur, ni l'historique, ni le
    tour. Elle réutilise :func:`construire_coup` et
    :func:`~scrabble.moteur.validation.valider_coup` (qui raisonne déjà sur une
    copie de travail interne) pour décider de la légalité, puis calcule le détail
    du score sur une **copie** du plateau — jamais sur le plateau réel.

    Tous les échecs prévisibles sont transformés en
    ``{"succes": False, "erreur": <message clair>}`` sans lever, de la même
    nature que ceux de :func:`jouer_placements` :

    * structure de coup incohérente (:class:`ValueError` de
      :func:`construire_coup`) ;
    * placement illégal ou mot hors dictionnaire
      (:class:`~scrabble.moteur.validation.CoupInvalide`).

    En cas de succès, renvoie ``{"succes": True, "points": ..., "nom": ...,
    "detail": ...}`` **de la même forme** qu'un coup réellement joué (``detail``
    sérialisé par :func:`serialiser_detail_score`), pour que l'UI puisse réutiliser
    l'affichage déjà en place. Le contrôle « les lettres viennent du chevalet »
    n'est volontairement pas rejoué : les lettres en attente proviennent par
    construction du chevalet du joueur (mécanique clic-clic), et cette simulation
    ne consomme aucun jeton.
    """
    try:
        coup = construire_coup(partie.plateau, placements)
    except ValueError as err:
        return {"succes": False, "erreur": str(err)}
    try:
        valider_coup(partie.plateau, coup, partie.dictionnaire)
    except CoupInvalide as err:
        return {"succes": False, "erreur": str(err)}
    # Score calculé sur une copie : le plateau réel n'est jamais touché.
    travail = partie.plateau.copie()
    nouvelles = travail.poser_coup(coup)
    detail = detailler_score(travail, nouvelles, coup.direction)
    return {
        "succes": True,
        "points": detail.total,
        "nom": partie.joueur_courant().nom,
        "detail": serialiser_detail_score(detail),
    }


# --------------------------------------------------------------------------- #
# Zone de brouillon et actions de tour supplémentaires (logique non-UI)
# --------------------------------------------------------------------------- #
# Ces fonctions restent pures / testables directement (aucune dépendance à
# pywebview). La vérification dictionnaire est en LECTURE SEULE : elle ne touche
# jamais à l'état de la partie. L'échange complet délègue à Partie.echanger, qui
# consomme le tour et lève ActionInvalide si le sac est trop pauvre.


def _concatener_lettres(lettres: Any) -> str:
    """Concatène ``lettres`` (liste de jetons ou chaîne) en une seule chaîne.

    Accepte aussi bien la liste des jetons du brouillon (chacun une chaîne d'un
    caractère) qu'une chaîne déjà assemblée. Tout élément non-chaîne est ignoré.
    """
    if isinstance(lettres, str):
        return lettres
    if isinstance(lettres, (list, tuple)):
        return "".join(str(jeton) for jeton in lettres if isinstance(jeton, str))
    return ""


def verifier_mot_dictionnaire(
    dictionnaire: DictionnaireMots, lettres: Any
) -> dict[str, Any]:
    """Teste l'appartenance au dictionnaire du mot formé par ``lettres``.

    ``lettres`` est la suite de jetons arrangés dans la zone de brouillon (dans
    l'ordre affiché), soit sous forme de liste, soit déjà concaténée. Le mot est
    normalisé (majuscules, NFC) comme le Trie ODS8 l'attend, puis testé via
    :meth:`dictionnaire.contient`. **Lecture seule** : aucune mutation de la
    partie ni du dictionnaire.

    Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool}`` ; si la suite est
    vide (après normalisation), ``{"succes": False, "erreur": <message>}``. Un
    joker (``*``) laissé dans le brouillon n'est pas une lettre fixe : il empêche
    tout mot d'être trouvé (le test renverra ``valide`` faux), ce qui est le
    comportement attendu d'un simple test d'appartenance.
    """
    mot = normaliser_mot(_concatener_lettres(lettres))
    if not mot:
        return {
            "succes": False,
            "erreur": "La zone de brouillon ne contient aucune lettre à vérifier.",
        }
    return {"succes": True, "mot": mot, "valide": bool(dictionnaire.contient(mot))}


def echanger_chevalet_complet(
    partie: Partie, id_partie: int | None
) -> dict[str, Any]:
    """Remet **tout** le chevalet du joueur courant dans le sac et passe le tour.

    Cœur non-UI de :meth:`ApiJeu.echanger_tout`. Délègue à
    :meth:`~scrabble.moteur.partie.Partie.echanger` avec la totalité du chevalet
    courant : l'échange consomme déjà le tour, aucun passe séparé n'est requis.
    Le cas « sac trop pauvre pour échanger tout le chevalet » (ou partie
    terminée) est capturé et transformé en ``{"succes": False, "erreur": ...}``
    sans plantage. En cas de succès, l'état public rafraîchi est joint.
    """
    joueur = partie.joueur_courant()
    jetons = list(joueur.chevalet)
    try:
        partie.echanger(jetons)
    except ActionInvalide as err:
        return {"succes": False, "erreur": str(err)}
    return {"succes": True, "etat": etat_public(partie, id_partie)}


def jouer_tours_ia_ui(partie: Partie, id_partie: int | None) -> dict[str, Any]:
    """Joue **un seul** tour d'ordinateur puis renvoie l'état rafraîchi.

    Cœur non-UI de :meth:`ApiJeu.faire_jouer_ia`. Délègue à
    :meth:`~scrabble.moteur.partie.Partie.jouer_tour_ia`, qui joue **exactement
    un** tour d'ordinateur (issue #55). À l'origine (issue #22) ce chemin
    enchaînait tous les tours IA consécutifs d'un coup ; le retour de test manuel
    demande qu'un clic ne fasse jouer qu'un seul ordinateur à la fois, l'humain
    recliquant pour chaque ordinateur suivant. Corrige toujours le défaut
    d'exposition du tour IA (issue #35) : c'est ce chemin — et non la
    manipulation manuelle du chevalet d'un ordinateur — qui fait avancer le jeu
    pendant un tour IA.

    Renvoie ``{"succes": True, "nb_tours": <int>, "etat": <état public>}`` où
    ``nb_tours`` vaut 1 si un tour d'ordinateur vient d'être joué, 0 sinon. Si le
    joueur courant est déjà humain (ou la partie terminée), aucun tour n'est joué
    (``nb_tours`` = 0) : l'appel reste sans effet, l'état est simplement renvoyé.
    """
    nb_tours = 0
    if not partie.terminee and not partie.joueur_courant().humain:
        partie.jouer_tour_ia()
        nb_tours = 1
    return {
        "succes": True,
        "nb_tours": nb_tours,
        "etat": etat_public(partie, id_partie),
    }


# --------------------------------------------------------------------------- #
# API Python exposée au JavaScript
# --------------------------------------------------------------------------- #


class ApiJeu:
    """API Python exposée au JavaScript de l'écran de jeu (issue #90).

    Deux fenêtres pywebview partagent cette même instance d'API : la fenêtre
    **plateau** (maximisée) et la fenêtre **chevalet** (flottante, frameless,
    toujours au-dessus). L'API respecte la règle de confidentialité : l'état
    poussé vers la fenêtre plateau est **public** (jamais les lettres du
    chevalet, issues #33/#35) ; seul l'état poussé vers la fenêtre chevalet
    contient les lettres privées du **seul** joueur courant.

    Source de vérité de l'état de pose (option 1 du rapport #89, §2.2) :
    ``ApiJeu`` centralise ``_selection`` (index de la lettre sélectionnée dans
    le chevalet) et ``_en_attente`` (liste des placements en attente). Les deux
    fenêtres ne sont que des vues : elles lisent/écrivent cet état via les
    méthodes exposées, et toute mutation est rediffusée aux deux fenêtres par
    :meth:`_diffuser`.
    """

    def __init__(
        self,
        partie: Partie,
        id_partie: int | None,
        chemin_persistance: Any = CHEMIN_DEFAUT,
    ) -> None:
        self._partie = partie
        self._id_partie = id_partie
        # Base où sont persistées les actions (issue #81). Par défaut la base de
        # l'application ; injectable pour les tests (base temporaire).
        self._chemin_persistance = chemin_persistance
        # Deux fenêtres distinctes (issue #90) au lieu du ``_window`` unique.
        self._window_plateau: webview.Window | None = None
        self._window_chevalet: webview.Window | None = None
        # État de pose centralisé côté Python (issue #90, option 1 du rapport
        # #89). ``_selection`` : index de la lettre sélectionnée dans le chevalet
        # du joueur courant, ou ``None``. ``_en_attente`` : placements en cours,
        # chacun un dict ``{ligne, colonne, lettre, joker, valeur, index}`` (la
        # ``lettre`` d'un placement est déjà la lettre affichée sur le plateau,
        # même pour un joker dont la lettre a été choisie).
        self._selection: int | None = None
        self._en_attente: list[dict[str, Any]] = []
        # Pose d'un joker en attente du choix de lettre (issue #90) : lorsqu'un
        # clic sur une case du plateau (fenêtre plateau) porte sur un joker, la
        # modale de choix s'ouvre côté chevalet. On mémorise ici la case visée en
        # attendant ce choix : ``{ligne, colonne, index}`` ou ``None``.
        self._joker_demande: dict[str, Any] | None = None
        # Évite de journaliser plusieurs fois la même fin de partie (issue #66).
        self._fin_journalisee = False
        # Évite de finaliser plusieurs fois la partie en base (issue #81).
        self._fin_persistee = False
        # Vrai lorsque l'utilisateur a demandé « Retour au menu » (issue #74) :
        # une fois les fenêtres de jeu fermées, ``lancer_jeu`` rouvre alors
        # l'écran d'accueil (au lieu de clôturer la session) — voir ``lancer_jeu``.
        self._retour_menu = False

    def set_windows(
        self,
        plateau: webview.Window,
        chevalet: webview.Window | None = None,
    ) -> None:
        """Associe les deux fenêtres pywebview (plateau + chevalet) — issue #90."""
        self._window_plateau = plateau
        self._window_chevalet = chevalet

    def set_window(self, window: webview.Window) -> None:
        """Associe la fenêtre **plateau** (compat. mono-fenêtre, issue #74).

        Conservée pour les appelants et tests historiques : elle ne renseigne que
        la fenêtre plateau, la fenêtre chevalet restant à ``None``. Le point
        d'entrée à privilégier depuis l'issue #90 est :meth:`set_windows`.
        """
        self._window_plateau = window

    def obtenir_etat(self) -> dict[str, Any]:
        """Retourne l'état public de la partie (sans lettres de chevalet)."""
        return etat_public(self._partie, self._id_partie)

    def obtenir_etat_plateau(self) -> dict[str, Any]:
        """État initial **public** pour la fenêtre plateau (issue #90).

        Équivalent de la charge diffusée par :meth:`_diffuser` vers la fenêtre
        plateau, exposé comme point d'entrée pour le chargement initial de cette
        fenêtre (avant toute mutation). Voir :meth:`_etat_plateau`.
        """
        return self._etat_plateau()

    def obtenir_etat_chevalet(self) -> dict[str, Any]:
        """État initial **privé** pour la fenêtre chevalet (issue #90).

        Équivalent de la charge diffusée par :meth:`_diffuser` vers la fenêtre
        chevalet (lettres du seul joueur humain courant comprises), exposé pour le
        chargement initial de cette fenêtre. Voir :meth:`_etat_chevalet`.
        """
        return self._etat_chevalet()

    def obtenir_theme_plateau(self) -> str:
        """Retourne le thème visuel du plateau choisi dans les réglages.

        Lit ``theme_plateau`` de :func:`~scrabble.config.charger_config` (champ
        auto-réparant : une valeur inconnue retombe sur ``"classique"``). Le JS
        applique la classe CSS ``theme-<nom>`` correspondante au plateau et
        choisit les libellés (complets ou abrégés). Par sécurité, si la valeur
        lue n'est pas un thème connu, on renvoie ``"classique"``.
        """
        theme = charger_config().get("theme_plateau", "classique")
        return theme if theme in THEMES_PLATEAU else "classique"

    def obtenir_chevalet(self, index_joueur: int) -> dict[str, Any]:
        """Retourne le chevalet du **seul** joueur d'index ``index_joueur``.

        C'est le point d'entrée du bouton « voir mes lettres ». Il ne renvoie
        jamais le chevalet d'un autre joueur ni la totalité des chevalets : le
        joueur qui révèle ses lettres ne dévoile rien de celles des autres.
        """
        if not isinstance(index_joueur, int) or not (
            0 <= index_joueur < len(self._partie.joueurs)
        ):
            return {"succes": False, "erreur": "Index de joueur invalide."}
        joueur = self._partie.joueurs[index_joueur]
        return {
            "succes": True,
            "index": index_joueur,
            "nom": joueur.nom,
            "lettres": serialiser_chevalet(joueur),
        }

    # ------------------------------------------------------------------ #
    # État de pose partagé et diffusion aux deux fenêtres (issue #90)
    # ------------------------------------------------------------------ #

    def _placements_publics(self) -> list[dict[str, Any]]:
        """Placements en attente **sans** l'index de chevalet (part côté plateau).

        La fenêtre plateau n'a aucun besoin de connaître de quel emplacement du
        chevalet provient une lettre posée (``index``) : elle n'affiche que la
        tuile sur le plateau. On ne lui transmet donc que la position, la lettre
        (déjà destinée à être visible sur le plateau), le drapeau joker et la
        valeur en points. Les lettres *non posées* du chevalet, elles, ne partent
        jamais vers la fenêtre plateau (issues #33/#35).
        """
        return [
            {
                "ligne": p["ligne"],
                "colonne": p["colonne"],
                "lettre": p["lettre"],
                "joker": p["joker"],
                "valeur": p["valeur"],
            }
            for p in self._en_attente
        ]

    def _etat_plateau(self) -> dict[str, Any]:
        """État **public** destiné à la fenêtre plateau (issue #90).

        C'est :func:`etat_public` (aucune identité de lettre de chevalet), enrichi
        des seuls placements en attente déjà posés sur le plateau
        (:meth:`_placements_publics`) et de l'index de la lettre sélectionnée
        (``selection`` : une information neutre — un simple index — qui ne dévoile
        aucune lettre).
        """
        etat = etat_public(self._partie, self._id_partie)
        etat["en_attente"] = self._placements_publics()
        etat["selection"] = self._selection
        return etat

    def _etat_chevalet(self) -> dict[str, Any]:
        """État **complet** (lettres privées incluses) destiné à la fenêtre chevalet.

        Contient les lettres du **seul** joueur courant — et seulement s'il est
        humain (jamais le chevalet d'un ordinateur, issue #35) — ainsi que l'état
        de pose complet (sélection, placements avec leur ``index`` de chevalet,
        éventuelle demande de choix de lettre pour un joker). Les quelques champs
        publics joints (nom du joueur courant, tour humain, nombre d'humains, fin
        de partie) évitent à la fenêtre chevalet un aller-retour supplémentaire.
        """
        partie = self._partie
        courant = partie.joueur_courant()
        return {
            "index_courant": partie.index_courant,
            "nom": courant.nom,
            "tour_humain": courant.humain,
            "terminee": partie.terminee,
            "nb_humains": compter_humains(partie),
            "nb_lettres": len(courant.chevalet),
            # Lettres privées : uniquement pour un joueur humain courant.
            "lettres": serialiser_chevalet(courant) if courant.humain else [],
            "selection": self._selection,
            "en_attente": [dict(p) for p in self._en_attente],
            "joker_demande": self._joker_demande,
        }

    def _diffuser(self) -> None:
        """Pousse l'état pertinent à chaque fenêtre après toute mutation (issue #90).

        Vers la fenêtre **plateau** : l'état **public** (:meth:`_etat_plateau`),
        jamais de lettre du chevalet. Vers la fenêtre **chevalet** : l'état
        **complet** (:meth:`_etat_chevalet`), lettres privées comprises. Chaque
        fenêtre expose un point d'entrée JS (``window.appliquerEtatPlateau`` /
        ``window.appliquerEtatChevalet``) que l'on appelle via ``evaluate_js``.
        L'appel est encadré d'un ``try/except`` : une fenêtre fermée ou un JS pas
        encore prêt ne doit jamais faire planter une action de jeu.
        """
        self._pousser(
            self._window_plateau, "appliquerEtatPlateau", self._etat_plateau()
        )
        self._pousser(
            self._window_chevalet, "appliquerEtatChevalet", self._etat_chevalet()
        )
        # Z-order (issue #91, point 3) : toute action de jeu passe par une des deux
        # fenêtres. On en profite pour ré-affirmer que le chevalet reste au-dessus
        # du plateau — sous certains gestionnaires de fenêtres Linux (WebKitGTK),
        # ``on_top`` (``set_keep_above``) n'est qu'un indice que le plateau peut
        # contourner en prenant le focus. Re-poser l'indicateur après chaque
        # interaction est le repositionnement applicatif recommandé (issue #91).
        self._remonter_chevalet()

    @staticmethod
    def _pousser(
        window: webview.Window | None, fonction: str, charge: dict[str, Any]
    ) -> None:
        """Appelle ``window.<fonction>(<charge JSON>)`` si la fenêtre existe."""
        if window is None:
            return
        script = (
            f"window.{fonction} && window.{fonction}("
            f"{json.dumps(charge, ensure_ascii=False)})"
        )
        try:
            window.evaluate_js(script)
        except Exception as e:  # noqa: BLE001 - une vue absente ne bloque pas le jeu
            journal.erreur("Jeu : échec de la diffusion d'un état à une fenêtre.", e)

    def _remonter_chevalet(self) -> None:
        """Ré-affirme que la fenêtre chevalet reste au premier plan (issue #91).

        Point de vigilance #3 de l'issue #91 : sous WebKitGTK (Linux), ``on_top``
        se traduit par ``Gtk.Window.set_keep_above(True)``, un simple **indice** de
        pile que le gestionnaire de fenêtres peut contourner — la fenêtre plateau
        peut alors repasser au-dessus du chevalet en prenant le focus. On re-pose
        donc l'indicateur ``on_top`` après chaque interaction (appelé par
        :meth:`_diffuser`). C'est délibérément non intrusif (aucun vol de focus) :
        si le WM honore la ré-affirmation, le chevalet remonte ; sinon, il s'agit
        d'une limite du backend/WM à confirmer en test manuel (voir rapport).
        """
        if self._window_chevalet is None:
            return
        try:
            self._window_chevalet.on_top = True
        except Exception as e:  # noqa: BLE001 - un z-order récalcitrant ne bloque pas le jeu
            journal.erreur("Jeu : ré-affirmation on_top du chevalet impossible.", e)

    def debut_deplacement_chevalet(self) -> dict[str, Any]:
        """Position absolue actuelle de la fenêtre chevalet, au début d'un drag JS.

        Correctif du point #2 de l'issue #91. Sous WebKitGTK, le mécanisme
        ``.pywebview-drag-region`` **n'est pas implémenté** (le backend GTK ne câble
        le déplacement d'une fenêtre ``frameless`` que via ``easy_drag=True``, qui
        déplacerait la fenêtre au moindre glissé — y compris pendant un clic-clic de
        pose). On implémente donc le déplacement côté application : le JS de la barre
        de titre lit ici la position de départ, puis appelle
        :meth:`deplacer_chevalet` en absolu à chaque mouvement. Portable sur tous les
        backends (repose sur ``window.move``).
        """
        if self._window_chevalet is None:
            return {"succes": False, "erreur": "Aucune fenêtre chevalet."}
        try:
            return {
                "succes": True,
                "x": int(self._window_chevalet.x),
                "y": int(self._window_chevalet.y),
            }
        except Exception as e:  # noqa: BLE001 - position indisponible : le JS ignore le drag
            return {"succes": False, "erreur": f"Position indisponible : {e}"}

    def deplacer_chevalet(self, x: Any, y: Any) -> dict[str, Any]:
        """Déplace la fenêtre chevalet à la position **absolue** ``(x, y)`` (issue #91).

        Appelée en continu par le glisser-déposer JS de la barre de titre
        (``.barre-drag``), pour le déplacement applicatif décrit dans
        :meth:`debut_deplacement_chevalet`. Les coordonnées sont bornées à des
        entiers ; tout échec est remonté au JS sans planter le jeu.
        """
        if self._window_chevalet is None:
            return {"succes": False, "erreur": "Aucune fenêtre chevalet."}
        try:
            self._window_chevalet.move(int(x), int(y))
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - un déplacement raté ne bloque pas le jeu
            return {"succes": False, "erreur": f"Déplacement impossible : {e}"}

    def selectionner_lettre(self, index: Any) -> dict[str, Any]:
        """Sélectionne (ou désélectionne) la lettre du chevalet d'index ``index``.

        Appelée par la fenêtre chevalet au clic sur une lettre. ``index`` à
        ``None`` (ou l'index déjà sélectionné) annule la sélection. Met à jour
        ``_selection`` puis diffuse l'état aux deux fenêtres.
        """
        if index is None:
            self._selection = None
        elif not isinstance(index, int):
            return {"succes": False, "erreur": "Index de lettre invalide."}
        elif self._selection == index:
            self._selection = None  # reclic sur la même lettre : on désélectionne
        else:
            self._selection = index
        # Toute (re)sélection annule une demande de choix de lettre de joker en
        # cours : elle permet notamment d'abandonner proprement la modale joker.
        self._joker_demande = None
        self._diffuser()
        return {"succes": True, "selection": self._selection}

    def poser_lettre_en_attente(
        self,
        ligne: Any,
        colonne: Any,
        lettre: Any = None,
        joker: Any = None,
        valeur: Any = None,
        index: Any = None,
    ) -> dict[str, Any]:
        """Place une lettre en attente sur la case ``(ligne, colonne)`` — issue #90.

        Deux modes d'appel, unifiés ici pour respecter strictement la séparation
        de confidentialité (la fenêtre plateau ne connaît aucune lettre du
        chevalet) :

        * **Depuis la fenêtre plateau** (clic sur une case vide) : seuls
          ``ligne``/``colonne`` sont fournis. La lettre est résolue côté Python à
          partir de ``_selection`` et du chevalet du joueur courant. Si la lettre
          sélectionnée est un **joker**, aucune lettre n'est encore posée : on
          mémorise la case (``_joker_demande``) et on renvoie ``joker_requis`` —
          la fenêtre chevalet ouvrira alors sa modale de choix.
        * **Depuis la fenêtre chevalet** (après choix de la lettre d'un joker) :
          ``lettre``/``joker``/``valeur``/``index`` sont fournis explicitement et
          le placement est finalisé tel quel.

        Renvoie ``{"succes": True}`` (ou ``joker_requis``) et diffuse le nouvel
        état ; ``{"succes": False, "erreur": ...}`` si le placement est refusé
        (aucune sélection, index invalide, case occupée…).
        """
        if not isinstance(ligne, int) or not isinstance(colonne, int):
            return {"succes": False, "erreur": "Position de pose invalide."}
        if not dans_plateau(ligne, colonne):
            return {"succes": False, "erreur": "Position hors plateau."}
        if not self._partie.plateau.case_vide(ligne, colonne):
            return {
                "succes": False,
                "erreur": "Cette case porte déjà une tuile.",
            }
        if any(p["ligne"] == ligne and p["colonne"] == colonne for p in self._en_attente):
            return {"succes": False, "erreur": "Une lettre est déjà posée ici."}

        # Mode « finalisation » : la lettre (et son index) sont fournis.
        if lettre is not None and index is not None:
            self._joker_demande = None
            return self._ajouter_placement(
                ligne, colonne, str(lettre), bool(joker),
                int(valeur) if valeur is not None else 0, int(index),
            )

        # Mode « clic plateau » : on résout la lettre via la sélection courante.
        if self._selection is None:
            return {
                "succes": False,
                "erreur": "Sélectionnez d'abord une lettre de votre chevalet.",
            }
        idx = self._selection
        chevalet = self._partie.joueur_courant().chevalet
        if not (0 <= idx < len(chevalet)):
            return {"succes": False, "erreur": "Lettre sélectionnée invalide."}
        jeton = chevalet[idx]
        if jeton == JOKER:
            # La lettre du joker se choisit côté chevalet : on diffère la pose.
            self._joker_demande = {"ligne": ligne, "colonne": colonne, "index": idx}
            self._diffuser()
            return {
                "succes": True,
                "joker_requis": True,
                "ligne": ligne,
                "colonne": colonne,
                "index": idx,
            }
        return self._ajouter_placement(
            ligne, colonne, jeton, False, valeur_lettre(jeton), idx
        )

    def _ajouter_placement(
        self,
        ligne: int,
        colonne: int,
        lettre: str,
        joker: bool,
        valeur: int,
        index: int,
    ) -> dict[str, Any]:
        """Ajoute un placement résolu à ``_en_attente``, réinitialise la sélection."""
        self._en_attente.append(
            {
                "ligne": ligne,
                "colonne": colonne,
                "lettre": lettre,
                "joker": joker,
                "valeur": 0 if joker else valeur,
                "index": index,
            }
        )
        self._selection = None
        self._joker_demande = None
        self._diffuser()
        return {"succes": True}

    def retirer_lettre_en_attente(self, ligne: Any, colonne: Any) -> dict[str, Any]:
        """Retire le placement en attente de la case ``(ligne, colonne)`` — issue #90.

        Appelée au clic sur une tuile en attente (retrait de la pose). La lettre
        redevient disponible au chevalet. Diffuse le nouvel état aux deux
        fenêtres. Sans effet (mais succès) si aucune lettre n'attend sur la case.
        """
        avant = len(self._en_attente)
        self._en_attente = [
            p for p in self._en_attente
            if not (p["ligne"] == ligne and p["colonne"] == colonne)
        ]
        if len(self._en_attente) != avant:
            self._selection = None
            self._diffuser()
        return {"succes": True}

    def annuler_pose(self) -> dict[str, Any]:
        """Abandonne toute la pose en cours (sélection + placements) — issue #90.

        Vide ``_selection`` et ``_en_attente`` (aucune lettre n'est consommée : le
        moteur n'a rien joué) puis diffuse l'état remis à zéro aux deux fenêtres.
        """
        self._selection = None
        self._en_attente = []
        self._joker_demande = None
        self._diffuser()
        return {"succes": True}

    def poser_mot(self, placements: list[Any] | None = None) -> dict[str, Any]:
        """Pose le mot formé par les lettres en attente (``_en_attente``) — issue #90.

        Depuis l'issue #90, la mécanique clic-clic est pilotée par l'état interne :
        la fenêtre chevalet a construit ``_en_attente`` au fil des appels à
        :meth:`poser_lettre_en_attente`, et cette méthode le lit directement — le
        JS ne passe donc plus de ``placements``. Le paramètre ``placements`` reste
        accepté (rétro-compatibilité et tests) : s'il est fourni, il **remplace**
        l'état de pose courant avant le jeu.

        Le sens du mot se déduit de l'alignement des lettres ; pour une lettre
        unique il est fixé à l'horizontale en interne (issue #43 : sans
        conséquence sur la validation ni le score). La méthode construit un
        :class:`~scrabble.moteur.plateau_partie.Coup`, appelle
        :meth:`~scrabble.moteur.partie.Partie.jouer_coup` et renvoie :

        * en cas de succès : ``{"succes": True, "points": ..., "etat": ...}`` où
          ``etat`` est l'état public rafraîchi. ``_selection``/``_en_attente`` sont
          réinitialisés (le moteur a consommé les lettres) et le nouvel état est
          diffusé aux deux fenêtres via :meth:`_diffuser` ;
        * en cas d'échec : ``{"succes": False, "erreur": <message clair>}`` — les
          lettres en attente **ne sont pas perdues** (elles restent dans
          ``_en_attente`` pour correction).

        Confidentialité : la réponse ne contient jamais l'identité des lettres
        d'un chevalet (``etat`` est l'état public, sans chevalet).
        """
        if placements is not None:
            self._en_attente = [self._normaliser_placement(p) for p in placements]
        nb_avant = len(self._partie.historique)
        resultat = jouer_placements(self._partie, self._en_attente)
        if resultat.get("succes"):
            detail = resultat.get("detail")
            mot = (
                detail["mots"][0]["texte"]
                if detail and detail.get("mots")
                else "?"
            )
            journal.info(
                f"Jeu : coup posé par {resultat.get('nom')} — "
                f"{mot} ({resultat.get('points')} pts)."
            )
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._journaliser_fin_partie()
            self._finaliser_si_terminee()
            # Le coup est joué : on repart d'un état de pose vierge et on
            # rediffuse le nouvel état (public / privé) aux deux fenêtres.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            resultat["etat"] = etat_public(self._partie, self._id_partie)
            self._diffuser()
        else:
            # Un coup refusé (mot hors dictionnaire, placement illégal…) est un
            # déroulé de jeu normal, pas un bug : on le trace en INFO pour pouvoir
            # reconstituer la session, sans déclencher la rétention du fichier
            # (réservée aux vraies erreurs, voir module ``journal``).
            journal.info(f"Jeu : coup refusé — {resultat.get('erreur')}")
        return resultat

    @staticmethod
    def _normaliser_placement(placement: Any) -> dict[str, Any]:
        """Normalise un placement (dict JS ou interne) en placement interne complet.

        Garantit la présence des clés attendues par ``_en_attente``
        (``ligne, colonne, lettre, joker, valeur, index``) à partir d'un dict qui
        peut n'en fournir qu'une partie (p. ex. ``{ligne, colonne, lettre, joker}``
        venu d'un test ou d'un ancien appelant). ``valeur`` et ``index`` sont
        déduits/comblés si absents.
        """
        if not isinstance(placement, dict):
            return {"ligne": None, "colonne": None, "lettre": None,
                    "joker": False, "valeur": 0, "index": None}
        joker = bool(placement.get("joker", False))
        lettre = placement.get("lettre")
        if "valeur" in placement and placement["valeur"] is not None:
            valeur = placement["valeur"]
        elif joker or not isinstance(lettre, str):
            valeur = 0
        else:
            valeur = valeur_lettre(lettre.upper())
        return {
            "ligne": placement.get("ligne"),
            "colonne": placement.get("colonne"),
            "lettre": lettre,
            "joker": joker,
            "valeur": 0 if joker else valeur,
            "index": placement.get("index"),
        }

    def verifier_coup(self, placements: list[Any] | None = None) -> dict[str, Any]:
        """Calcule les points du coup en attente **sans le jouer** (issue #69).

        Point d'entrée du bouton « 🔎 Vérifier et calculer ». Depuis l'issue #90 la
        méthode lit ``_en_attente`` (le JS ne passe plus de ``placements``) ;
        ``placements`` reste accepté pour compat/tests et remplace alors l'état de
        pose courant. Délègue à :func:`simuler_coup`, qui valide le coup et calcule
        son score sur une **copie** du plateau, sans rien modifier de la partie :
        ni le plateau réel, ni le chevalet, ni l'historique, ni le tour. Les
        lettres en attente ne sont donc pas perdues et aucun tour n'est consommé.

        Renvoie, comme un coup réellement joué,
        ``{"succes": True, "points": ..., "nom": ..., "detail": ...}`` si le coup
        est valide, ou ``{"succes": False, "erreur": <message clair>}`` sinon
        (aucun score affiché dans ce cas). La réponse ne contient jamais l'identité
        des lettres d'un chevalet.
        """
        if placements is not None:
            self._en_attente = [self._normaliser_placement(p) for p in placements]
        resultat = simuler_coup(self._partie, self._en_attente)
        if resultat.get("succes"):
            detail = resultat.get("detail")
            mot = (
                detail["mots"][0]["texte"]
                if detail and detail.get("mots")
                else "?"
            )
            journal.info(
                f"Jeu : coup vérifié (non joué) — {mot} "
                f"({resultat.get('points')} pts)."
            )
        else:
            journal.info(f"Jeu : vérification de coup — {resultat.get('erreur')}")
        return resultat

    def verifier_mot(self, lettres: Any) -> dict[str, Any]:
        """Teste dans le dictionnaire le mot formé par la zone de brouillon.

        ``lettres`` est la suite de jetons arrangés dans le brouillon (dans
        l'ordre affiché). Le test est en **lecture seule** : il ne pose aucun
        coup, ne consomme aucun tour et ne modifie en rien l'état de la partie.
        Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool}`` ou, si le
        brouillon est vide, ``{"succes": False, "erreur": <message>}``.
        """
        return verifier_mot_dictionnaire(self._partie.dictionnaire, lettres)

    def echanger_tout(self) -> dict[str, Any]:
        """Remet tout le chevalet du joueur courant dans le sac et passe le tour.

        Utilise :meth:`~scrabble.moteur.partie.Partie.echanger` avec la totalité
        du chevalet courant (l'échange consomme déjà le tour). En cas de succès :
        ``{"succes": True, "etat": <état public rafraîchi>}`` (tour suivant,
        chevalet à remasquer selon le nombre d'humains). Si le sac ne contient
        pas assez de jetons (ou partie terminée) :
        ``{"succes": False, "erreur": <message clair>}`` — l'état n'est pas
        modifié.
        """
        nom = self._partie.joueur_courant().nom
        nb_avant = len(self._partie.historique)
        resultat = echanger_chevalet_complet(self._partie, self._id_partie)
        if resultat.get("succes"):
            journal.info(f"Jeu : échange complet du chevalet par {nom}.")
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._finaliser_si_terminee()
            # Nouveau tirage + tour suivant : on repart d'un état de pose vierge
            # et on rediffuse le nouvel état public (plateau) et le nouveau
            # chevalet (fenêtre chevalet) — issue #90.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._diffuser()
        else:
            journal.info(f"Jeu : échange refusé pour {nom} — {resultat.get('erreur')}")
        return resultat

    def faire_jouer_ia(self) -> dict[str, Any]:
        """Fait jouer **un seul** tour d'ordinateur (celui du joueur courant).

        Point d'entrée du bouton « ▶ Faire jouer l'ordinateur » (issue #35,
        revu issue #55 : un clic = un seul ordinateur). S'appuie sur
        :meth:`~scrabble.moteur.partie.Partie.jouer_tour_ia` : joue exactement le
        tour de l'ordinateur courant, puis renvoie
        ``{"succes": True, "nb_tours": ..., "etat": <état public rafraîchi>}``
        (``nb_tours`` = 1 si un tour a été joué). Sans effet si le joueur courant
        est déjà humain (``nb_tours`` = 0). Si l'ordinateur suivant est encore un
        ordinateur, le bouton reste disponible : l'humain reclique pour le faire
        jouer à son tour.

        C'est la seule façon prévue de faire avancer le jeu pendant un tour IA :
        l'humain n'a jamais à manipuler le chevalet d'un ordinateur à sa place.
        """
        nom = self._partie.joueur_courant().nom
        nb_avant = len(self._partie.historique)
        resultat = jouer_tours_ia_ui(self._partie, self._id_partie)
        if resultat.get("nb_tours"):
            journal.info(f"Jeu : tour d'ordinateur joué ({nom}).")
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._journaliser_fin_partie()
            self._finaliser_si_terminee()
            # Tour suivant : état de pose remis à zéro et rediffusé (nouvel état
            # public au plateau, nouveau chevalet à la fenêtre chevalet) — #90.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._diffuser()
        return resultat

    def _persister_entrees(self, entrees: list[EntreeHistorique]) -> None:
        """Persiste en base chaque action produite par le moteur (issue #81).

        Diagnostic de l'issue #81 : les :class:`EntreeHistorique` produites par le
        moteur (un coup, un tour d'ordinateur, un échange) n'étaient jamais
        transmises à la persistance — une reprise reconstruisait donc toujours un
        plateau vide. Cette méthode branche
        :func:`~scrabble.persistance.enregistrer_action` après chaque action
        réussie, en préservant l'ordre.

        L'écriture est encadrée par un ``try/except`` : l'action de jeu reste
        valide côté joueur même si la persistance échoue, mais l'échec est rendu
        **visible** dans le journal (``journal.erreur``) plutôt que d'être avalé
        silencieusement. En mode démonstration (``_id_partie`` à ``None``), il n'y
        a aucune partie suivie en base : rien n'est écrit.
        """
        if self._id_partie is None:
            return
        for entree in entrees:
            try:
                enregistrer_action(
                    self._id_partie, entree, self._chemin_persistance
                )
            except Exception as e:  # noqa: BLE001 - on trace, sans planter le jeu
                journal.erreur(
                    f"Jeu : échec de l'enregistrement d'une action "
                    f"(partie #{self._id_partie}).",
                    e,
                )

    def _finaliser_si_terminee(self) -> None:
        """Marque la partie terminée en base (une seule fois) — issue #81.

        Appelée après chaque action susceptible de terminer la partie (coup,
        tour d'ordinateur, échange). Tant que la partie n'est pas terminée, ou si
        elle l'a déjà été persistée, la méthode est sans effet. Comme
        :meth:`_persister_entrees`, l'échec d'écriture est journalisé sans planter
        le jeu, et le mode démonstration (``_id_partie`` à ``None``) est ignoré.
        """
        if self._id_partie is None or self._fin_persistee:
            return
        if not self._partie.terminee:
            return
        self._fin_persistee = True
        try:
            finaliser_partie(
                self._id_partie, self._partie, self._chemin_persistance
            )
        except Exception as e:  # noqa: BLE001 - on trace, sans planter le jeu
            journal.erreur(
                f"Jeu : échec de la finalisation de la partie "
                f"#{self._id_partie}.",
                e,
            )

    def _journaliser_fin_partie(self) -> None:
        """Journalise (une seule fois) la fin de partie et son ou ses gagnants.

        Appelée après chaque action susceptible de terminer la partie (pose d'un
        coup humain, tour d'ordinateur). Le drapeau ``_fin_journalisee`` garantit
        qu'on n'écrit la ligne « fin de partie » qu'une fois, même si l'UI
        redéclenche des actions sans effet une fois la partie terminée.
        """
        if self._partie.terminee and not self._fin_journalisee:
            self._fin_journalisee = True
            gagnants = ", ".join(j.nom for j in self._partie.gagnants) or "aucun"
            journal.info(f"Jeu : fin de partie — gagnant(s) : {gagnants}.")

    def retour_menu(self) -> dict[str, Any]:
        """Ferme **les deux** fenêtres de jeu pour revenir à l'accueil (issues #74/#90).

        Point d'entrée du bouton « 🏠 Retour au menu ». Ferme les fenêtres de jeu
        **depuis Python** via ``window.destroy()`` — et non ``window.close()``
        côté JS, non honoré par tous les backends pywebview (GTK/WebKit sous
        Linux, issues #53/#57). Depuis l'issue #90, il faut détruire **la fenêtre
        plateau ET la fenêtre chevalet** : sans cela la fenêtre chevalet
        ``on_top`` resterait orpheline, flottant au-dessus de l'accueil rouvert.
        Une fois les fenêtres fermées, ``webview.start()`` rend la main à
        :func:`lancer_jeu`, qui, voyant le drapeau ``_retour_menu``, rouvre
        l'écran d'accueil (:func:`lancer_accueil`) en **réutilisant la session de
        journalisation** déjà ouverte (cohérent avec l'issue #66).

        La partie n'est pas modifiée ici : elle reste persistée et reprenable
        via « Reprendre une partie » (le suivi en base est mis à jour en continu
        après chaque action, issues #22/#25). Un éventuel coup en attente (non
        validé) est simplement abandonné — l'avertissement de confirmation est
        géré côté interface.

        Retourne ``{"succes": True}`` si la fermeture a été demandée, sinon
        ``{"succes": False, "erreur": ...}`` (le JS réactive alors le bouton
        plutôt que de rester bloqué).
        """
        if self._window_plateau is None and self._window_chevalet is None:
            return {"succes": False, "erreur": "Aucune fenêtre associée."}
        try:
            journal.info(
                f"Jeu : retour au menu demandé (partie #{self._id_partie})."
            )
            self._retour_menu = True
            # Détruire la fenêtre chevalet en premier : ``on_top``, elle doit
            # disparaître avant l'accueil rouvert. La fenêtre plateau ensuite.
            if self._window_chevalet is not None:
                self._window_chevalet.destroy()
            if self._window_plateau is not None:
                self._window_plateau.destroy()
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            # La fermeture a échoué : on ne rouvrira pas l'accueil (les fenêtres
            # de jeu restent ouvertes et le JS réactive le bouton).
            self._retour_menu = False
            return {"succes": False, "erreur": f"Fermeture impossible : {e}"}


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #


def lancer_jeu(partie: Partie, id_partie: int | None) -> None:
    """Lance l'écran de jeu pour la ``partie`` donnée (bloquant).

    ``partie`` est typiquement celle créée par l'écran d'accueil (issue #27) ;
    ``id_partie`` est son identifiant de persistance (peut être ``None`` en
    mode démonstration autonome).

    Session de journalisation (issue #66) : si une session est déjà ouverte
    (lancement normal depuis l'accueil), on la **réutilise** ; sinon (lancement
    autonome, ``python -m scrabble.ui.jeu``), on démarre une session propre.
    La session est clôturée à la fermeture de la fenêtre de jeu (= fin du
    programme), via ``try/finally`` pour garantir la clôture même en cas
    d'exception. ``cloturer_session`` étant idempotente, la clôture par
    l'accueil enchaîné reste sans effet redondant.

    Retour au menu (issue #74) : si l'utilisateur a cliqué « 🏠 Retour au menu »
    (drapeau ``ApiJeu._retour_menu``), la fenêtre de jeu a été fermée mais le
    programme ne se termine pas : on **ne clôture pas** la session et on rouvre
    l'écran d'accueil (:func:`lancer_accueil`), qui **réutilise** cette même
    session (symétrique de l'enchaînement accueil → jeu de l'issue #52, et
    cohérent avec l'issue #66). L'accueil rouvert se charge alors lui-même de
    clôturer la session à sa fermeture.
    """
    if journal.session_courante() is None:
        journal.demarrer_session()
    journal.info(f"Jeu : écran ouvert (partie #{id_partie}).")
    api = ApiJeu(partie, id_partie)
    retour_menu = False
    try:
        _lancer_fenetre_jeu(api)
        retour_menu = api._retour_menu
    finally:
        # Cas « retour au menu » : la session reste ouverte pour être réutilisée
        # par l'accueil rouvert. Dans tous les autres cas (fermeture normale de
        # la fenêtre, ou exception traversant la boucle), on clôture la session.
        if not retour_menu:
            journal.cloturer_session()
    if retour_menu:
        _rouvrir_accueil(id_partie)


def _rouvrir_accueil(id_partie: int | None) -> None:
    """Rouvre l'écran d'accueil après un « Retour au menu » (issue #74).

    Import local de :func:`~scrabble.ui.accueil.lancer_accueil` pour éviter le
    cycle d'import (l'accueil importe déjà ``lancer_jeu``). La session de
    journalisation courante est **réutilisée** (``reutiliser_session=True``) :
    elle n'est ni redémarrée ni clôturée ici, l'accueil la clôturant à sa propre
    fermeture (cohérent avec l'issue #66).
    """
    from scrabble.ui.accueil import lancer_accueil

    journal.info(
        f"Jeu : réouverture de l'écran d'accueil (retour au menu, "
        f"partie #{id_partie})."
    )
    lancer_accueil(reutiliser_session=True)


# Dimensions par défaut de la fenêtre chevalet flottante (issue #90, ajustées
# issue #91 point 4). La fenêtre doit loger, **côte à côte et sans défilement**,
# le bloc « À jouer » (chevalet 7 lettres + contrôles de tour) et le bloc
# « Brouillon » (9 emplacements). À 40 px par case + espacements + marges, les
# deux blocs alignés réclament ~830 px de large ; on prend une marge de sécurité.
# La hauteur laisse tenir l'en-tête, la zone à deux blocs et le pied sans scroll.
# Non redimensionnable : ces valeurs sont donc la taille réelle utilisée.
CHEVALET_LARGEUR = 880
CHEVALET_HAUTEUR = 400
# Marge basse : la fenêtre chevalet est posée près du bas de l'écran, à cette
# distance du bord inférieur de la zone de travail.
CHEVALET_MARGE_BAS = 40


def _position_chevalet(
    largeur: int = CHEVALET_LARGEUR, hauteur: int = CHEVALET_HAUTEUR
) -> tuple[int, int]:
    """Position (x, y) bas-centre de l'écran pour la fenêtre chevalet (issue #90).

    Calculée à partir des dimensions d'écran disponibles via ``webview.screens``
    (premier écran). Le chevalet est centré horizontalement et collé vers le bas
    (à :data:`CHEVALET_MARGE_BAS` du bord inférieur). En l'absence d'information
    d'écran exploitable (environnement sans affichage, ``webview.screens`` vide ou
    en erreur), on retombe sur un placement neutre ``(100, 100)`` plutôt que de
    faire échouer le lancement.

    Point de vigilance #1 de l'issue #91 : sous WebKitGTK, ``webview.screens`` ne
    renvoie des dimensions fiables **qu'une fois la boucle GUI démarrée**
    (``webview.start``). Appelée trop tôt (avant ``start``), elle retombait sur le
    repli neutre ``(100, 100)`` — d'où l'ouverture en haut à gauche. Cette fonction
    est donc désormais rappelée **après** le démarrage de la boucle par
    :func:`_repositionner_chevalet` pour corriger la position réelle de la fenêtre.
    """
    try:
        ecrans = webview.screens
        ecran = ecrans[0] if ecrans else None
        larg_ecran = int(getattr(ecran, "width", 0) or 0)
        haut_ecran = int(getattr(ecran, "height", 0) or 0)
    except Exception:  # noqa: BLE001 - pas d'écran interrogeable : repli neutre
        larg_ecran = haut_ecran = 0
    if larg_ecran <= 0 or haut_ecran <= 0:
        return 100, 100
    x = max(0, (larg_ecran - largeur) // 2)
    y = max(0, haut_ecran - hauteur - CHEVALET_MARGE_BAS)
    return x, y


def _lancer_fenetre_jeu(api: "ApiJeu") -> None:
    """Crée les **deux** fenêtres de jeu (plateau + chevalet) et démarre la boucle.

    Séparation plateau/chevalet en deux fenêtres pywebview (issue #90) :

    * Fenêtre **plateau** : maximisée (``maximized=True``), sans ``width``/
      ``height`` fixes, afin de s'adapter à n'importe quelle résolution logique
      (le CSS contraint désormais le plateau par la hauteur disponible pour éviter
      tout défilement). Elle porte le plateau, les panneaux joueurs, la barre du
      sac/historique, « Faire jouer l'ordinateur » et la vérification dictionnaire.
    * Fenêtre **chevalet** : flottante ``frameless=True``, ``on_top=True`` (toujours
      au-dessus), ``resizable=False`` et ``easy_drag=False``. Le déplacement passe
      par un glisser-déposer **applicatif** sur la barre du haut (``.barre-drag`` →
      :meth:`ApiJeu.deplacer_chevalet`) : sous WebKitGTK, ``.pywebview-drag-region``
      n'est pas géré (le backend GTK ne câble le drag d'une fenêtre ``frameless``
      que via ``easy_drag=True``, qui déplacerait la fenêtre au moindre glissé, y
      compris pendant un clic-clic de pose — issue #91 point 2). Taille ~880×400,
      posée en bas-centre de l'écran.

    Les deux fenêtres sont créées **avant** l'unique ``webview.start()`` (exigence
    pywebview : toutes les fenêtres se déclarent avant de démarrer la boucle). Elles
    partagent la même instance ``api`` (``js_api=api``), source de vérité de l'état
    de pose (issue #90). Un callback ``webview.start(func, …)`` repositionne la
    fenêtre chevalet une fois la boucle démarrée (issue #91 point 1 : ``screens``
    n'est fiable qu'à ce moment).
    """
    window_plateau = webview.create_window(
        "Scrabble - Plateau",
        str(DOSSIER_WEB / "jeu.html"),
        js_api=api,
        # Maximisée, sans taille fixe : le plateau + les panneaux tiennent sans
        # défilement à n'importe quelle résolution logique modeste (cf. jeu.css,
        # dimensionnement contraint par vh). La fenêtre reste redimensionnable.
        maximized=True,
        resizable=True,
    )
    x_chev, y_chev = _position_chevalet()
    window_chevalet = webview.create_window(
        "Scrabble - Chevalet",
        str(DOSSIER_WEB / "chevalet.html"),
        js_api=api,
        width=CHEVALET_LARGEUR,
        height=CHEVALET_HAUTEUR,
        x=x_chev,
        y=y_chev,
        frameless=True,     # fenêtre sans cadre ni barre de titre
        on_top=True,        # toujours au-dessus du plateau
        resizable=False,    # non redimensionnable par erreur
        easy_drag=False,    # pas de drag « corps entier » : drag applicatif ciblé
    )
    api.set_windows(window_plateau, window_chevalet)
    # Repositionnement après démarrage de la boucle (issue #91 point 1) : c'est
    # seulement une fois ``webview.start()`` en cours que ``webview.screens`` renvoie
    # des dimensions fiables sous WebKitGTK.
    webview.start(_repositionner_chevalet, (window_chevalet,))


def _repositionner_chevalet(window_chevalet: "webview.Window") -> None:
    """Replace la fenêtre chevalet en bas-centre une fois la boucle GUI démarrée.

    Exécuté par ``webview.start(func, …)`` dans un fil dédié, **après** le démarrage
    de la boucle : à ce stade seulement ``webview.screens`` renvoie sous WebKitGTK
    les dimensions réelles de l'écran (issue #91 point 1). On recalcule donc la
    position bas-centre (:func:`_position_chevalet`) et on déplace la fenêtre. Toute
    erreur est journalisée sans interrompre le jeu (la position initiale, au pire
    ``(100, 100)``, reste alors en place).
    """
    try:
        x, y = _position_chevalet()
        window_chevalet.move(x, y)
        journal.info(f"Jeu : fenêtre chevalet repositionnée en ({x}, {y}).")
    except Exception as e:  # noqa: BLE001 - un repositionnement raté ne bloque pas le jeu
        journal.erreur("Jeu : repositionnement de la fenêtre chevalet impossible.", e)


# Petit lexique du mode démonstration. Il doit contenir au minimum les mots
# déjà posés sur le plateau de démo (« MAISON », « OPUS ») pour que la partie
# soit cohérente, plus un socle de mots courts très courants : le générateur de
# coups (:func:`scrabble.moteur.generateur.generer_coups`) explore les ancrages
# autour des lettres posées et forme des mots transversaux ; sans un minimum de
# mots plausibles, l'IA passerait systématiquement son tour. On privilégie donc
# les mots de 2-3 lettres valides au Scrabble francophone, qui multiplient les
# possibilités de pose autour des lettres existantes. (Ce n'est PAS le vrai
# dictionnaire ODS8 : uniquement de quoi rendre le mode démo jouable.)
_MOTS_DEMO: tuple[str, ...] = (
    # Mots déjà posés sur le plateau de démo et quelques extensions plausibles.
    "MAISON", "MAISONS", "MAISONNEE", "OPUS", "OPUSCULE",
    # Mots de 2 lettres valides à l'ODS (socle d'ancrages transversaux).
    "AA", "AH", "AI", "AN", "AS", "AU", "AY", "BA", "BE", "BI", "BU",
    "CA", "CE", "CI", "DA", "DE", "DO", "DU", "EH", "EN", "ES", "ET",
    "EU", "EX", "FA", "FI", "GO", "HA", "HE", "HI", "HO", "IF", "IN",
    "JE", "KA", "LA", "LE", "LI", "LU", "MA", "ME", "MI", "MU", "NA",
    "NE", "NI", "NO", "NU", "OC", "OH", "OM", "ON", "OR", "OS", "OU",
    "PI", "PU", "RA", "RE", "RI", "RU", "SA", "SE", "SI", "SU", "TA",
    "TE", "TU", "UN", "US", "UT", "VA", "VS", "VU", "WU", "XI", "YE",
    "ZA", "ZE", "ZO",
    # Mots de 3 lettres courants, riches en combinaisons.
    "ANE", "ART", "AXE", "BAL", "BAR", "BAS", "BON", "BUS", "CAR", "COL",
    "CRI", "DES", "DUO", "EAU", "ELU", "EPI", "ERE", "FEU", "FIL", "FIN",
    "GAI", "GEL", "GRE", "HUE", "IRA", "JEU", "LAC", "LOI", "LOT", "MAL",
    "MER", "MIS", "MUR", "NEZ", "NID", "NOM", "OIE", "OSE", "OUI", "PAS",
    "PIN", "PIS", "POT", "PRE", "PUR", "RAT", "RIS", "ROI", "RUE", "SEL",
    "SOL", "SON", "SUR", "TAS", "THE", "TON", "TRI", "TUE", "VIN", "VIS",
    "VUE", "ZUT",
    # Quelques mots plus longs formables autour du plateau.
    "SAIN", "SAINT", "SOIN", "MAIS", "MAIN", "NAIS", "PONS",
    "PONT", "SONT",
)


#: Gabarits d'actions de démonstration pour l'historique glissant (issue #49) :
#: chaque tuple est ``(action, mot, score)``. Un ``mot`` non nul ⇒ un coup
#: cliquable (on lui fabrique un :class:`~scrabble.moteur.score.DetailScore` à la
#: volée) ; ``None`` ⇒ passe ou échange, sans détail. La liste est volontairement
#: plus longue que le plafond d'affichage (:data:`MAX_LIGNES_HISTORIQUE`) pour
#: aussi vérifier le compteur « (N) » et le fait que seules les plus récentes
#: sont montrées.
_HISTORIQUE_DEMO: list[tuple[str, str | None, int]] = [
    ("coup", "MAISON", 14),
    ("coup", "OPUS", 8),
    ("passe", None, 0),
    ("coup", "JOKER", 19),
    ("echange", None, 0),
    ("coup", "PLATEAU", 24),
    ("coup", "ZEN", 12),
    ("passe", None, 0),
    ("coup", "QUAI", 13),
    ("coup", "FORT", 7),
    ("echange", None, 0),
    ("coup", "VICTOIRE", 31),
]


def _peupler_historique_demo(partie: Partie) -> None:
    """Remplit ``partie.historique`` d'entrées de démonstration (issue #49).

    But : disposer, en mode démo autonome, d'un « Derniers coups » déjà rempli
    pour vérifier **visuellement** le rendu de la liste à pleine capacité (mélange
    de coups, passes et échanges répartis en tourniquet sur tous les joueurs),
    sans avoir à jouer plusieurs tours à la main à chaque vérification.

    Purement local au mode démo : une vraie partie créée depuis l'écran d'accueil
    démarre, elle, avec un historique vide et ne passe jamais par cette fonction.

    Les :class:`~scrabble.moteur.partie.EntreeHistorique` sont construites
    directement (pas de vrai coup rejoué sur le plateau, comme l'autorise l'issue
    #49) : ``index_joueur``/``nom_joueur`` pointent toujours un joueur existant et
    les scores restent plausibles, si bien que la sérialisation
    (:func:`serialiser_entree_historique`) reste parfaitement cohérente.
    """
    nb = len(partie.joueurs)
    cumuls = [0] * nb
    for i, (action, mot, score) in enumerate(_HISTORIQUE_DEMO):
        idx = i % nb
        joueur = partie.joueurs[idx]
        cumuls[idx] += score
        detail = (
            DetailScore(
                mots=[DetailMot(texte=mot, score=score, cases_bonus=[])],
                bonus_scrabble=0,
                total=score,
            )
            if action == "coup" and mot is not None
            else None
        )
        partie.historique.append(
            EntreeHistorique(
                index_joueur=idx,
                nom_joueur=joueur.nom,
                action=action,
                detail=detail,
                lettres_echangees=3 if action == "echange" else 0,
                jetons_echanges=["A", "E", "R"] if action == "echange" else [],
                score_cumule=cumuls[idx],
            )
        )


def construire_partie_demo(nb_joueurs: int = 2) -> tuple[Partie, int | None]:
    """Construit une partie d'exemple (plateau partiellement rempli).

    Sert au test manuel autonome de cet écran (``python -m scrabble.ui.jeu``),
    sans passer par l'écran d'accueil. Les tuiles sont posées directement sur le
    plateau et les scores fixés à des valeurs plausibles : le but est de valider
    le **rendu** (cases bonus, tuiles, joker, scores, joueur courant, sac,
    disposition spatiale des joueurs autour du plateau — issue #33), pas de
    rejouer une partie réelle. Un joker (« blanc ») figure dans le mot vertical
    pour illustrer sa distinction visuelle.

    ``nb_joueurs`` (borné à 1–4, défaut 2) permet de vérifier **manuellement** la
    disposition spatiale selon le nombre d'adversaires : un premier joueur humain
    (« Camille », toujours en bas) puis autant d'ordinateurs que nécessaire (en
    haut, gauche, droite). Lancer p. ex. ``python -m scrabble.ui.jeu 3`` pour une
    partie à 3 joueurs, ou ``1`` pour le cas solo (aucun panneau latéral).
    """
    nb_joueurs = max(1, min(4, nb_joueurs))
    # Vrai Trie (petit lexique de démo) : contrairement à un simple stub
    # « accepte tout », il expose l'attribut ``.racine`` exigé par le générateur
    # de coups, donc « Faire jouer l'ordinateur » fonctionne en mode démo.
    dictionnaire: DictionnaireMots = Trie.depuis_iterable(
        normaliser_mot(mot) for mot in _MOTS_DEMO
    )
    niveaux = [Niveau.INTERMEDIAIRE, Niveau.FACILE, Niveau.EXPERT]
    noms_ia = ["Léon", "Nadia", "Bruno"]
    joueurs = [Joueur(nom="Camille", humain=True)]
    for i in range(nb_joueurs - 1):
        joueurs.append(
            Joueur(nom=noms_ia[i], humain=False, niveau=niveaux[i])
        )
    partie = Partie(joueurs, dictionnaire, graine=20260716)

    # Mot horizontal « MAISON » passant par la case centrale (7, 7).
    mot_h = "MAISON"
    for i, lettre in enumerate(mot_h):
        partie.plateau.poser_tuile(7, 4 + i, Tuile(lettre))
    # Mot vertical « OPUS » croisant le « O » de MAISON en (7, 8).
    # Le « U » est joué avec un joker (lettre blanche) pour la démonstration.
    partie.plateau.poser_tuile(8, 8, Tuile("P"))
    partie.plateau.poser_tuile(9, 8, Tuile("U", joker=True))
    partie.plateau.poser_tuile(10, 8, Tuile("S"))

    # Scores plausibles (tour de Camille). Chaque joueur reçoit un score
    # distinct pour distinguer visuellement les panneaux.
    scores = [14, 9, 21, 5]
    for i, joueur in enumerate(partie.joueurs):
        joueur.score = scores[i % len(scores)]
    partie.index_courant = 0

    # Historique de démonstration pré-rempli (issue #49) : permet de vérifier
    # visuellement le rendu du menu « Derniers coups » une fois garni, sans jouer
    # plusieurs tours à la main. Local au mode démo uniquement.
    _peupler_historique_demo(partie)
    return partie, None


def main() -> int:
    """Point d'entrée de test : lance l'écran de jeu en mode démonstration.

    Un argument optionnel donne le nombre de joueurs (1 à 4) pour vérifier
    manuellement la disposition spatiale (issue #33) — p. ex.
    ``python -m scrabble.ui.jeu 3``. Sans argument : 2 joueurs.
    """
    import sys

    nb_joueurs = 2
    if len(sys.argv) > 1:
        try:
            nb_joueurs = int(sys.argv[1])
        except ValueError:
            nb_joueurs = 2
    partie, id_partie = construire_partie_demo(nb_joueurs)
    lancer_jeu(partie, id_partie)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
