# Installeur Windows (Inno Setup)

Ce dossier contient le script Inno Setup qui produit le `setup.exe`
autonome du jeu Scrabble (issue #217, issue A). **Les `setup.exe` générés ne
sont jamais commités dans le dépôt git** (volumineux, régénérables à tout
moment à partir du build PyInstaller + de ce script) : seuls `scrabble.iss`
et ce `README.md` sont suivis par git.

## Dépendances externes à déposer manuellement (nouveau clone/poste)

`build\rebuild_scrabble.bat` vérifie sa présence en étape 0 et s'arrête
immédiatement si elle manque. Sur un nouveau clone ou un nouveau poste de
build, déposez-la avant de lancer un build complet :

- `.tools\InnoSetup6\ISCC.exe` — installation portable d'Inno Setup 6 (voir
  section Prérequis ci-dessous). Non suivi par git (`.gitignore` ignore
  `.tools\`).

## Dictionnaires : absents du build et de l'installeur (issue #460)

Contrairement à avant l'issue #460, **`data\dictionnaire\` n'est pas une
dépendance de ce build** : le dépôt du jeu étant public et l'updater
Actualise téléchargeant les mises à jour sans identifiant, aucun fichier de
`data\dictionnaire\` (dictionnaires tiers ODS8/Hunspell, définitions, mots
courants, caches, personnalisations, belgicismes) n'est embarqué ni dans
`Scrabble-Setup.exe`, ni dans l'archive `scrabble-vN.zip` d'Actualise (voir
`scrabble.spec`). `rebuild_scrabble.bat` ne vérifie donc plus sa présence
avant de lancer un build (il affiche un simple message d'information en
étape 0, et PyInstaller ne regarde même plus ce dossier).

Ces données sont déposées **à la main par Alain**, après installation, dans
le dossier `data` situé à côté de `Scrabble.exe` (voir
`data\dictionnaire\README.md` pour le détail complet et la justification —
licence floue, contenu tiers non redistribuable). L'installeur affiche un
rappel de cet emplacement exact à la fin de l'installation. Les mises à jour
ultérieures via Actualise ne touchent pas à ces données (elles ne
suppriment que les chemins listés dans le manifeste de l'archive, qui ne
contient jamais de chemin `data\dictionnaire`) : un poste déjà équipé garde
ses dictionnaires d'une mise à jour à l'autre, et une désinstallation ne les
efface plus non plus (voir `[UninstallDelete]` dans `scrabble.iss`).

## Quel script lancer

Le pipeline complet (venv, PyInstaller, ISCC) est dans `build\rebuild_scrabble.bat`.
Ce script ne s'arrête jamais sur une interaction (aucun `pause`, aucune
dépendance à une variable d'environnement) : c'est celui à utiliser en
contexte automatisé (service CCW-Watcher).

Pour un lancement manuel par Alain (double-clic ou terminal interactif),
utiliser `build\rebuild_scrabble_manuel.bat` : il appelle
`rebuild_scrabble.bat`, propage son code de sortie, puis fait un `pause`
inconditionnel pour garder la fenêtre ouverte le temps de lire le résultat.

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
