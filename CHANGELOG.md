# Changelog — Projet Scrabble

Convention d'ajout : voir §10 de BRIDGE_AGENT_DOC.md.

Historique des changements notables, par ordre antéchronologique. Voir aussi
`git log` pour le détail commit par commit (convention `Issue #NNN : ...`).

## Non publié

### Corrigé

- **Issue #345** — `build/rebuild_scrabble.bat` ne téléchargeait pas
  `Actualise.exe` (dépendance de l'installeur, chemin attendu
  `C:\Temp\ScrabbleBuild\Actualise.exe`) et ne produisait pas `scrabble.zip`
  (archive de mise à jour consommée par l'updater), seulement
  `Scrabble-Setup.exe`.

  Deux étapes ajoutées au script (renumérotation `[n/7]` → `[n/9]`) : une
  nouvelle étape 6 (avant ISCC) télécharge `actualise.zip` depuis
  `github.com/AlainDelree/Actualise/releases/download/v1/actualise.zip` via
  `Invoke-WebRequest`, l'extrait et copie `Actualise.exe` vers
  `C:\Temp\ScrabbleBuild\Actualise.exe`, avec vérification `errorlevel` à
  chaque sous-étape ; une nouvelle étape 8 (après ISCC) écrit
  `manifest.json` (`{"build": 1, "supprimer": []}`) puis zippe
  `dist\Scrabble\*` et `manifest.json` (sans dossier englobant, l'updater
  extrayant directement par-dessus le dossier installé) vers
  `installeur\output\scrabble.zip`. L'étape finale recopie désormais aussi
  `scrabble.zip` vers `%ORIGDIR%\installeur\output\`, en plus de
  `Scrabble-Setup.exe`.

  `installeur\scrabble.iss` n'a pas été modifié : il ne référence
  actuellement aucun `Actualise.exe` dans sa section `[Files]`, et la tâche
  portait explicitement sur `rebuild_scrabble.bat` seul. Script non testé à
  l'exécution (pas d'environnement Windows/cmd.exe disponible côté agent) ;
  la syntaxe PowerShell suit le pattern déjà utilisé ailleurs dans le
  fichier.

- **Issue #339** — `scrabble.spec` embarquait tout le contenu de
  `data/dictionnaire/` sans filtre (`collect_tree` = `os.walk` récursif sur
  ce que contenait le disque local au moment du build). Un dump de travail de
  8,2 Go déposé par erreur dans ce dossier (`wiktionnaire-kaikki/`, jamais lu
  à l'exécution) s'est ainsi retrouvé embarqué dans plusieurs builds Windows
  le 31/07/2026, produisant des installeurs de 396 à 421 Mo (au lieu de
  ~26 Mo) en 25+ minutes et 18 Go de disque consommés — deux clones du même
  commit pouvaient produire deux installeurs différents selon l'état local
  non versionné de la machine de build.

  `scrabble.spec` énumère désormais explicitement les éléments de premier
  niveau de `data/dictionnaire/` à embarquer (`ELEMENTS_DICTIONNAIRE` /
  `ELEMENTS_DICTIONNAIRE_TIERS` ; ~87 Mo au total, mesuré le 31/07/2026) au
  lieu de déduire le contenu de l'installeur de ce qui traîne sur le disque.
  Un garde-fou de taille (`SEUIL_TAILLE_DATAS_OCTETS`, 200 Mo) fait échouer le
  build avec le détail des plus gros contributeurs si le total dépasse le
  seuil, et un élément déclaré mais absent du disque produit un avertissement
  (éléments optionnels/régénérables) ou fait échouer le build (aucun
  dictionnaire tiers ODS8/Hunspell trouvé).
