"""Stratégies de sélection de coup IA pour la boucle de partie.

Rôle : choisir, au tour d'un joueur IA, un coup parmi ceux générés
exhaustivement par :func:`scrabble.moteur.generateur.generer_coups`.
La génération est identique quel que soit le niveau ; seule la stratégie
de sélection dans la liste triée par score varie.

Niveaux de difficulté
---------------------
* **EXPERT** : choisit le meilleur coup (premier de la liste triée). En cas
  d'égalité de score entre plusieurs coups de tête, choix aléatoire parmi eux.
* **INTERMEDIAIRE** : choix aléatoire uniforme parmi le meilleur tiers des
  coups (top 33 %). Favorise les bons coups sans être optimal.
* **FACILE** : choix aléatoire uniforme parmi la moitié inférieure des coups.
  Délibérément sous-optimal mais pas absurde.
* **DEBUTANT** : choix aléatoire uniforme parmi TOUS les coups, sans
  considération de score. Peut occasionnellement jouer un bon coup par chance.

Comportement de repli (listes courtes)
--------------------------------------
Si la tranche calculée (tiers, moitié) est vide, on retombe sur la liste
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

if TYPE_CHECKING:
    from scrabble.moteur.generateur import TrieProtocol


class Niveau(Enum):
    """Niveaux de difficulté IA, du plus faible au plus fort."""

    DEBUTANT = auto()
    FACILE = auto()
    INTERMEDIAIRE = auto()
    EXPERT = auto()


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

    if niveau == Niveau.EXPERT:
        return _choisir_expert(coups, rng)
    if niveau == Niveau.INTERMEDIAIRE:
        return _choisir_intermediaire(coups, rng)
    if niveau == Niveau.FACILE:
        return _choisir_facile(coups, rng)
    # DEBUTANT
    return _choisir_debutant(coups, rng)


def _choisir_expert(coups: list[CoupNote], rng: random.Random) -> Coup:
    """EXPERT : meilleur coup, aléatoire en cas d'égalité de score."""
    meilleur_score = coups[0].score
    meilleurs = [cn for cn in coups if cn.score == meilleur_score]
    return rng.choice(meilleurs).coup


def _choisir_intermediaire(coups: list[CoupNote], rng: random.Random) -> Coup:
    """INTERMEDIAIRE : aléatoire parmi le meilleur tiers (top 33 %)."""
    taille_tiers = max(1, len(coups) // 3)
    return rng.choice(coups[:taille_tiers]).coup


def _choisir_facile(coups: list[CoupNote], rng: random.Random) -> Coup:
    """FACILE : aléatoire parmi la moitié inférieure des coups."""
    taille_moitie = len(coups) // 2
    if taille_moitie == 0:
        return rng.choice(coups).coup
    return rng.choice(coups[taille_moitie:]).coup


def _choisir_debutant(coups: list[CoupNote], rng: random.Random) -> Coup:
    """DEBUTANT : aléatoire parmi tous les coups."""
    return rng.choice(coups).coup
