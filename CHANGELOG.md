# Changelog — Projet Scrabble

Convention d'ajout : voir §10 de BRIDGE_AGENT_DOC.md.

Historique des changements notables, par ordre antéchronologique. Voir aussi
`git log` pour le détail commit par commit (convention `Issue #NNN : ...`).

## Non publié

### Ajouté

- **Issue #371** (lot F, suite de #366/#368/#369/#370) — Dernier lot du
  chantier « vocabulaire par niveau » : Champion du monde devient
  sélectionnable à l'accueil, avec un dégradé à six paliers et les niveaux
  indisponibles désactivés d'emblée.
  - **6ᵉ bouton** : `ui/web/accueil.html` ajoute le bouton « Champion du
    monde » à `.zone-niveaux` ; `ui/accueil.py` complète `NIVEAUX_LABELS`
    (`"Champion du monde": Niveau.CHAMPION_DU_MONDE`, l'exclusion
    documentée depuis le lot D est retirée).
  - **Dégradé à six paliers** (`ui/web/accueil.css`) : les six arrêts
    (fonds, bordures, texte, survol) ont été **recalculés dans leur
    ensemble**, pas seulement complétés d'un sixième — l'ancienne série à
    cinq paliers cachait un défaut : le palier Intermédiaire (`#c9963c`,
    texte foncé) ne respectait PAS le contraste WCAG AA en réalité (4.41:1
    en texte foncé, 2.65:1 en texte blanc, luminance de fond tombant dans
    la zone où aucun des deux textes ne convient). La nouvelle série
    (`#f5e6c8` → `#e3bd6c` → `#d1a352` → `#8a5a1a` → `#5c3d0a` → `#2e1c05`)
    passe ≥ 4.5:1 sur chaque bande, au repos comme au survol, vérifié par un
    calcul de luminance relative WCAG (pas une moyenne). Le survol suit
    désormais uniformément `hover_i = fond_{i+1}` (y compris pour
    Avancé/Expert, qui utilisaient jusqu'ici leur propre bordure) ; `#3d2606`
    (bordure d'Expert, candidat naturel pour le 6ᵉ fond mais déjà utilisé
    comme survol d'Expert dans l'ancienne série) redevient uniquement la
    bordure d'Expert, jamais réutilisé pour Champion du monde.
  - **Niveaux indisponibles** : l'accueil appelle
    `ApiAccueil.obtenir_disponibilite_niveaux()` (exposée par le lot C) **à
    l'affichage**, pas au lancement — un niveau dont le vocabulaire IA est
    absent du disque reste cliquable (pas de `disabled` natif, qui
    empêcherait tout événement clic) mais affiche le message dédié au survol
    (`title`) et au clic (`alert`), via la classe CSS `.niveau-indisponible`.
    Le refus côté Python (`ajouter_ordinateur`) reste en place comme défense
    en profondeur. Champion du monde, sans fichier de vocabulaire, est
    toujours disponible.
  - **Correctif au passage** (`ui/web/jeu.js`) : le badge de niveau affiché
    derrière le prénom d'un joueur ordinateur (fiche panneau) affichait
    « AVANCE » en majuscules et sans accent — la map de libellés n'y
    contenait pas `AVANCE`, défaut antérieur au chantier signalé par le
    rapport du lot D. Complétée avec `AVANCE` → « Avancé » et
    `CHAMPION_DU_MONDE` → « Champion du monde » ; la map homologue
    d'`accueil.js` (déjà correcte pour `AVANCE`) reçoit aussi
    `CHAMPION_DU_MONDE`.
  - **Harnais visuel** : `scripts/_harness_jeu/mock.js` mockait encore
    l'ancien format `etat.historique` avec détail de score embarqué, retiré
    par l'issue #364 — mis à jour vers le format à trois paliers actuel
    (`etat.nb_historique` + `etat.dernier_coup`, `api.obtenir_historique()`
    sans détail, `api.obtenir_detail_coup(index)` à la demande). Signalé
    sans régénération (rendu WebKitGTK non couvert par pytest) : les
    captures de référence `i289..i292_accueil_*` (5 boutons) et les scripts
    `verif_accueil_145.mjs`/`verif_niveaux_119.mjs` (encore bâtis sur
    l'ancienne modale « Ajouter un ordinateur » antérieure à #299, avec un
    mock à 4 niveaux ne couvrant même pas Avancé) sont obsolètes et devront
    être régénérés/réécrits séparément.
  - Tests : nouveau fichier `test_accueil_niveaux_visuels.py` (6ᵉ bouton,
    contraste WCAG AA par bande au repos et au survol pour les six paliers,
    monotonie du dégradé, garde-fous paramétrés sur tous les membres de
    `Niveau` pour les deux maps JS de libellés, consommation JS de
    `obtenir_disponibilite_niveaux`). `test_accueil.py` :
    `test_tous_les_niveaux_ont_un_label` perd son exclusion de
    `CHAMPION_DU_MONDE` (garde-fou complet, sur le modèle du lot D) ;
    `test_labels_attendus` couvre Avancé et Champion du monde. Suite
    complète : 874 tests verts.

- **Issue #370** (lot E, suite de #366/#369) — Suppression du réglage global
  « vocabulaire humain » (issue #206), devenu redondant et contradictoire
  depuis le lot C (#369) : chaque niveau joue désormais sur son propre palier
  de vocabulaire, et la case décochée (défaut historique du réglage avant
  #342) faisait retomber **tous** les niveaux sur l'ODS8 complet, annulant
  toute la différenciation introduite par le lot C. `config.py` : clé
  `vocabulaire_humain` retirée de `CONFIG_DEFAUT` et de `CLES_BOOLEENNES`.
  `ui/accueil.py` : `_construire_trie_ia` construit désormais
  inconditionnellement le mapping des niveaux présents (fin de la branche
  « réglage désactivé → mapping vide ») ; `_disponibilite_niveau` ne dépend
  plus que de la présence du fichier de vocabulaire du palier ;
  `obtenir_reglages_generaux` n'expose plus la clé. Écran d'accueil
  (`ui/web/accueil.html`/`.js`) : case à cocher, texte d'aide et gestionnaire
  JS retirés. Le repli défensif sur le dictionnaire complet pour un niveau
  absent du mapping (`Partie.__init__`/`jouer_tour_ia`) n'est PAS touché : il
  reste le filet de sécurité générique (mapping `None`, ou niveau non couvert
  par un futur ajout), indépendamment de tout réglage désormais.
  Risque principal validé (rapport #366) : une `config.json` **existante**
  contenant encore la clé (celles d'Alain, de sa mère et de Béatrice
  l'avaient toutes) se charge sans planter ni la réintroduire — la clé
  orpheline est traitée comme toute clé inconnue par la config
  auto-réparante (`_fusionner_defauts` ne construit `config` qu'à partir de
  `CONFIG_DEFAUT.items()`, et marque `doit_reparer=True` dès qu'une clé du
  fichier n'en fait pas partie), donc silencieusement nettoyée au premier
  chargement. Nouveau test dédié
  (`test_config.py::test_vocabulaire_humain_orpheline_ignoree`).
  Tests adaptés/retirés dans `test_reglages.py`, `test_config.py`,
  `test_accueil.py`, `test_jeu_pose.py`, `test_reglages_ui.py` : les tests qui
  testaient spécifiquement le réglage (round-trip booléen, exposition dans
  `obtenir_reglages_generaux`, branche « mapping vide si inactif ») sont
  supprimés ; ceux qui testaient autre chose au passage (disponibilité par
  palier, refus d'un niveau indisponible, reprise d'un niveau devenu
  indisponible, source du dictionnaire jusqu'à la validation d'un coup) sont
  conservés, débarrassés de la clé désormais inerte. Suite complète : 833
  tests verts.
  Non touché (hors périmètre, lot F) : écran d'accueil visuel — 6ᵉ bouton,
  dégradé CSS, boutons désactivés.

- **Issue #369** (lot C, suite de #366/#367/#368) — Résolution du Trie IA par
  niveau : fin du Trie IA unique de `Partie` (verrou structurel identifié par
  le rapport de lecture #366). `scrabble.moteur.ia.resoudre_palier(Niveau) ->
  str | None` résout un niveau vers sa clé de palier (`FICHIERS_VOCABULAIRE_PALIER`),
  `None` pour `CHAMPION_DU_MONDE` (Trie complet, pas de fichier) — placée côté
  moteur pour respecter le sens unique des dépendances établi au lot A
  (`dictionnaire.py` n'importe jamais le moteur ; le moteur peut décrire une
  correspondance vers de simples clés `str` sans importer `dictionnaire.py`).
  `Partie.dictionnaire_ia` (Trie unique) devient `Partie.dictionnaires_ia`
  (mapping `{Niveau: Trie}`) ; `jouer_tour_ia` transmet à `ia.choisir_coup` le
  Trie du **niveau du joueur courant**, avec repli sur `dictionnaire` complet
  pour un niveau absent du mapping (mapping vide par défaut = comportement
  historique inchangé, coût nul). `creer_partie`/`recreer_partie_meme_joueurs`
  et `stockage.reprendre_partie` suivent (paramètre `dictionnaires_ia`) ;
  nouvelle fonction `stockage.niveaux_ia_stockes(id_partie)` qui lit les
  niveaux directement dans le blob JSON stocké, sans reconstruire la partie —
  utilisée par `ApiAccueil.reprendre` pour que les Tries construits à la
  reprise reflètent les niveaux **stockés**, pas la config courante de
  l'accueil.
  `ApiAccueil._construire_trie_ia` construit désormais le mapping des niveaux
  réellement présents à la table (chargement paresseux : au plus 3 IA, donc au
  plus 3 paliers chargés, jamais les six), à la création comme à la reprise ;
  `FICHIERS_CACHE_IA_PALIER[palier]` sert de `chemin_cache` et `palier=palier`
  est transmis à `obtenir_trie_ia` (chemin distinct **et** défense en
  profondeur de l'en-tête, recommandation du lot B). `CHAMPION_DU_MONDE`
  réutilise le Trie complet déjà construit par l'appelant plutôt que d'en
  reconstruire un second. Le réglage « vocabulaire humain » (issue #206)
  continue de tout piloter : désactivé, mapping vide, tous les niveaux sur
  l'ODS8 complet (comportement historique inchangé) ; activé, un Trie par
  palier.
  Vocabulaire manquant (point 5) : nouvelle fonction
  `dictionnaire.paliers_disponibles()` (détecte l'absence, contrairement à
  `lire_liste_mots` qui la tolère silencieusement). `ApiAccueil.ajouter_ordinateur`
  refuse désormais un niveau dont le palier est indisponible dès la sélection
  (pas seulement au lancement), avec le message « <Niveau> en erreur, veuillez
  choisir un autre niveau. Prévenir Alain pour la réparation. » ; nouvelle
  méthode `ApiAccueil.obtenir_disponibilite_niveaux()` qui expose l'info pour
  un futur bouton désactivé d'emblée (rendu visuel laissé au lot F). Pour une
  partie **sauvegardée** dont le niveau est devenu indisponible, `reprendre()`
  renvoie `{"succes": False, "erreur": ...}` (même message) au lieu de
  planter — `ValueError` levée par `_construire_trie_ia` et rattrapée par le
  `except Exception` déjà en place.
  La monotonie `EXPERT < CHAMPION_DU_MONDE` devient **stricte** (le lot D la
  documentait comme égalité temporaire, faute de vocabulaire distinct) :
  `tests/test_moteur_ia.py` simule le câblage réel (Trie restreint pour
  EXPERT, Trie complet pour CHAMPION_DU_MONDE) via un nouveau paramètre
  `dico_champion` de `_moyennes_par_niveau` ; `_PAIRES_EGALITE_ATTENDUE` est
  retirée (plus aucune paire d'égalité attendue) et les mentions « temporaire »
  disparaissent des docstrings de `scrabble.moteur.ia`.
  Mesures `tracemalloc` (que le rapport #366 n'avait pas pu obtenir, sur les
  vraies données ODS8/Lexique présentes sur cette machine, hors dépôt) : Trie
  complet ODS8 (411 430 mots) — 5,5 s de construction, **175,7 Mo** de pic
  mémoire. Trie d'un palier restreint, construit depuis l'ensemble déjà filtré
  — DEBUTANT (16 818 mots) 0,08 s / **6,9 Mo** ; FACILE (21 784) 0,14 s /
  **8,8 Mo** ; INTERMEDIAIRE (32 737) 0,20 s / **12,9 Mo** ; AVANCE (45 335)
  0,39 s / **17,4 Mo** ; EXPERT (112 121) 1,18 s / **41,1 Mo**. Une table à 3
  IA (le pire cas, ex. Débutant + Facile + Expert) charge donc au plus
  6,9 + 8,8 + 41,1 ≈ **57 Mo**, contre 175,7 Mo pour le seul Trie complet et
  ≈263 Mo si les six paliers étaient chargés sans discrimination : le
  chargement paresseux des paliers présents (point 3) est donc largement
  justifié. Le coût dominant du **premier** appel (non caché) est le
  rechargement/normalisation de l'ODS8 depuis disque (`charger_source`, non
  mise en cache mémoire dans `construire_ensemble_ia`, ~4 s) plutôt que la
  construction du Trie lui-même ; le cache disque par palier (lot B) absorbe
  ce coût aux appels suivants (~0,26 s en lecture de cache, mesuré sur le
  palier EXPERT). Le lot D reste correct à ce stade : le lot C ne l'a pas
  invalidé.
  Tests synthétiques uniquement (aucun ODS8/Lexique dans l'environnement
  CCL) : résolution des six niveaux, deux IA de niveaux différents utilisant
  deux Tries distincts (test central du lot), chargement paresseux limité aux
  paliers présents, reprise pilotée par les niveaux stockés, vocabulaire
  manquant signalé sans repli silencieux, monotonie stricte Expert/Champion.
  Non touché (hors périmètre, volontairement) : le réglage `vocabulaire_humain`
  lui-même (lot E) et le rendu visuel de l'écran d'accueil — 6ᵉ bouton,
  dégradé CSS, bouton désactivé (lot F).

- **Issue #368** (lot D, suite de #366) — Ajout de `Niveau.CHAMPION_DU_MONDE`
  au moteur IA (`scrabble.moteur.ia`), en fin d'énumération (rétro-compatible
  avec les parties existantes, sérialisées par `.name` dans `stockage.py`).
  Réutilise EXACTEMENT la stratégie et les tranches de malus/bonus d'EXPERT
  (`_MALUS_LONGUEUR`/`_BONUS_PREMIUM` : -25/+20, sélection du meilleur coup) :
  il ne s'en distinguera par le vocabulaire (ODS8 complet) qu'à partir du lot
  C, câblage explicitement hors périmètre de ce lot. Nouveau test paramétré
  sur tous les membres de `Niveau` (`TestTousLesNiveauxResolventUnCoup`),
  garde-fou structurel contre l'oubli d'un dict indexé par `Niveau` lors d'un
  futur ajout de niveau. Tests de monotonie adaptés pour attendre l'ordre
  `DEBUTANT < FACILE < INTERMEDIAIRE < AVANCE < EXPERT <= CHAMPION_DU_MONDE`
  (égalité Expert/Champion documentée comme temporaire dans la docstring du
  module, levée par le lot C) plutôt que relâchés. Nouveau test paramétré de
  rétro-compatibilité de la sauvegarde (`test_reprise_tous_les_niveaux_ia`,
  `tests/test_persistance.py`) confirmant que `Niveau[niveau]` résout chaque
  membre, y compris le nouveau. CHAMPION_DU_MONDE n'est volontairement PAS
  proposable au joueur à ce stade (écran d'accueil et dégradé CSS réservés au
  lot F) — `tests/test_accueil.py::TestNiveauxLabels::test_tous_les_niveaux_ont_un_label`
  l'exclut explicitement de sa vérification pour cette raison. D'autres
  emplacements indexés par `Niveau` ont été recensés hors périmètre de ce lot
  et non modifiés : `NIVEAUX_LABELS` (`scrabble.ui.accueil`, lot F) et la map
  de libellés JS de `scrabble/ui/web/jeu.js` (celle-ci a un filet de repli qui
  affiche le nom brut de l'enum pour toute clé absente, donc pas de crash ;
  elle manquait déjà `AVANCE` avant ce lot).

- **Issue #366** (lot A, suite de #205/#206) — `scripts/generer_mots_courants.py
  --tous` : produit en une seule commande les cinq fichiers de vocabulaire IA
  par palier de difficulté (`mots_courants_debutant/facile/intermediaire/
  avance/expert.txt`, seuils de fréquence respectifs ≥ 3,0/2,0/1,0/0,5 et
  intersection brute sans seuil pour Expert), avec un récapitulatif des
  effectifs. Le sixième palier, Champion du monde, ne nécessite aucun fichier
  (ODS8 complet, résolu directement vers `obtenir_trie()`). Noms de fichiers
  centralisés dans la nouvelle constante
  `scrabble.dictionnaire.dictionnaire.FICHIERS_VOCABULAIRE_PALIER`, réutilisable
  par le futur lot C (résolution `Niveau` → palier). Fichiers dérivés purs
  (jamais édités à la main) : réécrits systématiquement, sans `--force`,
  contrairement à `classiques_ajoutes.txt`. Ce lot ne touche ni au moteur ni à
  l'UI — seule la génération des fichiers.

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
