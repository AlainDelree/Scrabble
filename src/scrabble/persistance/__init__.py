"""Sous-paquet persistance : historique et reprise des parties.

Rôle : conserver sur disque, au fil de l'eau, de quoi retrouver l'historique
des parties terminées et **reprendre une partie en cours** après un plantage.
L'implémentation vit dans :mod:`scrabble.persistance.stockage` (SQLite, sans
sérialiser l'état vivant : on ne stocke que la graine et la suite des actions,
et la reprise rejoue ces actions sur le moteur — déterministe).

Distinct de :mod:`scrabble.config`, qui ne gère que les préférences.
"""

from scrabble.persistance.stockage import (
    CHEMIN_DEFAUT,
    STATUT_EN_COURS,
    STATUT_TERMINEE,
    ResumePartie,
    demarrer_suivi,
    enregistrer_action,
    finaliser_partie,
    lister_parties,
    reprendre_partie,
)

__all__ = [
    "CHEMIN_DEFAUT",
    "STATUT_EN_COURS",
    "STATUT_TERMINEE",
    "ResumePartie",
    "demarrer_suivi",
    "enregistrer_action",
    "finaliser_partie",
    "lister_parties",
    "reprendre_partie",
]
