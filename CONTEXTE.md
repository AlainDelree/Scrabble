# CONTEXTE — Projet Scrabble

## Règles
- Le dictionnaire de jeu (`data/dictionnaire/`) n'est jamais public : aucun
  mot du dictionnaire ne doit apparaître dans un rapport ou une issue.
- `.audit.json` (racine) est tenu à la main par Alain : ne jamais le
  modifier depuis une issue. Note de révision : son exception pour le
  serveur local sans authentification, et la déclaration elle-même,
  deviennent caduques ou à revoir dès l'arrivée des comptes joueurs, du
  stockage par joueur ou d'un VPS — à signaler alors à Alain.
- Le serveur local (`scrabble.serveur`) est un prototype à un seul joueur
  de confiance, sans authentification, jamais à exposer sur Internet ; les
  fonctions qui permettraient de reconstituer le dictionnaire sont
  verrouillées côté serveur — détail : `docs/contexte/serveur_local.md`.
- Cache du Trie du dictionnaire : `cache/dictionnaire/`, toujours distinct
  de `data/dictionnaire/` où sont déposés manuellement les dictionnaires
  tiers.
- Commande de test par défaut : `pytest -m "not lent"` (exclut les tests
  lents).
- Code, docstrings et commentaires en français. Séparation stricte moteur
  (`src/scrabble/moteur/`, sans UI) / interface (`src/scrabble/ui/`,
  pywebview).

## Architecture
Scrabble francophone solo (une joueuse humaine contre un à trois
ordinateurs, IA à 6 niveaux). Application desktop empaquetée en exécutable
Windows via PyInstaller (`scrabble.spec`) ; interface **pywebview**
(fenêtres natives, HTML/CSS/JS) — pas une application web servie sur le
réseau par défaut.

`main.py` ajoute `src/` à `sys.path` puis appelle
`scrabble.ui.accueil.main()` (accueil → jeu).

`src/scrabble/` :
- `moteur/` — cœur logique sans UI (plateau, tirage, partie, score,
  validation, règles, ia, générateur de coups).
- `regles/` — lettres (sac, valeurs, joker) et plateau (cases
  multiplicatrices).
- `dictionnaire/` — Trie de validation des mots.
- `persistance/` — stockage SQLite (`data/parties.db`).
- `ui/` — fenêtres pywebview (accueil, jeu, application,
  backend_graphique) + assets front `ui/web/`.
- `serveur/` — prototype HTTP local (voir Règles et
  `docs/contexte/serveur_local.md`).
- `config.py`, `reglages.py`, `journal.py` (logs dans `logs/`).

`scripts/` = outils hors-jeu (génération d'assets, construction du
dictionnaire de définitions, mesure de force des niveaux IA) ;
`_harness_jeu/` = harnais Playwright de vérification visuelle.

## Conventions
- Docstrings d'en-tête référençant les numéros d'issue GitHub.
- Écritures fichier atomiques (`os.replace`) ; configuration
  auto-réparante.
- `SMOKE_TEST.md` = checklist de tests manuels obligatoires avant
  livraison (le rendu WebKitGTK réel n'est pas couvert par les tests
  headless).
- Tâches en attente : `TACHES.md` et `TODO.md`.

## Index des fichiers de domaine
- `docs/contexte/serveur_local.md` — avant de toucher
  `scrabble/serveur/` : verrouillage du dictionnaire, limites de
  fréquence, journal des abus.
- `docs/contexte/donnees_dictionnaire.md` — avant de toucher
  `data/dictionnaire/`, `cache/dictionnaire/` ou les scripts de
  génération (classiques, mots courants, définitions).
- `docs/contexte/tests.md` — avant de modifier la suite de tests,
  `pytest.ini` ou les dossiers de travail isolés.
- `docs/contexte/build_distribution.md` — avant de toucher
  `scrabble.spec`, `requirements.txt` ou le packaging Windows.
