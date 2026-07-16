"""Tirage de prénoms pour les joueurs « ordinateur ».

Terme volontaire : côté interface, on parle d'« ordinateur » plutôt que
d'« IA » (moins intimidant, notamment pour un public plus âgé). Les
identifiants de code du moteur (``Joueur.humain``, ``Niveau``, etc.) ne
changent pas ; seul le texte affiché évolue.

Ce module est du Python pur, testable indépendamment de toute interface.
"""

from __future__ import annotations

import random

# Prénoms francophones courants, mélange masculin/féminin. Une vingtaine
# suffit. « Béatrice » est explicitement exclue de cette liste.
PRENOMS_ORDINATEUR: tuple[str, ...] = (
    "Antoine",
    "Camille",
    "Chloé",
    "Claire",
    "Émile",
    "Étienne",
    "Gabriel",
    "Hugo",
    "Julien",
    "Léa",
    "Louis",
    "Manon",
    "Marc",
    "Marie",
    "Nathalie",
    "Nicolas",
    "Paul",
    "Pauline",
    "Sophie",
    "Sylvie",
    "Thomas",
    "Valentin",
)


class TropDePrenomsDemandes(ValueError):
    """Levée quand on demande plus de prénoms qu'il n'en reste de disponibles."""


def prenoms_disponibles(deja_utilises: set[str] | None = None) -> list[str]:
    """Retourne la liste des prénoms encore attribuables.

    La comparaison avec ``deja_utilises`` est insensible à la casse et aux
    espaces de bordure, afin d'éviter qu'un joueur « Marc » et un « marc  »
    soient considérés comme distincts.
    """
    pris = _normaliser(deja_utilises)
    return [p for p in PRENOMS_ORDINATEUR if p.casefold() not in pris]


def tirer_prenoms(nombre: int, deja_utilises: set[str] | None = None) -> list[str]:
    """Tire ``nombre`` prénoms distincts, hors ceux déjà utilisés.

    - ``nombre`` doit être un entier positif ou nul.
    - Les prénoms de ``deja_utilises`` (comparaison insensible à la casse)
      sont exclus, afin qu'un ordinateur ne porte pas le même nom qu'un
      joueur déjà présent dans la partie.
    - Si ``nombre`` dépasse le nombre de prénoms encore disponibles, une
      erreur explicite (``TropDePrenomsDemandes``) est levée plutôt que de
      planter obscurément ou de boucler indéfiniment.
    """
    if not isinstance(nombre, int) or isinstance(nombre, bool):
        raise TypeError("« nombre » doit être un entier.")
    if nombre < 0:
        raise ValueError("« nombre » ne peut pas être négatif.")

    disponibles = prenoms_disponibles(deja_utilises)
    if nombre > len(disponibles):
        raise TropDePrenomsDemandes(
            f"{nombre} prénoms demandés mais seulement {len(disponibles)} "
            f"disponible(s) (après exclusion des prénoms déjà utilisés)."
        )
    return random.sample(disponibles, nombre)


def _normaliser(deja_utilises: set[str] | None) -> set[str]:
    """Normalise un ensemble de prénoms pour comparaison (casse/espaces)."""
    if not deja_utilises:
        return set()
    return {p.strip().casefold() for p in deja_utilises}
