# Changelog — Projet Scrabble

Convention d'ajout : voir §10 de BRIDGE_AGENT_DOC.md.

# Changelog — Issue #465

## Corrigé

- **`CONTEXTE.md` : phrase obsolète sur le dictionnaire comme prérequis de
  build.** La section « Données » décrivait encore le dépôt du dictionnaire
  ODS8/Hunspell comme nécessaire « avant tout build », avec l'ancien
  comportement « le jeu démarre mais valide zéro mot ». Depuis l'issue #460,
  le dictionnaire n'est plus du tout lu par le build (`scrabble.spec`) ; et
  depuis l'issue #463, son absence empêche carrément de démarrer/reprendre
  une partie (au lieu de démarrer en validant zéro mot). Phrase corrigée en
  conséquence.

## Vérifié (sans modification)

- **`build\rebuild_scrabble.bat` étape 0** : la vérification de
  `data\dictionnaire\French-Scrabble-ODS8-main` visée par cette issue avait
  déjà été retirée par l'issue #460 (commit `e3f44b2`), remplacée par un
  message d'information et la vérification d'Inno Setup conservée. Rien à
  changer dans ce fichier.
- **`installeur\README.md`** et **`data\dictionnaire\README.md`** :
  présentent déjà correctement le dictionnaire comme nécessaire pour jouer,
  pas pour builder (section « Dictionnaires : absents du build et de
  l'installeur », issue #460). Rien à changer.
- **Contrôle de sécurité** : `git ls-files data/dictionnaire` ne retourne
  que `data/dictionnaire/README.md` — aucun dictionnaire, liste de mots,
  cache `.pkl` ni fichier de définitions suivi par git. `.gitignore` ignore
  `data/dictionnaire/*` en bloc (sauf le README) et
  `data/personnages/lettre_mots_meral.txt` nommément. Aucun fichier de ce
  type dans `installeur/` (seuls `scrabble.iss` et `README.md` suivis), ni
  listé dans `scrabble.spec` (`datas` ne contient que l'icône et
  `src/scrabble/ui/web/`) ni dans `installeur\scrabble.iss`.

# Changelog — Issue #464

## Ajouté

- **Marqueur pytest `lent` et exclusion propre des échecs dépendant de
  l'environnement, documentés dans `CONTEXTE.md`.** Chaque issue forçait
  CCL à lancer la suite deux fois (code d'origine puis le sien) pour
  prouver que cinq échecs systématiques dans les dossiers de travail
  isolés étaient préexistants — 4 à 7 minutes perdues à chaque fois.

  - **`pytest.ini`** : déclaration du marqueur `lent` (tests > 8 s).
  - **`tests/test_moteur_ia.py`** : marqueur `@pytest.mark.lent` sur les
    quatre tests de `TestProgressionTrieIaRestreint` (12 à 44 s, simulations
    de parties complètes) et sur `test_expert_score_moyen_entre_intermediaire_et_avance`
    (~7,4 s ici, 9-15 s rapportés sur le poste d'Alain). Ces tests restent
    dans la suite complète ; `-m "not lent"` les exclut désormais (24,9 s
    contre 137,1 s pour la suite complète, mesuré en séquentiel sans
    `pytest-xdist`).
  - **`tests/_aides_test_environnement.py`** (nouveau) : helper
    `palier_vocabulaire_indisponible(nom_palier)`, vrai quand le fichier de
    vocabulaire IA d'un palier est absent du disque (`data/dictionnaire/`
    gitignoré, fourni manuellement — absent d'un dossier de travail isolé).
  - **`tests/test_accueil.py`** : `test_infos_tirage_memorisees` ignoré
    (raison explicite) si le palier `intermediaire` est indisponible —
    cause réelle : `ApiAccueil.ajouter_ordinateur("Intermédiaire")` refuse
    silencieusement (vocabulaire IA absent), donc la table ne compte jamais
    les 3 joueurs attendus.
  - **`tests/test_journal_integration.py`** : `test_ajout_ordinateur_journalise`
    (palier `facile`) et `test_lancer_partie_journalise_avec_nb_joueurs`
    (palier `intermediaire`) ignorés pour la même cause — aucun ordinateur
    n'est réellement ajouté, donc rien n'est journalisé.
  - **`tests/test_application.py`** : `test_methode_propre_au_jeu_hors_vue_leve_attribute_error`
    et `test_parcours_complet_une_seule_session_et_fermeture` ignorés si le
    `theme_plateau` lu dans le `config.json` réel du poste (non mocké) n'est
    pas `"classique"`. Cause réelle, distincte des hypothèses de l'issue
    (interface graphique/dictionnaire) : voir note ci-dessous.
  - **`CONTEXTE.md`** : nouvelle section « Tests » (commande par défaut,
    quand relancer la suite complète, interdiction de comparer avec le code
    d'origine sauf échec lié aux fichiers modifiés, `-n auto` optionnel).

## Note — défaut potentiel révélé, non corrigé (hors périmètre de l'issue)

`ApiTirageOrdre.obtenir_theme_plateau()`
(`src/scrabble/ui/api_tirage_ordre.py:214`) retombe sur `"classique"` si la
valeur lue est inconnue, mais le défaut réel de `theme_plateau` dans
`CONFIG_DEFAUT` (`src/scrabble/config.py:90`) est `"vert"` depuis l'issue
#342. Les deux tests cités ci-dessus attendent `"classique"` et ne passent
sur le poste d'Alain que parce que son `config.json` (gitignoré, jamais
réécrit depuis avant l'issue #342) a conservé l'ancienne valeur — un hasard
d'état local, pas une garantie du code. Signalé sans être corrigé, les
vérifications n'étant pas modifiées (consigne de l'issue).

# Changelog — Issue #463

## Corrigé

- **Dictionnaires absents : message clair au lieu d'un jeu qui valide zéro
  mot ou d'une IA qui passe en silence.** Depuis que les dictionnaires ne
  sont plus embarqués dans l'archive ni dans l'installeur (issue #460), un
  nouveau PC — ou un PC dont `data\dictionnaire\` a été effacé — démarrait
  le jeu normalement tout en validant zéro mot, en violation de la règle
  d'Alain (le joueur humain a accès à tout le dictionnaire de la partie). La
  partie refuse désormais explicitement de démarrer ou de reprendre quand le
  dictionnaire de validation est absent ou vide.

  - **`src/scrabble/dictionnaire/dictionnaire.py`** : nouvelle fonction
    `message_dictionnaire_indisponible(dossier=DOSSIER_DICO)` — message
    convivial en français, sans vocabulaire technique, nommant le dossier
    exact où déposer les données et invitant à contacter Alain.
    `paliers_disponibles()` considère désormais aussi indisponible un
    fichier de vocabulaire de niveau **présent mais vide**
    (`stat().st_size > 0`, simple appel système — aucune lecture de
    contenu, donc aucun coût perceptible), pas seulement un fichier absent.
  - **`src/scrabble/ui/accueil.py`** : `lancer_partie()` et `reprendre()`
    vérifient, juste après `obtenir_trie(source, ...)`, que le Trie renvoyé
    n'est pas vide (`getattr(trie, "taille", None) == 0` — et non `len()`,
    pour rester neutre face aux doubles de test minimaux qui n'exposent que
    `contient()`). Si vide, la création/reprise est refusée avant toute
    autre opération, avec `message_dictionnaire_indisponible()` et une
    entrée `journal.erreur`. Sur un PC dont les données sont présentes (cas
    normal, PC déjà installés), le Trie est non vide et ce contrôle n'a
    aucun effet visible ni coût notable — il réutilise le Trie déjà construit
    par le chemin existant (cache disque inclus), sans lecture
    supplémentaire. Le vocabulaire par niveau (paliers) était déjà contrôlé
    en amont (issue #369, lot C, `_disponibilite_niveau`) : il bénéficie
    automatiquement du renforcement de `paliers_disponibles()` ci-dessus
    (fichier vide désormais traité comme absent), sans changement de code
    supplémentaire côté accueil.
  - **`src/scrabble/moteur/partie.py`** : défense en profondeur dans
    `Partie.jouer_tour_ia` — si l'ordinateur passe son tour (`coup is None`)
    alors que le Trie de son niveau a une `taille` de 0, l'anomalie est
    consignée dans le journal (`journal.erreur`, via l'alias `journal_app`
    pour ne pas masquer la variable locale `journal` du journal de décision
    IA) plutôt que de laisser l'ordinateur passer tous ses tours sans
    aucune trace. Ne change ni le moteur d'IA, ni les réglages par niveau,
    ni le comportement de jeu : seulement un `journal.erreur` en plus dans
    un cas qui ne devrait jamais se produire en pratique (le contrôle de
    l'accueil ci-dessus bloque déjà la création/reprise en amont).
  - **`installeur/scrabble.iss`** et **`data/dictionnaire/README.md`** :
    textes harmonisés — le message de fin d'installation et le README
    décrivent désormais le nouveau comportement (partie bloquée avec
    message, plus « démarre normalement en validant zéro mot »).

  Emplacement du contrôle : au lancement/reprise d'une partie (pas au
  démarrage de l'application), pour rester un garde-fou ciblé sans ajouter
  de vérification à l'ouverture de l'accueil (où rien ne charge encore de
  dictionnaire).

  Moteur d'IA, réglages par niveau et comportement du jeu quand les données
  sont présentes inchangés. 1400 tests avant ce lot : 1395 verts (5 échecs
  préexistants, sans rapport, confirmés par `git stash` : deux dans
  `test_journal_integration.py::TestJournalAccueil`, un dans
  `test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`,
  deux dans `test_application.py`) ; après ce lot, 1409 tests (9 nouveaux),
  1404 verts, mêmes 5 échecs préexistants seuls restants.

# Changelog — Issue #462

## Corrigé

- **Accueil : le sélecteur de personnage et le lien « Les personnages »
  restaient affichés quand l'interface des personnages était censée être
  masquée.** L'issue #461 masque côté serveur l'interface des personnages
  dès que moins de deux personnages sont actifs (`zonePersonnage.hidden =
  true`, `accueil.js`), mais ce masquage restait sans effet visuel à
  l'accueil : le libellé « Personnage du prochain ordinateur : », la liste
  déroulante et le lien « Les personnages » restaient visibles. Cause
  exacte : `.zone-personnage { display: flex }` (`accueil.css`) est une
  règle d'auteur, qui l'emporte toujours sur le `[hidden] { display: none }`
  par défaut du navigateur — une règle UA, structurellement perdante face à
  l'auteur quels que soient la spécificité ou l'ordre des règles.

  - **`src/scrabble/ui/web/accueil.css`** : ajout d'une règle globale et
    durable `[hidden] { display: none !important; }` juste après le reset
    `* { ... }`, plutôt qu'un correctif ciblé sur `.zone-personnage` : tout
    élément masqué de l'accueil (présent ou futur) en bénéficie désormais,
    pas seulement le bloc personnage. `.zone-personnage { display: flex }`
    est inchangée : à deux personnages actifs ou plus, l'accueil s'affiche
    exactement comme avant.
  - **`scripts/_harness_jeu/verif_443_personnages.mjs`** : le mock de l'API
    accueil ne définissait pas `interface_personnages_visible`, lacune
    restée invisible tant que le masquage ne produisait aucun effet
    (issue #461/#462) — l'appel manquant aurait désormais fait échouer le
    clic sur « Les personnages » dans ce harnais. Ajout du mock manquant
    (`async () => true`, cohérent avec les 3 personnages actifs de la
    scène). L'échec résiduel de ce script côté fenêtre « Jeu » (mock
    `interface_personnages_visible` absent de `mock.js`) est préexistant,
    confirmé par `git stash` — hors périmètre de ce lot.
  - **`tests/test_accueil_niveaux_visuels.py`** : nouvelle classe
    `TestMasquageHiddenNonEcraseParLeStyle` (3 tests) — vérifie la présence
    de la règle `[hidden] { display: none !important }`, qu'elle cible bien
    l'attribut nu (pas un sélecteur composé du style
    `.zone-personnage[hidden]`, qui laisserait le même piège ouvert pour un
    futur élément), et que `.zone-personnage` garde son `display: flex`
    normal.
  - **`scripts/_harness_jeu/verif_462_accueil_personnages.mjs`** (nouveau) :
    harnais Playwright (1280×800) qui monte `accueil.html` avec l'API
    mockée pour un seul personnage actif puis pour deux, capture les deux
    écrans et vérifie par `getComputedStyle` que le bloc personnage a
    bien `display: none`/hauteur nulle dans le premier cas et `display:
    flex`/hauteur normale dans le second.

  Suite pytest : 1397 → 1400 tests verts (3 ajoutés), mêmes 5 échecs
  préexistants et sans rapport (confirmés par `git stash`) :
  `test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`,
  `test_application.py::TestRoutageVueActive::test_methode_propre_au_jeu_hors_vue_leve_attribute_error`,
  `test_application.py::TestParcoursCompletUnifie::test_parcours_complet_une_seule_session_et_fermeture`,
  `test_journal_integration.py::TestJournalAccueil::test_ajout_ordinateur_journalise`,
  `test_journal_integration.py::TestJournalAccueil::test_lancer_partie_journalise_avec_nb_joueurs`.

# Changelog — Issue #461

## Modifié

- **Personnages IA : désactivation d'Opportuniste et Titeuf, et masquage
  complet de l'interface liée aux personnages tant que moins de deux
  personnages sont actifs.** Après l'issue #459 (Chasseur de scrabbles et
  Lettré déjà désactivés), Alain décide de ne proposer AUCUN personnage dans
  la première version diffusée : leur effet reste jugé trop discret pour
  être remarqué en jeu. Opportuniste et Titeuf déclarent à leur tour
  `actif=False` — rien n'est supprimé (code, réglages, listes de mots,
  tests de comportement) — et Classique redevient, pour cette première
  diffusion, le seul personnage actif du registre.

  - **`scrabble/moteur/personnages.py`** : `"opportuniste"` et `"titeuf"`
    déclarent désormais `actif=False`, avec un commentaire donnant la raison
    (décision d'Alain) et la procédure de réactivation (repasser à `True`).
    Nouvelles fonctions `nombre_personnages_actifs()` et
    `interface_personnages_visible()` (vrai dès que deux personnages ou plus
    sont actifs) calculées depuis le registre — jamais codées en dur, pour
    que la réapparition de l'interface soit automatique dès qu'un second
    personnage est réactivé. `libelle_choix_accueil`, `libelle_personnage_partie`
    et `lister_personnages` renvoient désormais respectivement chaîne vide,
    chaîne vide et liste vide dès que l'interface est masquée — y compris
    pour une partie sauvegardée qui mentionne un personnage (son profil reste
    résolu normalement, seul l'affichage entre parenthèses disparaît).
    L'accès direct par clé (`obtenir_personnage`, `profil_pour_niveau`,
    `PERSONNAGES[cle]`) reste inchangé, et `scripts/mesurer_force_niveaux.py`
    continue de pouvoir forcer n'importe quel personnage, actif ou non,
    puisqu'il accède au registre directement. Docstring du module mise à
    jour (nouvelle section « Désactivation d'Opportuniste et Titeuf,
    masquage de l'interface »).

  - **`scrabble/ui/accueil.py`** : `ApiAccueil.obtenir_personnages` renvoie
    la liste vide dès que l'interface est masquée. Nouvelle méthode
    `ApiAccueil.interface_personnages_visible()`, exposée au JS pour que
    `accueil.js` masque dès le chargement tout le bloc personnage (sélecteur,
    textes d'explication, lien « Les personnages ») — `accueil.html` donne un
    `id` à ce bloc (`zone-personnage`) sans `hidden` statique, pour que la
    réapparition reste automatique. `ApiAccueil.ajouter_ordinateur` refuse
    toujours un personnage inactif avec un message dédié, inchangé par ce
    lot ; un appel sans `personnage_cle` (Classique par défaut) continue de
    fonctionner normalement.

  - **`scrabble/ui/jeu.py`** : même mécanisme côté écran de jeu — nouvelle
    méthode `ApiJeu.interface_personnages_visible()`, `jeu.js` masque le
    bouton « 🎭 Personnages » dès l'initialisation si moins de deux
    personnages sont actifs.

  - **Comportement de l'ordinateur inchangé** : pour toute nouvelle partie,
    tous les ordinateurs jouent désormais comme Classique à tous les niveaux
    (plus aucun autre personnage n'étant tirable qu'à la réactivation d'un
    second), strictement comme avant l'introduction des personnages (même
    sélection de coup à graine égale, même consommation du générateur
    aléatoire — test explicite sur les six niveaux, déjà présent et
    inchangé par ce lot).

  - **Parties sauvegardées** : une partie sauvegardée avec Opportuniste,
    Titeuf, Chasseur de scrabbles ou Lettré continue de se charger et de se
    jouer avec son profil complet, sans aucune erreur — seul l'affichage
    entre parenthèses après le prénom disparaît, puisque l'interface qui
    l'afficherait est elle-même masquée.

  - **Tests adaptés** (`tests/test_accueil.py`, `tests/test_jeu_personnages.py`,
    `tests/test_moteur_partie.py`, `tests/test_moteur_personnages.py`,
    `tests/test_persistance.py`) : les tests qui supposaient Opportuniste ou
    Titeuf actifs (proposés au sélecteur, tirables par Aléatoire, affichés
    entre parenthèses) sont séparés en deux — un test par défaut (interface
    masquée, plus rien proposé/affiché) et une variante qui réactive
    localement le personnage via `monkeypatch.setitem` (procédure de
    réactivation documentée par le module, jamais de modification de code)
    pour continuer à couvrir le mécanisme générique sous-jacent (restriction
    de niveau/taille de table, tirage, repérage « dans la partie »...).
    Nouveaux tests explicites : interface masquée avec zéro ou un
    personnage actif, visible dès que deux le sont (réactivation simulée) ;
    `obtenir_personnages()` vide côté accueil et jeu par défaut ; parties
    sauvegardées avec Opportuniste et Titeuf rejouables sans erreur
    (`test_reprise_partie_avec_personnage_desactive_se_joue_normalement`
    étendu, nouveau `test_reprise_partie_avec_titeuf_desactive_se_joue_normalement`).
    Aucun test de comportement d'Opportuniste ou de Titeuf n'est supprimé.

  Moteur d'IA, réglages par niveau et personnages eux-mêmes inchangés —
  seule leur activité et l'affichage qui en dépend. 1370 tests avant ce lot :
  1365 verts (5 échecs préexistants, sans rapport, confirmés par
  `git stash` : `test_accueil::test_infos_tirage_memorisees`, deux dans
  `test_application.py`, deux dans `test_journal_integration.py`) ; après ce
  lot, 1400 tests (30 nouveaux), 1395 verts, mêmes 5 échecs préexistants
  seuls restants (voir le rapport de clôture pour le détail).

# Changelog — Issue #460

## Changé

- **Build et installateur : retrait des dictionnaires de l'archive
  publique, désinstallation qui conserve les données déposées à la main.**
  Le dépôt du jeu étant public, Actualise télécharge les mises à jour
  (archive de Release) sans identifiant : tout ce qui y était embarqué était
  donc public. Les dictionnaires et listes de mots de `data/dictionnaire/`
  ne sont désormais plus embarqués ni dans l'archive `scrabble-vN.zip`
  d'Actualise, ni dans `Scrabble-Setup.exe` ; ils sont déposés à la main par
  Alain dans `{dossier d'installation}\data\` sur chaque poste, séparément
  des mises à jour du programme.

  - **`scrabble.spec`** : la fonction `ajouter_elements_dictionnaire`
    (listes `ELEMENTS_DICTIONNAIRE`/`ELEMENTS_DICTIONNAIRE_TIERS`, issue
    #339) est retirée. Plus aucun fichier de `data/dictionnaire/`
    (dictionnaires tiers ODS8/Hunspell, `definitions.json`,
    `mots_courants*.txt`, caches `trie_cache*.pkl`,
    `belgicismes_a_revoir.csv`, personnalisations `mots_ajoutes_*`/
    `mots_retires_*`, `classiques_*`, `README.md`) n'est embarqué. Les
    autres embarquements (ressources de l'interface, icône) sont inchangés ;
    `data/personnages/` n'est pas concerné. La règle qui faisait échouer le
    build si aucun dictionnaire tiers n'était trouvé sur le disque de build
    est supprimée (elle n'a plus de sens, ce script ne lit plus ce dossier)
    et remplacée par un message d'information dans le journal du build
    (`avertir_dictionnaires_non_embarques`). Le garde-fou de taille de
    l'archive (`verifier_taille_datas`/`SEUIL_TAILLE_DATAS_OCTETS`) est
    conservé.

  - **`build/rebuild_scrabble.bat`** : l'étape 0 ne vérifie plus la présence
    de `data\dictionnaire\French-Scrabble-ODS8-main` (elle affiche
    désormais un message d'information équivalent) ; le `robocopy` qui copie
    les sources vers le répertoire de build local exclut maintenant
    `data\dictionnaire` (chemin complet, pour ne pas confondre avec
    `src\scrabble\dictionnaire\`, le code source), devenu inutile à copier
    puisque plus lu par `scrabble.spec`.

  - **`installeur/scrabble.iss`** : la désinstallation ne supprime plus
    `{app}\data` en bloc (section `[UninstallDelete]`) — elle ne touche plus
    ni à `data\dictionnaire\` ni aux fichiers de `data\personnages\` déposés
    à la main (ex. `lettre_mots_meral.txt`, jamais suivi par git), qui
    doivent survivre à une désinstallation ou réinstallation. Les entrées de
    nettoyage pour `{app}\logs` et `{app}\config.json` sont conservées. Un
    message s'affiche désormais à la fin de l'installation
    (`AfficherMessageDictionnaires`) pour rappeler que les dictionnaires ne
    sont pas inclus et doivent être copiés à la main dans `{app}\data\`
    avant le premier lancement.

  - **Documentation** : `data/dictionnaire/README.md` et
    `installeur/README.md` décrivent désormais explicitement ce qui est
    embarqué et ce qui ne l'est pas, l'emplacement où déposer les données
    sur un PC, et le fait que les mises à jour d'Actualise ne touchent pas
    aux données (elle ne supprime que les chemins listés dans le manifeste
    de l'archive, qui ne référence jamais `data/dictionnaire`).

  Comportement du jeu au lancement, chargement des données et personnages
  inchangés. Aucun build Windows n'a été lancé pour cette issue (vérification
  manuelle de l'archive à faire après un build réel, voir le rapport de
  clôture de l'issue).

# Changelog — Issue #459

## Modifié

- **Personnages IA : désactivation de Chasseur de scrabbles et Lettré, code
  conservé pour une réactivation éventuelle.** Après mesure
  (`scripts/mesurer_force_niveaux.py`, parties réellement jouées), l'effet
  des deux personnages est trop discret pour être remarqué en jeu : environ
  0,45 scrabble supplémentaire par partie à Avancé et 0,2 à Intermédiaire
  pour Chasseur de scrabbles, environ deux mots de sa liste par partie pour
  Lettré (mesures du 12 octobre 2026). Alain abandonne les deux — rien n'est
  supprimé (code, constantes de réglage, listes de mots, tests de
  comportement), pour une réactivation éventuelle si une meilleure idée de
  calibrage apparaît. Les personnages qui restent proposés sont Classique,
  Opportuniste, Titeuf et Aléatoire.

  - **`scrabble/moteur/personnages.py`** : nouveau champ facultatif
    `Personnage.actif` (vrai par défaut). Les entrées `"chasseur_de_scrabbles"`
    et `"lettre"` du registre déclarent `actif=False`, avec un commentaire
    donnant la raison et la procédure de réactivation (repasser à `True`).
    `tirer_personnage`, `personnages_disponibles_a_niveau`,
    `personnages_disponibles_a_nb_joueurs` et `lister_personnages` (fenêtre
    « Les personnages ») n'incluent plus désormais que les personnages
    actifs — donc aussi `aleatoire_disponible_a_niveau`/
    `aleatoire_disponible_a_nb_joueurs`, qui ne comptent plus que les
    personnages actifs. Nouvelle fonction `personnage_actif(cle)`. L'accès
    direct par clé (`obtenir_personnage`, `profil_pour_niveau`,
    `PERSONNAGES[cle]`) reste inchangé : un personnage inactif demeure une
    entrée normale du registre, résolue à l'identique — une partie
    sauvegardée qui le mentionne continue de se charger et de se jouer sans
    aucun changement de comportement, et le script de mesure peut toujours
    le forcer explicitement. Docstring du module mise à jour (nouvelle
    section « Désactivation de Chasseur de scrabbles et Lettré »).

  - **`scrabble/ui/accueil.py`** : `ApiAccueil.obtenir_personnages` (sélecteur
    de l'accueil, et fenêtre « Les personnages » à l'accueil qui réutilise
    cette même méthode) n'inclut plus que les personnages actifs.
    `ApiAccueil.ajouter_ordinateur` refuse désormais l'ajout d'un ordinateur
    sur un personnage inactif, avec un message dédié nommant le personnage
    (« <Personnage> n'est pas disponible actuellement. »), contrôle qui
    précède celui de niveau/taille de table.

  - Aléatoire reste disponible à Débutant (Classique + Titeuf) et de Facile
    à Champion du monde (Classique + Opportuniste), à deux joueurs — exactement
    comme avant cette désactivation, Chasseur de scrabbles et Lettré n'ayant
    jamais été les seuls personnages supplémentaires à ces niveaux — et
    indisponible aux autres tailles de table (seul Classique y figure).

  - **Tests adaptés** (`tests/test_moteur_personnages.py`,
    `tests/test_jeu_personnages.py`, `tests/test_accueil.py`,
    `tests/test_moteur_partie.py`) : les tests qui supposaient la présence des
    deux personnages dans le sélecteur, la liste affichée, le tirage
    d'Aléatoire ou la disponibilité par niveau/taille sont mis à jour pour
    refléter leur exclusion (ou, pour un test de pur contrôle de taille de
    table sans rapport avec cette désactivation, réactivés localement via
    `monkeypatch.setitem` le temps du test). Nouveaux tests couvrant
    explicitement l'issue #459 : absence des deux personnages de toute liste
    proposée à tous les niveaux, jamais tirés par Aléatoire sur de
    nombreuses graines, refus de l'ajout avec message clair, résolution de
    profil inchangée pour un personnage inactif (partie sauvegardée jouable
    normalement), et réactivation de l'indicateur dans un test (sans
    modifier le code) qui remet le personnage dans le sélecteur et dans le
    tirage. Aucun test de comportement du Chasseur de scrabbles ou du Lettré
    n'est supprimé.

  Comportement de Classique, Opportuniste, Titeuf et du moteur d'IA
  inchangé. 1360 tests au total : 1355 verts avant ce lot (5 échecs
  préexistants, sans rapport, confirmés par `git stash` :
  `test_accueil::test_infos_tirage_memorisees`, deux dans
  `test_application.py`, deux dans `test_journal_integration.py`) ; après
  adaptation, même compte de tests verts plus les nouveaux (voir le rapport
  de clôture pour le détail), les 5 mêmes échecs préexistants subsistant
  seuls.

# Changelog — Issue #458

## Corrigé

- **Tests des personnages désynchronisés des réglages mesurés, et rendus
  robustes aux futurs réglages.** Après les deux lots de mesure (bonus de
  mot favori du Lettré, 40 → 20 ; part de mots courts connus du Chasseur de
  scrabbles à Avancé, 0,7 → 0,55), six tests de
  `tests/test_moteur_personnages.py` échouaient : certains figeaient
  l'ancienne valeur en dur (`BONUS_FAVORI_LETTRE == 40`,
  `PART_VOCABULAIRE_COURT_CHASSEUR == {... 0.7, ... 0.7}`), d'autres
  construisaient un scénario fabriqué (plateau/chevalet réels) dont l'écart
  de score caché entre le mot favori et le coup concurrent dépendait
  implicitement de l'ancien bonus (40), sans marge suffisante avec le
  nouveau (20) à EXPERT/CHAMPION_DU_MONDE (où les tranches de malus/bonus
  de score stratégique diffèrent d'AVANCE).

  - **`TestPartVocabulaireCourtChasseur.test_valeurs_de_depart`,
    `test_profil_pour_niveau_intermediaire`, `test_profil_pour_niveau_avance`**
    : ne vérifient plus les chiffres exacts, seulement les niveaux couverts
    et le domaine de valeur (une part dans `]0, 1]`), ou comparent au
    contenu actuel de `PART_VOCABULAIRE_COURT_CHASSEUR` plutôt qu'à un
    chiffre écrit en dur.

  - **`TestPersonnageLettre.test_lettre_joue_toujours_le_mot_favori_sur_ce_scenario`**
    et **`TestMotsFavorisLettreComplement.test_lettre_joue_un_mot_du_fichier_complementaire`**
    : nouveau scénario fabriqué CONSTRUIT à partir de
    `bonus_favori` lui-même (nouveaux ``CoupNote`` synthétiques, même
    principe que `_coup_note` dans `test_moteur_ia.py`, sans case bonus ni
    malus de longueur ni reliquat — donc rigoureusement indépendant du
    niveau) : le coup concurrent l'emporte d'exactement
    `bonus_favori - 1` points avant bonus, donc le mot favori l'emporte de
    peu (1 point) une fois le bonus ajouté, quelle que soit sa valeur
    actuelle ou future. La sélection réelle (`_choisir_avance`/
    `_choisir_top5`, selon le niveau) est rejouée sur ces coups triés, pour
    continuer à exercer le même code que `choisir_coup`.

  - **`TestPersonnageLettre.test_lettre_profil_mots_favoris_et_bonus_favori`**
    : retrait de l'assertion `BONUS_FAVORI_LETTRE == 40` (seul le câblage du
    profil sur la constante reste vérifié).

  - **Documentation** : le docstring du module de tests précise désormais
    que les constantes de réglage par personnage sont ajustées par mesure
    et ne doivent jamais être figées dans un test.

  Aucune valeur de réglage ni aucun comportement du jeu n'a été modifié —
  seuls les tests (et leur documentation) ont changé.
  137 tests passent dans `tests/test_moteur_personnages.py` (contre 131
  avant correction, 6 en échec). Sur l'ensemble de la suite : 1281 tests
  verts après correction (1275 avant), les 5 mêmes échecs préexistants et
  sans rapport (`test_accueil`, `test_application`, `test_journal_integration`)
  subsistent, confirmés préexistants.

# Changelog — Issue #457

## Ajouté

- **Tests de garde : le joueur humain a accès à tous les mots du
  dictionnaire de la partie, quel que soit le personnage ou le niveau de
  l'ordinateur.** Lecture de code (`scrabble.moteur.partie.Partie`,
  `scrabble.ui.accueil.ApiAccueil.lancer_partie`, `scrabble.ui.jeu.
  simuler_coup`/`verifier_mot_dictionnaire`) confirmant qu'aucun écart
  n'existe : `Partie.dictionnaire` (le Trie complet construit par
  `obtenir_trie(source, mode_belgicisme=...)`) valide **toujours** un coup,
  humain ou IA, dans `Partie.jouer_coup` → `valider_coup(..., self.
  dictionnaire)` ; `Partie.dictionnaires_ia`/`ProfilPersonnage` (vocabulaire
  par palier, `vocabulaire_long`, `mots_favoris`) ne pilotent QUE la
  génération des coups candidats de l'ordinateur
  (`scrabble.moteur.ia.choisir_coup`), jamais la validation. La boîte
  « Dictionnaire » (`ApiJeu.verifier_mot` → `verifier_mot_dictionnaire`)
  reçoit elle aussi systématiquement `self._partie.dictionnaire`.

  - **`tests/test_garde_dictionnaire_humain.py`** (nouveau, 74 tests) :
    dictionnaires fabriqués (le dictionnaire réel est absent de ce worktree
    isolé). Pour chaque combinaison niveau × personnage disponible du
    registre (`personnages_disponibles_a_niveau`), et pour les deux états
    de l'option belgicismes, vérifie qu'une partie construite avec cette
    configuration d'ordinateur valide un échantillon de mots (vocabulaire
    courant, mot hors vocabulaire restreint, mot favori, mot court, mot de
    7 lettres hors vocabulaire du niveau, mot absent) exactement comme une
    partie sans ordinateur. Vérifie aussi l'identité de l'objet
    `Partie.dictionnaire` (jamais substitué par un Trie restreint) et que
    tout mot réellement joué par Titeuf/Lettré/Chasseur de scrabbles grâce
    à `mots_favoris`/`vocabulaire_long` (donc absent du vocabulaire
    restreint de son niveau) est accepté par cette même validation.

  - **`src/scrabble/moteur/personnages.py`** : nouvelle section dans la
    docstring du module énonçant la règle et renvoyant à
    `data/dictionnaire/README.md`.

  - **`data/dictionnaire/README.md`** : nouvelle section « Le joueur
    humain a accès à tout le dictionnaire (issue #457) ».

  Aucun écart constaté ; aucune modification de comportement du jeu ou des
  personnages. Tests : 1275 → 1349 verts (+74), les 11 échecs déjà présents
  avant ce lot (confirmés par `git stash`, notamment
  `TestPersonnageLettre`/`TestPartVocabulaireCourtChasseur` dans
  `tests/test_moteur_personnages.py`) restent inchangés et hors périmètre.

# Changelog — Issue #455

## Ajouté

- **Personnage Lettré : liste de mots complémentaire locale, hors git.**
  Alain peut maintenant ajouter des mots favoris au Lettré sans qu'ils
  soient publiés dans le dépôt.

  - **`data/personnages/lettre_mots_meral.txt`** (nouveau chemin, jamais
    créé dans le dépôt) : second fichier facultatif, un mot par ligne,
    mêmes règles de normalisation que `lettre_mots_favoris.txt` (accents et
    majuscules normalisés, lignes vides ignorées). Absent ou vide : aucune
    différence avec le comportement d'avant ce lot. Ajouté à `.gitignore`.

  - **`scrabble.moteur.personnages`** : nouvelle fonction
    `charger_mots_favoris_avec_complement(chemin, chemin_complement)`,
    réutilisant deux fois `charger_mots_favoris` existante (fichier absent
    -> ensemble vide pour cette moitié) puis union des deux résultats.
    `MOTS_FAVORIS_LETTRE` est désormais chargée avec cette fonction
    (`CHEMIN_MOTS_FAVORIS_LETTRE` + nouvelle constante
    `CHEMIN_MOTS_FAVORIS_LETTRE_MERAL`) ; le jeu utilise donc l'union des
    deux listes, sans doublon. Titeuf continue d'appeler
    `charger_mots_favoris` seule, comportement inchangé — la nouvelle
    fonction est disponible pour lui ou un futur personnage à liste s'il en
    a besoin plus tard.

  - **Indicateur de style du script de mesure**
    (`scripts/mesurer_force_niveaux.py`) : aucune modification nécessaire,
    il lit déjà `profil.mots_favoris` (qui porte désormais l'union) plutôt
    que la constante du fichier habituel directement.

  - **Tests** (`tests/test_moteur_personnages.py`,
    `TestMotsFavorisLettreComplement`) : fichier absent (résultat identique
    à `charger_mots_favoris` seule), fichier présent (mots pris en compte),
    union sans doublon, mot du complément absent du lexique ignoré sans
    filtrage dédié, et un scénario fabriqué où un mot présent seulement
    dans le fichier complémentaire est joué par le Lettré à Avancé/Expert/
    Champion du monde. Les tests existants de chargement de la liste réelle
    (`TestMotsFavorisLettre`) passent sans modification : le fichier
    complémentaire n'existe pas dans ce worktree isolé.

# Changelog — Issue #454

## Ajouté

- **Personnage Lettré, les mots rares au bonus de score (lot K, Avancé/Expert/
  Champion du monde).** Reprend exactement le mécanisme de Titeuf (lot J,
  issue #452) avec sa propre liste — des mots rares/littéraires plutôt que
  de cour de récré — et ajoute le levier qui manquait pour que le style se
  voie aux niveaux « meilleur coup » (Avancé, Champion du monde), où le
  tirage pondéré de Titeuf n'a par construction aucun effet.

  - **`data/personnages/lettre_mots_favoris.txt`** : liste de mots favoris
    fournie par Alain avant ce lot (2813 mots rares/littéraires croisés
    depuis Lexique 3 et l'ODS8), déjà présente et non vide au démarrage de
    ce lot — non reconstruite.

  - **`scrabble.moteur.ia`** : nouveau champ facultatif de
    `ProfilPersonnage`, `bonus_favori: int | None` (neutre par défaut,
    `None` traité comme 0). Généralise `bonus_scrabble` au critère de LISTE
    de `mots_favoris` : ajoute une constante au score stratégique
    (`_score_strategique`) des coups dont le mot principal est un mot
    favori — seul champ de ce module qui agit sur le score à TOUS les
    niveaux, y compris Avancé/Champion du monde (meilleur coup), puisqu'il
    intervient avant le tri plutôt qu'après comme `poids_tirage_favori`.
    Sans effet tant que `mots_favoris` est vide ou absent ; aucun impact sur
    Titeuf ni sur aucun autre personnage, qui ne renseignent pas ce champ.

  - **`scrabble.moteur.personnages`** : nouvelles constantes
    `BONUS_FAVORI_LETTRE = 40` (calcul détaillé dans le docstring du module
    et le rapport de l'issue, par analogie avec l'échelle de
    `_BONUS_PREMIUM`/`_MALUS_LONGUEUR` déjà en production — le dictionnaire
    réel n'étant pas disponible dans ce worktree isolé pour la mesurer par
    parties jouées), `CHEMIN_MOTS_FAVORIS_LETTRE`, `MOTS_FAVORIS_LETTRE`
    (chargée avec la même fonction `charger_mots_favoris` que Titeuf),
    `PRENOM_LETTRE = "Lettré"`, `NIVEAUX_LETTRE = {AVANCE, EXPERT,
    CHAMPION_DU_MONDE}` (provisoire, à ajuster par Alain après mesure),
    `NB_JOUEURS_LETTRE = {2}`. Nouvelle entrée `"lettre"` dans le registre
    `PERSONNAGES`, sans tirage pondéré (`poids_tirage_favori` non
    renseigné) : le bonus de score suffit sur les niveaux où ce personnage
    est disponible.

  - **Conséquence attendue (règle déjà en place, lot G) :** Avancé, Expert
    et Champion du monde comptaient déjà au moins deux personnages réels —
    aucun changement de disponibilité d'Aléatoire à ces niveaux, qui couvre
    simplement un personnage de plus.

  - **`scripts/mesurer_force_niveaux.py`** : nouvel exemple de commande
    documenté (Lettré contre Classique à Avancé/Expert/Champion du monde,
    200 parties chacune, avec tableau de style) ; l'indicateur de style
    « Coups dont le mot principal est un mot favori » (ajouté par le lot J)
    était déjà générique — aucun changement de code requis, il lit la liste
    propre à chaque joueur via son profil résolu.

  - **Tests** (`tests/test_moteur_ia.py`, `tests/test_moteur_personnages.py`,
    `tests/test_moteur_partie.py`, `tests/test_mesurer_force_niveaux_style.py`,
    `tests/test_persistance.py`) : neutralité du nouveau champ (`bonus_favori`
    absent de tout autre personnage, y compris Titeuf), application du bonus
    à tous les niveaux, nécessité du bonus démontrée sur un scénario fabriqué
    (sans lui, le mot favori perd quand même, malgré l'élargissement des
    coups candidats), choix du mot favori nettement plus fréquent que
    Classique à Avancé/Expert/Champion du monde (niveaux « meilleur coup »),
    mot favori hors vocabulaire du niveau accessible, mot absent du lexique
    ignoré sans erreur, liste indépendante de celle de Titeuf, disponibilité
    (niveaux + deux joueurs), tirage Aléatoire couvrant Lettré à Avancé,
    reprise d'une partie sauvegardée avec un Lettré, indicateur de style
    utilisant bien la liste du Lettré (nouvelle partie type sans coup
    jouable, comme pour Titeuf).

    Un test existant, qui encodait explicitement la liste exacte des
    personnages tirables par Aléatoire à Avancé à deux joueurs
    (`test_creer_partie_aleatoire_peut_tirer_opportuniste_a_deux_joueurs`),
    est mis à jour pour inclure `"lettre"` — cas prévu par les contraintes de
    l'issue. Deux échecs préexistants (calibrage `part_vocabulaire_court` du
    Chasseur de scrabbles, issue antérieure à ce lot, confirmé par
    `git stash`) et cinq autres échecs préexistants variant selon le dossier
    de travail (non liés aux personnages) sont laissés de côté, comme
    convenu.

# Changelog — Issue #453

## Ajouté

- **Part réglable des mots courts connus du Chasseur de scrabbles, par
  niveau (lot H quater).** Les mesures du lot H ter (#451, vocabulaire long
  et tirage pondéré) montraient un style enfin visible (0,14 scrabble par
  partie à Intermédiaire contre 0,01 pour Classique, 0,4 contre 0,11 à
  Avancé) mais trop fort : environ +12 points par partie à Intermédiaire,
  +20 à Avancé contre Classique au même niveau — la règle « un personnage ne
  change pas la force du niveau » n'était plus respectée. Un scrabble
  rapportant beaucoup de points (de l'ordre de 80 en moyenne), ce surplus de
  scrabbles explique une large part du surplus de force ; les mesures du
  curseur `part_vocabulaire_long` à des valeurs intermédiaires (30 à 70 % à
  Intermédiaire, 20 à 50 % à Avancé) montrent qu'aux parts basses, le
  surplus de scrabbles devient à peine visible alors qu'un excédent de force
  de 6 à 9 points subsiste : réduire seulement le vocabulaire long dilue le
  style sans forcément retrouver la neutralité de force. Ce lot prend le
  problème à l'envers, sur proposition d'Alain : garder la connaissance des
  longs mots intacte (100 % aux deux niveaux, remis depuis 50 % à Avancé) et
  faire payer la force du personnage par une MOINS BONNE connaissance des
  mots COURTS — pour qu'il devienne un spécialiste des scrabbles qui joue
  moins bien le reste, un personnage plus marqué et plus cohérent.

  - **`scrabble.moteur.ia`** :
    - Nouveau champ facultatif de `ProfilPersonnage` :
      `part_vocabulaire_court: float | None`, neutre par défaut (`None`,
      traité comme `1.0`). Va dans le sens inverse de
      `part_vocabulaire_long` : au lieu d'ÉLARGIR les coups candidats, il
      RESTREINT l'ensemble déjà constitué (vocabulaire du niveau, plus
      l'éventuel élargissement `vocabulaire_long`/`mots_favoris`) aux coups
      dont le mot principal compte MOINS de 7 lettres
      (`_SEUIL_VOCABULAIRE_LONG`) — ceux-là ne restent candidats que si ce
      mot est « connu » selon la nouvelle fonction privée
      `_mot_connu_vocabulaire_court(mot, part_vocabulaire_court)`. Les mots
      de 7 lettres et plus — du vocabulaire du niveau ou ajoutés par
      `vocabulaire_long` — ne sont JAMAIS filtrés par ce champ.
    - `_mot_connu_vocabulaire_court` reprend EXACTEMENT le procédé de
      `_mot_connu_vocabulaire_long` (hachage SHA-256 stable du texte du mot,
      pas le `hash()` intégré de Python, randomisé d'un processus à l'autre)
      avec un **décalage de hachage distinct** : préfixe `b"court:"` ajouté
      avant hachage. Pour un même mot, le résultat de cette fonction et
      celui de `_mot_connu_vocabulaire_long` sont donc statistiquement
      indépendants — exigence explicite de l'issue, vérifiée par mesure du
      taux d'accord entre les deux sur un grand échantillon de mots
      fabriqués (proche de 50 % à `part = 0.5`, pas de 100 %).
    - `_generer_coups_candidats` applique ce filtre en DERNIER, après les
      deux élargissements `vocabulaire_long`/`mots_favoris` (eux-mêmes
      inchangés) : contrairement à ces deux champs, `part_vocabulaire_court`
      n'a besoin ni de `dictionnaire_complet` ni de `vocabulaire_long`/
      `mots_favoris` actifs pour s'appliquer — un profil qui ne renseigne
      QUE ce champ filtre déjà l'ensemble issu du seul vocabulaire du
      niveau. La fonction a été restructurée pour que ce filtre s'applique
      indépendamment du bloc d'élargissement (lequel reste conditionné à
      `dictionnaire_complet is not None and (vocabulaire_long or
      mots_favoris)`, comportement inchangé).
    - **Garde-fou** (point 2 de l'issue) : si le filtre ne laisse plus aucun
      coup candidat (début de partie, chevalet difficile), il est ignoré
      pour CE TOUR — la liste non filtrée est utilisée à la place plutôt que
      de forcer une passe, qui fausserait la mesure de force du personnage
      (un passage forcé coûte des points et change radicalement la
      dynamique de la partie, sans rapport avec le style réel du
      personnage). Implémenté simplement : la liste filtrée ne remplace la
      liste d'origine que si elle est non vide.
    - Journal de décision et évaluation (point 5) : `evaluer_coups` n'a reçu
      aucune modification — comme pour `part_vocabulaire_long`, le filtre
      est une fonction pure du texte du mot (pas de l'aléa de la partie) et
      vit entièrement dans `_generer_coups_candidats`, appelée par
      `choisir_coup` ET `evaluer_coups` : les deux restent automatiquement
      en phase sur le MÊME ensemble de coups candidats filtré, sans logique
      de cohérence supplémentaire à écrire.
  - **`scrabble.moteur.personnages`** :
    - `PART_VOCABULAIRE_COURT_CHASSEUR = {INTERMEDIAIRE: 0.7, AVANCE: 0.7}` :
      nouvelle constante en tête de module, table niveau → part (comme
      `PART_VOCABULAIRE_LONG_CHASSEUR`) — voir le calcul plus bas.
    - `PART_VOCABULAIRE_LONG_CHASSEUR` remis à `{INTERMEDIAIRE: 1.0, AVANCE:
      1.0}` (AVANCE valait 0.5 depuis le lot H ter) : le style du
      personnage reste donc entier sur le vocabulaire long, c'est le
      nouveau levier ci-dessus qui ajuste la force.
    - Nouveau champ optionnel `Personnage.part_vocabulaire_court_par_niveau`
      (`dict[Niveau, float] | None`, défaut `None`), résolu par
      `profil_pour_niveau` exactement comme `part_vocabulaire_long_par_niveau`
      — les deux tables sont indépendantes et se combinent sans conflit
      (chacune ne touche que le champ de `profil` qui lui correspond),
      c'est le cas du Chasseur de scrabbles qui renseigne les deux
      désormais. `.profil` (accès direct) reste la valeur PLATE, sans
      résolution de niveau, comme pour `part_vocabulaire_long`.
    - `PERSONNAGES["chasseur_de_scrabbles"]` renseigne la nouvelle table
      `part_vocabulaire_court_par_niveau=PART_VOCABULAIRE_COURT_CHASSEUR`.
      `poids_tirage_scrabble` et `poids_leave` du personnage restent
      inchangés (point 3 de l'issue).
  - Aucune modification de `scrabble.ui.jeu` ni de
    `scripts/mesurer_force_niveaux.py` : les deux résolvent déjà le profil
    via `profil_pour_niveau` (lot H ter) — le nouveau champ s'applique donc
    automatiquement, en jeu réel comme en mesure, sans aucun code
    supplémentaire à écrire (point 6 de l'issue : « le script de mesure
    doit suivre le même chemin que le jeu » — déjà vrai par construction).

### Calcul justifiant `PART_VOCABULAIRE_COURT_CHASSEUR = 0.7` (70 %, aux deux niveaux)

Point médian raisonné entre « tout » (comportement actuel du personnage,
trop fort d'après les mesures du lot H ter) et une restriction sévère qui
risquerait de ne plus trouver assez de coups courts pour varier le jeu —
même logique que le point médian 50 % choisi au lot H ter pour
`part_vocabulaire_long` à Avancé. Le dictionnaire réel n'étant pas
disponible dans ce worktree isolé, cette valeur n'a pas pu être mesurée par
parties jouées : point de départ explicitement provisoire, à ajuster par
Alain après mesure réelle (voir les commandes ci-dessous) — objectif de
l'issue : écart de points proche de zéro contre Classique au même niveau,
avec un surplus de scrabbles qui reste visible.

### Neutralité stricte

- Un profil sans `part_vocabulaire_court` (absent, ou `ProfilPersonnage()`
  vide), ou avec `part_vocabulaire_court=1.0`, reproduit bit à bit
  l'ensemble de coups candidats d'avant l'introduction du champ —
  `TestPartVocabulaireCourt.test_part_1_identique_au_comportement_actuel`.
  Le calcul du filtre étant purement déterministe (aucun aléa), la
  consommation du générateur aléatoire de `choisir_coup` est elle aussi
  identique, pour les six niveaux —
  `TestPartVocabulaireCourt.test_neutre_rng_choisir_coup`.
- `part_vocabulaire_court` reste `None` pour Classique, Opportuniste et
  Titeuf — strictement additif, aucun effet de bord
  (`TestPartVocabulaireCourtChasseur.test_profil_pour_niveau_personnage_sans_table_inchange`).
- `profil_pour_niveau` pour un personnage sans table de surcharge, ou pour
  un niveau absent de la table, renvoie exactement `.profil` — aucune
  mutation du profil de base du registre.
- Les réglages par niveau (`_MALUS_LONGUEUR`, `_BONUS_PREMIUM`,
  `_POIDS_LEAVE`), les autres personnages et le tirage Aléatoire ne sont pas
  touchés.

### Comportement du garde-fou (point 2 de l'issue, demandé dans le rapport)

Si, après filtrage, aucun coup candidat ne reste (chevalet qui ne permet
plus aucun mot court connu, et aucun mot long disponible pour compenser), la
liste FILTRÉE est simplement abandonnée et la liste D'ORIGINE (non filtrée)
est utilisée pour ce tour — comportement identique à l'absence du champ pour
ce seul tour, puis le filtre redevient actif au tour suivant si de nouveaux
coups candidats apparaissent. Choix simple délibéré, sans action corrective
plus élaborée (par exemple retenter avec une part relâchée) : l'objectif du
garde-fou est seulement d'éviter une passe forcée qui fausserait la mesure
de force, pas de maximiser le respect du style dans ce cas limite, rare par
construction (une part de 70 % laisse en moyenne 70 % des mots courts
accessibles). Testé explicitement avec un scénario à un seul coup court
candidat et `part_vocabulaire_court=0.0` —
`TestPartVocabulaireCourt.test_garde_fou_si_aucun_coup_candidat_apres_filtre`.

### Tests ajoutés

- `tests/test_moteur_ia.py` :
  - `TestMotConnuVocabulaireCourt` : déterminisme et indépendance de
    l'ordre, bornes à 0,0/1,0, proportion proche de la part sur une liste de
    mots fabriquée (5 valeurs), et indépendance statistique avec
    `_mot_connu_vocabulaire_long` (taux d'accord proche de 50 % à `part =
    0.5` sur 2000 mots, pas de 100 %).
  - `TestPartVocabulaireCourt` : part à 100 % identique au comportement
    actuel ; part à 0 % ne laissant que les mots de 7 lettres et plus (sans
    déclencher le garde-fou, un mot long restant disponible) ; garde-fou
    déclenché quand le seul candidat est un mot court filtré et qu'aucun mot
    long n'est disponible pour compenser ; mots longs (vocabulaire du niveau
    ET `vocabulaire_long`) jamais concernés, à 3 valeurs de part ; résultat
    stable entre 5 appels successifs ; neutralité des autres profils ;
    neutralité de la consommation du générateur aléatoire dans
    `choisir_coup`, sur les six niveaux.
- `tests/test_moteur_personnages.py` :
  - `TestPartVocabulaireLongChasseur` : `test_valeurs_de_depart` et
    `test_profil_pour_niveau_avance` mis à jour pour la nouvelle valeur
    100 % à Avancé (valaient 50 %, lot H ter) — seuls changements
    nécessaires dans les tests existants, conformément à la contrainte de
    l'issue.
  - `TestPartVocabulaireCourtChasseur` (nouvelle) : valeurs de la table,
    `.profil` qui ne porte jamais la résolution par niveau,
    `profil_pour_niveau` pour Intermédiaire/Avancé (avec vérification que la
    surcharge de `part_vocabulaire_long`, indépendante, reste appliquée en
    même temps)/niveau absent, non-mutation du profil de base, neutralité
    pour Classique/Opportuniste/Titeuf.
- **Tests verts** : 1229 avant ce lot (1222 passés + 7 échecs — 2
  spécifiques aux anciennes valeurs du lot H ter, modifiés ci-dessus, et 5
  préexistants sans rapport avec ce lot, reconfirmés préexistants via `git
  stash`) ; **1252 après** (1247 passés + les 5 mêmes échecs préexistants,
  inchangés). Aucune régression, 23 tests nets ajoutés.

## Commandes de mesure prêtes à l'emploi

À lancer par Alain avec le dictionnaire réel installé (absent de ce
worktree isolé). Même script, même chemin que le jeu réel
(`ConfigJoueur.profil()` passe par `profil_pour_niveau`, lot H ter) : le
nouveau filtre de mots courts s'y applique donc bien. 200 parties chacune
(pas 100) — le bruit observé sur 100 parties au lot H ter, de plusieurs
points d'écart, est trop grand pour un réglage fin de ce niveau. Le script
ne propose pas de surcharge en ligne de commande pour un champ de personnage
propre à un seul d'entre eux (mêmes conventions que pour
`POIDS_TIRAGE_SCRABBLE_CHASSEUR`/`PART_VOCABULAIRE_LONG_CHASSEUR`) : éditer
`PART_VOCABULAIRE_COURT_CHASSEUR` dans
`src/scrabble/moteur/personnages.py` entre chaque commande.

**Intermédiaire**, plusieurs valeurs de
`PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.INTERMEDIAIRE]` :

```
# PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.INTERMEDIAIRE] = 0.7 (valeur de départ)
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_intermediaire_court70.csv

# Puis éditer la table à 0.5, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_intermediaire_court50.csv

# Puis à 0.3, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_intermediaire_court30.csv
```

**Avancé**, plusieurs valeurs de
`PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.AVANCE]` :

```
# PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.AVANCE] = 0.7 (valeur de départ)
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_avance_court70.csv

# Puis éditer la table à 0.5, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_avance_court50.csv

# Puis à 0.3, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_avance_court30.csv
```

Pour chaque run, lire dans la sortie du script le tableau de style
(scrabbles par partie, points par coup) et l'écart de points moyen contre
Classique. Objectif (rappelé par l'issue) : écart de points proche de zéro
avec un surplus de scrabbles (scrabbles par partie du Chasseur contre celui
de Classique) qui reste visible. Si à 70 % l'écart de points reste
nettement positif, descendre vers 0,5 puis 0,3 ; si au contraire le surplus
de scrabbles s'efface avant que l'écart de points n'approche zéro, c'est le
signe que ce levier seul ne suffit pas non plus (comme pour
`part_vocabulaire_long` au lot H ter) et qu'il faudra le rapport complet
pour trancher. Valeurs à ajuster uniquement sur validation d'Alain, pas en
boucle automatique.

# Changelog — Issue #452

## Ajouté

- **Personnage Titeuf, le farceur aux mots de cour de récré (lot J, niveau
  Débutant).** Débutant n'avait jusqu'ici aucun personnage disponible à
  part Classique (Opportuniste et Chasseur de scrabbles l'excluent tous les
  deux), ce qui rendait aussi Aléatoire indisponible à ce niveau (règle du
  lot G : au moins deux personnages). Titeuf comble ce trou : un personnage
  comique, inspiré de Titeuf (Zep), qui place ses mots favoris de cour de
  récré dès qu'il le peut, même peu rémunérateurs.

  - **`data/personnages/titeuf_mots_favoris.txt`** (nouveau fichier,
    versionné avec le code) : liste de mots favoris, un mot par ligne,
    modifiable sans toucher au code. Liste de départ : caca, pipi, prout,
    crotte, popo, fesses, zizi, slip, beurk, sexe — mots courts,
    humoristiques, de cour de récré, sans injure ni terme haineux.

  - **`scrabble.moteur.ia`** : deux nouveaux champs facultatifs de
    `ProfilPersonnage`, tous deux neutres par défaut (`None`), généralisant
    les mécanismes du lot H ter (Chasseur de scrabbles) à un critère de
    LISTE plutôt que de LONGUEUR :
    - `mots_favoris: frozenset[str] | None`. Élargit l'ensemble des coups
      candidats (`_generer_coups_candidats`) aux coups dont le **mot
      principal** figure dans cette liste : générés via un petit Trie
      construit depuis la liste, et VALIDÉS (mot principal et mots croisés)
      avec `dictionnaire_complet` — pas avec ce petit Trie, qui rejetterait
      presque tous les mots croisés. `generer_coups` (`scrabble.moteur.
      generateur`) reçoit pour cela un nouveau paramètre optionnel
      `dictionnaire_validation` (`None` par défaut = retombe sur
      `dictionnaire`, comportement strictement inchangé) qui découple le
      Trie d'EXPLORATION (élagage par préfixe) de celui de VALIDATION. Un
      mot de la liste absent du lexique complet n'est filtré par aucun code
      dédié : la génération/validation ne produit alors simplement aucun
      coup pour lui — ignoré sans erreur. Sans doublon avec les coups du
      vocabulaire du niveau (même ensemble `vus` que `vocabulaire_long`, les
      deux élargissements se combinant sans conflit).
    - `poids_tirage_favori: float | None`. Généralise
      `poids_tirage_scrabble` (lot H ter) au critère de liste, avec une
      différence essentielle : les coups à mot favori sont ajoutés au pool
      de tirage même s'ils sont EXCLUS de la tranche des meilleurs coups
      (`_tirer_dans_tranche`, nouveau paramètre `coups_complets`) — un mot
      favori peu rémunérateur, plausible à Débutant, pourrait sinon en être
      écarté d'office. Si un coup cumule les deux critères (scrabble ET mot
      favori), le plus grand des deux poids s'applique. Neutralité stricte
      inchangée : sans profil, ou avec les deux poids à `None`, c'est
      exactement `rng.choice(tranche).coup` — même consommation du
      générateur aléatoire qu'avant l'introduction de ces champs.
    - `Partie.jouer_tour_ia` transmet `self.dictionnaire` comme lexique
      complet dès que `profil.vocabulaire_long` OU `profil.mots_favoris` est
      actif (auparavant : seulement `vocabulaire_long`).

  - **`scrabble.moteur.personnages`** : nouvelles constantes
    `CHEMIN_MOTS_FAVORIS_TITEUF`, `MOTS_FAVORIS_TITEUF` (chargée une fois au
    chargement du module via la nouvelle fonction `charger_mots_favoris`,
    qui réutilise `lire_liste_mots`/`desaccentuer` de
    `scrabble.dictionnaire.dictionnaire`), `POIDS_TIRAGE_FAVORI_TITEUF =
    50.0` (calcul détaillé dans le docstring du module et le rapport de
    l'issue), `PRENOM_TITEUF = "Titeuf"`, `NIVEAUX_TITEUF = {DEBUTANT}`,
    `NB_JOUEURS_TITEUF = {2}`. Nouvelle entrée `"titeuf"` dans le registre
    `PERSONNAGES`.

  - **Conséquence attendue (règle déjà en place, lot G) :** Débutant compte
    maintenant deux personnages réels (Classique + Titeuf) — Aléatoire y
    redevient donc disponible, sans aucune autre modification, et son
    tirage à ce niveau couvre bien les deux.

  - **`scripts/mesurer_force_niveaux.py`** : nouvel indicateur de style
    « Coups dont le mot principal est un mot favori » (colonne CSV
    `part_mot_favori`, préfixée `a_`/`b_`), alimenté par la liste de mots
    favoris résolue depuis le profil de CHAQUE camp — vaut 0 pour un
    personnage sans liste. Nouvel exemple de commande documenté (Titeuf
    contre Classique à Débutant, 100 parties, avec tableau de style).

  - **Tests** (`tests/test_moteur_generateur.py`,
    `tests/test_moteur_ia.py`, `tests/test_moteur_personnages.py`,
    `tests/test_mesurer_force_niveaux_style.py`) : neutralité des deux
    nouveaux champs (profil vide, consommation du générateur aléatoire
    inchangée), accessibilité d'un mot favori COURT hors du vocabulaire du
    niveau (contrairement à `vocabulaire_long`, aucune contrainte de
    longueur), mot absent du lexique ignoré sans erreur, absence de
    doublons, cohérence du journal de décision, fréquence de tirage proche
    de la théorie, ajout au pool même hors tranche, liste modifiable sans
    toucher au code (fichier temporaire), disponibilité de Titeuf
    (Débutant + deux joueurs seulement), Aléatoire redevenu disponible à
    Débutant, neutralité des autres personnages.

    Quelques tests existants, qui encodaient explicitement qu'Aléatoire
    était indisponible à Débutant (lot G, issue #447) ou que tout le
    registre était disponible à un niveau donné, sont mis à jour pour
    refléter la nouvelle disponibilité plutôt que laissés en échec :
    `tests/test_accueil.py`,
    `tests/test_moteur_partie.py`,
    `tests/test_moteur_personnages.py`.

# Changelog — Issue #451

## Ajouté

- **Tirage pondéré en faveur des scrabbles et part de mots longs connus,
  réglables par niveau pour le Chasseur (lot H ter).** Après le lot H bis
  (#450), la mesure (hypothétique, dictionnaire absent de ce worktree, voir
  le rapport de l'issue) indiquait deux défauts distincts : à Intermédiaire,
  le style de Chasseur de scrabbles ne se voyait presque pas (le tirage
  uniforme dans la tranche des 15 % meilleurs coups dilue l'effet d'un
  scrabble qui n'y figure qu'une fois sur 10 à 15 coups) ; à Avancé, il était
  au contraire trop fort (vocabulaire long intégral, sans aucun levier pour
  en retenir une partie). Ce lot ajoute deux réglages indépendants pour
  corriger chaque défaut séparément, sans toucher aux réglages par niveau,
  aux autres personnages ni au tirage Aléatoire.

  - **`scrabble.moteur.ia`** : deux nouveaux champs facultatifs de
    `ProfilPersonnage`, tous deux neutres par défaut (`None`) :
    - `poids_tirage_scrabble: float | None`. S'applique UNIQUEMENT à
      l'étape du tirage dans la tranche de meilleurs coups, pour les niveaux
      qui tirent au hasard (DEBUTANT, FACILE, INTERMEDIAIRE, EXPERT) —
      aucun effet sur AVANCE/CHAMPION_DU_MONDE (meilleur coup, jamais un
      tirage dans une tranche). Nouvelle fonction privée
      `_tirer_dans_tranche(tranche, rng, profil)` : sans le champ renseigné,
      c'est exactement `rng.choice(tranche).coup` (même appel, même
      consommation du générateur aléatoire qu'avant son introduction) ; avec
      une valeur renseignée, les coups de la tranche posant les 7 lettres du
      chevalet (`nb_nouvelles == _SEUIL_BONUS_SCRABBLE`, même critère que
      `bonus_scrabble`) reçoivent ce poids dans un tirage pondéré
      (`rng.choices`), les autres coups gardant le poids 1 — la COMPOSITION
      de la tranche (déjà calculée par `_trier_par_score_strategique`) ne
      change jamais, seules les probabilités à l'intérieur changent.
      `_choisir_top5`/`_choisir_intermediaire`/`_choisir_facile`/
      `_choisir_debutant` reçoivent chacune un nouveau paramètre optionnel
      `profil` et délèguent à cette fonction ; `_choisir_avance` reste
      inchangée (pas de paramètre `profil` : aucun effet par construction).
    - `part_vocabulaire_long: float | None`. Affine `vocabulaire_long` (lot H
      bis) : parmi les mots de 7 lettres et plus du lexique complet qui
      élargissent les coups candidats, seule cette fraction reste
      accessible — jamais les mots courts, ni ceux déjà dans le vocabulaire
      du niveau (ceux-là ne passent jamais par ce filtre, par construction
      de `_generer_coups_candidats` : seuls les mots ajoutés par la seconde
      génération, donc absents du vocabulaire du niveau, y sont soumis).
      Nouvelle fonction privée `_mot_connu_vocabulaire_long(mot,
      part_vocabulaire_long)` : hachage SHA-256 stable du texte du mot
      (PAS le `hash()` intégré de Python, randomisé d'un processus à
      l'autre via `PYTHONHASHSEED`) comparé à `part_vocabulaire_long` — un
      même mot est donc toujours connu ou toujours inconnu, indépendamment
      de la graine de la partie et de l'ordre de génération des coups.
      `None` ou `1.0` (défaut) : tous les mots longs restent accessibles,
      comportement identique, bit à bit, à celui du lot H bis.
  - **`scrabble.moteur.personnages`** :
    - `POIDS_TIRAGE_SCRABBLE_CHASSEUR = 5.0` : nouvelle constante, champ
      plat (comme les trois réglages précédents du Chasseur) — voir le
      calcul ci-dessous.
    - `PART_VOCABULAIRE_LONG_CHASSEUR = {INTERMEDIAIRE: 1.0, AVANCE: 0.5}` :
      table niveau → part, PAS un champ plat (contrairement aux autres
      réglages du personnage) puisque l'intention demande deux valeurs
      différentes selon le niveau. Nouveau champ optionnel
      `Personnage.part_vocabulaire_long_par_niveau` (`dict[Niveau, float] |
      None`, défaut `None`) et nouvelle fonction publique
      `profil_pour_niveau(cle, niveau)` : renvoie `PERSONNAGES[cle].profil`
      tel quel, sauf si `part_vocabulaire_long_par_niveau` est renseigné ET
      contient une entrée pour `niveau`, auquel cas `part_vocabulaire_long`
      est remplacé par cette valeur (tous les autres champs inchangés).
      `niveau=None`, ou un niveau absent de la table, laissent le profil
      inchangé. **`.profil` (accès direct) reste la valeur PLATE, sans
      résolution de niveau** — c'est délibéré : les tests existants du lot H
      bis qui lisent `PERSONNAGES["chasseur_de_scrabbles"].profil`
      directement (AVANCE/EXPERT/CHAMPION_DU_MONDE) continuent de voir
      `part_vocabulaire_long=None` (100 %, comportement du lot H bis) sans
      aucune modification — seuls les appelants qui connaissent le niveau du
      joueur (le jeu réel, le script de mesure) doivent appeler
      `profil_pour_niveau`, jamais `.profil` directement.
  - **`scrabble.ui.jeu`** : `_profil_joueur_ia(joueur)` résout désormais via
    `profil_pour_niveau(joueur.personnage, joueur.niveau)` au lieu de
    `obtenir_personnage(joueur.personnage).profil` — c'est ce chemin qui
    fait que la part de vocabulaire long par niveau du Chasseur s'applique
    réellement en jeu (`joueur.niveau` est toujours renseigné pour un joueur
    IA). Sans effet pour tout personnage sans table de surcharge (Classique,
    Opportuniste) : `profil_pour_niveau` y renvoie alors exactement
    `.profil`, comme avant.
  - **`scripts/mesurer_force_niveaux.py`** : `ConfigJoueur.profil()` résout
    pareillement via `profil_pour_niveau(self.personnage, self.niveau)` au
    lieu de l'accès direct `PERSONNAGES[self.personnage].profil` — **même
    chemin que le jeu réel**, condition explicitement demandée par l'issue
    pour que le tirage pondéré et la part de vocabulaire long réglés par
    personnage s'appliquent identiquement en mesure et en partie.

### Calcul justifiant `POIDS_TIRAGE_SCRABBLE_CHASSEUR = 5.0`

Aux niveaux concernés, la tranche de meilleurs coups compte, en pratique, de
l'ordre de 10 à 20 coups. Sans ce champ (tirage uniforme), la probabilité de
tirer un scrabble présent dans la tranche n'est que `1/n` (10 % à n = 10,
5 % à n = 20) — c'est précisément le constat de départ de l'issue (0,05
scrabble/partie à Intermédiaire contre 0,02 pour Classique, dans la marge
d'erreur). Avec un poids `w` sur ce seul coup parmi les `n` de la tranche
(chaque autre coup gardant le poids 1), cette probabilité devient
`w / (n - 1 + w)`. Pour `w = 5` : `5 / (10 - 1 + 5) = 5/14 ≈ 36 %` à n = 10,
et `5 / (20 - 1 + 5) = 5/24 ≈ 21 %` à n = 20 — une hausse d'un facteur 3 à 4
par rapport au tirage uniforme, tout en laissant encore la majorité des
tirages aux autres coups de la tranche (ni un passage au tirage toujours
gagnant, qui romprait la règle « même tranche, probabilités seulement
modifiées », ni un effet encore dilué au point de rester dans la marge
d'erreur).

### Calcul justifiant `PART_VOCABULAIRE_LONG_CHASSEUR`

- **Intermédiaire : 1,0 (100 %, inchangé).** Le constat de départ à ce
  niveau est que le style ne se voit pas assez, pas qu'il est trop fort :
  rien à retirer côté vocabulaire, le levier est le tirage pondéré ci-dessus.
- **Avancé : 0,5 (50 %).** Le constat de départ à ce niveau (qui joue
  toujours son meilleur coup, donc insensible au tirage pondéré) est
  l'inverse : Chasseur trop fort (61 % de victoires, environ +20 points par
  partie contre Classique), un écart que faire varier `poids_leave` de 1,0 à
  2,0 ne corrigeait pas (l'écart restait de 14 à 23 points, la force venant
  du vocabulaire, pas du leave). Réduire de moitié le vocabulaire long
  accessible hors du vocabulaire du niveau est un point de départ médian
  entre « tout » (trop fort) et « rien » (retour à Classique) — à affiner
  par Alain après mesure réelle (voir les commandes ci-dessous).

### Neutralité stricte

- Un profil sans `poids_tirage_scrabble` (absent, ou `ProfilPersonnage()`
  vide) consomme le générateur aléatoire EXACTEMENT comme avant
  l'introduction du champ, pour les six niveaux — testé explicitement avec
  un générateur espion qui compte les appels à `choice`/`choices` et compare
  `getstate()` avant/après (`TestNeutraliteTirage`, paramétrée sur
  `list(Niveau)`), pas seulement le coup produit.
- Un profil sans `part_vocabulaire_long` (ou `1.0`) reproduit bit à bit
  l'ensemble de coups candidats du lot H bis (`TestPartVocabulaireLong`).
- Les deux champs restent `None` pour Classique et Opportuniste — strictement
  additifs, aucun effet de bord.
- `profil_pour_niveau` pour un personnage sans table de surcharge (Classique,
  Opportuniste), ou pour un niveau absent de la table, renvoie exactement
  `.profil` — aucune mutation du profil de base du registre.
- Le tirage Aléatoire et les réglages par niveau (`_MALUS_LONGUEUR`,
  `_BONUS_PREMIUM`, `_POIDS_LEAVE`) ne sont pas touchés.

### Journal de décision et évaluation

`evaluer_coups` n'a reçu aucune modification : la pondération du tirage
n'intervient qu'après le tri (dans `choisir_coup`, jamais dans
`_trier_par_score_strategique`), donc le journal (alternatives, rang du coup
choisi) reste calculé exactement comme avant. La part de vocabulaire long
étant une fonction pure du texte du mot (pas de l'aléa de la partie),
`evaluer_coups` appelé avec le même `profil`/`dictionnaire_complet` que
`choisir_coup` reste automatiquement en phase avec l'ensemble de coups
candidats réellement consulté — aucune logique de cohérence supplémentaire à
écrire.

### Tests ajoutés

- `tests/test_moteur_ia.py` : `TestNeutraliteTirage` (consommation du
  générateur aléatoire identique sur les six niveaux, paramétrée) ;
  `TestTirageSPondereDansLaTranche` (fréquence de tirage proche de la valeur
  théorique et nettement supérieure au tirage uniforme sur une tranche
  fabriquée, à 10/15/20 coups ; composition de la tranche inchangée ; tirage
  réellement pondéré, pas déterministe, même à poids élevé) ;
  `TestMotConnuVocabulaireLong` (déterminisme et indépendance de l'ordre,
  bornes à 0,0/1,0, proportion proche de la part sur une liste de mots
  fabriquée, plusieurs valeurs) ; `TestPartVocabulaireLong` (part à 100 %
  identique au lot H bis, part à 0 % sans aucun mot long hors vocabulaire,
  mots courts et vocabulaire du niveau non concernés quelle que soit la
  part, résultat stable entre deux appels, neutralité des autres profils).
- `tests/test_moteur_personnages.py` : `TestPoidsTirageScrabbleChasseur`
  (constante, neutralité des autres personnages, et confirmation du
  correctif — Chasseur choisit désormais plus souvent le scrabble que
  Classique à Intermédiaire, pas seulement à Avancé/Expert/Champion du
  monde comme au lot H bis) ; `TestPartVocabulaireLongChasseur` (valeurs de
  la table, `.profil` qui ne porte jamais la résolution par niveau,
  `profil_pour_niveau` pour Intermédiaire/Avancé/niveau absent/`None`/clé
  inconnue, non-mutation du profil de base, neutralité pour Classique et
  Opportuniste).
- **Tests verts** : 1143 avant ce lot (1138 passés + 5 échecs préexistants,
  sans rapport avec ce lot — reconfirmés préexistants via `git stash`) ;
  **1182 après** (1177 passés + les 5 mêmes échecs préexistants, inchangés).
  Aucune régression, 39 tests nets ajoutés.

## Commandes de mesure prêtes à l'emploi

À lancer par Alain avec le dictionnaire réel installé (absent de ce worktree
isolé). Même script, même chemin que le jeu réel (`ConfigJoueur.profil()`
passe maintenant par `profil_pour_niveau`, voir plus haut) : le tirage
pondéré et la part de vocabulaire long s'y appliquent donc bien.

**Point 6 — tirage pondéré, Intermédiaire, plusieurs valeurs de
`POIDS_TIRAGE_SCRABBLE_CHASSEUR`.** Éditer la constante dans
`src/scrabble/moteur/personnages.py` entre chaque commande (le script ne
propose pas de surcharge en ligne de commande pour un champ de personnage
propre à un seul d'entre eux, comme pour `BONUS_PREMIUM_OPPORTUNISTE` —
mêmes conventions que pour Opportuniste) :

```
# POIDS_TIRAGE_SCRABBLE_CHASSEUR = 5.0 (valeur de départ)
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire_poids5.csv

# Puis éditer POIDS_TIRAGE_SCRABBLE_CHASSEUR = 3.0, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire_poids3.csv

# Puis POIDS_TIRAGE_SCRABBLE_CHASSEUR = 8.0, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire_poids8.csv
```

**Point 11 — part de vocabulaire long, Avancé, plusieurs valeurs de
`PART_VOCABULAIRE_LONG_CHASSEUR[Niveau.AVANCE]`**, pour amener l'écart de
points près de zéro (objectif de l'issue) :

```
# PART_VOCABULAIRE_LONG_CHASSEUR[Niveau.AVANCE] = 0.5 (valeur de départ)
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance_part50.csv

# Puis éditer la table à 0.25, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance_part25.csv

# Puis à 0.75, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance_part75.csv
```

Si le taux de victoire/l'écart de points à Avancé reste loin de ~50 %/0 après
ces trois valeurs, affiner par dichotomie autour de la valeur la plus
proche. Si au contraire Intermédiaire montre déjà un style visible sans
distordre le taux de victoire (Chasseur doit rester proche de 50 % contre
Classique à niveau égal, comme pour Opportuniste), la valeur de départ du
poids de tirage peut rester 5,0 sans ajustement supplémentaire. Valeurs à
ajuster uniquement sur validation d'Alain, pas en boucle automatique.

# Changelog — Issue #450

## Ajouté

- **Chasseur de scrabbles connaît les mots de 7 lettres et plus du lexique
  complet (lot H bis).** La mesure du lot H (issue #448) montrait un style
  indiscernable de Classique (écarts de scrabbles par partie dans la marge
  d'erreur, à Avancé/Expert/Champion du monde) et une perte de force de 8 à
  20 points par partie : le poids de leave renforcé (2,0) faisait jouer de
  petits coups sans que le vocabulaire disponible ne lui donne plus
  d'occasions réelles de scrabble. Le personnage joue désormais avec le
  vocabulaire de son niveau pour les mots courts, mais peut en plus poser
  tout mot de 7 lettres ou plus du lexique complet — un spécialiste des longs
  mots, dont le caractère vient maintenant du vocabulaire plutôt que d'un
  réglage de score.
  - **`scrabble.moteur.ia`** : nouveau champ facultatif
    `ProfilPersonnage.vocabulaire_long` (`bool | None`, défaut `None`,
    neutre). Nouvelle fonction `_generer_coups_candidats(plateau, chevalet,
    dictionnaire, profil, dictionnaire_complet)` : sans le champ actif (ou
    sans `dictionnaire_complet`), renvoie exactement `generer_coups(...)`
    comme avant son introduction ; avec les deux, renvoie l'UNION, sans
    doublon (clé `(ligne, colonne, direction, mot)`), des coups habituels
    (vocabulaire du niveau) et des coups générés avec `dictionnaire_complet`
    dont le **mot principal** compte au moins 7 lettres (nouvelle constante
    `_SEUIL_VOCABULAIRE_LONG`). **Mot principal** = toutes les tuiles du coup
    dans sa direction, lettres déjà posées comprises (`len(coup.tuiles)`,
    PAS `nb_nouvelles`, qui ne compte que les lettres neuves) — définition
    déjà utilisée ailleurs dans le module (`AlternativeCoup.mot`). **Mots
    croisés** : aucune logique de validation ajoutée — la seconde génération
    (avec `dictionnaire_complet`) élague ET valide (`coup_valide`) avec ce
    même Trie, donc le mot principal et tous les mots croisés d'un coup long
    sont automatiquement validés avec le lexique complet, par construction
    de `generer_coups`. `choisir_coup` et `evaluer_coups` reçoivent un
    nouveau paramètre optionnel `dictionnaire_complet` (`None` par défaut,
    ignoré si le profil ne demande pas `vocabulaire_long`) et appellent tous
    les deux `_generer_coups_candidats` — le journal de décision
    (`evaluer_coups`) porte donc sur le même ensemble de coups candidats
    élargi que la sélection réelle (`choisir_coup`), jamais un ensemble
    différent.
  - **`scrabble.moteur.partie`** : `Partie.jouer_tour_ia` calcule
    `dictionnaire_complet = self.dictionnaire` **uniquement** si
    `profil.vocabulaire_long` est actif, sinon `None` (rien transmis,
    strictement identique à avant). **Aucun nouveau chargement** : contrairement
    au vocabulaire par palier, `self.dictionnaire` est déjà, pour TOUTE
    partie, le Trie complet qui valide chaque coup posé (humain ou IA,
    voir la docstring de `Partie`) — construit par l'appelant UI à la
    création *et* à la reprise d'une partie, que la table compte un Chasseur
    de scrabbles ou non. Il ne restait donc qu'à le **brancher** vers l'IA
    en plus de la validation ; les parties sans Chasseur (ou avec un profil
    qui ne demande pas `vocabulaire_long`) ne chargent rien de plus et
    n'appellent `choisir_coup`/`evaluer_coups` sans ce paramètre, à
    l'identique d'avant. Une partie sauvegardée avec un Chasseur se reprend
    donc normalement sans aucune modification de
    `scrabble.persistance.stockage` ni `scrabble.ui.accueil` : le mécanisme
    de chargement du Trie complet à la reprise (`ApiAccueil.reprendre` →
    `obtenir_trie` → `reprendre_partie(..., dictionnaire=trie)`) existait
    déjà et n'est pas spécifique au Chasseur.
  - **Temps de réflexion supplémentaire** : `vocabulaire_long` fait tourner
    `generer_coups` une seconde fois (sur le lexique complet, le double de la
    génération normale) à chaque tour du Chasseur. Mesuré sur un Trie
    synthétique (le dictionnaire réel est absent de ce worktree isolé) —
    vocabulaire de niveau à 3 000 mots contre lexique complet à 18 000 mots,
    plateau à mi-partie, dix tirages de chevalet : **23 ms/tour en Classique
    contre 103 ms/tour en Chasseur, soit ×4,4**. Le ratio réel dépendra de la
    taille relative ODS8 / palier du niveau (probablement plus grande que
    dans ce test synthétique) ; mesure réelle à faire par Alain avec le
    dictionnaire installé (voir commandes de mesure plus bas) — reste de
    l'ordre de quelques dizaines à centaines de millisecondes par tour, sans
    impact perceptible en jeu (le tour d'un ordinateur n'est jamais instantané
    à l'écran).
  - **`scrabble.moteur.personnages`** : `NIVEAUX_CHASSEUR_SCRABBLES` resserré
    à **Intermédiaire et Avancé** (remplace « Avancé à Champion du monde » du
    lot H). Déterminé par le code et la configuration des paliers plutôt que
    par la proposition par défaut de l'issue (« Avancé à Expert ») : d'après
    `scrabble.moteur.ia._PALIERS_PAR_NIVEAU`/`resoudre_palier` et
    `scrabble.dictionnaire.dictionnaire.FICHIERS_VOCABULAIRE_PALIER` (quatre
    entrées : debutant/facile/intermediaire/avance), **seuls ces quatre
    niveaux ont un vocabulaire restreint** — Expert et Champion du monde
    jouent déjà, tous les deux, sur le lexique complet (aucune entrée de
    palier pour eux, refonte de l'échelle issue #401). `vocabulaire_long` n'y
    changerait donc rigoureusement rien : l'union avec le lexique complet
    serait un no-op puisque le vocabulaire du niveau EST déjà le lexique
    complet. Exclure Expert suit donc exactement la même logique que
    l'exclusion de Champion du monde proposée par l'issue. Parmi les niveaux
    à vocabulaire restreint, Débutant et Facile restent exclus (scrabbles peu
    réalistes à ces niveaux, même critère qu'au lot H) : restent
    Intermédiaire et Avancé. Plage provisoire, à ajuster par Alain après
    mesure.
  - **`scrabble.moteur.personnages`** : poids de leave du Chasseur
    (`POIDS_LEAVE_CHASSEUR_SCRABBLES`) remplacé par `None` (**aucune
    surcharge** — le poids de leave du niveau du joueur s'applique tel quel,
    de 0,3 à Intermédiaire à 0,6 à Avancé), au lieu de 2,0 au lot H. Choix de
    la première des deux valeurs de départ proposées par l'issue (« celle du
    niveau, sans surcharge ») plutôt qu'une valeur légèrement supérieure :
    puisque `vocabulaire_long` devient l'unique trait de caractère du
    personnage, retirer la surcharge de leave isole proprement son effet
    pour la prochaine mesure, sans compounder deux changements à la fois —
    c'est justement le poids à 2,0 que la mesure du lot H incriminait pour la
    perte de force. La constante reste nommée en tête de module, à remonter
    à une valeur légèrement supérieure à `None` si la mesure montre que
    Chasseur garde encore trop facilement un petit coup plutôt qu'un reliquat
    prometteur. Le bonus de pose de 7 lettres (`bonus_scrabble` =
    `BONUS_SEPT_LETTRES_CHASSEUR` = 150) est inchangé.
  - **`scripts/mesurer_force_niveaux.py`** : `jouer_une_partie` transmet
    désormais `dictionnaire_complet=dictionnaire` (le Trie complet déjà
    chargé pour la validation) à `ia.choisir_coup` — même chemin que le jeu
    réel (`Partie.jouer_tour_ia`), pour que le Chasseur y dispose du lexique
    complet pendant la mesure. Ignoré par tout profil qui ne demande pas
    `vocabulaire_long` : aucun effet sur les mesures existantes (Opportuniste,
    Classique, niveaux bruts).
  - **Neutralité** : un profil vide, ou sans `vocabulaire_long`, reproduit
    bit à bit le comportement d'avant son introduction, à graine égale, pour
    tous les niveaux et personnages (testé explicitement, comme aux lots A et
    H) — y compris quand un `dictionnaire_complet` est malgré tout fourni à
    `choisir_coup`/`evaluer_coups` (défense en profondeur : c'est le profil,
    jamais l'appelant, qui décide).
  - Tests ajoutés : `tests/test_moteur_ia.py` (nouvelle classe
    `TestVocabulaireLong` — neutralité sans profil/profil vide, mot de 7
    lettres absent du vocabulaire du niveau trouvé et joué avec le lexique
    complet, mot croisé validé avec le lexique complet, mots courts non
    empruntés au lexique complet, journal de décision sur l'ensemble
    élargi) ; `tests/test_moteur_partie.py` (intégration `Partie.jouer_tour_ia`
    de bout en bout : Chasseur trouve le mot long via `self.dictionnaire`,
    Classique sur le même scénario ne le voit pas) ; `tests/test_moteur_personnages.py`
    (profil du Chasseur — `vocabulaire_long=True`, `poids_leave=None` ;
    neutralité de Classique/Opportuniste ; disponibilité resserrée à
    Intermédiaire/Avancé, libellés et messages associés mis à jour). Tests
    existants ajustés pour la nouvelle plage de disponibilité (sans changer
    ce qu'ils vérifient) : `test_ajouter_ordinateur_refuse_chasseur_a_quatre_joueurs`
    (niveau Avancé + `paliers_disponibles` monkeypatché, au lieu d'Expert,
    pour continuer à isoler le refus sur la taille de table) ;
    `test_creer_partie_aleatoire_peut_tirer_classique` et
    `test_creer_partie_aleatoire_peut_tirer_opportuniste_a_deux_joueurs`
    (niveau Avancé, où le registre complet reste disponible, au lieu de
    Champion du monde).
  - **Tests verts** : 1133 avant ce lot (1128 passés + 5 échecs préexistants,
    sans rapport avec ce lot — confirmés préexistants via `git stash`,
    `tests/test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`
    et 4 autres liés à l'environnement pywebview/GTK absent de ce worktree) ;
    **1143 après** (1138 passés + les 5 mêmes échecs préexistants, inchangés).
    Aucune régression, 10 tests nets ajoutés.

## Commandes de mesure prêtes à l'emploi

À lancer par Alain avec le dictionnaire réel installé (absent de ce worktree
isolé). Même script que pour Opportuniste (issue #439/#446), même format de
sortie (tableau de style — scrabbles par partie, points par coup — et taux de
victoire). Chasseur de scrabbles contre Classique, 100 parties, aux quatre
niveaux déjà mesurés au lot H (Intermédiaire, Avancé, Expert, Champion du
monde) — vocabulaire long attendu pour faire une différence à Intermédiaire et
Avancé (vocabulaire du niveau restreint), et pour n'en faire AUCUNE à Expert
et Champion du monde (vocabulaire déjà complet à ces deux niveaux, confirmant
ou infirmant l'hypothèse de ce lot) :

```
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire.csv

python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance.csv

python scripts/mesurer_force_niveaux.py EXPERT EXPERT \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_expert.csv

python scripts/mesurer_force_niveaux.py CHAMPION_DU_MONDE CHAMPION_DU_MONDE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_champion.csv
```

Ces commandes fonctionnent même si Chasseur de scrabbles n'est plus
« disponible » (au sens UI) à Expert/Champion du monde : le script, comme pour
Opportuniste, n'applique aucun garde-fou de disponibilité — c'est précisément
ce qui permet de mesurer l'absence d'effet attendue à ces deux niveaux.

# Changelog — Issue #449

## Ajouté

- **Personnages réservés aux parties à deux joueurs (lot I).** Tous les
  réglages et mesures des personnages ont été faits en parties à deux
  joueurs (humain contre un ordinateur) : rien n'a été vérifié à trois ou
  quatre joueurs. Les personnages sont donc réservés aux parties à deux
  joueurs pour cette première diffusion, levables personnage par personnage
  plus tard, sans se presser.
  - **`scrabble.moteur.personnages`** : nouveau champ facultatif
    `Personnage.nb_joueurs_disponibles` (`frozenset[int]`, défaut
    `TOUTES_TAILLES = {2, 3, 4}`), indépendant de `niveaux_disponibles`
    (les deux restrictions se combinent par ET logique). Opportuniste et
    Chasseur de scrabbles sont déclarés disponibles à deux joueurs
    seulement (`NB_JOUEURS_OPPORTUNISTE`/`NB_JOUEURS_CHASSEUR_SCRABBLES`).
    Nouvelles fonctions miroir de celles du lot G (niveaux) :
    `personnages_disponibles_a_nb_joueurs`, `aleatoire_disponible_a_nb_joueurs`,
    `personnage_disponible_a_nb_joueurs`, `libelle_tailles`,
    `libelle_tailles_aleatoire`, `explication_disponibilite_tailles`.
    « Aléatoire » suit une règle déduite comme pour les niveaux : disponible
    uniquement pour une taille où au moins deux personnages (hors lui-même)
    le sont — aujourd'hui disponible à deux joueurs, indisponible à trois ou
    quatre. `tirer_personnage` accepte désormais un paramètre `nb_joueurs`
    optionnel, combiné au niveau. `lister_personnages` expose un nouveau
    champ `tailles_label` par entrée.
  - **`scrabble.moteur.partie`** : `creer_partie` transmet la taille totale
    de la table à `tirer_personnage` pour qu'un tirage « Aléatoire » ne
    choisisse jamais un personnage indisponible à cette taille — comme pour
    le niveau, le moteur lui-même reste sans garde-fou (aucune vérification
    de disponibilité), seule l'UI contrôle en amont.
  - **`scrabble.ui.accueil`** : `obtenir_personnages()` expose `tailles_label`
    ; nouvelle méthode `obtenir_disponibilite_personnage_table()` (le
    sélecteur de personnage doit être désactivé dès que la table compte déjà
    un ordinateur, l'ajout d'un second faisant passer la table à trois
    joueurs ou plus — seul Classique y reste disponible dans le registre
    actuel). `ajouter_ordinateur()` refuse désormais un personnage non
    disponible pour la taille de table résultante (message dédié) et, si
    l'ajout fait passer la table à trois joueurs ou plus, remet
    automatiquement à Classique le personnage de tout ordinateur déjà
    présent (avec un avertissement nommant le joueur concerné, retiré ensuite
    sans être rétabli). `lancer_partie()` refuse de démarrer si un
    personnage assigné n'est plus disponible pour la taille de table finale
    (défense en profondeur).
  - **UI (accueil.html/js/css, commun.js, personnages.css)** : le sélecteur
    de personnage est désactivé avec une explication courte (« Les
    personnages sont réservés aux parties à deux joueurs. ») dès que la
    table comporte déjà un ordinateur ; les avertissements de remise à
    Classique sont affichés au joueur. La fenêtre « Les personnages »
    (accueil et jeu, composant partagé) affiche désormais aussi les tailles
    de table où chaque personnage est disponible, à côté des niveaux déjà
    affichés.
  - **Parties existantes et script de mesure inchangés** : aucune
    vérification de disponibilité n'a lieu au chargement d'une partie
    sauvegardée (une combinaison devenue indisponible continue de se jouer
    normalement) ; `scripts/mesurer_force_niveaux.py` continue de pouvoir
    forcer n'importe quelle combinaison, comme pour les niveaux.
  - Tests : `tests/test_moteur_personnages.py`, `tests/test_accueil.py`,
    `tests/test_accueil_niveaux_visuels.py`, `tests/test_moteur_partie.py`,
    `tests/test_persistance.py`.

# Changelog — Issue #448

## Ajouté

- **Personnage Chasseur de scrabbles (lot H).** Deuxième personnage après
  Opportuniste (lot B) : guette les coups posant les 7 lettres du chevalet
  (un « scrabble ») et garde ses meilleures lettres pour y arriver. D'après
  le rapport d'investigation (issue #437), classé « réalisable en partie » :
  le bonus direct sur la pose de 7 lettres relève de la même famille de
  calcul que le bonus premium d'Opportuniste ; l'anticipation fine du
  reliquat (deviner par avance qu'on approche d'un scrabble jouable) reste
  hors périmètre.
  - **`scrabble.moteur.ia`** : nouveau champ facultatif
    `ProfilPersonnage.bonus_scrabble` (`int | None`, défaut `None`). À la
    différence de `malus_longueur`/`bonus_premium`/`poids_leave`, ce champ
    n'a aucun réglage de production indexé par niveau à surcharger : il vaut
    0 (neutre) pour tous les niveaux tant qu'aucun personnage ne le
    renseigne. `_score_strategique` l'ajoute au score des coups dont
    `nb_nouvelles == 7` (nouvelle constante `_SEUIL_BONUS_SCRABBLE`), quel
    que soit le niveau. Un profil vide, ou sans ce champ, donne exactement
    le même résultat qu'avant son introduction, pour tous les niveaux, à
    graine égale — vérifié explicitement (comme au lot A).
  - **`scrabble.moteur.personnages`** : nouvelle entrée de registre
    `"chasseur_de_scrabbles"` (prénom « Chasseur de scrabbles »), avec deux
    nouvelles constantes nommées en tête de module (modifiables pour la
    mesure, comme `BONUS_PREMIUM_OPPORTUNISTE`) :
    - `BONUS_SEPT_LETTRES_CHASSEUR = 150` — valeur de départ déduite par
      analogie avec le bonus premium d'Opportuniste (100) : l'événement
      déclencheur (poser les 7 lettres) est bien plus rare que « toucher
      une case premium », donc le bonus doit être encore plus déterminant
      pour l'emporter sur un coup concurrent mieux payé en score brut — 150
      reprend l'échelle d'Opportuniste en l'augmentant d'un facteur
      comparable à celui qui sépare déjà ce dernier (×5) du bonus premium
      de production (20 à EXPERT/CHAMPION_DU_MONDE).
    - `POIDS_LEAVE_CHASSEUR_SCRABBLES = 2.0` — le plafond de production de
      `_POIDS_LEAVE` culmine à 1.0 (EXPERT, CHAMPION_DU_MONDE) ; Chasseur de
      scrabbles double ce plafond pour nettement privilégier la
      conservation des bonnes lettres en vue d'un futur scrabble, par
      analogie avec le facteur multiplicatif net choisi pour Opportuniste.
    - Ces deux valeurs sont des points de départ **raisonnés, non mesurés**
      (le dictionnaire réel n'est pas disponible dans ce worktree isolé,
      voir « Mesure réelle non lancée » ci-dessous) — provisoires,
      destinées à être ajustées par Alain après mesure.
    - Nouvelle constante `NIVEAUX_CHASSEUR_SCRABBLES` (disponibilité par
      niveau, mécanisme du lot G, issue #447) : Avancé à Champion du monde,
      **provisoire** elle aussi — d'après le rapport d'investigation (issue
      #437), les scrabbles sont rares aux niveaux plus bas (environ 0,01
      par partie à Intermédiaire, 0,1 à 0,2 à Avancé), rendant le
      personnage peu perceptible en dessous. Ajustable par Alain en un
      seul endroit (cette constante) après mesure.

## Tests

- `tests/test_moteur_ia.py` : `ProfilPersonnage.bonus_scrabble` vaut `None`
  par défaut ; un coup posant 7 lettres sans profil (ou avec profil vide)
  n'est pas affecté, pour tous les niveaux ; le bonus s'ajoute exactement
  (égalité stricte `score + bonus`) quand `nb_nouvelles == 7` ; le bonus est
  ignoré pour `nb_nouvelles` de 1, 2, 3, 5 et 6 — « le bonus s'applique
  uniquement aux coups qui posent 7 lettres ».
- `tests/test_moteur_personnages.py` : nouvelle classe
  `TestPersonnageChasseurDeScrabbles` —
  - plateau et chevalet fabriqués (`_plateau_chasseur`) où un coup de 7
    lettres (score brut modeste, bonus scrabble intrinsèque +50) est en
    concurrence avec un coup plus court mais mieux payé en score brut
    (lettres chères sur une case mot triple, sans bonus scrabble) ; sans
    personnage, le second l'emporte toujours (AVANCE/EXPERT/
    CHAMPION_DU_MONDE, 0/200 scrabbles choisis sur 200 graines), avec
    Chasseur de scrabbles le premier l'emporte toujours (200/200) — testé
    aux trois niveaux où le personnage est disponible ;
  - présence dans le registre, prénom, description non vide ;
  - présence dans `lister_personnages()` (sélecteur/liste) ;
  - indisponible à Débutant/Facile/Intermédiaire, disponible à
    Avancé/Expert/Champion du monde (mécanisme du lot G) ;
  - libellé « Avancé à Champion du monde » et explication « Disponible à
    partir de Avancé ».
- **`tests/test_moteur_partie.py`** : `test_creer_partie_aleatoire_peut_tirer_classique`
  mis à jour (ajout de `niveaux_ia=[Niveau.CHAMPION_DU_MONDE]`) — ce test
  historique tirait « Aléatoire » au niveau par défaut (Intermédiaire) en
  s'attendant à voir tout le registre, ce qui n'est plus vrai dès lors
  qu'un personnage (Chasseur de scrabbles) y est indisponible : changement
  structurel attendu du mécanisme de disponibilité par niveau (lot G, issue
  #447), pas une régression de comportement — le test est repris au niveau
  (Champion du monde) où tout le registre actuel reste disponible.
- Suite pytest complète : **1060 verts / 5 échecs préexistants** avant ce
  lot (confirmés préexistants par `git stash` — `test_accueil.py`,
  `test_application.py` ×2, `test_journal_integration.py` ×2) ; **1081
  verts / mêmes 5 échecs** après (21 nouveaux tests, aucune régression).

## Mesure réelle non lancée

Comme pour Opportuniste (lot B), le dictionnaire ODS8 n'est pas présent dans
ce worktree isolé (gitignoré, déposé manuellement) : conformément à la
consigne, il n'a pas été recherché ailleurs, et les deux constantes
ci-dessus n'ont donc pas pu être calibrées par mesure. Six commandes prêtes
à lancer par Alain — Chasseur de scrabbles contre Classique, aux six
niveaux, 100 parties chacun, vocabulaire du jeu réel, export CSV pour le
tableau de style (qui compte déjà les scrabbles par partie, issue #446) :

```
python scripts/mesurer_force_niveaux.py DEBUTANT DEBUTANT \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_debutant.csv

python scripts/mesurer_force_niveaux.py FACILE FACILE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_facile.csv

python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_intermediaire.csv

python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_avance.csv

python scripts/mesurer_force_niveaux.py EXPERT EXPERT \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_expert.csv

python scripts/mesurer_force_niveaux.py CHAMPION_DU_MONDE CHAMPION_DU_MONDE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_champion.csv
```

Les trois premières commandes (Débutant/Facile/Intermédiaire) forcent une
disponibilité aujourd'hui fermée par le registre (`NIVEAUX_CHASSEUR_SCRABBLES`)
— le script de mesure ne vérifie aucune disponibilité (comme pour
Opportuniste), elles servent à juger si la plage provisoire doit être
élargie vers le bas. À l'inverse, si les trois derniers niveaux montrent un
caractère trop peu perceptible ou un déséquilibre de force excessif, la
plage pourra être resserrée. Décision et ajustement des deux constantes
(`BONUS_SEPT_LETTRES_CHASSEUR`, `POIDS_LEAVE_CHASSEUR_SCRABBLES`) laissés à
Alain.

## Points à vérifier à la main

- Chasseur de scrabbles apparaît dans le sélecteur de personnage à
  l'accueil et dans la fenêtre « Les personnages », avec sa description et
  ses niveaux affichés.
- Les niveaux Débutant/Facile/Intermédiaire sont grisés pour ce personnage ;
  Avancé/Expert/Champion du monde restent actifs.
- Une partie avec un ordinateur Chasseur de scrabbles se déroule normalement
  (nécessite le dictionnaire réel, absent de ce worktree).

# Changelog — Issue #447

## Ajouté

- **Disponibilité des personnages IA selon le niveau de l'adversaire (lot
  G).** Un personnage n'a de sens qu'aux niveaux où son style se voit
  réellement (les mesures du lot B/C montrent qu'à Débutant, Opportuniste
  joue sur case bonus à peine plus souvent que Classique, 20,5 % contre
  20,1 % — son caractère n'y est pas perceptible). Règle générale : le jeu
  empêche désormais de choisir une combinaison personnage/niveau non
  disponible.
  - **`scrabble.moteur.personnages`** : nouveau champ facultatif
    `Personnage.niveaux_disponibles` (`frozenset[Niveau]`, défaut
    `TOUS_NIVEAUX` — un futur personnage sans déclaration reste disponible
    partout, comme Classique). Opportuniste déclare
    `NIVEAUX_OPPORTUNISTE` = tous les niveaux sauf Débutant.
  - Nouvelles fonctions : `personnages_disponibles_a_niveau`,
    `aleatoire_disponible_a_niveau` (Aléatoire n'a de sens qu'avec au moins
    deux personnages réels disponibles à ce niveau — règle **déduite**
    automatiquement des déclarations, sans qu'Aléatoire déclare quoi que ce
    soit : aujourd'hui indisponible à Débutant, seul Classique y figurant),
    `personnage_disponible_a_niveau`, `libelle_niveaux`/
    `libelle_niveaux_aleatoire` (texte « Tous les niveaux » ou « Facile à
    Champion du monde »), `explication_disponibilite_niveaux` (texte court,
    p. ex. « Disponible à partir de Facile », ou le message dédié
    d'Aléatoire).
  - `tirer_personnage` accepte désormais un `niveau` optionnel qui restreint
    le tirage aux personnages disponibles à ce niveau (défaut `None` :
    comportement historique inchangé, tout le registre). `creer_partie`
    (`scrabble.moteur.partie`) le lui transmet pour le niveau de l'IA
    concernée — le tirage reste fait une seule fois à la création de la
    partie, déterministe et injectable, identité réelle enregistrée comme
    avant. `creer_partie` lui-même ne vérifie aucune disponibilité (ni
    moteur ni IA modifiés) : le script `mesurer_force_niveaux.py` peut
    continuer à forcer n'importe quelle combinaison.
  - **`scrabble.ui.accueil.ApiAccueil`** : `ajouter_ordinateur` refuse
    désormais une combinaison personnage/niveau non disponible (message
    nommant le personnage et le niveau), défense en profondeur en plus du
    grisage côté accueil — un appel sans personnage (défaut Classique)
    continue de fonctionner sans changement. Nouvelle méthode
    `obtenir_disponibilite_niveaux_personnage(personnage_cle)` (disponibilité
    par niveau + courte explication), distincte du contrôle déjà existant
    sur le vocabulaire IA (`obtenir_disponibilite_niveaux`, combiné côté JS).
    `obtenir_personnages` et `scrabble.moteur.personnages.lister_personnages`
    exposent désormais `niveaux_label` par personnage (et pour Aléatoire),
    pour l'affichage dans « Les personnages » (accueil et jeu, même
    présentation — contrôleur commun dans `commun.js`).
  - Accueil (`accueil.html`/`.js`/`.css`) : les boutons de niveau où le
    personnage sélectionné n'est pas disponible sont réellement désactivés
    et grisés, avec l'explication affichée sous le sélecteur — mise à jour
    immédiate à chaque changement de personnage. Tous les boutons restent
    actifs pour Classique. Distinct du grisage (non désactivant) déjà
    existant pour le vocabulaire IA indisponible : les deux signaux se
    combinent par bouton.
  - Aucune vérification de disponibilité au chargement d'une partie
    sauvegardée (`reprendre_partie`) : une combinaison devenue indisponible
    se recharge et se joue normalement.

## Tests

- `tests/test_moteur_personnages.py` : disponibilité par défaut
  (`TOUS_NIVEAUX`), Opportuniste refusé à Débutant et accepté de Facile à
  Champion, Aléatoire indisponible à Débutant et disponible dès qu'un second
  personnage y est ajouté (registre patché en test), tirage restreint au
  niveau, libellés/explications.
- `tests/test_accueil.py` : refus serveur (message) pour Opportuniste et
  Aléatoire à Débutant, acceptation de Facile à Champion, appel sans
  personnage inchangé, `obtenir_disponibilite_niveaux_personnage`.
- `tests/test_moteur_partie.py` : tirage Aléatoire restreint au niveau de
  l'IA concernée dans `creer_partie`.
- `tests/test_persistance.py` : chargement d'une partie sauvegardée avec une
  combinaison aujourd'hui non disponible (Opportuniste à Débutant).
- `tests/test_accueil_niveaux_visuels.py` : câblage JS/HTML/CSS du grisage
  par personnage et de l'affichage des niveaux dans « Les personnages ».
- Deux tests existants qui vérifiaient l'exact des clés renvoyées par
  `lister_personnages`/`obtenir_personnages` (`{"cle", "prenom",
  "description", "dans_la_partie"}` / sans `dans_la_partie`) ont été mis à
  jour pour inclure le nouveau champ `niveaux_label` — changement structurel
  nécessaire au point 5 de l'issue, pas une régression de comportement.

# Changelog — Issue #446

## Ajouté

- **Indicateurs de style comparés A/B dans le script de mesure de force
  (`scripts/mesurer_force_niveaux.py`).** Le script oppose déjà deux
  configurations IA sur de nombreuses parties et mesure qui gagne et de
  combien (lot B, issue #439), mais ne disait rien de leur *style* de jeu :
  on savait qu'Opportuniste est aussi fort que Classique, pas s'il joue
  vraiment différemment — une seule partie à la main n'avait pas permis de
  trancher, le style y étant noyé dans le hasard du tirage.
  - Nouvelle dataclass **`IndicateursPartieJoueur`** (par joueur, par
    partie) et champs `indicateurs_a`/`indicateurs_b` ajoutés à
    `ResultatPartie`, remplis par la nouvelle `_calculer_indicateurs_joueur()`
    — appelée **après** la fin de la boucle de jeu dans `jouer_une_partie()`,
    en relecture pure de `Partie.historique` et des chevalets finaux (aucun
    appel supplémentaire à `ia.choisir_coup`, aucune consommation d'aléa) :
    `score_a`/`score_b`/`commence`/`tours` restent calculés exactement comme
    avant. Vérifié par comparaison directe avant/après la modification, même
    graines, 30 parties déterministes : résultats strictement identiques.
  - Indicateurs retenus, cumulés sur toutes les parties (définitions exactes
    dans le docstring de `IndicateursPartieJoueur`) :
    - part des coups touchant au moins une case à multiplicateur (toute case
      **neuve** du coup dont `TypeCase != NORMALE`, reflet direct de
      `DetailMot.cases_bonus`) ;
    - part des coups touchant un mot double ou triple — la case **centrale**
      y est comptée (elle fonctionne comme un mot double), sinon le tout
      premier coup de chaque partie, qui la couvre toujours, aurait été
      systématiquement exclu de ce sous-total ;
    - lettres posées par coup (`len(positions_posees)`, pas la longueur du
      mot formé) et part des coups de une ou deux lettres ;
    - points par coup, longueur du mot principal (premier mot de
      `detail.mots`, celui porté par la direction du coup) ;
    - scrabbles (7 lettres posées) par partie ;
    - jokers joués : nombre par partie, points du coup où le joker est posé,
      et tour de sa pose (rang 1-indexé de l'action dans l'historique
      **complet** de la partie, les deux joueurs confondus — même convention
      que `tours`/`MAX_TOURS` ailleurs dans le script) ; une tuile joker déjà
      posée un tour précédent et seulement retraversée par un coup ultérieur
      ne recompte pas ;
    - passes par partie ;
    - pénalité des lettres restantes en fin de partie
      (`Joueur.valeur_chevalet()` — le chevalet n'est pas vidé par
      `Partie._terminer`, seul le score l'intègre déjà en soustraction).
  - Écart-type d'échantillon (points/coup, longueur de mot, lettres posées)
    ou IC95 (proportions, via l'`_ic_95` existant ; nouvelle
    `_ic_95_moyenne` pour la moyenne des continus) selon le cas, pour juger
    si un écart A-B est significatif.
  - **Affichage** : nouveau tableau comparatif A vs B
    (`_afficher_tableau_style`), ajouté à la fin du résumé existant
    (`_afficher_resume`, lui-même **inchangé**) — colonnes valeur A, valeur
    B, écart A-B. Absent du mode `--comparer` (relit un CSV sans le détail
    par coup nécessaire à ces indicateurs).
  - **Export CSV** : 13 colonnes par joueur (préfixe `a_`/`b_`) ajoutées
    **après** les six colonnes historiques du CSV — `_lire_csv` (mode
    `--comparer`) les lit par position et ignore le reste, donc reste
    compatible avec les CSV produits avant et après cet ajout. Les moyennes
    sur zéro coup (ex. aucun joker joué cette partie) sont exportées en
    chaîne vide, pas en `0`, pour ne pas confondre « jamais » et « zéro
    point ».
  - **`tests/test_mesurer_force_niveaux_style.py`** (nouveau, 3 tests) :
    calcul des indicateurs sur une petite partie fabriquée à la main (CHAT
    au centre, CH sur lettre double, AS au joker sur une autre lettre
    double, puis une passe — valeurs attendues connues par avance : cases
    bonus, longueurs, joker et son tour, pénalité) ; export CSV complet
    (vérifie aussi la colonne vide du joker non joué) ; intégration
    `jouer_une_partie()` de bout en bout (dictionnaire vide à dessein, sans
    dépendre d'un vrai dictionnaire — absent de ce worktree isolé, comme au
    lot B) vérifiant le déterminisme du résultat de force entre deux appels
    identiques.
  - **Aucune modification** du moteur d'IA, des réglages par niveau, des
    personnages ni du tirage aléatoire (`moteur/ia.py`, `moteur/personnages.py`
    non touchés).
  - Suite pytest : 1023 verts / 5 échecs préexistants (inchangés, hors
    périmètre — `test_accueil.py`, `test_application.py` ×2,
    `test_journal_integration.py` ×2, confirmés préexistants avant toute
    modification) avant ce lot ; **1026 verts / mêmes 5 échecs** après (3
    nouveaux tests, aucune régression).
  - **Mesure réelle non lancée** : le dictionnaire ODS8 n'est pas présent
    dans ce worktree isolé (gitignoré, déposé manuellement — voir lot B,
    issue #439) ; conformément à la consigne, il n'a pas été recherché
    ailleurs. Deux commandes prêtes à lancer par Alain (vocabulaire par
    palier, comme le jeu réel, avec export CSV pour réanalyse ultérieure) :

    ```
    python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
        --personnage-a opportuniste --personnage-b classique --vocab palier \
        --parties 200 --csv style_opportuniste_vs_classique_avance.csv

    python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
        --personnage-a opportuniste --personnage-b classique --vocab palier \
        --parties 200 --csv style_opportuniste_vs_classique_intermediaire.csv
    ```

  - Exemple de tableau obtenu sur une mesure courte (30 parties, FACILE vs
    DEBUTANT, lexique de démonstration minimaliste — valeurs indicatives, pas
    une mesure réelle) :

    ```
    ============================================================
    STYLE DE JEU — FACILE (A) vs DEBUTANT (B)
    ============================================================
    Indicateur                                       FACILE    DEBUTANT     Écart (A-B)
    Coups touchant une case à multiplicateur     57.1% ± 10.2%  53.8% ± 11.1%           +3.3%
      dont mot double/triple (ou centre)         23.1% ± 8.7%  20.5% ± 9.0%           +2.6%
    Lettres posées par coup                      1.91 ± 0.18  1.58 ± 0.16           +0.34
    Coups de une ou deux lettres                 79.1% ± 8.4%  87.2% ± 7.4%           -8.1%
    Points par coup                              4.80 ± 0.43  4.23 ± 0.46           +0.57
    Longueur du mot principal                    2.67 ± 0.16  2.50 ± 0.15           +0.17
    Scrabbles (7 lettres) par partie             0.00 ± 0.00  0.00 ± 0.00           +0.00
    Jokers joués par partie                      0.43 ± 0.22  0.13 ± 0.12           +0.30
      points du coup où un joker est posé        3.69 ± 1.03  3.25 ± 1.47           +0.44
      tour de pose du joker                      3.85 ± 2.21  4.00 ± 2.53           -0.15
    Passes par partie                            1.40 ± 0.35  1.83 ± 0.46           -0.43
    Pénalité lettres restantes en fin de partie  19.37 ± 2.85  17.03 ± 2.31           +2.33
    ============================================================
    ```

  Fichiers touchés : `scripts/mesurer_force_niveaux.py` (modifié),
  `tests/test_mesurer_force_niveaux_style.py` (nouveau). Aucune modification
  de l'interface du jeu.

# Changelog — Issue #445

## Ajouté

- **Journal de décision de l'ordinateur : chevalet et meilleures alternatives
  à chaque tour, avec script de relecture.** Pour juger le style d'un
  personnage (Opportuniste, et d'autres plus tard), il fallait voir ce
  qu'un ordinateur avait comme lettres et quels coups il aurait pu jouer, pas
  seulement le coup joué (la base ne conservait que les coups réellement
  posés).
  - **`moteur/ia.py`** : nouvelles `AlternativeCoup` (mot, position,
    direction, score réel, score stratégique) et `EvaluationCoupsIA`
    (nb de coups possibles, 5 meilleurs, rang et fiche du coup choisi),
    produites par la nouvelle fonction **pure et sans aléa**
    `evaluer_coups()`. Le tri par score stratégique (deux passes, leave
    value) a été factorisé hors de `choisir_coup()` dans
    `_trier_par_score_strategique()`, réutilisé par les deux fonctions — elles
    restent ainsi trivialement en phase sans dupliquer la logique de tri.
    `choisir_coup()` n'a **ni nouveau paramètre ni changement de
    comportement** : `evaluer_coups()` est un second appel, indépendant,
    toujours fait **après** `choisir_coup()`, jamais à sa place.
  - **`moteur/partie.py`** : nouvelle `JournalDecisionIA` (chevalet avant
    action, meilleurs coups, rang, coup choisi) et champ optionnel
    `EntreeHistorique.journal_ia` (`None` par défaut). `Partie.jouer_tour_ia`
    capture le chevalet avant l'action puis appelle `ia.evaluer_coups()` en
    plus de `ia.choisir_coup()`, et transmet le journal à `jouer_coup()`/
    `passer()` (nouveau paramètre mot-clé `journal_ia=None` sur les trois
    méthodes d'action, jamais utilisé par un appelant humain). Garde-fou
    (`hasattr(dictionnaire_ia, "racine")`) : certains tests substituent au
    dictionnaire un double minimal n'exposant que `contient()`, prévu pour
    fonctionner tant que `choisir_coup` reste lui-même monkeypatché — le
    journal est alors simplement absent plutôt qu'en erreur.
  - **`persistance/stockage.py`** : colonne facultative `actions.journal_ia`
    (TEXT, migration idempotente comme `mode_belgicisme`) — **aucune
    migration manuelle** : une base antérieure à cette issue se recharge et
    se rejoue sans erreur, `journal_ia` valant `None`. Nouvelles fonctions de
    lecture **seule** `lire_configuration_partie()` et
    `lire_actions_journalisees()` (ouverture SQLite `mode=ro`, jamais
    d'écriture ni de migration — fonctionnent même sur une base jamais
    rouverte en écriture depuis l'ajout de la colonne, via une vérification
    `PRAGMA table_info`).
  - **`scripts/relire_journal_ia.py`** (nouveau) : affiche, tour par tour,
    joueur (personnage et niveau), chevalet avant action, coup joué, 5
    meilleures alternatives (le coup réellement joué signalé même hors top 5)
    et son rang — puis un résumé par joueur (part de coups sur case bonus,
    part sur mot double/triple, lettres posées par coup en moyenne, jokers
    joués et leur score, passes, échanges). Option `--joueur` pour filtrer un
    seul joueur. Base ouverte en lecture seule. Les parties sans journal
    (anciennes) affichent les coups seuls avec la mention « chevalet non
    enregistré ».

## Stockage : choix retenu

Colonne facultative plutôt que champ dans le JSON `detail` existant : aucun
test ne fige la structure de `actions.detail` ni de `EntreeHistorique`, donc
les deux options étaient ouvertes ; la colonne séparée garde `detail` (déjà
consulté à chaque tour pour l'affichage) inchangé et indépendant d'une
fonctionnalité d'analyse jamais lue pendant une partie.

## Poids ajouté par partie

Sur un petit dictionnaire de test, chaque entrée `journal_ia` pèse entre 139
et 741 octets (moyenne ~450 octets) selon le nombre d'alternatives
disponibles — toujours borné par le top 5, **indépendant** du nombre total de
coups possibles (qui peut se chiffrer en milliers avec le dictionnaire ODS8
complet : seul l'entier `nb_coups_possibles` en rend compte). Pour une partie
à 2 joueurs (1 humain + 1 IA) d'une trentaine de tours, l'ajout total est de
l'ordre de 5 à 10 Ko — négligeable comparé au reste de la table `actions`.

## Confidentialité

Le chevalet et les alternatives de l'IA ne sont lus que par
`lire_actions_journalisees()` (lecture seule, hors jeu) : aucune des fonctions
de sérialisation vers l'UI (`etat_public`, `serialiser_entree_historique`,
`serialiser_historique`, `serialiser_dernier_coup`) ne les mentionne —
vérifié par 4 nouveaux tests cherchant les clés `journal_ia`/
`chevalet_avant`/`score_strategique` dans le JSON envoyé au JS.

## Tests

Nouveau fichier `tests/test_journal_decision_ia.py` (28 tests) : présence/
absence du journal (ordinateur vs humain), cohérence du contenu (coup choisi
retrouvable, alternatives triées, 5 au plus), absence d'influence sur la
sélection (même coup à graine figée avec/sans journal, même état du
générateur aléatoire après `choisir_coup`, pour les 6 niveaux), aller-retour
de sauvegarde, chargement d'une ancienne base sans la colonne `journal_ia`
(écriture **et** lecture seule), poids d'une entrée, confidentialité (4
tests), et le script de relecture sur des parties fabriquées dans le test
(dont une ancienne sauvegarde sans journal et un filtre `--joueur`).

Suite complète : **995 tests verts avant** ce lot (+ 5 échecs préexistants,
confirmés avec `git stash`, sans rapport avec cette issue — `test_accueil.py`,
`test_application.py` ×2, `test_journal_integration.py` ×2) → **1023 tests
verts après** (995 + 28 nouveaux), mêmes 5 échecs préexistants inchangés.

## Exemple de sortie du script de relecture

```
=== Partie #1 (graine 2) ===
  Joueur 0 : Alice (humain)
  Joueur 1 : IA 1 (Opportuniste, INTERMEDIAIRE)

--- Tour 1 — IA 1 (Opportuniste, INTERMEDIAIRE) ---
  Chevalet avant : A E E D E U C
  Coup joué      : 'DA' en (7,7) H — score 6
  Rang du coup choisi : 1 / 4
  Meilleurs coups (score stratégique) :
    - 'DA' (7,7) H réel=6 stratégique=9 <- choisi
    - 'DE' (7,7) H réel=6 stratégique=9
    - 'DA' (7,7) V réel=6 stratégique=9
    - 'DE' (7,7) V réel=6 stratégique=9

--- Tour 5 — IA 1 (Opportuniste, INTERMEDIAIRE) ---
  Chevalet avant : E E U C B P N
  Action         : passe
  Rang du coup choisi : None / 0
  Aucun coup n'était disponible.

=== Résumé par joueur ===
- IA 1 (Opportuniste, INTERMEDIAIRE) :
    coups joués            : 2
    dont case bonus        : 2 (100 %)
    dont mot double/triple : 0 (0 %)
    lettres posées/coup    : 2.0 en moyenne
    jokers joués           : 0 (score cumulé 0)
    passes                 : 1
    échanges               : 0
```

## Contraintes respectées

- Sélection de coup, réglages par niveau, valeurs des personnages et tirage
  Aléatoire **non modifiés** : `choisir_coup()` garde exactement sa
  signature et son comportement d'avant l'issue.
- Tests existants non modifiés, tous verts (hors les 5 échecs préexistants).
- Aucune modification visible de l'interface (confirmé par les tests de
  confidentialité).
- Aucun push effectué.

# Changelog — Issue #443

## Modifié

- **Personnages IA, lot F bis : liste de l'accueil alignée sur celle du jeu,
  texte de Classique reformulé, marque « Dans cette partie » pour Aléatoire.**
  Corrige trois défauts relevés à l'essai du lot F (#442).
  - **Texte de Classique** (`moteur/personnages.py`) : description remplacée
    par « Joue normalement selon son niveau. » (plus clair que « Joue sans
    biais de personnalité... »).
  - **Styles de la fenêtre « Les personnages » isolés dans un seul fichier**
    (nouveau `web/personnages.css`, retiré de `commun.css`) : chargé par les
    DEUX fenêtres (`accueil.html`, `jeu.html`), qui ne peuvent donc plus
    diverger. L'accueil ne chargeait jamais `commun.css` (feuille
    entièrement autonome, propre à sa fenêtre) : c'est ce qui laissait la
    liste des personnages en texte brut, sans nom en évidence ni séparateur
    ni bouton « Fermer » stylé — même composant JS (`creerModalePersonnages`
    de `commun.js`), même markup, mais aucun style appliqué. La fenêtre de
    l'accueil est désormais visuellement identique à celle du jeu (vérifié
    par capture à 1280×800).
  - **Marque « Dans cette partie » pour l'entrée Aléatoire** (`moteur/
    personnages.py`, `ui/jeu.py`) : nouveau paramètre
    `lister_personnages(cles_dans_partie, aleatoire_dans_partie=False)` —
    l'entrée Aléatoire elle-même est désormais marquée dès qu'au moins un
    adversaire a été RÉGLÉ sur Aléatoire (`ApiJeu.obtenir_personnages`
    calcule ce drapeau séparément de `cles_dans_partie`, qui continue de
    n'inclure que des personnages choisis explicitement). Aucune fuite
    d'identité : le libellé « (Aléatoire) » est déjà affiché à côté du
    prénom de cet adversaire pendant toute la partie ; seul le personnage
    réellement tiré reste secret, jamais marqué lui-même.
  - **Tests** (`tests/test_moteur_personnages.py`,
    `tests/test_jeu_personnages.py`) : nouvelle description de Classique ;
    `aleatoire_dans_partie` ne marque que l'entrée Aléatoire ; marquage de
    l'entrée Aléatoire en jeu quand un adversaire y est réglé, absence de
    marquage sinon ; un personnage seulement tiré au hasard (jamais choisi
    explicitement) reste non marqué lui-même ; mêmes données
    (`ApiJeu`/`ApiAccueil.obtenir_personnages`) et même composant JS/CSS
    utilisés par les deux fenêtres.
  - **Vérification visuelle** (`scripts/_harness_jeu/verif_443_personnages.mjs`,
    captures `i443_accueil_personnages_1280x800.png` /
    `i443_jeu_personnages_1280x800.png`) : harnais Playwright headless
    comparant les deux fenêtres (même largeur de modale, mêmes classes,
    marquage Aléatoire visible en jeu, absent à l'accueil).

# Changelog — Issue #442

## Ajouté

- **Personnages IA, lot F : fenêtre « Les personnages », consultable à
  l'accueil comme en cours de partie.** Liste tous les personnages du
  registre (nom + description), construite dynamiquement pour qu'un
  personnage ajouté plus tard au registre y apparaisse sans autre
  modification, avec « Aléatoire » toujours en dernier.
  - **Données** (`moteur/personnages.py`) : nouvelle fonction pure
    `lister_personnages(cles_dans_partie=frozenset())`, qui construit
    `{"cle", "prenom", "description", "dans_la_partie"}` pour chaque
    personnage du registre puis l'entrée « Aléatoire » — jamais marquée
    `dans_la_partie`, pour ne jamais laisser deviner un tirage.
  - **Accueil** (`ui/accueil.py` inchangé, `web/accueil.html/js/css`) : un
    lien discret « Les personnages » à côté du sélecteur de personnage,
    qui réutilise la liste déjà chargée par `obtenir_personnages()`
    (aucun appel API supplémentaire).
  - **Écran de jeu** (`ui/jeu.py`, `web/jeu.html/js/css`) : nouvelle
    méthode `ApiJeu.obtenir_personnages()`, lecture pure (aucun effet sur
    le tour en cours, la partie ni la sauvegarde), qui marque
    `dans_la_partie` pour les personnages choisis À L'AVANCE par les
    adversaires — jamais pour un personnage tiré au hasard. Bouton
    « 🎭 Personnages » ajouté à la zone des boutons système (ligne 1,
    aux côtés de « Retour au menu »/« Resynchroniser »/Sac).
  - **Interface commune** (`web/commun.js`, `web/commun.css`) : contrôleur
    `creerModalePersonnages(refs)` et markup `#modale-personnages`
    dupliqué dans les deux fenêtres (même esprit que la modale de détail
    du score) — un seul composant de rendu, liste défilante
    (`overflow-y: auto`) pour rester lisible à 1280×800 même si le
    registre s'allonge. Fermeture par bouton, clic sur le fond ou Échap.
  - **Tests** (`tests/test_moteur_personnages.py`,
    `tests/test_jeu_personnages.py`) : la liste reflète le registre (un
    personnage ajouté dans un test y apparaît), Aléatoire toujours en
    dernier, jamais marqué `dans_la_partie`, et le marquage ne porte que
    sur les personnages choisis explicitement par les adversaires de la
    partie en cours — jamais sur un tirage aléatoire, même quand son
    identité réelle est déjà connue du moteur.

# Changelog — Issue #441

## Modifié

- **Personnages IA, lot D bis : prénoms aléatoires conservés, personnage
  affiché entre parenthèses.** Revient sur le choix du lot D (#440) qui
  faisait porter à l'ordinateur le prénom de son personnage (« Opportuniste »,
  « Opportuniste 2 ») : le prénom redevient un tirage banal dans la liste
  habituelle, et le personnage s'affiche à côté, entre parenthèses.
  - **Prénoms** (`ui/accueil.py`) : `ApiAccueil.ajouter_ordinateur()` tire
    toujours le prénom via `noms_ordinateur.tirer_prenoms()`, quel que soit
    le personnage choisi — fini la branche qui donnait le prénom du
    personnage. Suppression de `_nom_sans_doublon()` (plus de raison d'être :
    `tirer_prenoms()` exclut déjà les prénoms pris à la table, donc deux
    ordinateurs sur le même personnage ont toujours des prénoms distincts,
    sans suffixe numérique).
  - **Libellé entre parenthèses** (`moteur/personnages.py`) : deux nouvelles
    fonctions pures, réutilisées par l'accueil et l'écran de jeu.
    - `libelle_choix_accueil(personnage_cle)` — pour la clé **non résolue**
      du sélecteur de l'accueil (peut être `CLE_ALEATOIRE`) : chaîne vide
      pour Classique (ou l'absence de personnage), « Aléatoire » pour
      `CLE_ALEATOIRE`, sinon le prénom du personnage choisi.
    - `libelle_personnage_partie(personnage_cle, personnage_aleatoire,
      reveler=False)` — pour l'identité **réelle** d'un `Joueur` en partie :
      chaîne vide pour Classique choisi explicitement, le prénom du
      personnage sinon ; pour un tirage « Aléatoire »
      (`personnage_aleatoire=True`), reste « Aléatoire » tant que
      `reveler` est faux (pendant toute la partie), puis devient
      « Aléatoire : `<Personnage>` » une fois révélé — Classique compris,
      jamais le prénom seul (pour ne pas laisser croire à un défaut
      d'affichage).
  - **Accueil** (`ui/accueil.py`, `web/accueil.js`) :
    `ApiAccueil.obtenir_etat()` expose un nouveau champ
    `joueurs[i].personnage_libelle` (calculé via `libelle_choix_accueil`),
    affiché par le JS après le prénom, entre parenthèses
    (`Commun.nomAvecPersonnage`).
  - **Écran de jeu** (`ui/jeu.py`, `web/jeu.js`) :
    `serialiser_joueur_public()` gagne un paramètre `reveler_personnage`
    (`partie.terminee`, câblé depuis `etat_public()`) et un champ de
    réponse `personnage_libelle` (via `libelle_personnage_partie`). Le champ
    `nom` lui-même reste inchangé — seul l'affichage ajoute le personnage ;
    aucun effet sur l'historique des coups ni les sauvegardes. Le JS utilise
    ce libellé dans les trois affichages du prénom d'un ordinateur : le
    panneau joueur pendant la partie, le tableau de classement final et le
    message de victoire de la modale de fin de partie (tous les trois via
    la fonction partagée `Commun.nomAvecPersonnage`, ajoutée à `commun.js`).
  - **Sélecteur de personnage** (`web/accueil.html`) : libellé changé en
    « Personnage du prochain ordinateur : » (au lieu de « Personnage : »),
    pour que son rôle soit clair — aucun changement d'emplacement ni de
    comportement.
  - Le bloc de révélation dédié de la modale de fin de partie
    (« 🎭 Personnages Aléatoire dévoilés », `revelations_personnages()`)
    est conservé tel quel : il reste la source de la description complète
    du personnage révélé, en complément du libellé compact désormais affiché
    inline à côté du prénom.

## Tests

- `tests/test_moteur_personnages.py` : nouvelles classes
  `TestLibelleChoixAccueil` et `TestLibellePersonnagePartie` couvrant les
  deux fonctions de libellé (Classique, personnage explicite, Aléatoire
  non révélé, Aléatoire révélé pour chaque personnage du registre, Classique
  compris).
- `tests/test_accueil.py` :
  - `test_ajouter_ordinateur_personnage_explicite_porte_son_prenom` →
    renommé `..._porte_un_prenom_tire_au_hasard`, vérifie désormais que le
    prénom vient de `PRENOMS_ORDINATEUR`, indépendamment du personnage.
  - `test_ajouter_deux_ordinateurs_meme_personnage_noms_non_dupliques` →
    renommé `..._prenoms_distincts`, vérifie l'absence de suffixe numérique.
  - Nouvelle classe `TestObtenirEtatPersonnageLibelle` (Classique, personnage
    explicite, Aléatoire, joueur humain).
  - Deux assertions de forme exacte de `obtenir_etat()["joueurs"]`
    (`TestApiAccueilJoueurHumainParDefaut`, `TestApiAccueilAvatarPrincipal`)
    mises à jour avec le nouveau champ `personnage_libelle`.
- `tests/test_jeu_personnages.py` : nouvelle classe
  `TestPersonnageLibelleAffichage` (Classique, sans personnage, personnage
  explicite, Aléatoire pendant la partie, Aléatoire révélé pour chaque
  personnage du registre, personnage explicite jamais révélé, joueur humain).
- `tests/test_journal_integration.py` :
  `test_ouverture_accueil_place_le_joueur_humain_par_defaut` mise à jour
  (même raison que ci-dessus : forme exacte de `obtenir_etat()["joueurs"]`).
- Aucune modification des tests de persistance (`test_persistance.py`) ni du
  reste de `test_jeu_personnages.py` (révélation, `_profil_joueur_ia`,
  câblage IA) : comportement inchangé, déjà couvert par le lot D.
- Suite complète avant ces modifications : 957 passés / 5 échecs
  préexistants (confirmés par `git stash`, indépendants de cette issue —
  `test_infos_tirage_memorisees`, deux tests de `test_application.py`, deux
  de `test_journal_integration.py`). Après : 978 passés / 5 échecs, la même
  liste préexistante inchangée.

## Non traité

- L'écran de tirage d'ordre en début de partie (`detail_tirage_ordre`,
  liste « X a tiré la lettre Y ») n'affiche pas le personnage : ce n'est pas
  l'un des quatre emplacements listés par l'issue (accueil, tableau des
  scores, écran de jeu, écran de résultat), et son alimentation
  (`noms_creation`, simple liste de prénoms) est distincte de
  `etat_public()`. Laissé tel quel par prudence de périmètre.

# Changelog — Issue #440

## Ajouté

- **Personnages IA, lot D : choix à l'accueil, personnage Aléatoire et
  révélation en fin de partie.** Le registre de personnages (lot B) devient
  utilisable en jeu.
  - **Accueil** (`accueil.html`/`.css`/`.js`) : nouveau sélecteur de
    personnage (`<select>`), à côté de la rangée de boutons de niveau,
    construit dynamiquement depuis `ApiAccueil.obtenir_personnages()` — un
    choix par entrée de `PERSONNAGES`, puis « Aléatoire » toujours en
    dernier (un personnage ajouté plus tard au registre s'y insère sans
    autre modification). Sélectionner une option affiche sa description
    sous le menu (texte de mystère pour « Aléatoire », sans rien révéler).
    Le choix du sélecteur s'applique au prochain ordinateur ajouté par clic
    sur un bouton de niveau, exactement comme le niveau lui-même. Défaut :
    Classique (comportement inchangé pour qui ne touche à rien).
  - `ApiAccueil.ajouter_ordinateur(niveau_label, personnage_cle="classique")` :
    3ᵉ paramètre optionnel, rétro-compatible (tout appel existant à un seul
    argument continue de fonctionner à l'identique). Un personnage précis
    donne son prénom à l'ordinateur ; « Aléatoire » tire un prénom banal du
    pool habituel (`noms_ordinateur.tirer_prenoms`) pour ne rien trahir
    pendant la partie — la résolution réelle n'a lieu qu'au lancement.
  - **Prénoms en double (point 2 de l'issue)** : solution retenue, un
    suffixe numérique croissant (`_nom_sans_doublon`) — « Opportuniste »,
    puis « Opportuniste 2 » si un second ordinateur choisit le même
    personnage. Comparaison insensible à la casse/espaces, symétrique à
    `tirer_prenoms`.
  - **Tirage « Aléatoire »** : `creer_partie()` gagne `personnages_ia`
    (clé par IA, dont `CLE_ALEATOIRE`) et `generateur_aleatoire`
    (`random.Random` injectable, pour un tirage déterministe en test).
    Le tirage a lieu **une seule fois**, à la création, uniformément parmi
    *tout* `PERSONNAGES` (Classique compris, via la nouvelle
    `personnages.tirer_personnage()`) ; l'identité enregistrée dans
    `Joueur.personnage` est toujours la clé réelle tirée, jamais le libellé
    « Aléatoire ». Nouveau champ `Joueur.personnage_aleatoire: bool` qui
    mémorise si ce personnage vient d'un tirage (pour la révélation) —
    sérialisé/désérialisé en base symétriquement à `personnage`, avec
    repli `False` sur une sauvegarde d'avant ce lot.
  - **Révélation en fin de partie** : `scrabble.ui.jeu.revelations_personnages`
    (nouveau), exposée dans `etat_public()` sous `revelations_personnages` —
    liste vide tant que la partie n'est pas terminée (ne fuite jamais en
    cours de partie, l'état public étant diffusé en continu), puis une
    entrée `{nom, personnage_prenom, personnage_description}` par
    ordinateur dont le personnage avait été tiré au hasard. Rendu dans la
    modale de fin de partie (`jeu.html`/`.js`/`.css`, bloc
    `#modale-fin-revelations`), sous l'évaluation du score.
  - **Le personnage influence désormais réellement le jeu** : `jeu.py`
    résout le `ProfilPersonnage` du personnage courant
    (`_profil_joueur_ia`) et le transmet à `Partie.jouer_tour_ia(profil)`
    (paramètre déjà prévu par le lot A, jamais câblé jusqu'ici) — seul le
    point d'appel change, ni `ia.py` ni les réglages par niveau ne sont
    touchés. Un personnage vide ou une clé devenue inconnue retombent sur
    `None` (comportement identique à avant ce lot).
  - **Reprise de partie** : fonctionne sans changement supplémentaire —
    `stockage._reconstruire_joueurs` restaure `personnage`/
    `personnage_aleatoire` tels que sauvegardés ; une partie « Aléatoire »
    reprise avant sa fin garde son identité cachée (le champ stocké est déjà
    la clé réelle, mais `personnage_aleatoire` reste vrai jusqu'à la fin).
  - `recreer_partie_meme_joueurs` (action « Recommencer ») repropage le
    personnage de chaque IA au même titre que son niveau — pas de nouveau
    tirage, même pour un personnage obtenu par « Aléatoire » dans la partie
    d'origine : un « Recommencer » garde le même style de jeu.
  - Journal (`ApiAccueil.ajouter_ordinateur`) : la ligne existante
    (« Accueil : ordinateur ajouté (nom, niveau N) ») gagne en bout de
    phrase le personnage choisi, de façon additive — format existant
    inchangé.

## Tests

- `tests/test_moteur_personnages.py` : `TestTirerPersonnage` (tirage
  déterministe avec générateur injecté, toujours une entrée du registre,
  Classique non exclu, fonctionne sans générateur explicite).
- `tests/test_moteur_partie.py` : `creer_partie` sans `personnages_ia`
  (non-régression), avec personnage explicite, avec `"aleatoire"`
  (identité réelle jamais `"aleatoire"`, déterminisme à générateur égal,
  couverture de tout le registre sur 50 graines) ; `recreer_partie_meme_joueurs`
  conserve le personnage de chaque IA.
- `tests/test_persistance.py` : aller-retour de `personnage_aleatoire`
  (défaut `False`, round-trip `True`, ancienne sauvegarde sans la clé).
- `tests/test_accueil.py` : `obtenir_personnages()` (registre + Aléatoire en
  dernier) ; défaut Classique rétro-compatible (API et `ConfigPartie`) ;
  personnage explicite → prénom du personnage ; personnage inconnu refusé ;
  deux ordinateurs même personnage → prénoms non dupliqués ; « Aléatoire » →
  prénom banal, personnage non résolu avant `lancer_partie` ; `lancer_partie`
  résout « Aléatoire » en identité réelle marquée `personnage_aleatoire=True`,
  un personnage explicite n'est jamais marqué ainsi.
- `tests/test_jeu_personnages.py` (nouveau) : `revelations_personnages`
  (vide en cours de partie, vide pour un personnage choisi explicitement ou
  absent, peuplée pour un tirage Aléatoire en fin de partie, jamais pour un
  humain) ; exposition dans `etat_public` ; `_profil_joueur_ia` (vide,
  clé inconnue, Classique, Opportuniste) ; câblage effectif dans
  `jouer_tours_ia_ui` (le profil résolu atteint `choisir_coup`, non-régression
  sans personnage).

### Suite complète

**926 tests avant ce lot (921 verts, 5 échecs préexistants confirmés par
`git stash` — dictionnaire/accueil/application/journal, sans rapport avec ce
lot), 962 après (957 verts, les 5 mêmes échecs inchangés).**

## Solution retenue pour les prénoms en double

Suffixe numérique croissant (« Opportuniste », « Opportuniste 2»…),
comparaison insensible à la casse/espaces. Alternative écartée : retomber
sur un prénom générique du pool habituel aurait masqué le personnage choisi
dans la liste des joueurs, ce qui semblait moins transparent pour le joueur
qui compose sa table.

## À vérifier à la main par Alain (interface graphique, CCL ne peut pas la lancer)

1. **Sélecteur de personnage à l'accueil** : présent à côté des boutons de
   niveau, Classique sélectionné par défaut, Opportuniste puis Aléatoire
   disponibles, Aléatoire bien en dernière position.
2. **Description affichée** : changer la sélection met à jour le texte sous
   le menu (description réelle pour Classique/Opportuniste, texte de
   mystère pour Aléatoire, sans rien révéler).
3. **Ajout d'un ordinateur avec un personnage précis** : le prénom affiché
   dans « Joueurs autour de la table » est celui du personnage (p. ex.
   « Opportuniste ») ; un second ordinateur sur le même personnage obtient
   « Opportuniste 2 ».
4. **Partie avec Aléatoire** : lancer une partie avec un ordinateur en
   Aléatoire — son prénom affiché pendant la partie est un prénom banal
   (pas « Aléatoire », pas le nom d'un personnage).
5. **Écran de résultat** : en fin de partie, un bloc dédié révèle qui
   était vraiment l'ordinateur tiré au hasard (prénom du personnage +
   description) ; aucun bloc (ou vide) si aucun ordinateur n'était en
   Aléatoire.
6. **Reprise d'une partie sauvegardée** : reprendre une partie avec un
   personnage précis le conserve ; reprendre une partie Aléatoire non
   terminée garde l'identité cachée jusqu'à la fin de cette partie reprise.

## Contraintes respectées

- Moteur d'IA (`ia.py`), réglages par niveau et valeurs des personnages non
  modifiés : seul le point d'appel de `Partie.jouer_tour_ia` (déjà prévu
  pour recevoir un profil) a changé, dans `ui/jeu.py`.
- Aucun nouveau personnage, avatar ou image ; aucun changement de
  personnalité en cours de partie.
- Tests existants non modifiés (sauf la docstring-index de
  `tests/test_jeu.py`, garde-fou de `test_jeu_docstring.py`, mise à jour
  pour lister le nouveau fichier de tests — aucune assertion existante
  changée).
- Pas de push : commits locaux uniquement dans ce worktree.

# Changelog — Issue #439

## Ajouté

- **Personnages IA, lot B : personnage Opportuniste.** Nouveau module
  `src/scrabble/moteur/personnages.py` : registre unique `PERSONNAGES`
  (dict clé → `Personnage(cle, prenom, description, profil)`), chaque
  entrée associant un prénom, une description de caractère en français et
  un `ProfilPersonnage` (issue #438, lot A). Ajouter un personnage revient
  à ajouter une entrée à ce dict.
  - `classique` : `ProfilPersonnage()` vide — comportement standard,
    identique bit à bit à l'absence de profil.
  - `opportuniste` : `bonus_premium=28`, `poids_leave=0.0`. Combinaison de
    deux réglages déjà existants du lot A, aucun nouveau calcul, conforme
    au rapport d'investigation #437. `poids_leave=0.0` reprend telle
    quelle la valeur de production de DEBUTANT/FACILE. `bonus_premium=28`
    est dérivé de l'échelle existante (`_BONUS_PREMIUM` va de 3 à 20 par
    paliers +2/+3/+4/+8/+0) : valeur la plus haute déjà calibrée (20,
    EXPERT/CHAMPION_DU_MONDE) + le plus grand palier observé entre deux
    niveaux adjacents (+8, AVANCE → EXPERT) = 28. Surcharge **plate** (pas
    indexée par niveau) : le trait de caractère ne varie pas avec la force
    du joueur, par construction de `ProfilPersonnage`.
- `scripts/mesurer_force_niveaux.py` : `ConfigJoueur` gagne un champ
  `personnage: str | None`, résolu par la nouvelle méthode `profil()` vers
  le `ProfilPersonnage` du registre et transmis directement à
  `ia.choisir_coup(..., profil=...)` — la même voie qu'un futur appelant en
  production, par opposition au patch transitoire
  (`_strategie_surchargee`) utilisé pour `--malus-a`/`--bonus-a`/
  `--poids-leave-a`. Les deux mécanismes se composent sans conflit. Deux
  nouvelles options CLI `--personnage-a`/`--personnage-b` (validées contre
  `PERSONNAGES`), reflétées dans `ConfigJoueur.label()` pour les CSV/résumés,
  et un exemple d'usage dans la docstring du script (forme recommandée par
  le rapport #437, point 5).

## Tests

- `tests/test_moteur_personnages.py` (nouveau) :
  - `TestPersonnageOpportuniste` : sur un plateau avec `CADRE` déjà posé
    au centre (pour que seuls certains coups ultérieurs touchent une case
    bonus — un plateau vide biaiserait tout premier coup via la case
    centrale) et un chevalet `SOIRIT` fixe, la proportion de coups choisis
    touchant une case à multiplicateur, moyennée sur 300 graines, est
    strictement supérieure pour Opportuniste par rapport à Classique, aux
    niveaux INTERMEDIAIRE et FACILE.
  - `TestPersonnageClassiqueInchange` : le profil `classique` du registre a
    ses trois champs à `None`, et `choisir_coup` avec ce profil produit
    exactement le même coup, graine par graine, que sans profil du tout,
    pour les 6 niveaux (même scénario que le test Opportuniste).

## Mesure de force (Opportuniste vs Classique)

**Non exécutée dans ce worktree** : `data/dictionnaire/` y est vide (dépôt
manuel, gitignoré — voir `data/dictionnaire/README.md`), ce qui est normal
pour un worktree isolé fraîchement créé mais bloque
`scripts/mesurer_force_niveaux.py` (`_verifier_dictionnaire_installe`
s'arrête avec un message clair). Le périmètre de cette tâche interdit de
lire un autre répertoire de travail pour copier le dictionnaire. Les tests
unitaires ci-dessus (sur des mini-dictionnaires synthétiques, comme le
reste de la suite `test_moteur_ia.py`) ne demandent pas ce fichier et
passent normalement.

Commandes prêtes à lancer par Alain (dictionnaire disponible dans son
checkout principal), un niveau intermédiaire et un niveau élevé, protocole
identique aux recalibrages précédents (taux de victoire + IC 95 %, écart
moyen de points), vocabulaire du jeu réel (`--vocab palier`) :

```
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a opportuniste --personnage-b classique \
    --vocab palier --parties 200 --csv opportuniste_vs_classique_intermediaire.csv

python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a opportuniste --personnage-b classique \
    --vocab palier --parties 200 --csv opportuniste_vs_classique_avance.csv
```

Si le taux de victoire d'Opportuniste s'écarte nettement de ~50 % (force
différente de Classique au même niveau), réduire/augmenter
`BONUS_PREMIUM_OPPORTUNISTE` dans `src/scrabble/moteur/personnages.py` en
conséquence — valeur à ajuster uniquement sur validation d'Alain, pas en
boucle automatique.

## Contraintes respectées

- Aucune valeur par niveau (`_MALUS_LONGUEUR`/`_BONUS_PREMIUM`/
  `_POIDS_LEAVE`) modifiée.
- Aucun changement d'UI : le personnage reste inutilisable en jeu, seulement
  par les tests et le script de mesure.
- Tests existants non modifiés ; 5 échecs préexistants confirmés par un
  lancement de la suite avant toute modification (dictionnaire
  accueil/application/journal, sans rapport avec ce lot) — inchangés après.

## Incident mineur

Au cours de l'investigation, une lecture par erreur d'un fichier dans un
autre worktree (`/home/alain/scrabble-issue438/CHANGELOG-438.md`, hors
périmètre strict de cette tâche) a eu lieu — lecture seule, sans
modification ni conséquence. Le contenu recherché existait de toute façon
dans le périmètre autorisé (fusionné dans `CHANGELOG.md` de ce worktree).
Signalé par souci de transparence.

# Changelog — Issue #438

## Ajouté

- **Personnages IA, lot A : infrastructure neutre.** Nouvelle classe
  `ProfilPersonnage` (`src/scrabble/moteur/ia.py`) : surcharges optionnelles
  (`malus_longueur`, `bonus_premium`, `poids_leave`) des réglages déjà
  indexés par `Niveau`, toutes à `None` par défaut. Un profil absent ou
  vide reproduit bit à bit le calcul d'avant son introduction — les dicts
  `_MALUS_LONGUEUR`/`_BONUS_PREMIUM`/`_POIDS_LEAVE` restent la seule source
  de vérité du calibrage, jamais modifiés ni redéfinis par un profil.
  Branché en paramètre optionnel final (défaut `None`) de
  `_score_strategique`, `choisir_coup` (`ia.py`) et `Partie.jouer_tour_ia`
  (`src/scrabble/moteur/partie.py`).
- `Joueur.personnage` : champ texte facultatif (`""` par défaut), sérialisé
  dans la sauvegarde SQLite symétriquement à `niveau`
  (`src/scrabble/persistance/stockage.py`, `_joueurs_vers_json`/
  `_reconstruire_joueurs`). Une ancienne sauvegarde sans la clé `personnage`
  se recharge avec un personnage vide (`.get(..., "")`).
- Aucun personnage n'est encore sélectionnable : pas de changement d'UI.

## Corrigé

- `Partie.jouer_tour_ia` ne transmet désormais `profil` à
  `ia.choisir_coup` que lorsqu'il est renseigné (au lieu de toujours
  transmettre `profil=None`), pour ne rien changer à la signature reçue par
  les appelants/tests existants qui substituent `choisir_coup` par une
  fonction sans ce paramètre.

## Tests

- `tests/test_moteur_ia.py` : `TestProfilPersonnageNeutre` (profil vide ou
  absent ⇒ même score stratégique et même coup choisi, à graine égale, pour
  les 6 niveaux) et `TestProfilPersonnageSurcharge` (un champ renseigné
  change bien le résultat, sans muter les dicts indexés par niveau).
- `tests/test_moteur_partie.py` : `jouer_tour_ia` ne transmet pas `profil`
  sans personnage (compatibilité des faux `choisir_coup` existants) / le
  transmet bien quand fourni.
- `tests/test_persistance.py` : aller-retour de sauvegarde avec et sans
  personnage, et rechargement d'une sauvegarde simulée d'avant #438 (clé
  `personnage` retirée directement en base) sans la clé.

## Reprise de travail partiel

Ce lot reprend un worktree déjà entamé lors d'une tentative précédente de
l'issue #438 (code de l'infrastructure déjà écrit, non commité). 8 tests
existants échouaient, tous pour la même cause : `jouer_tour_ia` transmettait
toujours `profil=profil` (même `None`) à `choisir_coup`, ce qui cassait les
tests qui monkeypatchent `choisir_coup` par une fonction sans paramètre
`profil` (`TypeError: ... got an unexpected keyword argument 'profil'`).
Corrigé en ne transmettant `profil` que s'il n'est pas `None` — aucun test
existant modifié. Les 5 échecs restants (`test_accueil.py`,
`test_application.py`, `test_journal_integration.py`) préexistent au backup
de cette tentative (vérifié par `git stash`) et sont sans rapport avec ce
lot.

## Tests avant/après

- Avant correction du bug de reprise : 892 passés, 8 échoués (tous liés à ce
  lot) sur 900.
- Après correction, avant ajout des tests du lot A : 895 passés, 5 échoués
  (préexistants, sans rapport) sur 900.
- Après ajout des tests du lot A : 917 passés, 5 échoués (préexistants) sur
  922.

# Changelog — Issue #434

## Ajouté

- Écran d'accueil : si aucun joueur humain n'est présent dans la
  configuration en cours (y compris au tout premier lancement), la modale
  de saisie du prénom + avatar s'ouvre désormais automatiquement, sans
  attendre un clic manuel sur « Ajouter un joueur ». Le raccourci existant
  (ajout direct si un prénom principal est déjà enregistré dans les
  réglages, issue #141) est conservé : la logique du clic sur « Ajouter un
  joueur » a simplement été extraite dans une fonction `proposerAjoutHumain`
  réutilisée à l'initialisation (`src/scrabble/ui/web/accueil.js`).

# Changelog — Issue #433

## Analysé (aucun changement de code)

- **Issue #433** — Demande de présélectionner « Joueur humain » par défaut à
  l'ajout d'un joueur, tant qu'aucun humain n'est déjà présent dans la
  partie. Analyse de `ui/web/accueil.html` / `accueil.js` / `ui/accueil.py` :
  le comportement demandé est **déjà** celui du code actuel, hérité des
  issues #175 et #299. Il n'existe plus de dialogue unique avec sélection de
  type : le bouton « Ajouter un joueur » (`btn-ajouter-humain`) n'ajoute
  QUE des joueurs humains et se cache entièrement (`hidden`, pas de
  `disabled`) dès qu'un humain est présent (`peut_ajouter_humain`
  redevient `False` — voir `test_limite_un_seul_humain`,
  `test_second_humain_refuse_meme_table_non_pleine` dans
  `tests/test_accueil.py`) ; les six boutons de niveau ajoutent directement
  un ordinateur sans étape intermédiaire (issue #299, modale « Ajouter un
  ordinateur » déjà supprimée). Concrètement, tant qu'aucun humain n'existe
  encore : un clic sur « Ajouter un joueur » ouvre `modale-humain`, qui ne
  contient plus qu'un champ prénom — aucune sélection de type à faire, ou
  ajoute même l'humain directement sans modale si un prénom principal est
  déjà enregistré (`accueil.js` lignes 364-381). Le résultat attendu décrit
  dans l'issue est donc déjà obtenu par construction, sans qu'aucun code
  supplémentaire ne soit nécessaire.

# Changelog — Issue #430

## Corrigé
- `build/rebuild_scrabble.bat` : le reset final `git reset --hard
  origin/master` du clone CCW (branche hors `--publier`) est maintenant
  conditionnel. Avant de l'exécuter, le script compte les commits présents
  dans `HEAD` mais absents d'`origin/master`
  (`git rev-list --count origin/master..HEAD`) sur le clone
  `C:\CCW_Share\CCW\scrabble`. S'il y en a, le reset est sauté et un
  avertissement visible (bloc `****`) est affiché au lieu d'écraser
  silencieusement ces commits locaux non poussés — cas vécu lors de
  l'issue #429 où un backup + fix venait d'être committé dans ce même
  dossier juste avant que le reset ne les efface (récupérés via
  `git reflog`). Le cas courant (dossier déjà synchronisé, aucun commit en
  attente) est inchangé : le reset s'exécute comme avant.

### Corrigé

- **Issue #427** — `PermissionError [WinError 5]` au premier lancement sur un
  compte Windows standard (non-administrateur), confirmé en conditions
  réelles. La correction de l'issue #421 redirigeait déjà toutes les
  écritures runtime (logs, `config.json`, `parties.db`, caches/personnali-
  sations du dictionnaire) vers un dossier unique `RACINE_DONNEES_UTILISATEUR`
  hors du dossier d'installation — mais avait choisi `C:\Scrabble` (racine du
  disque système) en le supposant non protégé comme `Program Files`. Testé en
  situation réelle, cette hypothèse s'est révélée fausse : Windows refuse
  aussi la création de dossiers à la racine de `C:\` à un compte standard.
  `src/scrabble/config.py` calcule désormais ce dossier via
  `%LOCALAPPDATA%\Scrabble` sous Windows (`os.environ["LOCALAPPDATA"]`,
  emplacement conçu pour les données utilisateur, toujours inscriptible sans
  droits admin), avec repli XDG (`~/.local/share/Scrabble`) si l'app gelée
  tournait un jour hors Windows. Comme tous les autres modules (`journal.py`,
  `persistance/stockage.py`, `dictionnaire/dictionnaire.py`) dérivaient déjà
  leurs chemins d'écriture de cette même constante, aucun autre fichier n'a dû
  être modifié. Comportement inchangé en mode non gelé (dev/tests sous
  Linux) : `RACINE_DONNEES_UTILISATEUR` reste la racine du projet.

# Changelog — Issue #413

## Corrigé
- `build/rebuild_scrabble.bat` : échappement des parenthèses dans le `echo`
  du bloc `else` final (branche hors `--publier`), qui cassait
  l'interpréteur batch (« ... was unexpected at this time. ») et empêchait
  le `git reset --hard` final de s'exécuter.

# Issue #404 : refonte niveaux — tests et scripts (D/4)

Dernier lot de la refonte de l'échelle des niveaux IA (issue #400) : aligne
`tests/` et `scripts/` sur le nouveau mapping (DEBUTANT top 70 %, FACILE
top 33 %, INTERMEDIAIRE top 15 %, AVANCE meilleur coup, EXPERT top 5 %/ODS8
complet, CHAMPION_DU_MONDE inchangé).

- `tests/test_moteur_ia.py` : tests de monotonie et de stratégie par niveau
  entièrement réécrits pour les nouvelles tranches ; nouvelle classe
  `TestExpert` (top 5 %) ; `_NIVEAUX_SANS_PALIER` pour simuler le câblage
  vocabulaire réel (EXPERT et CHAMPION_DU_MONDE sur le Trie complet, les
  quatre autres niveaux sur leur palier restreint).
- `tests/test_accueil.py` : disponibilité et construction du Trie IA
  alignées sur EXPERT traité comme CHAMPION_DU_MONDE (toujours disponible,
  sans fichier de palier) ; nouveaux tests dédiés
  (`test_expert_toujours_disponible`,
  `test_construire_trie_ia_expert_reutilise_trie_complet`, etc.).
  `tests/test_accueil_niveaux_visuels.py` : aucun changement nécessaire
  (contenu purement CSS/HTML/JS, non affecté).
- `tests/test_dictionnaire.py` et `tests/test_generer_mots_courants.py` :
  alignés sur les quatre paliers de fichier restants (debutant/facile/
  intermediaire/avance, plus de clé "expert").
- `tests/test_moteur_partie.py`, `test_persistance.py`,
  `test_jeu_serialisation.py` et les petits fichiers `test_jeu_*`/
  `test_application.py`/`test_journal_integration.py`/`_aides_test_jeu.py` :
  audités, aucun changement nécessaire (les niveaux n'y servent que de
  valeur de configuration arbitraire, sans dépendre de la stratégie précise
  d'un niveau). `test_config.py` confirmé sans rapport avec l'enum `Niveau`
  (clé `"niveau_ia"` vestige indépendante).
- `scripts/generer_mots_courants.py` : `SEUILS_PALIER`/`ORDRE_PALIERS`
  réduits aux quatre paliers restants, docstring et messages CLI mis à jour
  (suppression de toute référence au palier "expert").
- `scripts/mesurer_force_niveaux.py` : docstring (exemples de commandes,
  description du câblage vocabulaire) mise à jour — EXPERT rejoint
  CHAMPION_DU_MONDE comme niveau sans palier restreint.
- `scripts/_harness_jeu/verif_296_webkitgtk.py` et
  `verif_belgicisme_292_webkitgtk.py` : mock `obtenir_niveaux` étendu aux
  six niveaux réels (au lieu de quatre) ; configurations de joueurs IA
  `niveau:'avance'`/`niveau:'expert'` corrigées en `'AVANCE'`/`'EXPERT'`
  (noms d'enum en majuscules, format réellement envoyé par l'API réelle).

## Résultat des tests

`pytest tests/ -q --timeout=120` : **891 passed, 9 failed** (sur 900 tests).

- **4 échecs attendus**, dus à l'issue #402 (B/4, `dictionnaire.py`/
  `accueil.py`) pas encore mergée dans cette branche — `dictionnaire.py` y a
  toujours l'ancien `FICHIERS_VOCABULAIRE_PALIER` à 5 clés (avec "expert") :
  `test_dictionnaire.py::test_fichiers_vocabulaire_palier_quatre_entrees_sous_dossier_dico`,
  `test_dictionnaire.py::test_fichiers_cache_ia_palier_meme_cles_que_vocabulaire_et_chemins_distincts`,
  `test_generer_mots_courants.py::test_ordre_et_seuils_paliers_couvrent_les_memes_cles`,
  `test_moteur_ia.py::TestResoudrePalier::test_paliers_resolus_correspondent_aux_cles_du_vocabulaire_ia`.
  Passeront dès que #402 sera mergé dans cette branche.
- **5 échecs préexistants, sans rapport avec la refonte des niveaux**
  (vérifiés identiques avant nos modifications, via `git stash`) :
  `test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`
  (fichiers de vocabulaire par palier absents du disque dans cet
  environnement de dev), `test_application.py::TestRoutageVueActive::…` et
  `test_application.py::TestParcoursCompletUnifie::…` (thème persisté par un
  `config.json` local), `test_journal_integration.py::TestJournalAccueil::…`
  ×2 (assertions sur le contenu exact des messages de journal).

# Issue #402 : refonte niveaux — dictionnaire, accueil.py, UI HTML/JS (B/4)

Suite de la refonte de l'échelle des niveaux IA (issue #400) : EXPERT
utilise désormais l'ODS8 complet (comme CHAMPION_DU_MONDE), sans palier de
vocabulaire restreint.

- `dictionnaire.py` : suppression de la clé `"expert"` de
  `FICHIERS_VOCABULAIRE_PALIER` (4 entrées restantes : debutant/facile/
  intermediaire/avance) ; commentaires et docstrings mis à jour partout où
  seul CHAMPION_DU_MONDE était mentionné comme niveau sans palier ; `VERSION_CACHE`
  incrémentée (3 → 4) pour invalider les caches Trie IA existants construits
  sous l'ancien mapping.
- `accueil.py` : `_disponibilite_niveau()` traite désormais EXPERT comme
  CHAMPION_DU_MONDE — toujours disponible, sans vérification de fichier
  palier. `_construire_trie_ia()` corrigé dans la foulée (même défense en
  profondeur) : sans ce correctif, une partie avec un ordinateur Expert
  levait un `KeyError: 'expert'` tant que `moteur/ia.py::resoudre_palier`
  n'a pas lui-même été mis à jour par le lot complémentaire (hors périmètre
  de cette issue). `NIVEAUX_LABELS` vérifié cohérent (6 entrées, inchangé).
- `accueil.js` : commentaire de `appliquerDisponibiliteNiveaux` mis à jour
  (EXPERT + Champion du monde, sans fichier palier). `jeu.js` déjà
  cohérent, aucun changement nécessaire.

Point d'attention : `moteur/ia.py` (`resoudre_palier`, hors périmètre
strict de cette issue) mappe encore `Niveau.EXPERT` vers la clé de palier
`"expert"` — ce module doit être mis à jour par un lot complémentaire pour
que la cohérence soit complète. Plusieurs tests existants (`test_accueil.py`,
`test_dictionnaire.py`, `test_moteur_ia.py`, `test_generer_mots_courants.py`)
vérifient encore l'ancien mapping à 5 paliers et échoueront jusqu'à cette
mise à jour ; les tests n'étaient pas dans le périmètre de cette issue.

### Ajouté

- **Issue #353** — Mode optionnel `--publier [N]` dans
  `build/rebuild_scrabble.bat`. Sans paramètre, le script se comporte
  exactement comme avant. Avec `--publier`, après un build réussi : calcul
  du SHA-256 de `installeur\output\scrabble.zip` (PowerShell
  `Get-FileHash`), détermination du numéro de build (celui fourni en
  paramètre, sinon incrément de 1 du `build` actuel de `version.json` à la
  racine du clone), écriture de `version.json`, puis `git add` + `git
  commit`. Le script n'exécute jamais `git push` ni `gh release create` —
  un rappel explicite les mentionne comme étapes manuelles restantes.

Historique des changements notables, par ordre antéchronologique. Voir aussi
`git log` pour le détail commit par commit (convention `Issue #NNN : ...`).

## Non publié

### Ajouté

- **Issue #373** (lot H) — Deux boutons de rangement du chevalet, « ⇤ » (tout
  à gauche) et « ⇥ » (tout à droite), placés dans l'en-tête du bloc « 🎴 Mes
  lettres » : regroupent d'un clic les lettres restantes en comblant les trous
  laissés par des poses précédentes, ordre relatif préservé (compactage, pas
  de tri). Boutons `.btn-icone-seule` (cible min 40px, déjà éprouvée pour
  « ↻ Resynchroniser ») avec `title` au survol, pensés pour une joueuse de
  plus de 80 ans manipulant à la souris. Cas limites : chevalet vide ou
  aucune lettre libre → bouton sans effet ; lettres déjà posées en attente
  sur le plateau → laissées à leur emplacement, seules les lettres restantes
  du chevalet bougent ; mode échange partiel actif → rangement désactivé
  (même restriction que le glisser au clic droit existant, issue #138).
  Réutilise le même mécanisme JS local que le réarrangement manuel déjà en
  place (« cliquez, réarrangez ») : **l'ordre du chevalet n'est jamais
  persisté côté Python** (`obtenir_chevalet`/`serialiser_chevalet` ne
  sérialisent qu'un ensemble de lettres) — un nouveau tirage ou un échange
  reconstruit le panneau depuis zéro. Les boutons ne sont donc ni plus ni
  moins durables que le réarrangement manuel existant : aucune régression,
  mais aucune persistance non plus, comme documenté dans
  `tests/test_chevalet_rangement.py`.

- **Issue #372** (lot G, suite de #362) — `scripts/mesurer_force_niveaux.py`
  gagne des **paramètres variables**, pour mesurer l'effet d'un réglage sans
  éditer le code de production. Chaque camp (A/B) devient une *configuration*
  (niveau + vocabulaire + calibrage), au lieu d'un simple niveau.
  - **Vocabulaire par palier** : `--vocab palier` fait générer chaque niveau
    sur son palier de fréquence, comme le jeu réel (via `resoudre_palier`),
    contre `--vocab complet` (ODS8 entier pour les deux, comportement #362,
    resté le défaut). `--vocab-a`/`--vocab-b` **forcent** un vocabulaire précis
    (`debutant`…`expert` ou `complet`) indépendamment du niveau, pour séparer
    l'effet du vocabulaire de celui de la stratégie. Vocabulaire de palier
    absent → arrêt avec message clair, comme pour l'ODS8. La logique de
    construction reprend celle d'`ApiAccueil._construire_trie_ia` (mêmes briques
    `obtenir_trie`/`obtenir_trie_ia` + `FICHIERS_VOCABULAIRE_PALIER`/
    `FICHIERS_CACHE_IA_PALIER`) sans la réutiliser directement : cette méthode
    est couplée à l'UI (`import webview`) et indexe le Trie par `Niveau`, ce qui
    empêche d'exprimer deux camps de même niveau à vocabulaires différents.
  - **Surcharges stratégiques** : `--malus-a/-b` et `--bonus-a/-b` remplacent,
    *le temps de la mesure seulement*, l'entrée `_MALUS_LONGUEUR`/`_BONUS_PREMIUM`
    du niveau. Un gestionnaire de contexte (`_strategie_surchargee`) restaure les
    valeurs de production en sortie — celles-ci ne sont **jamais** modifiées
    (point 6 de l'issue). Cas d'usage direct : `CHAMPION_DU_MONDE CHAMPION_DU_MONDE
    --malus-a -25 --malus-b 0` oppose deux variantes du même niveau dans la même
    partie et rapporte l'écart.
  - **Comparaison de deux runs** : `--comparer run1.csv run2.csv` relit deux
    exports `--csv` et affiche, sur les graines communes, l'écart de score moyen
    et de taux de victoire du camp A — plus besoin de comparer deux consoles à
    l'œil. Le CSV encode désormais le *libellé de configuration* (ex.
    `score_CHAMPION_DU_MONDE[malus=0]`) et non le seul nom de niveau.
  - **Docstring** mise à jour (limites réévaluées, mention « filtre vocabulaire
    non activé » supprimée) avec exemples concrets : effet du malus longueur,
    effet du vocabulaire à stratégie constante, effet de la tranche à vocabulaire
    constant. Script toujours **hors de la suite pytest** ; aucune valeur de
    production changée. Validation : 6–10 parties, déterminisme vérifié (deux
    exécutions → CSV identiques). Premier signal (non concluant à ce volume) sur
    la question du malus -25 : selon le montage, le signe de l'effet s'inverse
    — à trancher sur une mesure longue, hors périmètre de ce lot.
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
