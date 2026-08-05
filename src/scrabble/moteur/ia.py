"""Stratégies de sélection de coup IA pour la boucle de partie.

Rôle : choisir, au tour d'un joueur IA, un coup parmi ceux générés
exhaustivement par :func:`scrabble.moteur.generateur.generer_coups`.
La génération est identique quel que soit le niveau ; seule la stratégie
de sélection dans la liste triée par score varie.

Niveaux de difficulté
---------------------
* **CHAMPION_DU_MONDE** : même stratégie de sélection qu'EXPERT (meilleur
  coup) et même tranche de malus/bonus stratégiques. Ne se distingue
  d'EXPERT que par le vocabulaire — câblé par l'appelant (issue #369, lot C)
  via :func:`resoudre_palier` : EXPERT reçoit le Trie restreint du palier
  ``"expert"`` (intersection Lexique), CHAMPION_DU_MONDE le Trie complet
  (ODS8 sans filtre, ``obtenir_trie()``). Ce module lui-même reste agnostique
  du dictionnaire reçu (voir « Ordre réel de force » ci-dessous).
* **EXPERT** : choisit le meilleur coup (premier de la liste triée). En cas
  d'égalité de score entre plusieurs coups de tête, choix aléatoire parmi eux.
* **AVANCE** : choix aléatoire uniforme parmi les 15 % meilleurs coups (top
  15 %). Plus fort qu'INTERMEDIAIRE (top 33 %) mais moins strict qu'EXPERT
  (coup unique). Niveau intercalaire pour une progression plus fine (issue
  #202).
* **INTERMEDIAIRE** : choix aléatoire uniforme parmi le meilleur tiers des
  coups (top 33 %). Favorise les bons coups sans être optimal.
* **FACILE** : choix aléatoire uniforme parmi les 60 % meilleurs coups (top
  60 %), c'est-à-dire en écartant les 40 % de coups les plus faibles. Reste
  délibérément sous-optimal, mais réellement plus fort que DEBUTANT en score
  moyen (issue #208, voir la note ci-dessous).
* **DEBUTANT** : choix aléatoire uniforme parmi les 85 % meilleurs coups (top
  85 %). N'écarte que les 15 % de coups les plus faibles au sens du score
  stratégique (typiquement les hooks pénalisés par le malus longueur), ce qui
  le laisse très proche d'un tirage au hasard tout en garantissant qu'il reste
  le niveau le plus faible (issue #361).

Ordre réel de force (score moyen)
---------------------------------
Les stratégies ci-dessus produisent, en moyenne, l'ordre croissant
``DEBUTANT < FACILE < INTERMEDIAIRE < AVANCE < EXPERT < CHAMPION_DU_MONDE``
— cohérent avec l'ordre de la classe :class:`Niveau` et avec ce que
suggèrent les noms des niveaux.

Cette monotonie est STRUCTURELLE pour les cinq premiers niveaux : tous
passent par le même mécanisme (tri par score stratégique puis tirage
uniforme dans une tranche haute), et les tranches sont strictement
emboîtées — top 85 % (DEBUTANT) ⊃ top 60 % (FACILE) ⊃ top 33 %
(INTERMEDIAIRE) ⊃ top 15 % (AVANCE) ⊃ meilleur coup (EXPERT). Chaque tranche
étant un sous-ensemble strictement meilleur de la précédente, les scores
moyens croissent mécaniquement avec le niveau, indépendamment du dictionnaire
employé. Aucun niveau n'a de filtre dur spécifique : l'issue #359 avait doté
DEBUTANT d'un filtre sur la longueur (``nb_nouvelles >= 3``) qui le rendait
plus sélectif que FACILE et cassait la monotonie ; l'issue #361 l'a remplacé
par la tranche top 85 %.

Le dernier maillon, EXPERT < CHAMPION_DU_MONDE, est de nature DIFFÉRENTE : ce
n'est pas la stratégie de sélection qui les distingue (:func:`_choisir_expert`
sert les deux identiquement), mais le vocabulaire reçu en paramètre — câblé
par l'appelant (issue #369, lot C, voir :func:`resoudre_palier`) : EXPERT
génère ses coups sur le Trie restreint du palier ``"expert"`` (intersection
Lexique), CHAMPION_DU_MONDE sur le Trie complet ODS8. Le vocabulaire plus
large de CHAMPION_DU_MONDE lui ouvre des coups inaccessibles à EXPERT, d'où
l'inégalité stricte en moyenne. Contrairement aux cinq premiers niveaux, ce
n'est donc PAS une propriété de ce module : à dictionnaire identique (par
exemple si l'appelant transmettait le même Trie aux deux, ou avec le
vocabulaire humain désactivé — voir ``ui.accueil``), les deux niveaux
redeviennent mécaniquement égaux, comme le vérifie la fixture de test dédiée.

Pourquoi « top 60 % » pour FACILE plutôt qu'une moitié/tranche centrale ? La
distribution des scores est fortement asymétrique : quelques coups à très
fort score (un « scrabble » vaut ~70 pts) tirent la MOYENNE d'un tirage large
bien au-dessus de la médiane. Une tranche centrée sur la médiane resterait
donc, en moyenne, SOUS DEBUTANT. Écarter les 40 % les plus faibles garantit
au contraire ``FACILE > DEBUTANT`` (issue #208).

Comportement de repli (listes courtes)
--------------------------------------
Si la tranche calculée (top 15 %, tiers, top 60 %, top 85 %) est vide, on
retombe sur la liste complète via ``max(1, ...)``. Cela évite tout crash sur
des positions avec peu de coups jouables.
Exemple : 2 coups disponibles, tiers = 0 → on choisit parmi les 2.

Reproductibilité
----------------
Le paramètre ``alea`` (:class:`random.Random` optionnel) permet d'injecter
un générateur aléatoire à graine fixée pour des tests reproductibles.
"""

from __future__ import annotations

import random
from enum import Enum, auto
from typing import TYPE_CHECKING

from scrabble.moteur.generateur import CoupNote, generer_coups
from scrabble.moteur.plateau_partie import Coup, PlateauPartie
from scrabble.regles.plateau import TypeCase

if TYPE_CHECKING:
    from scrabble.moteur.generateur import TrieProtocol


class Niveau(Enum):
    """Niveaux de difficulté IA, du plus faible au plus fort.

    :attr:`CHAMPION_DU_MONDE` est ajouté en fin de liste (issue #368, lot D) :
    la position en fin garantit la rétro-compatibilité des parties existantes
    sérialisées par ``.name`` (voir ``stockage.py``), la position des
    ``auto()`` précédents n'ayant aucun impact sur les données stockées.
    """

    DEBUTANT = auto()
    FACILE = auto()
    INTERMEDIAIRE = auto()
    AVANCE = auto()
    EXPERT = auto()
    CHAMPION_DU_MONDE = auto()


# Résolution Niveau → clé de palier de vocabulaire IA (issue #369, lot C).
#
# Emplacement volontaire : ce module (``moteur.ia``) connaît :class:`Niveau`,
# et les clés ci-dessous ne sont que des chaînes — aucune dépendance vers
# ``scrabble.dictionnaire`` n'est introduite ici. C'est le sens inverse qui est
# strictement interdit (choix du lot A, issue #366) : ``dictionnaire.py`` ne
# doit jamais importer le moteur, pour rester utilisable sans lui. Le moteur,
# lui, peut décrire une correspondance vers des clés de palier sans en
# importer la définition : ces mêmes clés sont utilisées, côté appelant
# (``scrabble.ui.accueil``, qui importe déjà les deux modules), pour indexer
# :data:`scrabble.dictionnaire.dictionnaire.FICHIERS_VOCABULAIRE_PALIER` et
# :data:`~scrabble.dictionnaire.dictionnaire.FICHIERS_CACHE_IA_PALIER` — une
# correspondance de test (``test_moteur_ia.py``) vérifie qu'elles restent en
# phase.
#
# :data:`Niveau.CHAMPION_DU_MONDE` n'a volontairement aucune entrée : il ne se
# résout vers aucun palier restreint mais vers le Trie complet
# (:func:`~scrabble.dictionnaire.dictionnaire.obtenir_trie`, ODS8 sans
# filtre) — voir :func:`resoudre_palier`.
_PALIERS_PAR_NIVEAU: dict[Niveau, str] = {
    Niveau.DEBUTANT: "debutant",
    Niveau.FACILE: "facile",
    Niveau.INTERMEDIAIRE: "intermediaire",
    Niveau.AVANCE: "avance",
    Niveau.EXPERT: "expert",
}


def resoudre_palier(niveau: Niveau) -> str | None:
    """Résout un :class:`Niveau` vers sa clé de palier de vocabulaire IA.

    Renvoie la clé de palier (``"debutant"``, ``"facile"``… voir
    :data:`_PALIERS_PAR_NIVEAU`) pour les cinq niveaux filtrés, et ``None``
    pour :data:`Niveau.CHAMPION_DU_MONDE` : ce niveau n'est câblé sur aucun
    fichier de vocabulaire restreint, l'appelant doit se rabattre sur le Trie
    complet (``obtenir_trie()``) plutôt que sur ``obtenir_trie_ia(palier=...)``.
    """
    return _PALIERS_PAR_NIVEAU.get(niveau)


#: Malus (négatif) appliqué au score de tri d'un coup posant peu de lettres
#: (``nb_nouvelles <= 2``), doublé si une seule lettre est posée (« hook
#: pur »). Croissant en valeur absolue avec le niveau : un niveau fort doit
#: éviter les hooks encore plus nettement qu'un niveau faible (issue #359).
_MALUS_LONGUEUR: dict[Niveau, int] = {
    Niveau.DEBUTANT: -5,
    Niveau.FACILE: -8,
    Niveau.INTERMEDIAIRE: -12,
    Niveau.AVANCE: -18,
    Niveau.EXPERT: -25,
    Niveau.CHAMPION_DU_MONDE: -25,
}

#: Bonus (positif) appliqué au score de tri d'un coup exploitant au moins
#: une case premium (mot ou lettre compte double/triple). Croissant avec le
#: niveau (issue #359).
_BONUS_PREMIUM: dict[Niveau, int] = {
    Niveau.DEBUTANT: 3,
    Niveau.FACILE: 5,
    Niveau.INTERMEDIAIRE: 8,
    Niveau.AVANCE: 12,
    Niveau.EXPERT: 20,
    Niveau.CHAMPION_DU_MONDE: 20,
}

#: Cases dont le bonus porte sur le mot entier (plus précieuses que les
#: cases à bonus de lettre seule) : reçoivent le plein bonus premium, contre
#: la moitié pour LETTRE_DOUBLE/LETTRE_TRIPLE.
_CASES_BONUS_MOT = frozenset({TypeCase.MOT_DOUBLE, TypeCase.MOT_TRIPLE, TypeCase.CENTRE})

#: Seuil (en nombre de lettres nouvellement posées) en-deçà duquel la
#: pénalité longueur s'applique.
_SEUIL_PENALITE_LONGUEUR = 2


def _score_strategique(cn: CoupNote, niveau: Niveau) -> int:
    """Score ajusté servant UNIQUEMENT au tri des coups par niveau IA.

    N'affecte pas :attr:`CoupNote.score` (score réel affiché/marqué) : c'est
    une clé de tri parallèle qui corrige deux biais du tri glouton sur score
    brut (issue #359) :

    * pénalise les coups posant peu de lettres (``nb_nouvelles <= 2``), en
      particulier les « hooks » purs (une seule lettre posée, malus doublé) ;
    * valorise les coups exploitant une case premium, même à score brut
      légèrement inférieur à un hook.

    Les deux ajustements sont proportionnels au niveau : un niveau fort doit
    éviter les hooks et viser les cases premium plus nettement qu'un niveau
    faible, cohérent avec l'idée qu'un débutant humain *essaie* de faire de
    vrais mots — c'est la qualité de sa recherche qui est faible, pas son
    style de jeu.
    """
    ajustement = 0

    if cn.nb_nouvelles <= _SEUIL_PENALITE_LONGUEUR:
        malus = _MALUS_LONGUEUR[niveau]
        if cn.nb_nouvelles == 1:
            malus *= 2
        ajustement += malus

    if any(mot.cases_bonus for mot in cn.detail.mots):
        bonus = _BONUS_PREMIUM[niveau]
        types_case = {
            type_case
            for mot in cn.detail.mots
            for (_, _, type_case) in mot.cases_bonus
        }
        if not types_case & _CASES_BONUS_MOT:
            bonus //= 2
        ajustement += bonus

    return cn.score + ajustement


def choisir_coup(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: "TrieProtocol",
    niveau: Niveau,
    alea: random.Random | None = None,
) -> Coup | None:
    """Choisit un coup selon le niveau IA, ou None pour passer.

    Args:
        plateau: État courant du plateau de jeu.
        chevalet: Jetons disponibles pour le joueur IA.
        dictionnaire: Trie du dictionnaire.
        niveau: Stratégie de sélection à appliquer.
        alea: Générateur aléatoire optionnel pour reproductibilité.

    Returns:
        Le coup choisi, ou None si aucun coup n'est jouable (le joueur passe).
    """
    coups = generer_coups(plateau, chevalet, dictionnaire)
    if not coups:
        return None

    rng = alea if alea is not None else random.Random()

    coups = sorted(coups, key=lambda cn: _score_strategique(cn, niveau), reverse=True)

    if niveau in (Niveau.EXPERT, Niveau.CHAMPION_DU_MONDE):
        return _choisir_expert(coups, rng)
    if niveau == Niveau.AVANCE:
        return _choisir_avance(coups, rng)
    if niveau == Niveau.INTERMEDIAIRE:
        return _choisir_intermediaire(coups, rng)
    if niveau == Niveau.FACILE:
        return _choisir_facile(coups, rng)
    return _choisir_debutant(coups, rng)


def _choisir_expert(coups: list[CoupNote], rng: random.Random) -> Coup:
    """EXPERT et CHAMPION_DU_MONDE : meilleur coup, aléatoire en cas d'égalité.

    Les deux niveaux partagent exactement la même stratégie de sélection et
    les mêmes tranches de malus/bonus (:data:`_MALUS_LONGUEUR`,
    :data:`_BONUS_PREMIUM`) : seul le vocabulaire reçu en paramètre les
    distingue, câblé par l'appelant (issue #369, lot C, voir
    :func:`resoudre_palier`).
    """
    meilleur_score = coups[0].score
    meilleurs = [cn for cn in coups if cn.score == meilleur_score]
    return rng.choice(meilleurs).coup


def _choisir_avance(coups: list[CoupNote], rng: random.Random) -> Coup:
    """AVANCE : aléatoire parmi les 15 % meilleurs coups (top 15 %).

    Seuil intercalaire entre le top 33 % d'INTERMEDIAIRE et le coup unique
    d'EXPERT. ``max(1, ...)`` garantit un sous-ensemble non vide (repli sur le
    seul meilleur coup pour les listes très courtes), comme les autres niveaux.
    """
    taille_haut = max(1, len(coups) * 15 // 100)
    return rng.choice(coups[:taille_haut]).coup


def _choisir_intermediaire(coups: list[CoupNote], rng: random.Random) -> Coup:
    """INTERMEDIAIRE : aléatoire parmi le meilleur tiers (top 33 %)."""
    taille_tiers = max(1, len(coups) // 3)
    return rng.choice(coups[:taille_tiers]).coup


def _choisir_facile(coups: list[CoupNote], rng: random.Random) -> Coup:
    """FACILE : aléatoire parmi les 60 % meilleurs coups (top 60 %).

    Écarte les 40 % de coups les plus faibles, ce qui remonte le score moyen
    au-dessus de DEBUTANT (qui tire parmi TOUS les coups) tout en restant
    nettement sous INTERMEDIAIRE (top 33 %, sous-ensemble strictement meilleur).
    ``max(1, ...)`` garantit un sous-ensemble non vide (repli sur le seul
    meilleur coup pour les listes très courtes), comme les autres niveaux
    (issue #208).
    """
    taille_haut = max(1, len(coups) * 60 // 100)
    return rng.choice(coups[:taille_haut]).coup


def _choisir_debutant(coups: list[CoupNote], rng: random.Random) -> Coup:
    """DEBUTANT : aléatoire parmi les 85 % meilleurs coups (top 85 %).

    Tranche la plus large de tous les niveaux : seuls les 15 % de coups les
    plus faibles au sens du score stratégique sont écartés (le malus longueur
    y relègue les hooks les plus pauvres). C'est ce qui rend le tri
    stratégique opérant pour DEBUTANT tout en le maintenant strictement sous
    FACILE (top 60 %, sous-ensemble strictement meilleur) — issue #361, en
    remplacement du filtre dur ``nb_nouvelles >= 3`` de l'issue #359 qui
    cassait la monotonie des niveaux. ``max(1, ...)`` garantit un
    sous-ensemble non vide, comme les autres niveaux.
    """
    taille_haut = max(1, len(coups) * 85 // 100)
    return rng.choice(coups[:taille_haut]).coup
