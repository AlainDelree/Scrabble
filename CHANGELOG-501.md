# Changelog — Issue #501

## Build

- **Build Windows v15 publié, avec relevé des versions de paquets Python installées par le script de build (issue #501).**
  - `build\rebuild_scrabble.bat --publier --build 15` lancé depuis la racine du worktree ; `version.json` passe au build 15 avec le SHA-256 de `scrabble-v15.zip`, recalculé et identique à la valeur écrite par le script.
  - `manifest.json` à la racine de l'archive : premiers octets `7B 22 62` (pas de BOM), contenu `{"build": 15, "supprimer": []}`.
  - Archive : 77 fichiers, aucun fichier de dictionnaire (confirmé conforme à l'issue #460/#481). Tailles quasi stables par rapport au build 14 (installeur +0,09 %, archive +0,08 %), à mettre en regard du +0,6 % constaté au build 14 — l'environnement `.venv_build` étant recréé à chaque build sans version figée dans `requirements.txt` (`pywebview`, `pyinstaller`, `pytest`, `spylls` sans borne ; `pythonnet` borné en plage `>=3.0.0rc1,<4.0` seulement), deux builds peuvent embarquer des versions de paquets légèrement différentes. Relevé complet des versions installées au build 15 consigné dans le rapport de clôture de cette issue, en vue d'une issue ultérieure de figement de `requirements.txt`.
  - Avertissements PyInstaller : les deux `WARNING: Hidden import "pycparser.lextab"/"pycparser.yacctab" not found!` habituels, sans impact.
