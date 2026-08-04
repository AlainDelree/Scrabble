"""Stratégies de sélection de coup IA pour la boucle de partie.

Rôle : choisir, au tour d'un joueur IA, un coup parmi ceux générés
exhaustivement par :func:`scrabble.moteur.generateur.generer_coups`.
La génération est identique quel que soit le niveau ; seule la stratégie
de sélection dans la liste triée par score varie.

Niveaux de difficulté
---------------------
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
* **DEBUTANT** : choix aléatoire uniforme parmi TOUS les coups, sans
  considération de score. Peut occasionnellement jouer un bon coup par chance.

Ordre réel de force (score moyen)
---------------------------------
Les stratégies ci-dessus produisent, en moyenne, l'ordre croissant
``DEBUTANT < FACILE < INTERMEDIAIRE < AVANCE < EXPERT`` — cohérent avec l'ordre
de la classe :class:`Niveau` et avec ce que suggèrent les noms des niveaux.

Pourquoi « top 60 % » plutôt qu'une moitié/tranche centrale ? La distribution
des scores est fortement asymétrique : quelques coups à très fort score (un
« scrabble » vaut ~70 pts) tirent la MOYENNE de DEBUTANT (qui échantillonne
tous les coups) bien au-dessus de la médiane. Une tranche centrée sur la
médiane resterait donc, en moyenne, SOUS DEBUTANT. Écarter les 40 % les plus
faibles garantit au contraire ``FACILE > DEBUTANT`` (on ne retient que la
partie haute), tout en gardant ``FACILE < INTERMEDIAIRE`` puisque le top 33 %
d'INTERMEDIAIRE est un sous-ensemble strictement meilleur du top 60 %. Cette
monotonie est donc structurelle, indépendante du dictionnaire employé (elle
vaut avec ou sans le filtre de « vocabulaire humain », issue #206/#207).

Comportement de repli (listes courtes)
--------------------------------------
Si la tranche calculée (top 15 %, tiers, top 60 %) est vide, on retombe sur la liste
complète. Cela évite tout crash sur des positions avec peu de coups jouables.
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
    """Niveaux de difficulté IA, du plus faible au plus fort."""

    DEBUTANT = auto()
    FACILE = auto()
    INTERMEDIAIRE = auto()
    AVANCE = auto()
    EXPERT = auto()


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

    if niveau == Niveau.EXPERT:
        return _choisir_expert(coups, rng)
    if niveau == Niveau.AVANCE:
        return _choisir_avance(coups, rng)
    if niveau == Niveau.INTERMEDIAIRE:
        return _choisir_intermediaire(coups, rng)
    if niveau == Niveau.FACILE:
        return _choisir_facile(coups, rng)
    # DEBUTANT : parmi les coups formant un vrai mot (>= 3 lettres posées) si
    # certains existent, sinon repli sur la liste complète (issue #359).
    coups_longs = [cn for cn in coups if cn.nb_nouvelles >= 3]
    return _choisir_debutant(coups_longs if coups_longs else coups, rng)


def _choisir_expert(coups: list[CoupNote], rng: random.Random) -> Coup:
    """EXPERT : meilleur coup, aléatoire en cas d'égalité de score."""
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
    """DEBUTANT : aléatoire parmi tous les coups."""
    return rng.choice(coups).coup
