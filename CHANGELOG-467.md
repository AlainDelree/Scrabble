# Changelog — Issue #467

## Modifié

- **`build\rebuild_scrabble.bat` : Inno Setup cherché hors du dépôt, script
  indépendant de l'emplacement du clone.** Étape 0 (vérification des
  dépendances) et étape 6 (compilation) cherchaient `ISCC.exe` uniquement
  dans `.tools\InnoSetup6\` à l'intérieur du dépôt — dossier non suivi par
  git, présent seulement dans le clone principal. Lancé depuis un worktree
  jetable (CCW, qui ne contient que les fichiers suivis par git), le build
  échouait dès cette vérification. Le script cherche maintenant `ISCC.exe`
  dans l'ordre : `C:\CCW\tools\InnoSetup6\ISCC.exe` (nouvel emplacement
  stable du poste, hors dépôt), puis à défaut `.tools\InnoSetup6\ISCC.exe`
  dans le clone (ancien emplacement, toléré pour un build manuel). Erreur
  claire nommant les deux emplacements si aucun des deux n'existe. Le
  compilateur est appelé directement depuis l'emplacement trouvé
  (`%ISCC_EXE%`), sans le recopier vers le dossier de build local — `.tools`
  ajouté aux exclusions du `robocopy` de l'étape 1. Aucun autre
  comportement du script ne change (copie des sources, PyInstaller,
  archive, mode `--publier`, commit local de `version.json`).
- **`installeur\README.md`** : section « Dépendances externes » et
  « Prérequis » mises à jour pour décrire le nouvel ordre de recherche
  d'Inno Setup (emplacement préféré hors dépôt, ancien emplacement toléré).

## Vérifié (sans modification)

- Aucun chemin en dur vers `C:\CCW\scrabble` ou un autre clone trouvé dans
  `build\rebuild_scrabble.bat`, `installeur\scrabble.iss` ni
  `installeur\README.md` (le script ne dépend que de `%~dp0..`, son propre
  emplacement). `CONTEXTE.md` ne mentionne pas l'emplacement d'Inno Setup,
  rien à y aligner.
- Syntaxe batch des lignes modifiées relue attentivement (script non
  exécutable sous Linux) : parenthèses équilibrées, échappement `^(`/`^)`
  dans les `echo` à l'intérieur des blocs `if`, fins de ligne CRLF
  préservées sur tout le fichier (vérifié programmatiquement, aucune ligne
  en LF seul). `git diff --stat` ne montre que les lignes des étapes 0, 1
  (robocopy) et 6, plus la documentation.
- Suite rapide (`pytest -m "not lent"`) : 1404 passed, 5 skipped,
  5 deselected.
