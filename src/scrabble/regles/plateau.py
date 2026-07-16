"""Géométrie du plateau de Scrabble et cases bonus.

Rôle : décrire la grille standard 15×15 (indices ``0`` à ``14`` en ligne comme
en colonne) et le type de bonus attaché à chaque case (lettre ou mot compte
double/triple, case centrale). C'est une donnée de référence, figée, servant
d'entrée au futur moteur de génération de coups (calcul des scores, repérage des
cases bonus).

Module volontairement **sans état** : aucune notion de tour de jeu, de tirage
aléatoire ni de nombre de joueurs n'y figure. La logique de tirage, de tour et
de nombre de joueurs relève d'un futur moteur de jeu — ce module reste ainsi
réutilisable tel quel par de futures variantes (Duplicate, variante Joker, etc.).

Convention des positions
-------------------------
Les positions correspondent au **plateau standard officiel du Scrabble**, connu
pour être symétrique par rotation d'un quart de tour et par réflexion sur les
deux diagonales (groupe dièdral d'ordre 8). La case centrale ``(7, 7)`` est
l'étoile de départ ; elle compte comme un mot double.

Disposition (repère : ligne 0 en haut, colonne 0 à gauche)::

    MT .  .  LD .  .  .  MT .  .  .  LD .  .  MT
    .  MD .  .  .  LT .  .  .  LT .  .  .  MD .
    .  .  MD .  .  .  LD .  LD .  .  .  MD .  .
    LD .  .  MD .  .  .  LD .  .  .  MD .  .  LD
    .  .  .  .  MD .  .  .  .  .  MD .  .  .  .
    .  LT .  .  .  LT .  .  .  LT .  .  .  LT .
    .  .  LD .  .  .  LD .  LD .  .  .  LD .  .
    MT .  .  LD .  .  .  ★  .  .  .  LD .  .  MT
    .  .  LD .  .  .  LD .  LD .  .  .  LD .  .
    .  LT .  .  .  LT .  .  .  LT .  .  .  LT .
    .  .  .  .  MD .  .  .  .  .  MD .  .  .  .
    LD .  .  MD .  .  .  LD .  .  .  MD .  .  LD
    .  .  MD .  .  .  LD .  LD .  .  .  MD .  .
    .  MD .  .  .  LT .  .  .  LT .  .  .  MD .
    MT .  .  LD .  .  .  MT .  .  .  LD .  .  MT

Décompte : 8 mots triples (MT), 16 mots doubles (MD) + l'étoile centrale,
12 lettres triples (LT), 24 lettres doubles (LD).
"""

from __future__ import annotations

import enum

#: Dimension de la grille (plateau carré ``TAILLE`` × ``TAILLE``).
TAILLE = 15


class TypeCase(enum.Enum):
    """Type de bonus d'une case du plateau.

    Une case sans bonus est une case :attr:`NORMALE`.
    """

    NORMALE = "normale"
    LETTRE_DOUBLE = "LD"
    LETTRE_TRIPLE = "LT"
    MOT_DOUBLE = "MD"
    MOT_TRIPLE = "MT"
    #: Case centrale (étoile de départ). Compte comme un mot double.
    CENTRE = "centre"


# --------------------------------------------------------------------------- #
# Positions officielles des cases bonus (plateau standard)
# --------------------------------------------------------------------------- #
# Chaque ensemble liste les coordonnées ``(ligne, colonne)`` en base 0. Le
# tableau est symétrique par les rotations et réflexions du carré ; les
# positions ci-dessous en sont l'énumération explicite.

_MOTS_TRIPLES = frozenset({
    (0, 0), (0, 7), (0, 14),
    (7, 0), (7, 14),
    (14, 0), (14, 7), (14, 14),
})

_MOTS_DOUBLES = frozenset({
    (1, 1), (2, 2), (3, 3), (4, 4),
    (1, 13), (2, 12), (3, 11), (4, 10),
    (13, 1), (12, 2), (11, 3), (10, 4),
    (13, 13), (12, 12), (11, 11), (10, 10),
})

_LETTRES_TRIPLES = frozenset({
    (1, 5), (1, 9),
    (5, 1), (5, 5), (5, 9), (5, 13),
    (9, 1), (9, 5), (9, 9), (9, 13),
    (13, 5), (13, 9),
})

_LETTRES_DOUBLES = frozenset({
    (0, 3), (0, 11),
    (2, 6), (2, 8),
    (3, 0), (3, 7), (3, 14),
    (6, 2), (6, 6), (6, 8), (6, 12),
    (7, 3), (7, 11),
    (8, 2), (8, 6), (8, 8), (8, 12),
    (11, 0), (11, 7), (11, 14),
    (12, 6), (12, 8),
    (14, 3), (14, 11),
})

#: Coordonnées de la case centrale (étoile de départ).
CENTRE = (7, 7)


def _valider_bornes(ligne: int, colonne: int) -> None:
    """Vérifie que ``(ligne, colonne)`` est dans la grille, sinon lève.

    :raises IndexError: si ``ligne`` ou ``colonne`` sort de ``0..TAILLE-1``.
    """
    if not (0 <= ligne < TAILLE) or not (0 <= colonne < TAILLE):
        raise IndexError(
            f"Position hors plateau : (ligne={ligne}, colonne={colonne}) ; "
            f"attendu 0 <= ligne < {TAILLE} et 0 <= colonne < {TAILLE}."
        )


def type_case(ligne: int, colonne: int) -> TypeCase:
    """Renvoie le :class:`TypeCase` de la case ``(ligne, colonne)``.

    Les indices sont en base 0 (``0`` à ``TAILLE-1``). Une case sans bonus
    renvoie :attr:`TypeCase.NORMALE`. La case centrale renvoie
    :attr:`TypeCase.CENTRE`.

    :raises IndexError: si la position est hors du plateau (aucune valeur
        « normale » n'est renvoyée silencieusement dans ce cas).
    """
    _valider_bornes(ligne, colonne)
    pos = (ligne, colonne)
    if pos == CENTRE:
        return TypeCase.CENTRE
    if pos in _MOTS_TRIPLES:
        return TypeCase.MOT_TRIPLE
    if pos in _MOTS_DOUBLES:
        return TypeCase.MOT_DOUBLE
    if pos in _LETTRES_TRIPLES:
        return TypeCase.LETTRE_TRIPLE
    if pos in _LETTRES_DOUBLES:
        return TypeCase.LETTRE_DOUBLE
    return TypeCase.NORMALE
