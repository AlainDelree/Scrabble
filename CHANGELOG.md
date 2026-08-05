# Changelog — Projet Scrabble

Convention d'ajout : voir §10 de BRIDGE_AGENT_DOC.md.

Historique des changements notables, par ordre antéchronologique. Voir aussi
`git log` pour le détail commit par commit (convention `Issue #NNN : ...`).

## Non publié

### Ajouté

- **Issue #362** — `scripts/mesurer_force_niveaux.py` : script de mesure
  manuel (hors suite pytest) de la force relative de deux niveaux IA sur des
  parties complètes jouées l'une contre l'autre dans la **même** partie (même
  sac au départ, même tirage d'ordre), seul moyen d'isoler l'effet de la
  stratégie du bruit du tirage. Déterministe (toute l'aléa d'une partie dérive
  d'une graine unique, y compris un `random.Random` distinct par joueur IA) :
  deux exécutions identiques donnent des résultats identiques, ce qui permet
  de comparer deux runs avant/après un changement de calibrage
  (`_MALUS_LONGUEUR`, `_BONUS_PREMIUM`). Affiche une progression (parties
  jouées, temps écoulé, restant estimé) et un résumé avec taux de victoire par
  niveau (intervalle de confiance à 95 %), score moyen, écart moyen, matchs
  nuls et répartition de qui a commencé (avec alerte si déséquilibrée).
  Export CSV optionnel (une ligne par partie). Complète
  `tests/test_moteur_ia.py`, qui mesure le score moyen par coup sur des
  positions figées mais rien sur une partie complète (score cumulé, milieu de
  partie riche en hooks — contexte des issues #359/#361).

### Modifié

- **Issue #364** (suite de #363) — Historique diffusé allégé en trois paliers
  de chargement à la demande, pour supprimer la principale source de
  croissance non bornée de la charge poussée à chaque diffusion continue
  (suspectée de contribuer au `SyntaxError: Unexpected end of script` de fin
  de partie observé dans #363, non reproduit). `etat_public()` (`jeu.py`)
  n'expose plus l'intégralité de l'historique : seul un compteur
  (`nb_historique`) et un résumé minimal du dernier coup seul
  (`dernier_coup`, taille bornée, nécessaire à l'animation de pose et à la
  surbrillance du dernier coup) subsistent. La liste des coups sans détail
  se charge désormais à la demande via `ApiJeu.obtenir_historique()` (au
  dépliage du panneau « Derniers coups »), et le détail du score d'une
  entrée via `ApiJeu.obtenir_detail_coup(index)` (au clic sur une ligne).
  Mesuré sur une partie IA de 29 coups (dictionnaire réel) : le payload de
  `etat_public()` passe de ~26,4 Ko à un plateau constant d'environ 15,2 Ko,
  indépendant de la longueur de la partie (contre une croissance linéaire
  avant correctif). `MixinDiffusion._pousser` (`api_diffusion.py`)
  journalise désormais la taille de chaque script poussé en **octets UTF-8**
  avant l'appel `evaluate_js`, pour disposer d'une mesure réelle si le bug
  venait à se reproduire. `jeu.js` adapté en conséquence (rafraîchissement
  de la liste au dépliage et après une diffusion si le panneau est déjà
  ouvert, chargement du détail au clic).

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

- **Issue #364** (suite de #363) — `ApiJeu.faire_jouer_ia()` protégé contre les
  appels concurrents : un drapeau `_ia_en_cours`, posé en tête de méthode et
  remis à zéro dans un bloc `finally` (y compris en cas d'exception),
  refuse tout second appel reçu pendant qu'un premier est encore en cours.
  Le JS désactivait déjà le bouton « ▶ Jouer » cliqué, mais le panneau du
  joueur courant est reconstruit à chaque diffusion (`jeu.js`) — un bouton
  neuf et actif pouvait donc réapparaître avant la réponse de l'appel en
  vol, permettant à des clics rapides répétés de déclencher deux tours IA en
  parallèle. `jeu.js` désactive désormais tous les boutons « ▶ Jouer »
  présents pendant l'attente (pas seulement celui cliqué), doublé d'un
  drapeau JS ignorant tout clic pendant qu'une requête est déjà en vol —
  défense en profondeur en complément du verrou côté Python.

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
