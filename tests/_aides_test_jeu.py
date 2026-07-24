"""Helpers partagés pour les tests de l'écran de jeu (issue #254).

Ce module contient des classes et fonctions utilisées par plusieurs fichiers
de tests issus du découpage de test_jeu.py. Le préfixe _ évite que pytest ne
le collecte comme un fichier de tests.
"""

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie


class _DicoFactice:
    """Dictionnaire minimal (accepte tout) — l'écran de jeu ne valide rien."""

    def contient(self, mot: str) -> bool:
        return True


def _partie_simple(graine: int = 42) -> Partie:
    """Petite partie déterministe à deux joueurs (humain + ordinateur)."""
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
    ]
    return Partie(joueurs, _DicoFactice(), graine=graine)
