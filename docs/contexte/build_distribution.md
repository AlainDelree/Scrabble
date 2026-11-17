# Build et distribution

À lire avant de toucher `scrabble.spec`, `requirements.txt`, les scripts
sous `build/`, ou le dossier `installeur/`.

## Build PyInstaller

`scrabble.spec`, mode `--onedir` (pas `--onefile` : plus fiable pour une
appli pywebview/EdgeChromium). Sortie dans `dist/Scrabble/`.
`scrabble.config.RACINE_PROJET` bascule sur `sys._MEIPASS` quand
`sys.frozen` est vrai, dossier de l'exécutable lui-même en `--onedir` (pas
nettoyé à la sortie) : les fichiers écrits à l'usage (`config.json`,
`logs/`, `data/parties.db`, personnalisations du dictionnaire)
persistent d'un lancement à l'autre.

`data/dictionnaire/` n'est **pas** embarqué dans le build ni dans
l'installeur : le dépôt est public et l'updater externe Actualise
télécharge les mises à jour sans authentification. Les dictionnaires
tiers sont déposés à la main par Alain sur chaque poste après
installation (voir `data/dictionnaire/README.md` et
`docs/contexte/donnees_dictionnaire.md`).

## Build Windows et installeur

`build/rebuild_scrabble.bat` (`--publier`, `--build N`) : construit dans
un environnement virtuel dédié (`.venv_build`, dépendances de
`requirements.txt`), lance PyInstaller puis compile l'installeur Inno
Setup (`installeur/scrabble.iss`, binaire ISCC recherché hors dépôt).
Produit `installeur/output/Scrabble-Setup-vN.exe` et
`installeur/output/scrabble-vN.zip` (ce dernier avec `manifest.json`,
consommé par l'updater Actualise) — dossier ignoré par git, et une copie
est aussi faite vers un dossier fixe hors du worktree (chemin en dur dans
le script) pour survivre à la suppression du worktree. `version.json`
(racine du dépôt, `{"build": N, "sha256": "..."}`) n'est écrit que par
`--publier`, jamais à la main.

L'updater Actualise (outil externe, dépôt séparé) dépose un fichier
`actualise_update.flag` à côté de l'exécutable installé ; il est lu par
`scrabble/actualise.py` au démarrage et à la fermeture.

## Dépendances (`requirements.txt`)

Versions **figées** (`==` strict) aux versions relevées lors du build v15
(environnement de build recréé à neuf) : `pywebview` (UI), `pyinstaller`
(build), `pytest` (tests), `spylls` (dépliage Hunspell, requis seulement
pour la source « hunspell »), plus les dépendances transitives Windows de
`pywebview` (dont `pythonnet`, épinglée en 3.x). Toute mise à jour de ce
fichier doit être volontaire (nouveau relevé explicite), jamais une
dérive au fil des recréations de l'environnement.
`tests/test_requirements_figees.py` vérifie que chaque dépendance du
fichier utilise bien `==` (garde-fou purement syntaxique, ne lance ni pip
ni accès réseau).
