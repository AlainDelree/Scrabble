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
from pathlib import Path
from typing import Any

import webview

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
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.moteur.validation import CoupInvalide, DictionnaireMots
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
    """API Python exposée au JavaScript de l'écran de jeu (lecture seule).

    L'API respecte la règle de confidentialité : ``obtenir_etat`` ne révèle
    aucune lettre de chevalet, et ``obtenir_chevalet`` n'expose que le chevalet
    d'**un seul** joueur (celui dont l'index est demandé) à la fois.
    """

    def __init__(self, partie: Partie, id_partie: int | None) -> None:
        self._partie = partie
        self._id_partie = id_partie
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """Associe la fenêtre pywebview pour les callbacks."""
        self._window = window

    def obtenir_etat(self) -> dict[str, Any]:
        """Retourne l'état public de la partie (sans lettres de chevalet)."""
        return etat_public(self._partie, self._id_partie)

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

    def poser_mot(self, placements: list[Any]) -> dict[str, Any]:
        """Pose le mot décrit par ``placements`` (mécanique clic-clic du JS).

        ``placements`` est la liste des lettres déposées sur des cases vides
        (dicts ``{ligne, colonne, lettre, joker}``). Le sens du mot se déduit de
        l'alignement des lettres ; pour une lettre unique il est fixé à
        l'horizontale en interne (issue #43 : sans conséquence sur la validation
        ni le score). Aucun paramètre de sens n'est plus attendu du JS. La
        méthode construit un
        :class:`~scrabble.moteur.plateau_partie.Coup`, appelle
        :meth:`~scrabble.moteur.partie.Partie.jouer_coup` et renvoie :

        * en cas de succès : ``{"succes": True, "points": ..., "etat": ...}``
          où ``etat`` est l'état public rafraîchi (plateau, scores, tour) ;
        * en cas d'échec : ``{"succes": False, "erreur": <message clair>}`` — les
          lettres en attente ne sont pas perdues (le JS les conserve pour
          correction).

        Confidentialité : la réponse ne contient jamais l'identité des lettres
        d'un chevalet (``etat`` est l'état public, sans chevalet).
        """
        resultat = jouer_placements(self._partie, placements)
        if resultat.get("succes"):
            resultat["etat"] = etat_public(self._partie, self._id_partie)
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
        return echanger_chevalet_complet(self._partie, self._id_partie)

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
        return jouer_tours_ia_ui(self._partie, self._id_partie)


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #


def lancer_jeu(partie: Partie, id_partie: int | None) -> None:
    """Lance l'écran de jeu pour la ``partie`` donnée (bloquant).

    ``partie`` est typiquement celle créée par l'écran d'accueil (issue #27) ;
    ``id_partie`` est son identifiant de persistance (peut être ``None`` en
    mode démonstration autonome).
    """
    api = ApiJeu(partie, id_partie)
    chemin_html = DOSSIER_WEB / "jeu.html"
    window = webview.create_window(
        "Scrabble - Partie en cours",
        str(chemin_html),
        js_api=api,
        # Fenêtre par défaut agrandie (issue #55) : le plateau et la fenêtre de
        # l'issue #47 (1120×800, plateau min(52vw, 360px)) étaient jugés trop
        # petits au test manuel. On agrandit nettement pour redonner sa place au
        # plateau (désormais min(68vw, 560px), voir jeu.css), quitte à accepter un
        # léger défilement vertical à 4 joueurs plutôt que de sacrifier la
        # lisibilité des cases. La fenêtre reste redimensionnable.
        width=1320,
        height=980,
        resizable=True,
    )
    api.set_window(window)
    webview.start()


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
