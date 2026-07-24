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


class _DicoMots:
    """Dictionnaire de test acceptant uniquement un ensemble de mots donnés."""

    def __init__(self, *mots: str) -> None:
        self._mots = {mot.upper() for mot in mots}

    def contient(self, mot: str) -> bool:
        return mot.upper() in self._mots


def _placement(ligne: int, colonne: int, lettre: str, joker: bool = False) -> dict:
    """Fabrique un placement JS simulé (dict {ligne, colonne, lettre, joker})."""
    return {"ligne": ligne, "colonne": colonne, "lettre": lettre, "joker": joker}


class _FenetreEspionne:
    """Fenêtre pywebview factice qui enregistre les appels ``evaluate_js``."""

    def __init__(self) -> None:
        self.scripts: list[str] = []
        self.detruite = False

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)

    def destroy(self) -> None:
        self.detruite = True


def _partie_simple(graine: int = 42) -> Partie:
    """Petite partie déterministe à deux joueurs (humain + ordinateur)."""
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
    ]
    return Partie(joueurs, _DicoFactice(), graine=graine)
