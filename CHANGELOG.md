# Changelog — Projet Scrabble

Convention d'ajout : voir §10 de BRIDGE_AGENT_DOC.md.

Historique des changements notables, par ordre antéchronologique. Voir aussi
`git log` pour le détail commit par commit (convention `Issue #NNN : ...`).

## Non publié

### Modifié

- **Issue #359** — Stratégie IA : ajout d'un score stratégique de tri
  (`_score_strategique` dans `moteur/ia.py`), distinct du score réel du coup,
  corrigeant deux biais du tri glouton sur score brut : pénalité sur les
  coups posant peu de lettres (`nb_nouvelles <= 2`, malus doublé pour un
  « hook » d'une seule lettre) et bonus pour les coups exploitant une case
  premium (plein bonus pour MOT_DOUBLE/MOT_TRIPLE/CENTRE, moitié pour les
  bonus de lettre). Les deux ajustements croissent avec le niveau
  (`_MALUS_LONGUEUR`, `_BONUS_PREMIUM`). `moteur/generateur.py` expose
  désormais `nb_nouvelles` (nombre de cases nouvellement posées) dans
  `CoupNote` pour permettre ce tri, les cases bonus étant déjà portées par
  `DetailMot`. Entrée rétroactive : le travail avait été committé sous les
  libellés `avant-issue-359-*` (7efd0d5) sans entrée CHANGELOG. NB : le
  filtre dur `nb_nouvelles >= 3` que #359 avait donné à DEBUTANT a été
  remplacé par l'issue #361 (voir ci-dessous).

### Corrigé

- **Issue #361** — Monotonie des niveaux IA rétablie. Le filtre dur
  `nb_nouvelles >= 3` introduit par #359 pour DEBUTANT le rendait plus
  sélectif que FACILE sur ce critère : sa moyenne pouvait dépasser celle de
  FACILE (une joueuse choisissant « Débutant » pouvait affronter une IA plus
  forte qu'en « Facile »), et le test `test_score_moyen_superieur_a_debutant`
  avait été relâché pour tolérer la rupture. DEBUTANT passe désormais par le
  même mécanisme de tranche que les autres niveaux : tirage uniforme dans le
  top 85 % des coups triés par score stratégique (`max(1, len(coups) * 85 //
  100)`). La chaîne d'inclusion des tranches redevient stricte (85 % ⊃ 60 %
  ⊃ 33 % ⊃ 15 % ⊃ meilleur), ce qui rend la monotonie
  `DEBUTANT < FACILE < INTERMEDIAIRE < AVANCE < EXPERT` structurelle ; le
  malus longueur (-5) de DEBUTANT devient opérant (les hooks les plus
  faibles tombent dans les 15 % écartés). L'assertion complète
  `moy_debutant < moy_facile < moy_inter` est rétablie, et les fixtures de
  `TestProgressionTrieIaRestreint` incluent désormais des mots de 2 lettres
  (courants dans le vocabulaire « humain » : ON, OR, AS, AN, OS ; obscurs
  dans le seul dico complet : RA, OC, NA, TA, SA) pour que la monotonie soit
  réellement éprouvée en présence de hooks — elle était auparavant
  trivialement satisfaite par artefact de fixture (aucun mot < 3 lettres).
  Écarts mesurés entre niveaux adjacents (400 tirages, dico restreint) :
  1.20 / 1.48 / 2.06 / 3.37 points — tous ≥ 1.0, seuil 85 % retenu sans
  ajustement.

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
