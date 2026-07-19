"""Point d'entrée unique de l'application packagée (PyInstaller, issue #154).

En développement, ajoute ``src/`` à ``sys.path`` (comme ``pytest.ini`` le fait
via ``pythonpath = src``) puis lance l'écran d'accueil, qui enchaîne ensuite
normalement vers l'écran de jeu. Une fois gelé par PyInstaller, ``scrabble``
est déjà importable tel quel (collecté par l'Analysis du ``.spec``) : l'ajout
au chemin est sauté.
"""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from scrabble.ui.accueil import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
