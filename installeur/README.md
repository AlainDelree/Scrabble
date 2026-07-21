# Installeur Windows (Inno Setup)

Ce dossier contient le script Inno Setup qui produit le `setup.exe`
autonome du jeu Scrabble (issue #217, issue A). **Les `setup.exe` générés ne
sont jamais commités dans le dépôt git** (volumineux, régénérables à tout
moment à partir du build PyInstaller + de ce script) : seuls `scrabble.iss`
et ce `README.md` sont suivis par git.

## Prérequis

1. [Inno Setup 6](https://jrsoftware.org/isdl.php) installé (ou disponible en
   portable, `ISCC.exe` — le compilateur en ligne de commande). Installation
   silencieuse : `innosetup-6.x.x.exe /PORTABLE=1 /VERYSILENT /SUPPRESSMSGBOXES
   /SP- /NORESTART /DIR="<dossier cible>"` (mode portable : pas de droits
   admin, pas d'entrée registre/désinstalleur Windows).
2. `dist\Scrabble\` doit déjà exister, généré par le build PyInstaller
   existant (`pyinstaller scrabble.spec`, depuis la racine du dépôt — voir le
   docstring de `scrabble.spec`). Le script `.iss` ne déclenche pas ce build
   lui-même ; l'intégration au pipeline (`rebuild_scrabble.bat`) est traitée
   dans l'Issue B, à venir.

## Contenu attendu de `dist\Scrabble\` avant compilation

Vérifiez que `dist\Scrabble\` provient d'un build PyInstaller propre, **sans**
fichiers de test générés par un lancement manuel de l'exécutable gelé sur la
machine de build (`config.json`, `data\parties.db`, contenu de `logs\`) : ces
fichiers sont explicitement exclus par `scrabble.iss` (voir la section
`[Files]`, directive `Excludes`) pour éviter qu'un nouvel utilisateur hérite
des préférences ou de l'historique de parties de quelqu'un d'autre dès la
première ouverture — mais autant partir d'un `dist\Scrabble\` propre pour
éviter toute confusion.

## Compiler

Depuis la racine du dépôt (ou depuis ce dossier) :

```
ISCC.exe installeur\scrabble.iss
```

Produit `installeur\output\Scrabble-Setup.exe` (dossier `output\` gitignoré,
voir ci-dessous).

## Résultat de l'installation

`Scrabble-Setup.exe` installe le jeu dans `%LOCALAPPDATA%\Programs\Scrabble`,
**sans droits administrateur** (`PrivilegesRequired=lowest`), avec raccourcis
Bureau et menu Démarrer pointant vers `Scrabble.exe`, et un désinstalleur
standard (entrée dans "Applications" de Windows 11).

## Règle git

Le `.gitignore` à la racine ignore `installeur\output\` (les `setup.exe`
générés) ainsi que `.tools\` (l'installation locale d'Inno Setup elle-même,
si utilisée en mode portable) : seuls `scrabble.iss` et ce `README.md` sont
suivis par git. Vérifiez avec `git status` qu'aucun `.exe` généré n'apparaît
comme non suivi avant de committer.
