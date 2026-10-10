# Changelog — Projet Scrabble

Convention d'ajout : voir §10 de BRIDGE_AGENT_DOC.md.

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
