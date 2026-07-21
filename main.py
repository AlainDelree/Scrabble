"""Point d'entrée unique de l'application packagée (PyInstaller, issue #154).

En développement, ajoute ``src/`` à ``sys.path`` (comme ``pytest.ini`` le fait
via ``pythonpath = src``) puis lance la **coquille mono-fenêtre unifiée**
(``scrabble.ui.application`` — issues #179 à #183). Une fois gelé par
PyInstaller, ``scrabble`` est déjà importable tel quel (collecté par l'Analysis
du ``.spec``) : l'ajout au chemin est sauté.

Bascule vers la coquille unifiée (issue #212). Historiquement, ``main.py``
appelait ``scrabble.ui.accueil.main`` (chemin ``lancer_accueil``/``lancer_jeu``),
qui détruisait la fenêtre Accueil pour recréer une fenêtre Jeu séparée à chaque
transition — d'où un flash visible (fenêtre qui se ferme puis se rouvre) entre
« Lancer la partie » et l'écran de tirage. La coquille unifiée
(``lancer_application_unifiee``) supprime ce flash par construction : **une seule
fenêtre physique** navigue via ``load_url`` au lieu de detruire/recréer, pour
toutes les transitions (accueil↔jeu, retour au menu, recommencer, annuler).

Filet de sécurité : le chemin historique (``lancer_accueil``/``lancer_jeu`` et
``scrabble.ui.accueil.main``) reste présent dans le code, simplement plus
invoqué par défaut — disponible pour un rollback rapide si nécessaire.
"""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from scrabble.ui.application import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
