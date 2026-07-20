# CONTEXTE — Projet Scrabble

## Objectif
Jeu de **Scrabble francophone** en solo : une joueuse humaine affronte un à
trois ordinateurs (IA, niveaux Débutant/Facile/Intermédiaire/Expert).
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
  (`accueil/jeu/chevalet` .html/.css/.js, avatars SVG, images).
- **`config.py`** (config auto-réparante `config.json`), `reglages.py`,
  `journal.py` (logs dans `logs/`).

Hérité/non utilisé (ne pas s'y fier) : `src/scrabble/interface/` (stub « non
implémenté »), `src/scrabble/ia/`, `src/scrabble/generateur/` et le dossier
racine **`web/`** — vestiges d'une ancienne interface web abandonnée.

`scripts/` = outils hors-jeu (génération d'avatars/icônes, construction du
dictionnaire de définitions, filtres Wiktionnaire) et `_harness_jeu/`
(harnais Playwright + captures de vérification visuelle).

## Données
`data/dictionnaire/` (gitignoré) reçoit **manuellement** les dictionnaires
tiers — **ODS8** (défaut) ou **Hunspell** déplié — avant tout build, sinon le
jeu démarre mais valide zéro mot. Contient aussi `definitions.json`,
personnalisations `mots_ajoutes_*`/`mots_retires_*` (une paire par source) et
le cache `trie_cache.pkl`.

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

## Maintenance de ce fichier
Si la tâche que tu exécutes modifie l'architecture, les dépendances, les
conventions de code, ou l'état d'avancement majeur de ce projet, mets à
jour ce CONTEXTE.md en conséquence, dans le même commit.
