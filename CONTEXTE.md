# CONTEXTE — Projet Scrabble

## Objectif
Jeu de **Scrabble francophone** en solo : une joueuse humaine affronte un à
trois ordinateurs (IA, 5 niveaux Débutant/Facile/Intermédiaire/Avancé/Expert).
Application **desktop** empaquetée en exécutable Windows via **PyInstaller**
(`scrabble.spec`, mode `--onedir`, cf. issue #154). L'interface utilise
**pywebview** : des fenêtres natives affichent du HTML/CSS/JS, rendu par
WebKitGTK sous Linux (dév) et EdgeChromium sous Windows (prod). Ce n'est PAS
une application web servie sur le réseau.

## Point d'entrée
`main.py` ajoute `src/` au `sys.path` (sauf si gelé) puis appelle
`scrabble.ui.accueil.main()`, qui ouvre l'écran d'accueil (composition de la
table, réglages) puis enchaîne vers l'écran de jeu.

## Architecture (`src/scrabble/`)
- **`moteur/`** — cœur logique, sans UI : `plateau`/`plateau_partie`,
  `tirage`, `ordre`, `partie`, `score`, `validation`, `regles`, `ia`,
  `generateur` (recherche des coups possibles).
- **`regles/`** — `lettres.py` (sac, valeurs, joker) et `plateau.py` (cases
  multiplicatrices, `TypeCase`).
- **`dictionnaire/`** — `Trie` de validation des mots.
- **`persistance/`** — `stockage.py`, sauvegarde des parties en SQLite
  (`data/parties.db`).
- **`ui/`** — fenêtres pywebview (`accueil`, `jeu`, `application`,
  `backend_graphique`, `noms_ordinateur`) + assets front dans **`ui/web/`**
  (`accueil/jeu` .html/.css/.js, avatars SVG, images ; le chevalet est une zone
  intégrée à `jeu.html`, plus de fenêtre ni de fichier `chevalet.*` — issues
  #187/#193).
- **`config.py`** (config auto-réparante `config.json`), `reglages.py`,
  `journal.py` (logs dans `logs/`).
- **`serveur/`** — prototype de serveur HTTP local, un seul joueur (issue
  #475) : sert `ui/web/` dans un navigateur à la place d'une fenêtre
  pywebview, en réutilisant tel quel le routeur d'API (`ui.application.
  ApiRouteur`). Voir « Serveur local (prototype) » plus bas.

Note : les anciens sous-paquets reliquats `src/scrabble/interface/`,
`src/scrabble/ia/`, `src/scrabble/generateur/` et le dossier racine `web/`
(vestiges d'une interface web abandonnée) ont été supprimés (issue #229). Le
vrai code vit désormais dans `scrabble.moteur.generateur`, `scrabble.moteur.ia`,
`scrabble.ui.application` et `src/scrabble/ui/web/` respectivement.

`scripts/` = outils hors-jeu (génération d'avatars/icônes, construction du
dictionnaire de définitions, filtres Wiktionnaire, mesure manuelle de la force
relative des niveaux IA sur parties complètes via `mesurer_force_niveaux.py`,
issue #362) et `_harness_jeu/` (harnais Playwright + captures de vérification
visuelle).

## Données
`data/dictionnaire/` (gitignoré) reçoit **manuellement** les dictionnaires
tiers — **ODS8** (défaut) ou **Hunspell** déplié — nécessaires pour **jouer**
(pas pour construire l'installeur, issue #460), sans quoi le jeu refuse de
démarrer/reprendre une partie (issue #463). Contient aussi `definitions.json`,
personnalisations `mots_ajoutes_*`/`mots_retires_*` (une paire par source), la
liste des « classiques du jeu » `classiques_ajoutes.txt`/`classiques_retires.txt`
(étiquette sur le mot lui-même, gérée depuis l'onglet Dictionnaire, amorcée par
`scripts/generer_classiques.py`, issue #204) et le cache `trie_cache.pkl`.
Reçoit aussi manuellement `Lexique383.tsv` (Lexique 3, base de fréquence
lexicale, CC-BY-SA 4.0), croisé avec l'ODS8 par
`scripts/generer_mots_courants.py` (issue #205) pour produire `mots_courants.txt`
(vocabulaire « humain » de l'IA — croisement **désaccentué** car l'ODS8 est
stocké sans accents ; consommé par le futur filtre de vocabulaire, issue C).

## Serveur local (prototype, issue #475)
Prototype **un seul joueur de confiance**, pour essayer l'interface existante
dans un navigateur (bureau, puis téléphone sur le même réseau local) sans
attendre la vraie version « serveur » du jeu. Bibliothèque standard
uniquement (`http.server`) : aucune dépendance ajoutée.

```
PYTHONPATH=src python -m scrabble.serveur [--reseau] [--port 8765] [--dossier-donnees CHEMIN]
```

- Par défaut : écoute sur `127.0.0.1` seulement (cette machine). `--reseau`
  bascule sur `0.0.0.0` (joignable depuis un téléphone du même réseau local) —
  l'agent ne touche à aucun pare-feu, à vous de l'ouvrir si besoin.
- Port par défaut **8765** (délibérément différent de 8000).
- `--dossier-donnees` : dossier de données utilisateur du serveur
  (`config.json`, `data/parties.db`, `logs/`) — **distinct** de celui de
  l'application de bureau par défaut (`~/.local/share/scrabble-serveur` sur
  Linux), pour ne jamais mélanger ni écraser les parties du bureau. Le
  dictionnaire (`data/dictionnaire/`, lu depuis la racine du dépôt) n'est lui
  jamais copié ni redirigé : il reste la seule copie en lecture, partagée.

**AUCUNE authentification.** Affiché au démarrage : réservé à un réseau local
de confiance, jamais à exposer sur Internet.

**Une seule partie à la fois** (même modèle que le bureau : un seul routeur
d'API par processus). Un second navigateur qui se connecte partage le MÊME
état de partie que le premier (pas de comptes, pas de session par onglet) —
prototype, non résolu.

Les fonctions qui, côté bureau, supposent une fenêtre pywebview native sont
adaptées dans `serveur/` sans toucher à `ui/` :
- navigation Accueil↔Jeu (`demarrer_jeu`/`retourner_accueil`/
  `recommencer_jeu`/`annuler_tirage_accueil`) : le routeur laissé sans fenêtre
  (code déjà prévu) saute sa navigation Python ; le script injecté dans les
  pages HTML navigue à sa place (`window.location.href`) sur succès ;
- diffusion d'état après chaque coup (`ApiJeu._diffuser`, qui pousse
  normalement via `window.evaluate_js`) : relayée en Server-Sent Events
  (`/__scrabble__/evenements`) vers `window.appliquerEtatPlateau`/
  `appliquerEtatChevalet`, déjà présents dans `jeu.js` ;
- positionnement/maximisation de fenêtre (`_maximiser_plateau` et consorts) :
  déjà tolérants à une fenêtre absente (code existant, testé comme tel) —
  aucune adaptation nécessaire.

Limites connues de ce prototype (voir le rapport de clôture de l'issue #475
pour le détail) : onglet Dictionnaire des réglages et `verifier_mot`/
`verifier_coup` restent, pour l'instant, un oracle de dictionnaire utilisable
par quiconque atteint le serveur — leur verrouillage est le chantier suivant,
volontairement hors de cette issue.

## Stack (`requirements.txt`)
`pywebview` (UI), `pyinstaller` (build .exe), `pytest` (tests), `spylls`
(dépliage Hunspell, requis seulement pour la source « hunspell »).

## Conventions
- Code, noms de modules, docstrings et commentaires **en français**.
- Séparation stricte moteur (pur, testable) / UI (pywebview).
- Docstrings d'en-tête référençant les numéros d'issue GitHub.
- Écritures fichier atomiques (`os.replace`) ; config auto-réparante.
- Tests **pytest** dans `tests/` (`pytest.ini` : `pythonpath = src`,
  `testpaths = tests`), ~22 fichiers `test_*.py` couvrant surtout le moteur.
- `SMOKE_TEST.md` = checklist de tests **manuels** obligatoires avant
  livraison (les tests headless Chromium ne couvrent pas le rendu WebKitGTK
  réel).

## État d'avancement
Projet mature et jouable (~328 commits, ~issue #188). Écran d'accueil, moteur,
IA multi-niveaux, persistance, packaging Windows et refonte récente de l'écran
de jeu (2 colonnes, chevalet intégré, issues #186/#187) en place. Tâches
restantes : voir `TACHES.md` (confirmations modales, tri des « derniers
coups », sélection auto du joueur humain, onglet dictionnaire des réglages,
avatars) et `TODO.md` (restriction de vocabulaire par niveau d'IA).

## Tests
~1 400 tests, 2 à 3,5 minutes en séquentiel (`pytest.ini` : `pythonpath = src`,
`testpaths = tests`). Par défaut, lancer **sans** les tests lents :

```
pytest -m "not lent"
```

Neuf tests (9 à 44 s, surtout `tests/test_moteur_ia.py::TestProgressionTrieIaRestreint`,
simulations de parties complètes) portent le marqueur `lent` (déclaré dans
`pytest.ini`). Ils restent dans la suite complète — seule l'exclusion via
`-m "not lent"` est ajoutée. Relancer la suite **complète** (avec les tests
lents) uniquement si le travail modifie le moteur d'IA, les réglages de
niveau ou la progression des niveaux, et dans tous les cas une seule fois en
fin de travail :

```
pytest
```

Si `pytest-xdist` est installé (ne pas l'installer sinon), paralléliser avec
`-n auto` sur l'une ou l'autre commande.

Dans un dossier de travail isolé (clone secondaire sans les données
manuellement déposées dans `data/dictionnaire/`, ni config.json persistant du
poste), cinq tests sont ignorés proprement (`SKIPPED`, raison explicite dans
le rapport pytest) — vocabulaire IA par palier ou `config.json` du poste
absents, sans rapport avec le code modifié. Ils s'exécutent normalement sur
un poste complet qui possède ces données. **Ne pas relancer la suite sur le
code d'origine pour comparer** : ces skips suffisent à distinguer un échec
préexistant d'un échec introduit, sauf échec inattendu et lié aux fichiers
modifiés.

## Maintenance de ce fichier
Si la tâche que tu exécutes modifie l'architecture, les dépendances, les
conventions de code, ou l'état d'avancement majeur de ce projet, mets à
jour ce CONTEXTE.md en conséquence, dans le même commit.
