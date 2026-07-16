"""Répartition officielle des jetons du Scrabble français et valeurs.

Rôle : décrire la donnée de référence « quelles lettres, en quelle quantité, et
combien de points chacune » pour l'édition **française** du Scrabble, ainsi que
la constitution du sac initial complet.

Répartition officielle : **102 jetons** au total, dont **2 jokers** (lettres
blanches). Le joker vaut 0 point et peut être joué comme n'importe quelle lettre.

Module volontairement **sans état** : aucune notion de tirage aléatoire ni de
tour de jeu. :func:`constituer_sac` renvoie la liste **complète et déterministe**
des 102 jetons initiaux ; le mélange, le tirage aléatoire et toute variante de
composition (par exemple le retrait des jokers de la variante « Joker ») sont la
responsabilité d'un futur module de tirage / moteur de jeu, pas de celui-ci.

Représentation du joker
------------------------
Dans les jetons produits par :func:`constituer_sac`, un joker est représenté par
la constante :data:`JOKER`, à savoir la chaîne ``"*"``. Les lettres ordinaires
sont des majuscules ``"A"`` à ``"Z"`` (accents non distingués ici : la lettre
posée avec un joker sera précisée par le moteur de jeu, pas par ce module).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Symbole représentant un joker (lettre blanche) dans le sac.
JOKER = "*"


@dataclass(frozen=True)
class Jeton:
    """Description d'un type de jeton : sa quantité et sa valeur en points."""

    nombre: int
    valeur: int


# --------------------------------------------------------------------------- #
# Répartition officielle du Scrabble français
# --------------------------------------------------------------------------- #
# 26 lettres + le joker. Total : 102 jetons (dont 2 jokers).

REPARTITION: dict[str, Jeton] = {
    "A": Jeton(nombre=9, valeur=1),
    "B": Jeton(nombre=2, valeur=3),
    "C": Jeton(nombre=2, valeur=3),
    "D": Jeton(nombre=3, valeur=2),
    "E": Jeton(nombre=15, valeur=1),
    "F": Jeton(nombre=2, valeur=4),
    "G": Jeton(nombre=2, valeur=2),
    "H": Jeton(nombre=2, valeur=4),
    "I": Jeton(nombre=8, valeur=1),
    "J": Jeton(nombre=1, valeur=8),
    "K": Jeton(nombre=1, valeur=10),
    "L": Jeton(nombre=5, valeur=1),
    "M": Jeton(nombre=3, valeur=2),
    "N": Jeton(nombre=6, valeur=1),
    "O": Jeton(nombre=6, valeur=1),
    "P": Jeton(nombre=2, valeur=3),
    "Q": Jeton(nombre=1, valeur=8),
    "R": Jeton(nombre=6, valeur=1),
    "S": Jeton(nombre=6, valeur=1),
    "T": Jeton(nombre=6, valeur=1),
    "U": Jeton(nombre=6, valeur=1),
    "V": Jeton(nombre=2, valeur=4),
    "W": Jeton(nombre=1, valeur=10),
    "X": Jeton(nombre=1, valeur=10),
    "Y": Jeton(nombre=1, valeur=10),
    "Z": Jeton(nombre=1, valeur=10),
    JOKER: Jeton(nombre=2, valeur=0),
}

#: Nombre total de jetons du sac officiel français.
TOTAL_JETONS = 102


def constituer_sac() -> list[str]:
    """Construit la liste complète et déterministe des 102 jetons initiaux.

    Chaque jeton est une chaîne d'un caractère : une majuscule ``"A"``–``"Z"``
    pour une lettre ordinaire, ou :data:`JOKER` (``"*"``) pour un joker. La liste
    est ordonnée (lettres dans l'ordre de :data:`REPARTITION`) et **non
    mélangée** : le mélange et le tirage relèvent d'un futur module de jeu.
    """
    sac: list[str] = []
    for symbole, jeton in REPARTITION.items():
        sac.extend([symbole] * jeton.nombre)
    return sac


def valeur_lettre(lettre: str) -> int:
    """Renvoie la valeur en points d'une lettre (``0`` pour un joker).

    ``lettre`` doit être une majuscule ``"A"``–``"Z"`` ou :data:`JOKER`.

    :raises ValueError: si ``lettre`` n'est pas une lettre valide de l'alphabet
        français (majuscule A-Z) ni le joker.
    """
    try:
        return REPARTITION[lettre].valeur
    except (KeyError, TypeError):
        raise ValueError(
            f"Lettre invalide : {lettre!r} ; attendu une majuscule 'A'-'Z' "
            f"ou le joker {JOKER!r}."
        ) from None
