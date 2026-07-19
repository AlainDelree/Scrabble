"""Écran de jeu : affichage du plateau et du chevalet (pywebview).

Première brique de l'écran de jeu (suite de l'écran d'accueil, issue #27).
Cet écran est **en lecture seule** : il affiche le plateau, les tuiles déjà
posées, les scores, le joueur courant et le nombre de jetons restants dans le
sac. Aucune pose de mot n'est encore possible ici (ce sera l'étape suivante).

Confidentialité du chevalet
---------------------------
Le panneau du bas suit le **joueur humain de référence** — le premier joueur
humain de la partie (voir :func:`index_humain_reference`). Depuis l'issue #99,
ses lettres sont **toujours** exposées à la fenêtre chevalet (panneau toujours
visible et réarrangeable, comme un vrai chevalet physique), y compris hors de
son tour ; seule la pose réelle sur le plateau reste réservée à son tour (garde
de tour côté API, voir :meth:`ApiJeu._refuser_hors_tour`). En revanche le
chevalet n'est **jamais** exposé pour un autre joueur — ni un ordinateur, ni un
second humain : :meth:`ApiJeu._etat_chevalet` ne sérialise que le chevalet du
joueur de référence. Côté API, deux règles structurelles garantissent ce
principe : :meth:`ApiJeu.obtenir_chevalet` n'expose **que** le chevalet du
joueur dont l'index est demandé — il n'existe aucune méthode renvoyant tous les
chevalets d'un coup — et :func:`etat_public` ne contient aucune identité de
lettre.

Lancement de l'écran pour test (mode démonstration) ::

    python -m scrabble.ui.jeu

Ce mode construit une :class:`~scrabble.moteur.partie.Partie` d'exemple à deux
joueurs, avec un plateau partiellement rempli (voir :func:`construire_partie_demo`),
et ouvre l'écran de jeu sans passer par l'écran d'accueil.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

import webview

from scrabble import journal
from scrabble.config import AVATARS_DISPONIBLES, THEMES_PLATEAU, charger_config
from scrabble.reglages import lire_reglage, modifier_reglage
from scrabble.dictionnaire.dictionnaire import (
    CHEMIN_DEFINITIONS,
    Trie,
    definition_mot,
    normaliser_mot,
)
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import (
    ActionInvalide,
    EntreeHistorique,
    Joueur,
    Partie,
    recreer_partie_meme_joueurs,
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
    demarrer_suivi,
    enregistrer_action,
    finaliser_partie,
)
from scrabble.moteur.validation import CoupInvalide, DictionnaireMots, valider_coup
from scrabble.regles.lettres import JOKER, valeur_lettre
from scrabble.regles.plateau import TAILLE, type_case
from scrabble.ui import TAPIS_VERT

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


# Côtés attribués aux autres joueurs, indexés par leur rang *relatif* au joueur
# humain de référence dans l'ordre de jeu (issue #122). La clé est l'effectif
# total ; la valeur donne, pour le 1er, 2e, 3e joueur *après* la référence dans
# l'ordre de jeu, le côté du plateau à occuper, en tournant dans le sens horaire
# à partir du bas : bas → gauche → haut → droite.
#
# Exception documentée à 2 joueurs : face-à-face bas/haut, il n'y a pas de strict
# sens horaire dans ce cas précis (l'unique adversaire est placé en face).
SEQUENCES_POSITIONS = {
    2: ("haut",),
    3: ("gauche", "haut"),
    4: ("gauche", "haut", "droite"),
}


def index_humain_reference(joueurs: list[Joueur]) -> int:
    """Index du **joueur humain de référence** : le premier joueur ``humain``.

    Source de vérité unique du « joueur humain de référence » (issue #99) — celui
    dont le panneau du bas (chevalet) est toujours visible et réarrangeable, y
    compris hors de son tour, et dont on expose les lettres à la fenêtre chevalet.
    Reprend exactement la règle déjà utilisée pour la position ``"bas"`` : le
    premier joueur ``humain`` de la liste, ou l'index ``0`` s'il n'y a aucun
    humain (cas théorique / test). Réutilisée par :func:`calculer_positions`
    (placement au bas du plateau), par :meth:`ApiJeu._etat_chevalet` et par la
    garde de tour des mutations de pose (:meth:`ApiJeu._refuser_hors_tour`) — plus
    aucune duplication de ce ``next(...)`` ailleurs dans le module.
    """
    return next(
        (index for index, joueur in enumerate(joueurs) if joueur.humain), 0
    )


def calculer_positions(joueurs: list[Joueur]) -> list[str]:
    """Position spatiale de chaque joueur autour du plateau (index → côté).

    Renvoie une liste parallèle à ``joueurs`` où l'élément ``i`` est le côté
    (``"bas"``, ``"haut"``, ``"gauche"`` ou ``"droite"``) assigné au joueur
    d'index ``i``. Règle (issues #33 puis #122), avec une seule source de vérité
    côté Python :

    * Le **joueur humain de référence** — le premier joueur ``humain`` de la
      liste ``joueurs`` — est toujours en ``"bas"`` (position naturelle face à
      l'écran). S'il n'y a aucun humain (cas théorique / test), le premier
      joueur tient ce rôle.
    * Tous les autres joueurs (humains et ordinateurs confondus) se répartissent
      sur les côtés restants **dans le sens horaire** (bas → gauche → haut →
      droite), selon leur rang *relatif* à la référence dans l'ordre de jeu :
      le joueur qui joue juste après la référence occupe le côté suivant dans le
      sens horaire, et ainsi de suite. L'ordre de jeu étant déjà encodé dans
      l'ordre de la liste ``joueurs`` (le tirage d'ordre l'a réordonnée), les
      positions suivent l'ordre de jeu réel — y compris quand l'humain n'est pas
      le premier à jouer.

    Exception documentée à 2 joueurs : face-à-face bas/haut (voir
    :data:`SEQUENCES_POSITIONS`), sans strict sens horaire dans ce cas précis.

    Cas particuliers : liste vide → ``[]`` ; un seul joueur → ``["bas"]`` (aucune
    position latérale).
    """
    if not joueurs:
        return []
    n = len(joueurs)
    positions = [""] * n
    reference = index_humain_reference(joueurs)
    positions[reference] = "bas"
    sequence = SEQUENCES_POSITIONS.get(n, ())
    for k in range(1, n):
        positions[(reference + k) % n] = sequence[k - 1]
    return positions


# Bibliothèque d'avatars SVG (issue #34). Chaque identifiant correspond à un
# fichier ``web/avatars/<id>.svg`` (portraits stylisés originaux, un jeu de
# traits distinctifs par avatar). Une quinzaine suffit largement à garantir
# l'absence de doublon avec au plus 4 joueurs par partie. L'ordre de cette liste
# fait partie du contrat déterministe : ne pas la réordonner sans raison. La
# définition (source de vérité unique) vit désormais dans ``scrabble.config``
# (issue #143), partagée avec les réglages ; on la ré-exporte ici sous son nom
# historique ``AVATARS`` pour ne pas casser les usages existants.
AVATARS: tuple[str, ...] = AVATARS_DISPONIBLES


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


def calculer_avatars(
    joueurs: list[Joueur], avatar_principal: str = ""
) -> list[str]:
    """Avatar attribué à chaque joueur autour du plateau (index → identifiant).

    Renvoie une liste parallèle à ``joueurs`` où l'élément ``i`` est l'identifiant
    d'avatar (voir :data:`AVATARS`) assigné au joueur d'index ``i``. Comme
    :func:`calculer_positions`, c'est **une seule source de vérité** côté Python,
    consommée telle quelle par l'UI (aucune logique d'attribution dupliquée en
    JS). Propriétés garanties (issue #34) :

    * **Déterminisme** : l'attribution ne dépend que de la liste ``joueurs`` (nom
      + rang) et de ``avatar_principal``, donc un même appel sur une même partie
      rend toujours le même résultat — pas de ré-tirage à chaque rafraîchissement
      d'écran.
    * **Absence de doublon** tant qu'il reste des avatars libres : chaque joueur
      vise l'avatar de sa graine puis, s'il est déjà pris, un sondage linéaire
      lui trouve le prochain avatar libre. Avec ≤ 4 joueurs et 15 avatars, aucun
      doublon n'est possible.
    * **Dégradation propre** si le nombre de joueurs dépassait celui des avatars
      (cas théorique, impossible avec ``MAX_JOUEURS`` = 4) : le sondage échoue,
      on retombe sur l'avatar préféré et un doublon est toléré plutôt que de
      planter.

    Choix d'avatar du joueur humain (issue #143) : si ``avatar_principal`` est un
    identifiant connu **et** que la partie compte au moins un joueur humain, cet
    avatar est attribué d'office au **joueur humain de référence** (voir
    :func:`index_humain_reference`) et retiré du pool avant le tirage des autres
    joueurs. Aucun ordinateur ne peut donc recevoir l'avatar choisi par
    l'humaine. Un ``avatar_principal`` vide ou inconnu (ou une partie sans humain)
    laisse l'attribution historique inchangée.
    """
    nb = len(AVATARS)
    assignes: list[str] = [""] * len(joueurs)
    pris: set[int] = set()

    # Réservation éventuelle de l'avatar choisi au joueur humain de référence.
    reference = index_humain_reference(joueurs) if joueurs else -1
    reserver = (
        avatar_principal in AVATARS
        and any(joueur.humain for joueur in joueurs)
    )
    if reserver:
        indice_reserve = AVATARS.index(avatar_principal)
        pris.add(indice_reserve)
        assignes[reference] = AVATARS[indice_reserve]

    for index, joueur in enumerate(joueurs):
        if reserver and index == reference:
            continue  # avatar déjà attribué d'office à l'humain de référence
        prefere = _graine_avatar(joueur, index) % nb
        choix = prefere
        for pas in range(nb):
            candidat = (prefere + pas) % nb
            if candidat not in pris:
                choix = candidat
                break
        pris.add(choix)
        assignes[index] = AVATARS[choix]
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


# Seuils officiels d'évaluation du score total combiné en fin de partie
# (livret de règles Jeux Spear, page 10, issue #137). Un total combiné
# (somme des scores finaux de tous les joueurs) est jugé :
#   >= 700         → « Excellent score »
#   600 .. 699     → « Très bon score »
#   500 .. 599     → « Bon score »
#   < 500          → aucun qualificatif (la règle n'en définit pas)
# Les seuils portent sur le total combiné : ils sont volontairement
# indépendants du nombre de joueurs. La règle cite des seuils individuels
# (125-150 à 4 joueurs, 250-300 à 2 joueurs) qui sont exactement 500-600
# divisés par le nombre de joueurs ; comparer le total combiné aux seuils
# fixes est donc strictement équivalent à comparer la moyenne individuelle
# aux mêmes seuils divisés par le nombre de joueurs — d'où une seule
# classification, présentée à titre indicatif aussi en moyenne par joueur.
SEUIL_BON_SCORE = 500
SEUIL_TRES_BON_SCORE = 600
SEUIL_EXCELLENT_SCORE = 700


def classer_score_total(total_combine: int) -> str | None:
    """Qualificatif officiel du total combiné, ou ``None`` en dessous de 500.

    Applique les seuils :data:`SEUIL_BON_SCORE` / :data:`SEUIL_TRES_BON_SCORE`
    / :data:`SEUIL_EXCELLENT_SCORE` (issue #137). Ne dépend **que** du total
    combiné, jamais du nombre de joueurs (voir la note sur les seuils).
    """
    if total_combine >= SEUIL_EXCELLENT_SCORE:
        return "Excellent score"
    if total_combine >= SEUIL_TRES_BON_SCORE:
        return "Très bon score"
    if total_combine >= SEUIL_BON_SCORE:
        return "Bon score"
    return None


def evaluer_score_total(joueurs: "list[Joueur]") -> dict[str, Any]:
    """Évalue le total combiné des scores finaux de tous les joueurs (issue #137).

    Renvoie un dictionnaire sérialisable pour l'UI :

    * ``total`` : somme des scores finaux (déductions/bonus de fin de partie
      déjà appliqués, issue #130) ;
    * ``nb_joueurs`` : nombre de joueurs pris en compte ;
    * ``moyenne`` : score individuel de référence (``total / nb_joueurs``),
      arrondi à l'entier le plus proche, à afficher à titre indicatif ;
    * ``qualificatif`` : « Bon score » / « Très bon score » / « Excellent
      score » selon les seuils officiels, ou ``None`` en dessous de 500.

    La moyenne ne donne **pas** lieu à une classification distincte : elle est
    mathématiquement équivalente au total combiné rapporté au même nombre de
    joueurs (voir la note sur les seuils).
    """
    total = sum(joueur.score for joueur in joueurs)
    nb_joueurs = len(joueurs)
    moyenne = round(total / nb_joueurs) if nb_joueurs else 0
    return {
        "total": total,
        "nb_joueurs": nb_joueurs,
        "moyenne": moyenne,
        "qualificatif": classer_score_total(total),
    }


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

    ``evaluation_score`` (issue #137) n'est renseigné qu'en fin de partie : il
    porte le total combiné des scores, son qualificatif officiel éventuel et le
    score individuel de référence (voir :func:`evaluer_score_total`) ; ``None``
    tant que la partie n'est pas terminée.

    ``historique`` (issue #37, #144) est l'**intégralité** de l'historique des
    actions (voir :func:`serialiser_historique`) : la plus récente en premier,
    chacune avec le détail du score inclus pour l'ouverture au clic — l'UI
    alimente son encart glissant (scrollable) à partir de ce seul champ, rafraîchi
    après chaque action (coup humain ou série de tours IA).
    """
    positions = calculer_positions(partie.joueurs)
    avatar_principal = charger_config().get("avatar_principal", "")
    avatars = calculer_avatars(partie.joueurs, avatar_principal)
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
        "evaluation_score": (
            evaluer_score_total(partie.joueurs) if partie.terminee else None
        ),
        "historique": serialiser_historique(partie),
    }


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
    """Sérialise l'**intégralité** de l'historique pour l'encart « Derniers coups ».

    Renvoie **toutes** les actions de la partie (issue #144), **la plus récente
    en premier** (ordre décroissant d'ancienneté — choix documenté de l'issue #37 :
    le dernier coup apparaît en tête de l'encart). En début de partie, l'historique
    ne compte que ce qui a été joué (p. ex. 2 lignes seulement à 1 humain +
    1 ordinateur après un tour chacun).

    Le fenêtrage d'affichage historique (``min(nb_joueurs * 2, 8)`` lignes, issue
    #37) a été retiré (issue #144) : l'encart est désormais scrollable côté UI et
    montre toute la partie, la plus récente en haut. Aucune borne n'est donc plus
    appliquée ici.

    Chaque entrée est sérialisée par :func:`serialiser_entree_historique`, en
    conservant son index d'origine dans ``partie.historique`` (identifiant stable
    du coup).
    """
    entrees = [
        serialiser_entree_historique(partie, entree, index)
        for index, entree in enumerate(partie.historique)
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
    dictionnaire: DictionnaireMots,
    lettres: Any,
    chemin_definitions: Path = CHEMIN_DEFINITIONS,
    source: str = "ods",
) -> dict[str, Any]:
    """Teste l'appartenance au dictionnaire du mot formé par ``lettres``.

    ``lettres`` est la suite de jetons arrangés dans la zone de brouillon (dans
    l'ordre affiché), soit sous forme de liste, soit déjà concaténée. Le mot est
    normalisé (majuscules, NFC) comme le Trie ODS8 l'attend, puis testé via
    :meth:`dictionnaire.contient`. **Lecture seule** : aucune mutation de la
    partie ni du dictionnaire.

    Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool, "definition":
    [gloses] | None}`` ; si la suite est vide (après normalisation),
    ``{"succes": False, "erreur": <message>}``. Un joker (``*``) laissé dans le
    brouillon n'est pas une lettre fixe : il empêche tout mot d'être trouvé (le
    test renverra ``valide`` faux), ce qui est le comportement attendu d'un
    simple test d'appartenance.

    La définition n'est calculée que si le mot est valide **et** que la source
    active de la partie (``source``) est ``"ods"``, en réutilisant
    :func:`~scrabble.dictionnaire.dictionnaire.definition_mot` (ODS8 uniquement,
    même source que l'onglet Dictionnaire des réglages, issue #111). Quand la
    partie est jouée avec ``"hunspell"`` comme source active (issue #127), la
    définition est **systématiquement** ``None``, même si le mot valide se
    trouve, par coïncidence, présent dans l'index ODS8 : « Vérification
    dictionnaire » reste ainsi strictement cohérent avec ce qui valide les coups
    sur le plateau et ne laisse pas croire que l'ODS8 joue un rôle dans cette
    partie. En source ODS, un mot présent seulement dans Hunspell — ou absent de
    l'index — renvoie aussi ``"definition": None`` : à l'UI d'afficher
    « définition indisponible ». Un mot invalide renvoie toujours ``None``
    (aucune définition n'a de sens).
    """
    mot = normaliser_mot(_concatener_lettres(lettres))
    if not mot:
        return {
            "succes": False,
            "erreur": "La zone de brouillon ne contient aucune lettre à vérifier.",
        }
    valide = bool(dictionnaire.contient(mot))
    definition = (
        definition_mot(mot, chemin_definitions)
        if valide and source == "ods"
        else None
    )
    return {
        "succes": True,
        "mot": mot,
        "valide": valide,
        "definition": definition,
    }


def echanger_jetons(
    partie: Partie, id_partie: int | None, jetons: list[str]
) -> dict[str, Any]:
    """Échange la liste précise ``jetons`` du chevalet courant et passe le tour.

    Cœur non-UI commun à l'échange **complet** (:func:`echanger_chevalet_complet`)
    et à l'échange **partiel** (:meth:`ApiJeu.echanger_selection`, issue #138).
    Délègue à :meth:`~scrabble.moteur.partie.Partie.echanger`, qui suit les mêmes
    règles quel que soit le nombre de lettres : sac suffisant, remise en jeu des
    lettres échangées, tirage de remplacement et consommation du tour (aucun
    passe séparé n'est requis). Tout rejet du moteur (sac trop pauvre, liste
    vide, lettres absentes, partie terminée) est capturé et transformé en
    ``{"succes": False, "erreur": ...}`` sans plantage. En cas de succès, l'état
    public rafraîchi est joint.
    """
    try:
        partie.echanger(jetons)
    except ActionInvalide as err:
        return {"succes": False, "erreur": str(err)}
    return {"succes": True, "etat": etat_public(partie, id_partie)}


def echanger_chevalet_complet(
    partie: Partie, id_partie: int | None
) -> dict[str, Any]:
    """Remet **tout** le chevalet du joueur courant dans le sac et passe le tour.

    Cœur non-UI de :meth:`ApiJeu.echanger_tout`. Cas particulier « toutes les
    lettres » de :func:`echanger_jetons`, auquel il délègue avec la totalité du
    chevalet courant.
    """
    joueur = partie.joueur_courant()
    return echanger_jetons(partie, id_partie, list(joueur.chevalet))


def passer_tour(partie: Partie, id_partie: int | None) -> dict[str, Any]:
    """Fait **passer** le joueur courant sans rien échanger (issue #132).

    Cœur non-UI de :meth:`ApiJeu.passer`. Délègue à
    :meth:`~scrabble.moteur.partie.Partie.passer`, qui incrémente
    ``passes_consecutives`` et termine la partie par blocage lorsque tous les
    joueurs ont passé d'affilée (``passes_consecutives >= len(joueurs)``).

    Contrairement à :func:`echanger_chevalet_complet`, passer ne dépend pas du
    sac : c'est le recours qui débloque un joueur humain sac vide (rapport #130),
    tout en restant un droit normal du jeu utilisable à tout moment de son tour.
    Le seul échec prévisible (partie déjà terminée) est capturé et transformé en
    ``{"succes": False, "erreur": ...}`` sans plantage. En cas de succès, l'état
    public rafraîchi est joint.
    """
    try:
        partie.passer()
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
        # Échange partiel (issue #138). ``_type_echange`` fige, à la construction
        # de l'API (donc au démarrage de la partie), le mode choisi dans les
        # réglages : "complet" (bouton « Remettre toutes ses lettres ») ou
        # "partiel" (sélection libre de 1 à 7 lettres). ``_mode_echange`` indique
        # que le joueur est en train de marquer des lettres à échanger, et
        # ``_selection_echange`` porte les index de chevalet ainsi marqués (une
        # information neutre — de simples index — ne dévoilant aucune lettre).
        self._type_echange: str = charger_config().get("type_echange", "complet")
        self._mode_echange: bool = False
        self._selection_echange: list[int] = []
        # Pose d'un joker en attente du choix de lettre (issue #90) : lorsqu'un
        # clic sur une case du plateau (fenêtre plateau) porte sur un joker, la
        # modale de choix s'ouvre côté chevalet. On mémorise ici la case visée en
        # attendant ce choix : ``{ligne, colonne, index}`` ou ``None``.
        self._joker_demande: dict[str, Any] | None = None
        # Évite de journaliser plusieurs fois la même fin de partie (issue #66).
        self._fin_journalisee = False
        # Anti-flood pour le glisser-déposer applicatif du chevalet
        # (issue #91 point 2, tracé pour l'issue #92) : on journalise le début de
        # chaque drag et son PREMIER déplacement effectif (preuve que les événements
        # pointeur JS atteignent bien Python), pas chacune des frames suivantes.
        self._drag_premier_deplacement = False
        # Évite de finaliser plusieurs fois la partie en base (issue #81).
        self._fin_persistee = False
        # Vrai lorsque l'utilisateur a demandé « Retour au menu » (issue #74) :
        # une fois les fenêtres de jeu fermées, ``lancer_jeu`` rouvre alors
        # l'écran d'accueil (au lieu de clôturer la session) — voir ``lancer_jeu``.
        self._retour_menu = False
        # « Recommencer » depuis la modale de fin de partie (issue #142) : quand
        # l'utilisateur choisit de rejouer avec les mêmes joueurs, on prépare ici
        # la nouvelle partie (et son identifiant de persistance) puis on ferme les
        # fenêtres. ``lancer_jeu``, voyant ce drapeau, relance alors l'écran de
        # jeu sur cette nouvelle partie (au lieu de clôturer la session).
        self._recommencer = False
        self._nouvelle_partie: Partie | None = None
        self._nouvel_id_partie: int | None = None
        # Garde-fou anti-boucle de la fermeture croisée par la croix (issue #94) :
        # fermer une fenêtre par sa croix détruit l'autre, dont la destruction
        # re-déclenche l'événement ``closing`` (sous GTK, ``destroy()`` passe aussi
        # par ``close_window``). Ce drapeau, posé au premier passage, fait
        # court-circuiter les déclenchements suivants pour éviter une récursion.
        self._fermeture_en_cours = False

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

    def installer_fermeture_croisee(self) -> None:
        """Câble la fermeture native (croix ✕) des deux fenêtres — issue #94.

        Avant l'issue #90, l'écran de jeu était une **fenêtre unique** : la fermer
        par sa croix quittait proprement l'application (issue #74). Depuis la
        séparation en deux fenêtres, fermer « Scrabble - Plateau » par sa croix
        laissait « Scrabble - Chevalet » (``on_top``) orpheline, et inversement —
        seul le bouton applicatif « Retour au menu » détruisait bien les deux.

        On s'abonne donc à l'événement pywebview ``events.closing`` de **chacune**
        des deux fenêtres : à la fermeture native de l'une, on détruit l'autre
        (:meth:`_sur_fermeture_native`). Contrairement à « Retour au menu », une
        fermeture par la croix **quitte l'application** (on ne positionne pas
        ``_retour_menu``, donc :func:`lancer_jeu` ne rouvre pas l'accueil) —
        comportement attendu d'une croix, cohérent avec la fenêtre unique d'avant
        l'issue #90.

        Tolère les fenêtres factices des tests (pas d'attribut ``events`` ou pas
        d'événement ``closing``) : dans ce cas on n'abonne rien.
        """
        for fenetre in (self._window_plateau, self._window_chevalet):
            evenements = getattr(fenetre, "events", None)
            closing = getattr(evenements, "closing", None)
            if closing is None:
                continue
            # ``Event.__iadd__`` (pywebview) ajoute un abonné et renvoie l'événement
            # lui-même : ``closing += handler`` mute l'événement en place. Le
            # handler déclare un paramètre ``window`` : pywebview lui passe alors la
            # fenêtre émettrice, ce qui permet de détruire *l'autre*.
            closing += self._sur_fermeture_native

    def _sur_fermeture_native(self, window: "webview.Window") -> None:
        """Ferme la fenêtre jumelle quand ``window`` est fermée par sa croix (issue #94).

        Abonné à ``events.closing`` des deux fenêtres par
        :meth:`installer_fermeture_croisee`. La fenêtre qui reçoit la croix se
        ferme d'elle-même (on ne la détruit pas ici, pour éviter une double
        fermeture) ; on se contente de détruire **l'autre** fenêtre si elle est
        encore ouverte, afin qu'aucune ne reste orpheline.

        Garde-fou anti-boucle (``_fermeture_en_cours``) : sous GTK, ``destroy()``
        repasse par ``close_window`` et re-déclenche ``closing``. Sans ce drapeau,
        détruire la fenêtre B depuis la fermeture de A relancerait le traitement
        pour B (qui tenterait de re-détruire A), etc. Au premier passage on lève le
        drapeau ; les déclenchements suivants ressortent immédiatement.

        On ne renvoie jamais ``False`` : l'événement ``closing`` de pywebview
        n'annule la fermeture que si un abonné renvoie ``False``. Renvoyer ``None``
        laisse donc la fermeture se poursuivre normalement.
        """
        if self._fermeture_en_cours:
            return
        self._fermeture_en_cours = True
        journal.info(
            "Jeu : fermeture native (croix) détectée — fermeture des deux "
            f"fenêtres et sortie (partie #{self._id_partie})."
        )
        autre = (
            self._window_chevalet
            if window is self._window_plateau
            else self._window_plateau
        )
        if autre is None:
            return
        try:
            autre.destroy()
        except Exception as e:  # noqa: BLE001 - une fermeture ratée ne doit rien bloquer
            journal.erreur(
                "Jeu : destruction de la fenêtre jumelle (fermeture croisée) "
                "impossible.",
                e,
            )

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
        # Échange partiel (issue #138) : le mode réglé et l'éventuelle sélection
        # d'échange en cours (index neutres) pilotent l'affichage des boutons de
        # la zone de jeu (« Échanger des lettres… » / « Échanger la sélection »).
        etat["type_echange"] = self._type_echange
        etat["mode_echange"] = self._mode_echange
        etat["selection_echange"] = list(self._selection_echange)
        return etat

    def _etat_chevalet(self) -> dict[str, Any]:
        """État **complet** (lettres privées incluses) destiné à la fenêtre chevalet.

        Depuis l'issue #99, le payload porte sur le **joueur humain de référence**
        (:func:`index_humain_reference`), et non plus sur le joueur courant : ses
        lettres sont **toujours** sérialisées (panneau toujours visible et
        réarrangeable), y compris hors de son tour. ``mon_tour`` dit si c'est
        actuellement son tour — seule condition pour poser réellement (garde de
        tour, :meth:`_refuser_hors_tour`). L'état de pose complet est joint
        (sélection, placements avec leur ``index`` de chevalet, éventuelle demande
        de choix de lettre pour un joker), ainsi que quelques champs publics (nom
        du joueur de référence, fin de partie) pour éviter un aller-retour.

        La garantie de confidentialité demeure : jamais le chevalet d'un
        ordinateur ni d'un autre joueur humain que le joueur de référence.
        """
        partie = self._partie
        index_reference = index_humain_reference(partie.joueurs)
        reference = partie.joueurs[index_reference]
        return {
            "index_reference": index_reference,
            "nom": reference.nom,
            "mon_tour": partie.index_courant == index_reference
            and not partie.terminee,
            "terminee": partie.terminee,
            "nb_lettres": len(reference.chevalet),
            # Lettres privées : toujours celles du joueur de référence (issue #99),
            # jamais un ordinateur ni un autre humain.
            "lettres": serialiser_chevalet(reference),
            "selection": self._selection,
            "en_attente": [dict(p) for p in self._en_attente],
            "joker_demande": self._joker_demande,
            # Échange partiel (issue #138) : le panneau marque distinctement les
            # lettres à échanger quand ``mode_echange`` est actif.
            "type_echange": self._type_echange,
            "mode_echange": self._mode_echange,
            "selection_echange": list(self._selection_echange),
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
        # Z-order : plus de ré-affirmation applicative d'``on_top`` ici (issue #105).
        # Le chevalet est désormais lié au plateau par une relation transiente
        # (``set_transient_for``, cf. :func:`_lier_chevalet_au_plateau`), honorée
        # une fois pour toutes par le gestionnaire de fenêtres — inutile de la
        # re-poser après chaque interaction.

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
            x, y = int(self._window_chevalet.x), int(self._window_chevalet.y)
            # Trace (issue #92) : confirme que l'événement pointeur de la barre de
            # drag a bien traversé le pont JS → Python. Réarme la trace du premier
            # déplacement pour ce nouveau drag.
            self._drag_premier_deplacement = False
            journal.info(
                f"Jeu : début de déplacement du chevalet demandé (position "
                f"actuelle ({x}, {y}))."
            )
            return {"succes": True, "x": x, "y": y}
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
            if not self._drag_premier_deplacement:
                self._drag_premier_deplacement = True
                journal.info(
                    f"Jeu : premier déplacement du chevalet reçu et appliqué "
                    f"(move vers ({int(x)}, {int(y)}) ; frames suivantes "
                    f"silencieuses)."
                )
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - un déplacement raté ne bloque pas le jeu
            return {"succes": False, "erreur": f"Déplacement impossible : {e}"}

    def fin_deplacement_chevalet(self) -> dict[str, Any]:
        """Mémorise la position de la fenêtre chevalet à la **fin** d'un drag (issue #135).

        Appelée par le JS de la barre de titre une seule fois, au relâchement du
        clic (``mouseup``) — surtout pas à chaque mouvement, pour n'écrire sur
        disque qu'une fois par déplacement plutôt qu'à chaque pixel parcouru. La
        position lue (``window.x``/``.y``, fiable depuis la bascule XWayland de
        l'issue #93) est persistée dans le réglage ``position_chevalet`` via le
        mécanisme habituel (:mod:`scrabble.reglages`, auto-réparation + écriture
        atomique), pour être réutilisée au prochain lancement de l'écran de jeu.
        Tout échec est journalisé sans planter le jeu.
        """
        if self._window_chevalet is None:
            return {"succes": False, "erreur": "Aucune fenêtre chevalet."}
        try:
            x, y = int(self._window_chevalet.x), int(self._window_chevalet.y)
        except Exception as e:  # noqa: BLE001 - position indisponible : on n'enregistre rien
            return {"succes": False, "erreur": f"Position indisponible : {e}"}
        try:
            modifier_reglage("position_chevalet", {"x": x, "y": y})
            journal.info(f"Jeu : position du chevalet mémorisée ({x}, {y}).")
        except Exception as e:  # noqa: BLE001 - une mémorisation ratée ne bloque pas le jeu
            journal.erreur(
                "Jeu : échec de la mémorisation de la position du chevalet.", e
            )
            return {"succes": False, "erreur": f"Mémorisation impossible : {e}"}
        return {"succes": True, "x": x, "y": y}

    def diagnostiquer_joker_modale(self, mesures: Any = None) -> dict[str, Any]:
        """Journalise les dimensions RÉELLES à l'ouverture de la modale du joker (issue #140).

        Suite de l'issue #121 : le sélecteur de lettre du joker reste tronqué en
        conditions réelles (WebKitGTK) alors que la mesure headless de l'issue #131
        ne trouvait aucun débordement. C'est le second écart rendu-réel /
        rendu-mesuré sur ce composant précis ; le projet en a déjà rencontré
        d'autres (Wayland #93, chevalet #92/#94/#96/#97). Plutôt qu'une troisième
        mesure headless (méthode en échec deux fois ici), on trace les valeurs du
        vrai moteur de rendu, sur le modèle du diagnostic z-order de l'issue #93 :
        le JS mesure le DOM effectivement affiché et le remonte via cette méthode,
        qui l'ajoute à la géométrie native de la fenêtre chevalet lue côté Python.

        ``mesures`` est le dictionnaire construit côté JS (viewport, boîte du
        contenu de ``#joker-modale``, grille scrollable, bouton Annuler). Purement
        diagnostique : aucune mutation d'état, tout échec est absorbé sans planter
        le jeu. Le correctif définitif sera appliqué une fois la cause confirmée
        par le prochain journal d'Alain, selon la même philosophie « toujours
        accessible » retenue en #121 (grille scrollable, Annuler épinglé).
        """
        # 1. Géométrie native de la fenêtre chevalet au moment de l'affichage
        #    (cible théorique CHEVALET_LARGEUR×CHEVALET_HAUTEUR = 480×175, #106).
        native = "indisponible (fenêtre absente ou backend non-GTK)"
        if self._window_chevalet is not None:
            try:
                w = int(getattr(self._window_chevalet, "width", 0))
                h = int(getattr(self._window_chevalet, "height", 0))
                x = int(getattr(self._window_chevalet, "x", 0))
                y = int(getattr(self._window_chevalet, "y", 0))
                native = f"{w}×{h} px @ ({x}, {y})"
            except Exception as e:  # noqa: BLE001 - lecture purement diagnostique
                native = f"illisible ({e!r})"
        journal.info(
            f"Jeu : [diag #140] ouverture modale joker — fenêtre chevalet native = "
            f"{native} (cible {CHEVALET_LARGEUR}×{CHEVALET_HAUTEUR})."
        )

        # 2. Mesures DOM remontées par le JS (viewport CSS, boîtes réelles).
        if not isinstance(mesures, dict):
            journal.info(
                "Jeu : [diag #140] aucune mesure DOM remontée par le JS "
                "(mesures manquantes ou invalides)."
            )
            return {"succes": True}
        try:
            vp = mesures.get("viewport") or {}
            de = mesures.get("documentElement") or {}
            contenu = mesures.get("contenu") or {}
            grille = mesures.get("grille") or {}
            annuler = mesures.get("annuler") or {}
            vp_h = vp.get("hauteur")
            contenu_bas = contenu.get("bas")
            annuler_bas = annuler.get("bas")
            # Débordement bas = combien la boîte du contenu dépasse sous le viewport
            # (positif => tronqué malgré le max-height:100vh du correctif #121).
            debordement = (
                contenu_bas - vp_h
                if isinstance(contenu_bas, (int, float))
                and isinstance(vp_h, (int, float))
                else None
            )
            annuler_visible = (
                annuler_bas <= vp_h
                if isinstance(annuler_bas, (int, float))
                and isinstance(vp_h, (int, float))
                else None
            )
            grille_scroll = grille.get("scrollHeight")
            grille_client = grille.get("clientHeight")
            grille_defilable = (
                grille_scroll > grille_client
                if isinstance(grille_scroll, (int, float))
                and isinstance(grille_client, (int, float))
                else None
            )
            # Issue #146 : on objective l'agrandissement de la zone visible de la
            # grille. « caché » = hauteur de contenu non visible sans défiler
            # (scrollHeight - clientHeight) ; « part visible » = fraction affichée
            # d'emblée. Le prochain journal d'Alain doit montrer une part visible
            # nettement plus haute qu'en #140 (grille 62 px visibles / 166 px totaux
            # ≈ 37 %) — idéalement 100 % (aucun défilement) grâce aux 9 colonnes.
            grille_cache = (
                max(0, grille_scroll - grille_client)
                if isinstance(grille_scroll, (int, float))
                and isinstance(grille_client, (int, float))
                else None
            )
            grille_part_visible = (
                round(100 * grille_client / grille_scroll)
                if isinstance(grille_scroll, (int, float))
                and isinstance(grille_client, (int, float))
                and grille_scroll > 0
                else None
            )
            journal.info(
                "Jeu : [diag #140] mesures DOM réelles — "
                f"viewport CSS {vp.get('largeur')}×{vp_h} ; "
                f"documentElement {de.get('largeur')}×{de.get('hauteur')} ; "
                f"devicePixelRatio {mesures.get('devicePixelRatio')} ; "
                f"contenu boîte [haut={contenu.get('haut')}, bas={contenu_bas}, "
                f"hauteur={contenu.get('hauteur')}] ; "
                f"grille [scrollHeight={grille_scroll}, clientHeight={grille_client}, "
                f"défilable={grille_defilable}] ; "
                f"bouton Annuler [bas={annuler_bas}, visible={annuler_visible}] ; "
                f"débordement bas sous viewport = {debordement}."
            )
            journal.info(
                "Jeu : [diag #146] zone visible de la grille — "
                f"hauteur visible (clientHeight) = {grille_client} px sur "
                f"{grille_scroll} px de contenu total (scrollHeight), soit "
                f"{grille_part_visible} % affichés d'emblée ; "
                f"{grille_cache} px encore cachés derrière le défilement "
                f"(défilable={grille_defilable}). Cible : ≥ 3-4 lignes visibles, "
                "à comparer aux ~37 % de l'issue #140."
            )
            if debordement is not None and debordement > 0:
                journal.info(
                    "Jeu : [diag #140] ⚠ le contenu de la modale déborde SOUS le "
                    f"viewport de {debordement} px — le max-height:100vh du "
                    "correctif #121 ne borne pas le contenu dans le vrai rendu."
                )
            elif annuler_visible is False:
                journal.info(
                    "Jeu : [diag #140] ⚠ le bouton Annuler tombe sous le viewport "
                    "alors que le contenu n'y déborde pas globalement — piste : le "
                    "bouton n'est pas épinglé hors zone défilante dans le vrai rendu."
                )
        except Exception as e:  # noqa: BLE001 - un diagnostic raté ne bloque pas le jeu
            journal.erreur("Jeu : [diag #140] mesures DOM illisibles.", e)
        return {"succes": True}

    def _refuser_hors_tour(self) -> dict[str, Any] | None:
        """Refus normalisé si une mutation de pose est tentée hors du tour.

        Garde de tour de l'issue #99. Le panneau du joueur de référence est
        désormais toujours visible et sélectionnable, y compris hors de son tour
        (réflexion libre) ; mais **muter** l'état de pose (sélection, placement en
        attente, retrait, annulation) reste réservé à son tour réel — jusqu'ici
        c'était garanti seulement par le masquage du chevalet hors tour, ce qui
        n'est plus le cas (signalé par le rapport #98).

        Renvoie ``{"succes": False, "erreur": ...}`` si la partie est terminée ou
        si ce n'est pas le tour du joueur humain de référence
        (:func:`index_humain_reference`), sinon ``None`` (action autorisée).
        """
        partie = self._partie
        if partie.terminee or partie.index_courant != index_humain_reference(
            partie.joueurs
        ):
            return {"succes": False, "erreur": "Ce n'est pas votre tour."}
        return None

    def selectionner_lettre(self, index: Any) -> dict[str, Any]:
        """Sélectionne (ou désélectionne) la lettre du chevalet d'index ``index``.

        Appelée par la fenêtre chevalet au clic sur une lettre. ``index`` à
        ``None`` (ou l'index déjà sélectionné) annule la sélection. Met à jour
        ``_selection`` puis diffuse l'état aux deux fenêtres.

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, la sélection est refusée sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
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

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, la pose est refusée sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if not isinstance(ligne, int) or not isinstance(colonne, int):
            return {"succes": False, "erreur": "Position de pose invalide."}
        if not dans_plateau(ligne, colonne):
            return {"succes": False, "erreur": "Position hors plateau."}
        if not self._partie.plateau.case_vide(ligne, colonne):
            return {
                "succes": False,
                "erreur": "Cette case porte déjà une tuile.",
            }
        # Mode « finalisation » : la lettre (et son index) sont fournis. Traité
        # avant le garde « lettre déjà posée ici » car une finalisation peut
        # légitimement écraser une lettre en attente (remplacement par un joker,
        # issue #129).
        if lettre is not None and index is not None:
            self._joker_demande = None
            # Remplacement d'une lettre en attente par un joker (issue #129) :
            # l'ancienne lettre a été laissée en place jusqu'à la validation de la
            # modale de choix ; on la retire ici pour que le joker prenne sa place
            # (l'ancienne redevient disponible au chevalet). Sur une case vierge,
            # ce filtre est sans effet.
            self._en_attente = [
                p for p in self._en_attente
                if not (p["ligne"] == ligne and p["colonne"] == colonne)
            ]
            return self._ajouter_placement(
                ligne, colonne, str(lettre), bool(joker),
                int(valeur) if valeur is not None else 0, int(index),
            )

        if any(p["ligne"] == ligne and p["colonne"] == colonne for p in self._en_attente):
            return {"succes": False, "erreur": "Une lettre est déjà posée ici."}

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

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, le retrait est refusé sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        avant = len(self._en_attente)
        self._en_attente = [
            p for p in self._en_attente
            if not (p["ligne"] == ligne and p["colonne"] == colonne)
        ]
        if len(self._en_attente) != avant:
            self._selection = None
            self._diffuser()
        return {"succes": True}

    def remplacer_ou_retirer_lettre_en_attente(
        self, ligne: Any, colonne: Any
    ) -> dict[str, Any]:
        """Clic sur une case portant une lettre en attente du tour courant — issue #129.

        Point d'entrée unique appelé par la fenêtre plateau au clic sur une case
        qui porte déjà une lettre **en attente** (pas une tuile validée). La
        fenêtre plateau ignore l'état de sélection du chevalet ; c'est donc ici,
        côté Python, que se décide le comportement :

        * **aucune lettre sélectionnée** (``_selection is None``) : simple retrait,
          la lettre redevient disponible au chevalet — comportement historique
          strictement préservé (cas limite 1) ;
        * **une lettre sélectionnée** : la lettre sélectionnée **prend la place**
          de la lettre en attente, laquelle **retourne** au chevalet, en un seul
          geste. Si la lettre sélectionnée est un **joker**, on diffère la pose
          via la modale de choix (``_joker_demande``) exactement comme sur une
          case vide : l'ancienne lettre reste en place jusqu'à la validation du
          choix, et la finalisation la remplacera (annuler la modale ne change
          alors rien).

        Ne concerne jamais une case sans lettre en attente ni une tuile validée
        (le JS n'y route pas ce clic) ; renvoie ``{"succes": True}`` sans effet si
        aucune lettre n'attend sur la case. Réservée au tour du joueur de
        référence (garde :meth:`_refuser_hors_tour`).
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        placement = next(
            (
                p for p in self._en_attente
                if p["ligne"] == ligne and p["colonne"] == colonne
            ),
            None,
        )
        if placement is None:
            # Rien en attente ici : aucun effet (le JS ne devrait pas router ici).
            return {"succes": True}
        # Sans sélection active : on conserve le retrait simple (cas limite 1).
        if self._selection is None:
            return self.retirer_lettre_en_attente(ligne, colonne)
        idx = self._selection
        chevalet = self._partie.joueur_courant().chevalet
        if not (0 <= idx < len(chevalet)):
            return {"succes": False, "erreur": "Lettre sélectionnée invalide."}
        jeton = chevalet[idx]
        if jeton == JOKER:
            # Le remplacement par un joker passe par la modale de choix : on ne
            # retire pas encore l'ancienne lettre (la finalisation le fera), pour
            # qu'un abandon de la modale laisse la case inchangée.
            self._joker_demande = {"ligne": ligne, "colonne": colonne, "index": idx}
            self._diffuser()
            return {
                "succes": True,
                "joker_requis": True,
                "ligne": ligne,
                "colonne": colonne,
                "index": idx,
            }
        # Remplacement direct : l'ancienne lettre retourne au chevalet, la nouvelle
        # prend sa place sur la même case (``_ajouter_placement`` remet la sélection
        # à None et diffuse — une seule opération perçue côté joueur).
        self._en_attente = [p for p in self._en_attente if p is not placement]
        return self._ajouter_placement(
            ligne, colonne, jeton, False, valeur_lettre(jeton), idx
        )

    def annuler_pose(self) -> dict[str, Any]:
        """Abandonne toute la pose en cours (sélection + placements) — issue #90.

        Vide ``_selection`` et ``_en_attente`` (aucune lettre n'est consommée : le
        moteur n'a rien joué) puis diffuse l'état remis à zéro aux deux fenêtres.

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, l'annulation est refusée sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
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
        Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool, "definition":
        [gloses] | None}`` ou, si le brouillon est vide, ``{"succes": False,
        "erreur": <message>}``. La ``definition`` (ODS8 uniquement, issue #124)
        est ``None`` quand le mot est invalide ou absent de l'index — l'UI
        affiche alors « définition indisponible ».

        Restriction à la source active (issue #127) : la définition n'est
        renvoyée que si la partie est jouée avec ``"ods"`` comme source de
        dictionnaire (``config["source_dictionnaire"]``, seule source de vérité
        de la source active — ni ``Partie`` ni ``Dictionnaire`` ne la
        mémorisent). En source ``"hunspell"``, ``definition`` vaut toujours
        ``None``, même pour un mot par ailleurs présent dans l'index ODS8, pour
        rester strictement cohérent avec ce qui valide réellement les coups sur
        le plateau.
        """
        source = charger_config().get("source_dictionnaire", "ods")
        return verifier_mot_dictionnaire(
            self._partie.dictionnaire, lettres, source=source
        )

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

    # ---- Échange partiel (issue #138) --------------------------------- #

    def commencer_echange(self) -> dict[str, Any]:
        """Entre dans le mode de **sélection** pour l'échange partiel (issue #138).

        Point d'entrée du bouton « ♻️ Échanger des lettres… », affiché à la place
        de l'échange complet quand le réglage ``type_echange`` vaut ``"partiel"``.
        Abandonne toute pose en cours (le joueur ne fait pas les deux à la fois),
        vide la sélection d'échange et active :attr:`_mode_echange`, puis diffuse.

        Réservé au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99/#130). Refusé si le réglage n'est pas ``"partiel"``.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if self._type_echange != "partiel":
            return {
                "succes": False,
                "erreur": "L'échange partiel n'est pas activé dans les réglages.",
            }
        self._selection = None
        self._en_attente = []
        self._joker_demande = None
        self._selection_echange = []
        self._mode_echange = True
        self._diffuser()
        return {"succes": True}

    def annuler_echange(self) -> dict[str, Any]:
        """Quitte le mode de sélection d'échange partiel sans rien échanger.

        Vide la sélection d'échange et désactive :attr:`_mode_echange`, puis
        rediffuse. C'est le moyen clair d'annuler une sélection en cours avant de
        la valider (issue #138). Réservé au tour du joueur de référence.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        self._selection_echange = []
        self._mode_echange = False
        self._diffuser()
        return {"succes": True}

    def basculer_echange(self, index: Any) -> dict[str, Any]:
        """Marque/démarque la lettre d'index ``index`` pour l'échange partiel.

        Appelée par la fenêtre chevalet, en mode échange (:attr:`_mode_echange`),
        au clic sur une lettre : un premier clic la marque, un reclic la démarque
        (sélection multiple, distincte de la sélection simple de pose). ``index``
        vise la position de la lettre dans le chevalet du joueur courant (qui est
        le joueur de référence, la garde de tour l'assurant). Diffuse l'état.

        Réservé au tour du joueur de référence (garde :meth:`_refuser_hors_tour`).
        Refusé hors du mode échange ou sur un index invalide.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if not self._mode_echange:
            return {"succes": False, "erreur": "Le mode échange n'est pas actif."}
        if isinstance(index, bool) or not isinstance(index, int):
            return {"succes": False, "erreur": "Index de lettre invalide."}
        if not 0 <= index < len(self._partie.joueur_courant().chevalet):
            return {"succes": False, "erreur": "Index de lettre hors du chevalet."}
        if index in self._selection_echange:
            self._selection_echange.remove(index)
        else:
            self._selection_echange.append(index)
        self._diffuser()
        return {"succes": True, "selection_echange": list(self._selection_echange)}

    def echanger_selection(self, indices: Any = None) -> dict[str, Any]:
        """Échange les lettres sélectionnées et passe le tour (issue #138).

        Point d'entrée du bouton « Échanger la sélection et passer ». Les lettres
        visées sont désignées par leurs ``indices`` dans le chevalet du joueur
        courant ; si ``indices`` vaut ``None`` (appel depuis l'UI), on utilise la
        sélection d'échange courante (:attr:`_selection_echange`). Convertit les
        index en jetons puis délègue à :func:`echanger_jetons`, qui applique
        exactement les mêmes règles que l'échange complet (sac suffisant, remise
        en jeu, tirage de remplacement, passage du tour).

        Une sélection **vide** est refusée (1 à 7 lettres, jamais 0). En cas de
        succès : ``{"succes": True, "etat": <état public>}`` (tour suivant, état
        de pose et sélection d'échange remis à zéro, mode échange quitté). En cas
        d'échec (sac trop pauvre, index invalide, partie terminée, hors tour) :
        ``{"succes": False, "erreur": <message>}`` — l'état n'est pas modifié.

        Réservé au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99/#130) : c'est cette garde qui assure que les index visent bien
        le chevalet du joueur de référence (alors joueur courant).
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if indices is None:
            indices = list(self._selection_echange)
        joueur = self._partie.joueur_courant()
        nb = len(joueur.chevalet)
        if not isinstance(indices, list) or not indices:
            return {"succes": False, "erreur": "Aucune lettre sélectionnée à échanger."}
        vus: set[int] = set()
        for i in indices:
            if (
                isinstance(i, bool)
                or not isinstance(i, int)
                or not 0 <= i < nb
                or i in vus
            ):
                return {"succes": False, "erreur": "Sélection de lettres invalide."}
            vus.add(i)
        jetons = [joueur.chevalet[i] for i in indices]
        nom = joueur.nom
        nb_avant = len(self._partie.historique)
        resultat = echanger_jetons(self._partie, self._id_partie, jetons)
        if resultat.get("succes"):
            journal.info(
                f"Jeu : échange partiel de {len(jetons)} lettre(s) par {nom}."
            )
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._finaliser_si_terminee()
            # Nouveau tirage + tour suivant : on repart d'un état de pose et
            # d'échange vierge, puis on rediffuse les deux fenêtres (issue #90).
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._selection_echange = []
            self._mode_echange = False
            self._diffuser()
        else:
            journal.info(
                f"Jeu : échange partiel refusé pour {nom} — {resultat.get('erreur')}"
            )
        return resultat

    def passer(self) -> dict[str, Any]:
        """Fait **passer** le tour du joueur courant sans rien échanger (issue #132).

        Point d'entrée du bouton « Passer son tour ». Sur le modèle de
        :meth:`echanger_tout`, mais sans toucher au sac : c'est le recours qui
        débloque un joueur humain sac vide (rapport #130), tout en restant un
        droit normal du jeu utilisable à tout moment de son tour. Délègue à
        :func:`passer_tour` (qui appelle
        :meth:`~scrabble.moteur.partie.Partie.passer`).

        En cas de succès : ``{"succes": True, "etat": <état public rafraîchi>}``
        (tour suivant, ou fin de partie par blocage si tous ont passé d'affilée),
        l'état de pose est remis à zéro et rediffusé aux deux fenêtres. Si la
        partie est déjà terminée : ``{"succes": False, "erreur": <message>}`` —
        l'état n'est pas modifié.
        """
        nom = self._partie.joueur_courant().nom
        nb_avant = len(self._partie.historique)
        resultat = passer_tour(self._partie, self._id_partie)
        if resultat.get("succes"):
            journal.info(f"Jeu : {nom} passe son tour.")
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._journaliser_fin_partie()
            self._finaliser_si_terminee()
            # Tour suivant (ou fin de partie) : on repart d'un état de pose vierge
            # et on rediffuse le nouvel état public / privé aux deux fenêtres.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._diffuser()
        else:
            journal.info(f"Jeu : passe refusée pour {nom} — {resultat.get('erreur')}")
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
            # On détruit nous-mêmes les deux fenêtres : on lève donc le garde-fou
            # anti-boucle (issue #94) pour que l'événement ``closing`` déclenché par
            # ces ``destroy()`` (sous GTK, ``destroy`` repasse par ``close_window``)
            # ne relance pas :meth:`_sur_fermeture_native`, qui tenterait de
            # re-détruire l'autre fenêtre — un double ``destroy`` lèverait une
            # exception qui, ici, ferait basculer ``_retour_menu`` à ``False`` et
            # empêcherait la réouverture de l'accueil.
            self._fermeture_en_cours = True
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

    def creer_partie_recommencee(self) -> Partie:
        """Fabrique une nouvelle partie reprenant les joueurs de la partie courante.

        Cœur « moteur/API » de l'action « Recommencer » (issue #142) : réutilise
        les mêmes joueurs (noms, humain/ordinateur, niveaux de difficulté) via
        :func:`~scrabble.moteur.partie.recreer_partie_meme_joueurs`, avec une
        **graine explicite tirée au hasard** (nécessaire au suivi de persistance,
        qui refuse une partie sans graine) et un **nouveau tirage d'ordre**. Le
        dictionnaire et le réglage ``bonus_fin_partie`` sont hérités de la partie
        courante — on ne repasse pas par l'écran de configuration.

        La partie terminée courante n'est pas touchée : elle reste finalisée en
        base (voir :meth:`_finaliser_si_terminee`) et consultable dans
        l'historique. Méthode isolée pour rester testable sans fenêtre.
        """
        graine = random.randint(0, 2**31 - 1)
        return recreer_partie_meme_joueurs(
            self._partie,
            self._partie.dictionnaire,
            graine=graine,
            tirage_ordre=True,
        )

    def recommencer(self) -> dict[str, Any]:
        """Rejoue une nouvelle partie avec les mêmes joueurs (issue #142).

        Troisième action de la modale de fin de partie. Crée une partie neuve
        (:meth:`creer_partie_recommencee`), la déclare en base
        (:func:`~scrabble.persistance.demarrer_suivi`) puis ferme **les deux**
        fenêtres de jeu à la manière de :meth:`retour_menu`. Une fois la boucle
        rendue, :func:`lancer_jeu` relance l'écran de jeu sur cette nouvelle
        partie (drapeau ``_recommencer``).

        En mode démonstration (``_id_partie`` à ``None``), aucune persistance
        n'est déclenchée : la nouvelle partie n'est simplement pas suivie.

        Retourne ``{"succes": True}`` si la fermeture a été demandée, sinon
        ``{"succes": False, "erreur": ...}`` (le JS réactive alors le bouton).
        """
        if self._window_plateau is None and self._window_chevalet is None:
            return {"succes": False, "erreur": "Aucune fenêtre associée."}
        try:
            nouvelle = self.creer_partie_recommencee()
            nouvel_id: int | None = None
            if self._id_partie is not None:
                nouvel_id = demarrer_suivi(nouvelle, self._chemin_persistance)
            journal.info(
                f"Jeu : recommencer une partie avec les mêmes joueurs "
                f"(ancienne #{self._id_partie} → nouvelle #{nouvel_id})."
            )
            self._nouvelle_partie = nouvelle
            self._nouvel_id_partie = nouvel_id
            self._recommencer = True
            # Même garde-fou anti-boucle que ``retour_menu`` : on détruit soi-même
            # les deux fenêtres, on neutralise donc la fermeture croisée native.
            self._fermeture_en_cours = True
            if self._window_chevalet is not None:
                self._window_chevalet.destroy()
            if self._window_plateau is not None:
                self._window_plateau.destroy()
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            # Échec (création ou fermeture) : on n'enchaîne pas de nouvelle partie
            # (les fenêtres restent ouvertes et le JS réactive le bouton).
            self._recommencer = False
            self._nouvelle_partie = None
            self._nouvel_id_partie = None
            return {"succes": False, "erreur": f"Recommencer impossible : {e}"}


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
    # Bascule XWayland avant tout ``webview.start()`` en lancement autonome
    # (``python -m scrabble.ui.jeu``) : voir issue #93. Sans effet si l'accueil
    # l'a déjà fait (idempotente) ou hors session Wayland.
    from scrabble.ui.backend_graphique import configurer_backend_graphique

    configurer_backend_graphique()
    if journal.session_courante() is None:
        journal.demarrer_session()
    journal.info(f"Jeu : écran ouvert (partie #{id_partie}).")
    api = ApiJeu(partie, id_partie)
    retour_menu = False
    recommencer = False
    nouvelle_partie: Partie | None = None
    nouvel_id_partie: int | None = None
    try:
        _lancer_fenetre_jeu(api)
        retour_menu = api._retour_menu
        recommencer = api._recommencer
        nouvelle_partie = api._nouvelle_partie
        nouvel_id_partie = api._nouvel_id_partie
    finally:
        # Cas « retour au menu » ou « recommencer » : la session reste ouverte
        # pour être réutilisée (par l'accueil rouvert, ou par la nouvelle partie
        # enchaînée). Dans tous les autres cas (fermeture normale de la fenêtre,
        # ou exception traversant la boucle), on clôture la session.
        if not retour_menu and not recommencer:
            journal.cloturer_session()
    if retour_menu:
        _rouvrir_accueil(id_partie)
    elif recommencer and nouvelle_partie is not None:
        # Recommencer (issue #142) : on enchaîne directement une nouvelle partie
        # avec les mêmes joueurs, en réutilisant la session de journalisation
        # courante (symétrique du « Retour au menu »). L'écran de jeu s'ouvre à
        # nouveau, directement sur le nouveau tirage.
        lancer_jeu(nouvelle_partie, nouvel_id_partie)


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
# #91/#94, épurées #102, resserrées #104). Depuis l'issue #102 la fenêtre ne
# contient plus que la barre de déplacement fine et le panneau unique des lettres :
# l'en-tête vert (titre « Chevalet de [nom] » + instructions) et l'icône d'aide
# « i » ont été retirés. Les dimensions sont recalculées au plus près du contenu
# réel restant, mesuré en headless (Chromium/Playwright, cf.
# ``scripts/_harness_jeu/mesure_chevalet_104.mjs`` puis ``…_106.mjs`` qui mesure en
# plus la symétrie verticale et le vide à droite). L'issue #102 (620×190) laissait
# encore un espace vide notable à droite et un peu d'air sous la rangée : la marge
# de sécurité prise sur la mesure Chromium (~32 % en largeur, ~26 % en hauteur)
# s'avérait trop généreuse. #104 la ramène à ~15-25 %, plus proche du contenu, tout
# en gardant de quoi absorber l'écart de rendu Chromium ↔ WebKitGTK (viser un peu
# large plutôt que pile-poil, cf. issues #92/#94).
#
# Largeur : la rangée de 9 cases (7 lettres + 2 vides) fait 408 px (40 px/case +
# 6 px de gap) — c'est du pixel FIXE, identique quel que soit le moteur de rendu ;
# avec les paddings (bloc 24 px + fenêtre 28 px) elle réclame 460 px, PLANCHER sous
# lequel la rangée elle-même se comprimerait (mesuré : à 460 px la rangée retombe à
# 406 px). Le titre du panneau (« 🎴 Mes lettres — cliquez… ») fait ~418 px en
# Chromium, soit ~470 px paddings compris : gardé sur une seule ligne au-dessus de
# 470 px, il peut se replier sur 2 lignes en dessous sans casser la mise en page (la
# hauteur ci-dessous le tolère). #104 avait fixé 540 px (~79 px de vide à droite de
# la dernière case) ; #106 resserre à 480 px : le vide tombe à ~19 px tout en gardant
# le titre sur une ligne (480 > 470) et ~20 px de marge sur le plancher de 460 px.
#
# Hauteur : le contenu (barre ~35 px + panneau ~98 px + paddings) descend à ~141 px
# en Chromium sur une ligne de titre, ~166 px si le titre se replie sur 2 lignes. On
# garde 175 px : c'est le plancher qui, avec le recentrage vertical du cadre
# (``justify-content: center`` sur ``.chevalet-fenetre``, issue #106), contient encore
# le cas replié (166 px) sans coupe ni défilement. #106 ne réduit PAS la hauteur :
# l'asymétrie verticale (plus de vert sous le cadre qu'au-dessus) n'était pas un
# problème de taille mais d'alignement — le corps flex absorbait toute la hauteur
# résiduelle en la rejetant en bas. Le recentrage répartit désormais le vert à parts
# égales en haut et en bas (mesuré : gapHaut = gapBas = 21 px à 480×175), quelle que
# soit la hauteur exacte. Non redimensionnable : ces valeurs sont la taille réelle
# utilisée. Des garde-fous de test (``test_largeur_suffisante_pour_le_contenu`` /
# ``test_hauteur_suffisante_pour_le_contenu``) empêchent une régression de repasser
# sous la taille du contenu.
CHEVALET_LARGEUR = 480
CHEVALET_HAUTEUR = 175
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
    nb_ecrans = 0
    try:
        ecrans = webview.screens
        # ``webview.screens`` est un proxy paresseux (proxy_tools) : y toucher avant
        # qu'un backend GUI (GTK/QT) soit chargé lève ``WebViewException``. On lit
        # donc le nombre d'écrans DANS ce try (une seule fois) — l'accès dupliqué et
        # NON gardé qui traînait dans la trace ci-dessous faisait planter le lancement
        # (et 6 tests) dès que le backend n'était pas encore prêt (issue #96).
        nb_ecrans = len(ecrans) if ecrans else 0
        ecran = ecrans[0] if ecrans else None
        larg_ecran = int(getattr(ecran, "width", 0) or 0)
        haut_ecran = int(getattr(ecran, "height", 0) or 0)
    except Exception as e:  # noqa: BLE001 - pas d'écran interrogeable : repli neutre
        journal.erreur("Jeu : lecture de webview.screens impossible.", e)
        larg_ecran = haut_ecran = 0
    # Trace explicite (issue #92) : permet de vérifier après coup ce que
    # ``webview.screens`` a réellement renvoyé au moment de l'appel (0×0 = écran
    # non encore interrogeable, typiquement avant le démarrage de la boucle GUI).
    journal.info(
        f"Jeu : _position_chevalet — écran mesuré {larg_ecran}×{haut_ecran}px "
        f"(nb écrans = {nb_ecrans})."
    )
    if larg_ecran <= 0 or haut_ecran <= 0:
        return 100, 100
    x = max(0, (larg_ecran - largeur) // 2)
    y = max(0, haut_ecran - hauteur - CHEVALET_MARGE_BAS)
    return x, y


def _dimensions_ecran() -> tuple[int, int]:
    """Dimensions ``(largeur, hauteur)`` du premier écran, ou ``(0, 0)`` si illisible.

    Lit ``webview.screens`` comme :func:`_position_chevalet` (même moteur, même
    contrainte : fiable seulement une fois la boucle GUI démarrée sous WebKitGTK,
    issue #91). Ne lève jamais : en l'absence d'écran interrogeable, retourne
    ``(0, 0)`` — le repli est laissé à l'appelant.
    """
    try:
        ecrans = webview.screens
        ecran = ecrans[0] if ecrans else None
        larg = int(getattr(ecran, "width", 0) or 0)
        haut = int(getattr(ecran, "height", 0) or 0)
    except Exception as e:  # noqa: BLE001 - pas d'écran interrogeable
        journal.erreur("Jeu : lecture des dimensions d'écran impossible.", e)
        return 0, 0
    return larg, haut


def _position_chevalet_memorisee(
    largeur: int = CHEVALET_LARGEUR, hauteur: int = CHEVALET_HAUTEUR
) -> tuple[int, int] | None:
    """Position mémorisée du chevalet si elle tient dans l'écran actuel (issue #135).

    Lit le réglage ``position_chevalet`` (via :mod:`scrabble.reglages`). Retourne
    ``(x, y)`` uniquement si une position est enregistrée **et** que la fenêtre
    (``largeur``×``hauteur`` posée en ``(x, y)``) tient entièrement dans le premier
    écran mesuré via ``webview.screens`` — le même contrôle de limites que celui
    servant au calcul bas-centre par défaut. Sinon retourne ``None`` (l'appelant
    retombe alors sur :func:`_position_chevalet`) :

    * réglage absent (``None``) ou illisible ;
    * écran non mesurable (dimensions ``0`` — typiquement avant le démarrage de la
      boucle GUI) : on ne peut pas garantir la validité, on préfère le calcul par
      défaut sans toucher au réglage (il peut rester bon) ;
    * position hors des limites de l'écran actuel (résolution/moniteur différent
      entre deux sessions) : le réglage périmé est alors **réinitialisé** à
      ``None`` plutôt que laissé invalide indéfiniment.
    """
    try:
        pos = lire_reglage("position_chevalet")
    except Exception as e:  # noqa: BLE001 - réglage illisible : repli par défaut
        journal.erreur("Jeu : lecture du réglage position_chevalet impossible.", e)
        return None
    if not isinstance(pos, dict):
        return None  # aucune position mémorisée (défaut None)
    x, y = pos.get("x"), pos.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return None
    larg_ecran, haut_ecran = _dimensions_ecran()
    if larg_ecran <= 0 or haut_ecran <= 0:
        # Écran non mesurable : on ne réinitialise pas (position peut-être encore
        # valide), mais on laisse le calcul par défaut décider pour cet appel.
        journal.info(
            "Jeu : position chevalet mémorisée non vérifiable (écran non mesuré) "
            "— repli sur le calcul par défaut."
        )
        return None
    dans_ecran = (0 <= x <= larg_ecran - largeur) and (0 <= y <= haut_ecran - hauteur)
    if not dans_ecran:
        journal.info(
            f"Jeu : position chevalet mémorisée ({x}, {y}) hors de l'écran actuel "
            f"{larg_ecran}×{haut_ecran}px — réinitialisation et repli bas-centre."
        )
        try:
            modifier_reglage("position_chevalet", None)
        except Exception as e:  # noqa: BLE001 - réinitialisation ratée : sans gravité
            journal.erreur(
                "Jeu : réinitialisation de position_chevalet impossible.", e
            )
        return None
    journal.info(f"Jeu : position chevalet mémorisée réutilisée ({x}, {y}).")
    return x, y


def _lancer_fenetre_jeu(api: "ApiJeu") -> None:
    """Crée les **deux** fenêtres de jeu (plateau + chevalet) et démarre la boucle.

    Séparation plateau/chevalet en deux fenêtres pywebview (issue #90) :

    * Fenêtre **plateau** : maximisée (``maximized=True``), sans ``width``/
      ``height`` fixes, afin de s'adapter à n'importe quelle résolution logique
      (le CSS contraint désormais le plateau par la hauteur disponible pour éviter
      tout défilement). Elle porte le plateau, les panneaux joueurs, la barre du
      sac/historique, « Faire jouer l'ordinateur » et la vérification dictionnaire.
    * Fenêtre **chevalet** : flottante ``frameless=True``, ``resizable=False`` et
      ``easy_drag=False``. Elle n'est plus « toujours au-dessus » globalement
      (``on_top`` retiré, issue #105) : elle est liée au plateau par une relation
      transiente (:func:`_lier_chevalet_au_plateau`). Le déplacement passe
      par un glisser-déposer **applicatif** sur la barre du haut (``.barre-drag`` →
      :meth:`ApiJeu.deplacer_chevalet`) : sous WebKitGTK, ``.pywebview-drag-region``
      n'est pas géré (le backend GTK ne câble le drag d'une fenêtre ``frameless``
      que via ``easy_drag=True``, qui déplacerait la fenêtre au moindre glissé, y
      compris pendant un clic-clic de pose — issue #91 point 2). Taille resserrée
      au panneau (``CHEVALET_LARGEUR``×``CHEVALET_HAUTEUR``, 480×175 depuis #106),
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
        # Fond vert dès le mappage de la fenêtre (issue #113) : évite le blanc
        # par défaut de pywebview pendant le chargement HTML/CSS.
        background_color=TAPIS_VERT,
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
        # Plus d'``on_top`` global (issue #105) : le chevalet est lié au plateau
        # par une relation transiente (:func:`_lier_chevalet_au_plateau`), posée
        # une fois les deux fenêtres affichées — il reste au-dessus du plateau
        # sans être forcé au-dessus de toutes les applications du système.
        resizable=False,    # non redimensionnable par erreur
        easy_drag=False,    # pas de drag « corps entier » : drag applicatif ciblé
        # Fond vert dès le mappage de la fenêtre (issue #113), comme le plateau.
        background_color=TAPIS_VERT,
    )
    api.set_windows(window_plateau, window_chevalet)
    # Fermeture croisée par la croix (issue #94) : fermer nativement l'une des deux
    # fenêtres détruit l'autre et quitte l'application (plus de fenêtre orpheline).
    api.installer_fermeture_croisee()
    # Finalisation après démarrage de la boucle (issues #91 point 1 et #95) : c'est
    # seulement une fois ``webview.start()`` en cours et les fenêtres affichées que
    # (a) ``webview.screens`` renvoie des dimensions fiables sous WebKitGTK et que
    # (b) une (ré)affirmation de l'état maximisé du plateau est honorée par le WM.
    #
    # Point B de l'issue #96 (fenêtre plateau ouverte « réduite ») — confirmation par
    # lecture du code de pywebview installé (``platforms/gtk.py``) : à la création,
    # ``BrowserView.__init__`` fait ``self.window.maximize()`` AVANT ``browser.show()``
    # (la fenêtre n'est donc pas encore mappée), et pour le plateau sans ``width``/
    # ``height`` la taille initiale non maximisée est le défaut ~800×600. Sous XWayland
    # (backend forcé #93), cette maximisation pré-mappage est un no-op → fenêtre petite.
    # La création du chevalet juste après (frameless, lié au plateau par transient
    # depuis #105) est
    # INDÉPENDANTE : rien dans le backend ne lie l'état maximisé du plateau à la seconde
    # fenêtre. Le correctif (:func:`_maximiser_plateau`) est donc appliqué ici pour les
    # DEUX chemins de lancement — autonome (``python -m scrabble.ui.jeu``) et normal
    # (accueil → :func:`lancer_jeu`) — puisque tous deux passent par cette fonction et
    # basculent XWayland avant le premier ``webview.start()`` : le chemin normal est
    # affecté à l'identique, et corrigé à l'identique.
    webview.start(_finaliser_fenetres, (window_plateau, window_chevalet))


def _finaliser_fenetres(
    window_plateau: "webview.Window", window_chevalet: "webview.Window"
) -> None:
    """Finalise l'état des deux fenêtres une fois la boucle GUI démarrée (issue #95).

    Exécuté par ``webview.start(func, …)`` dans un fil dédié, **après** le démarrage
    de la boucle. On y enchaîne deux corrections qui exigent toutes deux que la
    fenêtre concernée soit déjà affichée par le backend :

    1. **Maximisation du plateau** (:func:`_maximiser_plateau`) : ``maximized=True``
       demandé à la création n'est pas honoré sous XWayland (cf. cette fonction).
    2. **Repositionnement du chevalet** (:func:`_repositionner_chevalet`) : la
       position bas-centre n'est calculable qu'une fois ``webview.screens`` fiable
       (issue #91 point 1).
    3. **Liaison chevalet↔plateau** (:func:`_lier_chevalet_au_plateau`) : le
       chevalet est déclaré fenêtre transiente du plateau (``set_transient_for``,
       issue #105), ce qui remplace l'ancien « always-on-top » global.
    """
    _maximiser_plateau(window_plateau)
    _repositionner_chevalet(window_chevalet)
    _lier_chevalet_au_plateau(window_plateau, window_chevalet)


def _lier_chevalet_au_plateau(
    window_plateau: "webview.Window", window_chevalet: "webview.Window"
) -> None:
    """Lie la fenêtre chevalet au plateau via ``set_transient_for`` (issue #105).

    Remplace l'ancien « always-on-top » global (``on_top`` / ``set_keep_above``,
    issues #91/#93, ré-affirmé après chaque interaction) par une relation
    **transiente** : le chevalet est déclaré fenêtre transitoire (au sens des
    boîtes de dialogue) du plateau. Le gestionnaire de fenêtres empile alors les
    deux ensemble — le chevalet reste au-dessus du plateau, mais passe **sous**
    une autre application lorsque celle-ci prend le focus (contrairement à
    ``on_top``, qui le forçait au-dessus de tout le système).

    Les deux fenêtres doivent être affichées (``shown``) avant l'appel : sous GTK,
    ``set_transient_for`` opère sur les ``Gtk.Window`` natives, disponibles une
    fois les fenêtres mappées. On réutilise donc :func:`_attendre_fenetre_affichee`
    (déjà en place pour la maximisation/le repositionnement). En renfort optionnel
    (évoqué par #103), on pose aussi l'indice ``Gdk.WindowTypeHint.UTILITY``, qui
    invite le WM à traiter le chevalet comme une fenêtre utilitaire et non comme
    une fenêtre principale (importé comme dans :func:`_zone_travail_ecran`).

    Tolère les fenêtres factices des tests, dépourvues d'attribut ``native``
    (garde ``getattr``) : la liaison est alors simplement ignorée. Toute erreur est
    journalisée sans interrompre le jeu.

    Point d'incertitude (issue #103/#105) : la fiabilité réelle du ré-empilement
    sous Mutter/XWayland ne peut être garantie qu'après une vérification visuelle —
    ce correctif n'est pas à considérer comme définitivement validé tant qu'Alain
    n'a pas confirmé en pratique que le chevalet reste bien au-dessus du plateau
    (et seulement du plateau) après ce changement.
    """
    _attendre_fenetre_affichee(window_plateau, "plateau")
    _attendre_fenetre_affichee(window_chevalet, "chevalet")

    natif_plateau = getattr(window_plateau, "native", None)
    natif_chevalet = getattr(window_chevalet, "native", None)
    if natif_plateau is None or natif_chevalet is None:
        journal.info(
            "Jeu : liaison chevalet↔plateau ignorée — fenêtre native indisponible "
            "(backend non-GTK ou fenêtre factice de test)."
        )
        return

    try:
        natif_chevalet.set_transient_for(natif_plateau)
        journal.info(
            "Jeu : chevalet lié au plateau via set_transient_for (issue #105) ; "
            "fiabilité du ré-empilement à confirmer visuellement."
        )
    except Exception as e:  # noqa: BLE001 - une liaison ratée ne bloque pas le jeu
        journal.erreur("Jeu : liaison transiente chevalet↔plateau impossible.", e)

    # Renfort optionnel (#103) : indice UTILITY au gestionnaire de fenêtres. GDK est
    # importé à la demande, comme dans _zone_travail_ecran ; son absence (tests,
    # backend non-GTK) n'est pas bloquante.
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        natif_chevalet.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        journal.info("Jeu : indice type_hint UTILITY posé sur le chevalet (issue #105).")
    except Exception as e:  # noqa: BLE001 - renfort optionnel : l'absence de GDK n'est pas bloquante
        journal.info(
            f"Jeu : indice type_hint UTILITY non posé sur le chevalet ({e!r}) — "
            "renfort optionnel ignoré."
        )


def _zone_travail_ecran() -> tuple[int, int, int, int] | None:
    """Zone de travail (x, y, largeur, hauteur) du moniteur principal — issue #95.

    Surface d'écran réellement **utilisable**, panneaux et barres système EXCLUS
    (EWMH ``_NET_WORKAREA``) : c'est la cible d'une vraie maximisation. Lue via
    **GDK**, le même moteur que ``webview.screens`` (déjà employé pour placer le
    chevalet, issue #91). Sur cette machine, GDK renvoie p. ex. ``(66, 32, 1294,
    736)`` sous un écran 1360×768 avec dock latéral + barre haute.

    Replis successifs si GDK est indisponible (tests, backend non-GTK) : géométrie
    **plein écran** de ``webview.screens[0]`` (peut chevaucher un panneau, mais mieux
    qu'une fenêtre minuscule), puis ``None`` si rien n'est interrogeable.
    """
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or Gdk.Display.get_monitor(display, 0)
        wa = monitor.get_workarea()
        return int(wa.x), int(wa.y), int(wa.width), int(wa.height)
    except Exception as e:  # noqa: BLE001 - GDK indisponible : on tente un repli
        journal.info(
            f"Jeu : zone de travail GDK indisponible ({e!r}) — repli sur "
            "webview.screens."
        )
    try:
        ecrans = webview.screens
        ecran = ecrans[0] if ecrans else None
        if ecran is not None:
            return int(ecran.x), int(ecran.y), int(ecran.width), int(ecran.height)
    except Exception as e:  # noqa: BLE001 - aucun écran interrogeable
        journal.info(f"Jeu : webview.screens illisible pour la zone de travail ({e!r}).")
    return None


def _maximiser_plateau(window_plateau: "webview.Window") -> None:
    """Déploie la fenêtre plateau en plein écran utile après démarrage (issue #95).

    Cause racine (issue #95 point B) : ``maximized=True`` à la création se traduit,
    côté backend GTK, par un ``Gtk.Window.maximize()`` émis **avant** que la fenêtre
    soit mappée. Sous **XWayland / mutter** (backend forcé par l'issue #93), cette
    requête est silencieusement **ignorée** — et pas seulement avant l'affichage :
    vérifié dans cet environnement, ``Gtk.Window.maximize()`` est un **no-op** même
    après ``shown``, y compris pour une fenêtre GTK « nue » hors pywebview
    (``_NET_WM_STATE`` reste vide). La fenêtre s'ouvre donc à sa taille par défaut
    (~800×600), ce qui se lit comme une fenêtre « réduite » / non déployée.

    Contournement retenu, dans la lignée de l'issue #93 (``move()`` fiable une fois
    passé sous XWayland) : une fois la boucle démarrée et la fenêtre affichée, on
    (1) émet tout de même la demande native ``maximize()`` — honorée par les
    gestionnaires de fenêtres coopératifs — puis (2) on **force** la fenêtre à
    remplir la :func:`zone de travail <_zone_travail_ecran>` par un ``resize`` +
    ``move`` explicites, honorés sous XWayland là où la maximisation ne l'est pas.
    Résultat : plateau déployé sur tout l'espace utile, quel que soit le WM.

    Robuste aux fenêtres factices des tests : ``shown`` / ``restore`` / ``maximize``
    / ``resize`` / ``move`` absents sont simplement ignorés, chaque étape étant
    indépendante.
    """
    # Comme pour le chevalet (#92), n'agir qu'une fois la fenêtre réellement affichée :
    # une requête émise avant que le backend l'ait mappée peut être ignorée.
    _attendre_fenetre_affichee(window_plateau, "plateau")
    # Symptôme signalé (#95 point B) : la fenêtre s'ouvre « réduite dans la barre des
    # tâches ». Si elle est iconifiée, ni ``resize`` ni ``move`` ne la ramènent à
    # l'écran — on la dé-iconifie d'abord (``restore`` = deiconify + present côté GTK).
    restaurer = getattr(window_plateau, "restore", None)
    if callable(restaurer):
        try:
            restaurer()
        except Exception as e:  # noqa: BLE001 - une restauration ratée ne bloque pas le jeu
            journal.erreur("Jeu : dé-iconification du plateau impossible.", e)
    maximiser = getattr(window_plateau, "maximize", None)
    if callable(maximiser):
        try:
            maximiser()
        except Exception as e:  # noqa: BLE001 - échec sans conséquence : le resize suit
            journal.erreur("Jeu : demande native de maximisation du plateau impossible.", e)

    zone = _zone_travail_ecran()
    if zone is None:
        journal.info(
            "Jeu : zone de travail inconnue — maximisation limitée à la demande "
            "native (issue #95 point B)."
        )
        return
    x, y, largeur, hauteur = zone
    redimensionner = getattr(window_plateau, "resize", None)
    deplacer = getattr(window_plateau, "move", None)
    try:
        if callable(redimensionner):
            redimensionner(largeur, hauteur)
        if callable(deplacer):
            deplacer(x, y)
        journal.info(
            f"Jeu : plateau déployé sur la zone de travail {largeur}×{hauteur} en "
            f"({x}, {y}) — contournement XWayland de la maximisation (issue #95 point B)."
        )
    except Exception as e:  # noqa: BLE001 - un déploiement raté ne bloque pas le jeu
        journal.erreur("Jeu : déploiement plein écran du plateau impossible.", e)


def _repositionner_chevalet(window_chevalet: "webview.Window") -> None:
    """Replace la fenêtre chevalet en bas-centre une fois la boucle GUI démarrée.

    Exécuté par ``webview.start(func, …)`` dans un fil dédié, **après** le démarrage
    de la boucle : à ce stade seulement ``webview.screens`` renvoie sous WebKitGTK
    les dimensions réelles de l'écran (issue #91 point 1). On recalcule donc la
    position bas-centre (:func:`_position_chevalet`) et on déplace la fenêtre. Toute
    erreur est journalisée sans interrompre le jeu (la position initiale, au pire
    ``(100, 100)``, reste alors en place).
    """
    journal.info(
        "Jeu : _repositionner_chevalet atteint (boucle GUI démarrée, "
        "callback webview.start exécuté)."
    )
    try:
        # Sous WebKitGTK, le fil de ``webview.start`` démarre dès l'entrée dans la
        # boucle GUI, parfois AVANT que la fenêtre chevalet soit réellement mappée
        # à l'écran. Un ``move()`` émis trop tôt peut être ignoré par le
        # gestionnaire de fenêtres. On attend donc explicitement l'événement
        # ``shown`` de la fenêtre avant de la déplacer.
        #
        # NB (issue #93) : la cause racine de l'ouverture en haut à gauche n'était
        # pas ce timing mais le backend Wayland natif, où ``move()`` est purement
        # ignoré et ``window.x``/``window.y`` renvoient (0, 0). Cette fonction ne
        # produit un repositionnement effectif qu'une fois l'application basculée
        # sur XWayland (cf. :func:`scrabble.ui.backend_graphique.
        # configurer_backend_graphique`, appelée au lancement) ; l'attente de
        # ``shown`` reste une précaution utile sous X11.
        _attendre_fenetre_affichee(window_chevalet)
        # Priorité à la dernière position mémorisée si elle tient dans l'écran
        # actuel (issue #135) ; sinon, calcul bas-centre par défaut (issue #90).
        memorisee = _position_chevalet_memorisee()
        if memorisee is not None:
            x, y = memorisee
            journal.info(
                f"Jeu : repositionnement chevalet — position mémorisée ({x}, {y})."
            )
        else:
            x, y = _position_chevalet()
            journal.info(
                f"Jeu : repositionnement chevalet — cible calculée ({x}, {y})."
            )
        window_chevalet.move(x, y)
        # Relire la position réellement prise par la fenêtre après le move : c'est
        # la preuve, dans le log, que le déplacement a bien été honoré par le WM
        # (ou, sinon, qu'il s'agit d'une limite backend/WM — voir issue #92).
        pos_reelle = _lire_position_fenetre(window_chevalet)
        journal.info(
            f"Jeu : window.move({x}, {y}) exécuté ; position lue après move = "
            f"{pos_reelle}."
        )
    except Exception as e:  # noqa: BLE001 - un repositionnement raté ne bloque pas le jeu
        journal.erreur("Jeu : repositionnement de la fenêtre chevalet impossible.", e)


def _attendre_fenetre_affichee(
    window: "webview.Window", nom: str = "chevalet", timeout: float = 5.0
) -> None:
    """Attend l'événement ``shown`` de ``window`` (au plus ``timeout`` s) — issue #92.

    ``webview.Window.events.shown`` est un événement pywebview signalé une fois la
    fenêtre affichée par le backend. On l'attend avant tout ``move``/``resize``/
    ``maximize`` pour éviter une requête ignorée (fenêtre pas encore mappée sous
    WebKitGTK — cf. issues #92 pour le chevalet et #95 pour la maximisation du
    plateau). ``nom`` sert uniquement aux traces. Tolère l'absence d'attribut
    ``events`` (backends/fenêtres factices des tests) : dans ce cas on n'attend pas.
    Toute erreur est journalisée sans interrompre le jeu.
    """
    evenements = getattr(window, "events", None)
    shown = getattr(evenements, "shown", None)
    attendre = getattr(shown, "wait", None)
    if attendre is None:
        journal.info(
            f"Jeu : événement 'shown' indisponible ({nom}) — poursuite immédiate."
        )
        return
    try:
        signale = attendre(timeout)
        journal.info(
            f"Jeu : attente de l'affichage de la fenêtre {nom} — shown={signale!r}."
        )
    except Exception as e:  # noqa: BLE001 - une attente ratée ne bloque pas le jeu
        journal.erreur(
            f"Jeu : attente de l'affichage de la fenêtre {nom} impossible.", e
        )


def _lire_position_fenetre(window: "webview.Window") -> str:
    """Position ``(x, y)`` lue sur ``window`` sous forme lisible pour le journal."""
    try:
        return f"({int(window.x)}, {int(window.y)})"
    except Exception:  # noqa: BLE001 - position indisponible : trace neutre
        return "(indisponible)"


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
#: volée) ; ``None`` ⇒ passe ou échange, sans détail. La liste compte 12 entrées,
#: volontairement plus de 8, pour vérifier visuellement le compteur « (N) » et le
#: fait que l'encart montre désormais TOUT l'historique (issue #144), scrollable,
#: la plus récente en haut.
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
