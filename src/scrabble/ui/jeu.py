"""Écran de jeu : affichage du plateau et du chevalet (pywebview).

Première brique de l'écran de jeu (suite de l'écran d'accueil, issue #27).
Cet écran est **en lecture seule** : il affiche le plateau, les tuiles déjà
posées, les scores, le joueur courant et le nombre de jetons restants dans le
sac. Aucune pose de mot n'est encore possible ici (ce sera l'étape suivante).

Confidentialité du chevalet
---------------------------
Le panneau du bas suit le **joueur humain de référence** — le premier joueur
humain de la partie (voir :func:`index_humain_reference`). Depuis l'issue #99,
ses lettres sont **toujours** exposées au panneau du chevalet (zone C intégrée à
``jeu.html`` depuis l'issue #187 ; panneau toujours visible et réarrangeable,
comme un vrai chevalet physique), y compris hors de son tour ; seule la pose
réelle sur le plateau reste réservée à son tour (garde
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
import threading
from pathlib import Path
from typing import Any

import webview

from scrabble import journal
from scrabble.config import AVATARS_DISPONIBLES, THEMES_PLATEAU, charger_config
from scrabble.dictionnaire.dictionnaire import (
    CHEMIN_DEFINITIONS,
    Trie,
    definition_mot,
    normaliser_mot,
)
from scrabble.moteur.ia import Niveau
from scrabble.moteur.ordre import determiner_ordre_jeu
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
from scrabble.persistance.stockage import supprimer_partie
from scrabble.moteur.validation import CoupInvalide, DictionnaireMots, valider_coup
from scrabble.regles.lettres import JOKER, valeur_lettre
from scrabble.regles.plateau import TAILLE, type_case
from scrabble.ui import TAPIS_VERT
from scrabble.ui.api_diffusion import MixinDiffusion
from scrabble.ui.api_echange import MixinEchange
from scrabble.ui.api_pose import MixinPose
from scrabble.ui.api_tirage_ordre import MixinTirageOrdre
from scrabble.ui.api_tour_fin_partie import MixinTourEtFinPartie

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


# Slots attribués aux autres joueurs, indexés par leur rang *relatif* au joueur
# humain de référence dans l'ordre de jeu (issues #122 puis #195). La clé est
# l'effectif total ; la valeur donne, pour le 1er, 2e, 3e joueur *après* la
# référence dans l'ordre de jeu, le slot à occuper dans la zone B de la marge
# gauche.
#
# Depuis la refonte en 4 zones (#186), les fiches ne sont plus disposées
# spatialement autour du plateau : elles sont EMPILÉES verticalement dans la
# marge gauche, dans l'ordre DOM des slots — de haut en bas : ``haut`` →
# ``gauche`` → ``droite`` → ``bas`` (voir ``jeu.html``/``jeu.css``, ``.slot`` et
# ``.slot:empty { display: none }`` qui replie les slots inutilisés). Les noms de
# slots sont donc devenus de simples repères de RANG vertical (« 1er, 2e, 3e slot
# à partir du haut »), l'ancienne sémantique spatiale « côté du plateau » étant
# obsolète.
#
# On veut que la lecture de haut en bas suive l'ORDRE DE JEU : le joueur qui joue
# juste après l'humain de référence en haut, puis les suivants dans l'ordre, la
# référence restant toujours en bas (slot ``bas``, comportement acquis #33/#99).
# On mappe donc le rang relatif k directement sur les slots du haut vers le bas :
# k=1 → ``haut``, k=2 → ``gauche``, k=3 → ``droite`` ; la référence occupe
# ``bas``.
SEQUENCES_POSITIONS = {
    2: ("haut",),
    3: ("haut", "gauche"),
    4: ("haut", "gauche", "droite"),
}


def index_humain_reference(joueurs: list[Joueur]) -> int:
    """Index du **joueur humain de référence** : le premier joueur ``humain``.

    Source de vérité unique du « joueur humain de référence » (issue #99) — celui
    dont le panneau du bas (chevalet) est toujours visible et réarrangeable, y
    compris hors de son tour, et dont on expose les lettres au panneau chevalet.
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
    """Slot vertical de chaque joueur dans la marge gauche (index → slot).

    Renvoie une liste parallèle à ``joueurs`` où l'élément ``i`` est le slot
    (``"bas"``, ``"haut"``, ``"gauche"`` ou ``"droite"``) assigné au joueur
    d'index ``i``. Depuis la refonte en 4 zones (#186) ces noms ne désignent plus
    un côté du plateau mais un RANG dans l'empilement vertical de la zone B (de
    haut en bas : ``haut`` → ``gauche`` → ``droite`` → ``bas`` ; voir
    :data:`SEQUENCES_POSITIONS`). Règle (issues #33, #122 puis #195), avec une
    seule source de vérité côté Python :

    * Le **joueur humain de référence** — le premier joueur ``humain`` de la
      liste ``joueurs`` — est toujours en ``"bas"`` (dernière fiche, en bas de la
      pile, face à l'écran). S'il n'y a aucun humain (cas théorique / test), le
      premier joueur tient ce rôle.
    * Tous les autres joueurs (humains et ordinateurs confondus) s'empilent
      **dans l'ordre de jeu**, du haut vers le bas, selon leur rang *relatif* à
      la référence : le joueur qui joue juste après la référence occupe la fiche
      du haut, le suivant celle d'en dessous, et ainsi de suite jusqu'à revenir
      à la référence en bas. L'ordre de jeu étant déjà encodé dans l'ordre de la
      liste ``joueurs`` (le tirage d'ordre l'a réordonnée), la lecture de haut en
      bas suit l'ordre de jeu réel — y compris quand l'humain n'est pas le
      premier à jouer.

    Cas particuliers : liste vide → ``[]`` ; un seul joueur → ``["bas"]`` (aucune
    autre fiche).
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
    rectangles grisés sans rien dévoiler. ``position`` est le slot d'empilement
    vertical assigné au joueur (voir :func:`calculer_positions`) : l'UI place la
    fiche du joueur dans ce slot (une seule source de vérité, calculée côté
    Python), la lecture de haut en bas suivant l'ordre de jeu (issue #195).
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
      « attente » (message d'attente + bouton « ▶ Jouer » dans la fiche de
      l'ordinateur courant, issue #149).

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
# Tirage de l'ordre de jeu (logique non-UI) — migré de ApiAccueil (issue #170)
# --------------------------------------------------------------------------- #
# Le tirage de l'ordre de jeu (« Chaque joueur a tiré une lettre ») était
# autrefois calculé et affiché DANS la fenêtre d'accueil (issues #54/#61), puis
# celle-ci se fermait avant l'ouverture séparée de la fenêtre Jeu — d'où une
# transition entre deux fenêtres. Depuis l'issue #170, le tirage est affiché
# « à la place » du plateau dans la fenêtre Jeu elle-même ; la reconstitution de
# son détail vit donc désormais ici, à côté de l'API qui l'expose au JS.


def detail_tirage_ordre(
    noms_creation: list[str],
    graine: int | None,
    noms_humains: "set[str] | list[str] | None" = None,
) -> dict[str, Any]:
    """Reconstitue le détail du tirage d'ordre pour affichage côté JS.

    ``creer_partie(tirage_ordre=True)`` réordonne bien les joueurs mais ne
    renvoie pas le détail du tirage. On le rejoue ici avec **la même graine**
    (``random.Random(graine)``) : :func:`~scrabble.moteur.ordre.determiner_ordre_jeu`
    ne dépend que du nombre de joueurs et de la graine, le résultat est donc
    identique à celui appliqué à la partie (l'ordre reproduit exactement
    ``partie.joueurs``).

    ``noms_creation`` est la liste des noms dans l'ordre de création (humains
    puis ordinateurs), qui est l'ordre d'origine sur lequel raisonne
    :class:`~scrabble.moteur.ordre.ResultatTirageOrdre` (``lettres[i]``
    correspond au joueur ``i`` de cette liste ; ``ordre`` en donne les indices
    rangés dans l'ordre de jeu).

    ``noms_humains`` (optionnel) est l'ensemble des noms de joueurs humains :
    chaque tirage porte alors un booléen ``humain`` pour que le JS remplace,
    côté joueur humain, la révélation automatique par une interaction « tirer sa
    lettre » (issue #61). Absent, tous les tirages sont considérés non humains.

    Retourne
    ``{"tirages": [{"nom", "lettre", "humain"}, ...], "ordre": [nom, ...]}``.
    """
    humains = set(noms_humains or ())
    resultat = determiner_ordre_jeu(noms_creation, random.Random(graine))
    tirages = [
        {
            "nom": noms_creation[i],
            "lettre": resultat.lettres[i],
            "humain": noms_creation[i] in humains,
        }
        for i in range(len(noms_creation))
    ]
    ordre = [noms_creation[i] for i in resultat.ordre]
    return {"tirages": tirages, "ordre": ordre}


# --------------------------------------------------------------------------- #
# API Python exposée au JavaScript
# --------------------------------------------------------------------------- #


class ApiJeu(MixinDiffusion, MixinTirageOrdre, MixinTourEtFinPartie, MixinPose, MixinEchange):
    """API Python exposée au JavaScript de l'écran de jeu (issue #90).

    Depuis l'issue #187 (migration du chevalet en zone C) puis l'issue #193
    (nettoyage du modèle de fenêtres), **une seule** fenêtre pywebview porte
    tout l'écran de jeu (``jeu.html`` : plateau + panneau chevalet intégré). Il
    n'y a plus de fenêtre chevalet compagnon flottante. L'API respecte la règle
    de confidentialité : la charge ``appliquerEtatPlateau`` est **publique**
    (jamais les lettres du chevalet, issues #33/#35), tandis que la charge
    ``appliquerEtatChevalet`` contient les lettres privées du **seul** joueur
    humain de référence — toutes deux poussées à cette même fenêtre.

    Source de vérité de l'état de pose (option 1 du rapport #89, §2.2) :
    ``ApiJeu`` centralise ``_selection`` (index de la lettre sélectionnée dans
    le chevalet) et ``_en_attente`` (liste des placements en attente). La
    fenêtre n'est qu'une vue : elle lit/écrit cet état via les méthodes
    exposées, et toute mutation est rediffusée par :meth:`_diffuser`.

    Instanciation différée et réutilisation (issue #179) : dans le modèle
    mono-fenêtre, une **même** instance d'``ApiJeu`` sert plusieurs parties
    successives (la fenêtre physique est réutilisée via ``load_url`` au lieu
    d'être recréée). ``partie``/``id_partie``/``infos_tirage`` sont donc
    **optionnels** au constructeur : on peut créer une instance « vide » puis y
    charger une partie après coup via :meth:`charger_partie`, qui remet à zéro
    la totalité de l'état interne. **Contrat** : tant qu'aucune partie n'est
    chargée (``self._partie is None``), aucune méthode de jeu ne doit être
    appelée. Le routeur d'API (``ApiRouteur``, issue #179) garantit ce contrat
    en ne routant vers cette sous-API que lorsque la vue « jeu » est active,
    c'est-à-dire après un :meth:`charger_partie`. Par prudence, les getters
    d'état exposés au JS (``obtenir_etat``, ``obtenir_etat_plateau``,
    ``obtenir_etat_chevalet``, ``obtenir_chevalet``) renvoient une charge d'erreur
    plutôt que de déréférencer un ``self._partie`` à ``None`` ; les autres
    méthodes de jeu (pose, échange, tour…) ne sont, elles, pas gardées et
    présupposent une partie chargée.
    """

    def __init__(
        self,
        partie: Partie | None = None,
        id_partie: int | None = None,
        chemin_persistance: Any = CHEMIN_DEFAUT,
        infos_tirage: dict[str, Any] | None = None,
    ) -> None:
        # Base où sont persistées les actions (issue #81). Par défaut la base de
        # l'application ; injectable pour les tests (base temporaire). Réglage
        # d'infrastructure indépendant d'une partie : posé une seule fois ici,
        # jamais remis à zéro par :meth:`charger_partie`.
        self._chemin_persistance = chemin_persistance
        # Fenêtre unique de l'écran de jeu (``jeu.html`` : plateau + chevalet
        # intégré en zone C depuis #187 ; plus de fenêtre chevalet compagnon
        # depuis #193). Dans le modèle mono-fenêtre (issue #179), la fenêtre
        # physique PERSISTE d'une partie à l'autre : :meth:`charger_partie` ne la
        # touche donc pas (elle ne fait pas partie de l'état « par partie » remis
        # à zéro).
        self._window_plateau: webview.Window | None = None
        # Tout l'état interne lié à UNE partie est posé par un point unique de
        # remise à zéro (issue #179) : une même instance servant plusieurs parties
        # successives dans le modèle mono-fenêtre, ce point garantit qu'aucun
        # résidu (sélection, placements, drapeaux de fin…) d'une partie précédente
        # ne fuite dans la suivante. Voir :meth:`_reinitialiser_etat` pour le
        # détail de chaque champ.
        self._reinitialiser_etat()
        # Chargement immédiat si une partie est fournie (chemin historique
        # accueil → jeu, tests). Sinon l'instance reste « vide » jusqu'à un appel
        # différé à :meth:`charger_partie` (nouveau modèle mono-fenêtre) : aucune
        # méthode de jeu ne doit être appelée avant ce chargement.
        if partie is not None:
            self.charger_partie(partie, id_partie, infos_tirage)
        else:
            self._id_partie = id_partie
            self._infos_tirage = infos_tirage
            self._tirage_termine = infos_tirage is None

    def _reinitialiser_etat(self) -> None:
        """Remet à zéro **tout** l'état interne lié à une partie (issue #179).

        Point unique de remise à zéro partagé par :meth:`__init__` et
        :meth:`charger_partie`. Ne touche ni aux fenêtres ni au chemin de
        persistance (indépendants d'une partie donnée) : uniquement l'état de
        pose, d'échange, de tirage et les drapeaux de fin/retour/recommencer, de
        sorte qu'une instance réutilisée reparte d'un état parfaitement neuf.
        """
        # Partie courante et son identifiant de persistance : ``None`` tant
        # qu'aucune partie n'a été chargée (voir contrat dans le docstring de
        # classe).
        self._partie: Partie | None = None
        self._id_partie: int | None = None
        # Tirage de l'ordre de jeu affiché « à la place » du plateau au tout
        # début d'une NOUVELLE partie (issue #170, ex-modale de l'accueil). Quand
        # ``infos_tirage`` est fourni — un dict ``{noms_creation, graine,
        # noms_humains}`` transmis par l'accueil (« Lancer la partie ») ou par
        # « Recommencer » (issue #142) — l'écran de jeu s'ouvre en état « pré-
        # partie » : plateau, fiches joueurs, barre globale et panneau chevalet
        # masqués par le JS, écran de tirage affiché à leur place. ``None``
        # (reprise d'une partie existante) : pas de tirage, écran directement jouable.
        # ``_tirage_termine`` passe à True dès qu'il n'y a plus de tirage à mener
        # (aucun tirage demandé, ou « Continuer » cliqué) : il garde
        # :meth:`terminer_tirage` idempotente.
        self._infos_tirage: dict[str, Any] | None = None
        self._tirage_termine: bool = True
        # État de pose centralisé côté Python (issue #90, option 1 du rapport
        # #89). ``_selection`` : index de la lettre sélectionnée dans le chevalet
        # du joueur courant, ou ``None``. ``_en_attente`` : placements en cours,
        # chacun un dict ``{ligne, colonne, lettre, joker, valeur, index}`` (la
        # ``lettre`` d'un placement est déjà la lettre affichée sur le plateau,
        # même pour un joker dont la lettre a été choisie).
        self._selection: int | None = None
        self._en_attente: list[dict[str, Any]] = []
        # Échange partiel (issue #138). ``_type_echange`` fige, au chargement de
        # la partie (donc à son démarrage), le mode choisi dans les réglages :
        # "complet" (bouton « Remettre toutes ses lettres ») ou "partiel"
        # (sélection libre de 1 à 7 lettres). Relu à chaque chargement pour
        # refléter un éventuel changement de réglage entre deux parties.
        # ``_mode_echange`` indique que le joueur est en train de marquer des
        # lettres à échanger, et ``_selection_echange`` porte les index de
        # chevalet ainsi marqués (une information neutre — de simples index — ne
        # dévoilant aucune lettre).
        self._type_echange: str = charger_config().get("type_echange", "complet")
        self._mode_echange: bool = False
        self._selection_echange: list[int] = []
        # Pose d'un joker en attente du choix de lettre (issue #90) : lorsqu'un
        # clic sur une case du plateau porte sur un joker, la pose est différée le
        # temps que le joueur choisisse la lettre représentée. Depuis l'issue #168,
        # ce choix se fait dans un menu déroulant de la fenêtre plateau (et non plus
        # dans une modale de la fenêtre chevalet) ; le contrat côté Python est
        # inchangé — on mémorise ici la case visée en attendant ce choix :
        # ``{ligne, colonne, index}`` ou ``None``.
        self._joker_demande: dict[str, Any] | None = None
        # Évite de journaliser plusieurs fois la même fin de partie (issue #66).
        self._fin_journalisee = False
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
        # Détail à transmettre à l'écran de jeu relancé après « Recommencer »
        # (issue #170) : la nouvelle partie a, elle aussi, un tirage d'ordre à
        # afficher. On mémorise ici les infos (``noms_creation``/``graine``/
        # ``noms_humains``) que :func:`lancer_jeu` passera à la nouvelle ``ApiJeu``.
        self._nouvelles_infos_tirage: dict[str, Any] | None = None

    def charger_partie(
        self,
        partie: Partie,
        id_partie: int | None,
        infos_tirage: dict[str, Any] | None = None,
    ) -> None:
        """Charge une partie dans cette instance et remet tout l'état à zéro.

        Dans le modèle mono-fenêtre (issue #179), une **même** instance
        d'``ApiJeu`` sert plusieurs parties successives (la fenêtre physique est
        réutilisée via ``load_url`` plutôt que recréée). Cette méthode
        réinitialise donc **intégralement** l'état interne
        (:meth:`_reinitialiser_etat`) avant d'installer la nouvelle partie,
        garantissant qu'aucun résidu (sélection, placements en attente, drapeaux
        de fin, mode d'échange…) d'une partie précédente ne subsiste.

        ``infos_tirage`` suit la même sémantique qu'au constructeur : non ``None``
        pour une nouvelle partie (écran de tirage d'ordre affiché à la place du
        plateau), ``None`` pour une reprise (partie directement jouable).
        """
        self._reinitialiser_etat()
        self._partie = partie
        self._id_partie = id_partie
        self._infos_tirage = infos_tirage
        self._tirage_termine = infos_tirage is None

    def set_window(self, window: webview.Window) -> None:
        """Associe la fenêtre **unique** de l'écran de jeu (issues #74/#193).

        Depuis le nettoyage du modèle de fenêtres (issue #193), l'écran de jeu ne
        comporte plus qu'une seule fenêtre physique (``jeu.html`` : plateau +
        chevalet intégré en zone C). Cette méthode remplace l'ancien
        ``set_windows(plateau, chevalet)`` de l'issue #90.
        """
        self._window_plateau = window

    @staticmethod
    def _erreur_aucune_partie() -> dict[str, Any]:
        """Charge d'erreur standard quand aucune partie n'est chargée (issue #179).

        Renvoyée par les getters d'état exposés au JS lorsqu'ils sont appelés
        alors que ``self._partie is None`` (instance créée en différé, pas encore
        chargée via :meth:`charger_partie`). Évite un ``AttributeError`` sur
        ``None`` : en fonctionnement normal, le routeur ne route jamais vers cette
        sous-API avant chargement, donc ce cas ne survient pas — c'est un filet.
        """
        return {
            "succes": False,
            "erreur": "Aucune partie chargée (charger_partie non appelée).",
        }

    def obtenir_etat(self) -> dict[str, Any]:
        """Retourne l'état public de la partie (sans lettres de chevalet)."""
        if self._partie is None:
            return self._erreur_aucune_partie()
        return etat_public(self._partie, self._id_partie)

    def obtenir_etat_plateau(self) -> dict[str, Any]:
        """État initial **public** pour la fenêtre plateau (issue #90).

        Équivalent de la charge diffusée par :meth:`_diffuser` vers la fenêtre
        plateau, exposé comme point d'entrée pour le chargement initial de cette
        fenêtre (avant toute mutation). Voir :meth:`_etat_plateau`.
        """
        if self._partie is None:
            return self._erreur_aucune_partie()
        return self._etat_plateau()

    def obtenir_etat_chevalet(self) -> dict[str, Any]:
        """État initial **privé** pour le panneau chevalet (zone C — issues #90/#187).

        Équivalent de la charge ``appliquerEtatChevalet`` diffusée par
        :meth:`_diffuser` (lettres du seul joueur humain de référence comprises),
        exposé pour le chargement initial du panneau chevalet intégré à
        ``jeu.html``. Voir :meth:`_etat_chevalet`.
        """
        if self._partie is None:
            return self._erreur_aucune_partie()
        return self._etat_chevalet()



# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #


def lancer_jeu(
    partie: Partie,
    id_partie: int | None,
    infos_tirage: dict[str, Any] | None = None,
) -> None:
    """Lance l'écran de jeu pour la ``partie`` donnée (bloquant).

    ``partie`` est typiquement celle créée par l'écran d'accueil (issue #27) ;
    ``id_partie`` est son identifiant de persistance (peut être ``None`` en
    mode démonstration autonome).

    ``infos_tirage`` (issue #170) : quand l'accueil vient de créer une partie
    (« Lancer la partie »), il passe ici le détail nécessaire au tirage d'ordre
    (``{noms_creation, graine, noms_humains}``). L'écran de jeu s'ouvre alors en
    état « pré-partie » — plateau, fiches joueurs, barre globale et panneau
    chevalet masqués par le JS, écran de tirage affiché à leur place — jusqu'à ce
    que l'utilisateur clique « Continuer ». ``None`` (reprise de partie) : l'écran
    s'ouvre directement jouable, sans tirage.

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
    api = ApiJeu(partie, id_partie, infos_tirage=infos_tirage)
    retour_menu = False
    recommencer = False
    nouvelle_partie: Partie | None = None
    nouvel_id_partie: int | None = None
    nouvelles_infos_tirage: dict[str, Any] | None = None
    try:
        _lancer_fenetre_jeu(api)
        retour_menu = api._retour_menu
        recommencer = api._recommencer
        nouvelle_partie = api._nouvelle_partie
        nouvel_id_partie = api._nouvel_id_partie
        nouvelles_infos_tirage = api._nouvelles_infos_tirage
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
        # nouveau sur le nouveau tirage d'ordre (issue #170) : on transmet les
        # infos de tirage préparées par ``creer_partie_recommencee``.
        lancer_jeu(nouvelle_partie, nouvel_id_partie, nouvelles_infos_tirage)


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


def _lancer_fenetre_jeu(api: "ApiJeu") -> None:
    """Crée l'**unique** fenêtre de jeu et démarre la boucle (issues #90/#193).

    Depuis la migration du chevalet en zone C (issue #187) et le nettoyage du
    modèle de fenêtres (issue #193), l'écran de jeu ne comporte plus qu'**une
    seule** fenêtre pywebview (``jeu.html``) : plateau, panneaux joueurs, barre du
    sac/historique, « Faire jouer l'ordinateur », vérification dictionnaire ET le
    panneau chevalet intégré. Plus de fenêtre chevalet compagnon flottante à créer,
    positionner, lier ou fermer en croisé.

    Fenêtre maximisée (``maximized=True``), sans ``width``/``height`` fixes, pour
    s'adapter à n'importe quelle résolution logique (le CSS contraint le plateau par
    la hauteur disponible, évitant tout défilement). Un callback
    ``webview.start(func, …)`` (:func:`_finaliser_fenetres`) réaffirme sa
    maximisation une fois la boucle démarrée et la fenêtre affichée (issue #95 point
    B : ``maximized=True`` n'est pas honoré sous XWayland tant que la fenêtre n'est
    pas mappée).
    """
    window_plateau = webview.create_window(
        "Scrabble",
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
    api.set_window(window_plateau)
    # Finalisation après démarrage de la boucle (issues #91 point 1 et #95) : c'est
    # seulement une fois ``webview.start()`` en cours et la fenêtre affichée que
    # (a) ``webview.screens`` renvoie des dimensions fiables sous WebKitGTK et que
    # (b) une (ré)affirmation de l'état maximisé du plateau est honorée par le WM.
    #
    # Point B de l'issue #96 (fenêtre plateau ouverte « réduite ») — confirmation par
    # lecture du code de pywebview installé (``platforms/gtk.py``) : à la création,
    # ``BrowserView.__init__`` fait ``self.window.maximize()`` AVANT ``browser.show()``
    # (la fenêtre n'est donc pas encore mappée), et sans ``width``/``height`` la taille
    # initiale non maximisée est le défaut ~800×600. Sous XWayland (backend forcé #93),
    # cette maximisation pré-mappage est un no-op → fenêtre petite. Le correctif
    # (:func:`_maximiser_plateau`) est donc appliqué ici pour les DEUX chemins de
    # lancement — autonome (``python -m scrabble.ui.jeu``) et normal
    # (accueil → :func:`lancer_jeu`) — puisque tous deux passent par cette fonction et
    # basculent XWayland avant le premier ``webview.start()``.
    webview.start(_finaliser_fenetres, window_plateau)


def _finaliser_fenetres(window_plateau: "webview.Window") -> None:
    """Finalise l'état de la fenêtre unique une fois la boucle GUI démarrée (issue #95).

    Exécuté par ``webview.start(func, …)`` dans un fil dédié, **après** le démarrage
    de la boucle. Depuis le nettoyage du modèle de fenêtres (issue #193), il n'y a
    plus qu'une seule fenêtre : la seule finalisation restante est la
    **maximisation du plateau** (:func:`_maximiser_plateau`), ``maximized=True``
    demandé à la création n'étant pas honoré sous XWayland tant que la fenêtre n'est
    pas mappée (cf. cette fonction).
    """
    _maximiser_plateau(window_plateau)


def _zone_travail_ecran() -> tuple[int, int, int, int] | None:
    """Zone de travail (x, y, largeur, hauteur) du moniteur principal — issue #95.

    Surface d'écran réellement **utilisable**, panneaux et barres système EXCLUS
    (EWMH ``_NET_WORKAREA``) : c'est la cible d'une vraie maximisation. Lue via
    **GDK**, le même moteur que ``webview.screens`` (déjà employé pour mesurer
    l'écran, issue #91). Sur cette machine, GDK renvoie p. ex. ``(66, 32, 1294,
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
    # N'agir qu'une fois la fenêtre réellement affichée (issue #92) :
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


def _attendre_fenetre_affichee(
    window: "webview.Window", nom: str = "plateau", timeout: float = 5.0
) -> None:
    """Attend l'événement ``shown`` de ``window`` (au plus ``timeout`` s) — issue #92.

    ``webview.Window.events.shown`` est un événement pywebview signalé une fois la
    fenêtre affichée par le backend. On l'attend avant tout ``move``/``resize``/
    ``maximize`` pour éviter une requête ignorée (fenêtre pas encore mappée sous
    WebKitGTK — cf. issue #95 pour la maximisation du plateau). ``nom`` sert
    uniquement aux traces. Tolère l'absence d'attribut ``events``
    (backends/fenêtres factices des tests) : dans ce cas on n'attend pas.
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
    empilement vertical des fiches joueurs dans l'ordre de jeu — issues
    #33/#195), pas de rejouer une partie réelle. Un joker (« blanc ») figure
    dans le mot vertical
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
