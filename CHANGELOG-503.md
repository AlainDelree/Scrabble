## Issue #503 — Contexte : restructurer CONTEXTE.md et déplacer le détail dans docs/contexte/

- **`CONTEXTE.md` : passe de 12 700 à 3 357 caractères** (`wc -m`), bien sous
  la limite d'injection de 4 000 caractères du watcher. Nouvel ordre imposé :
  règles, architecture, conventions, index des fichiers de domaine.
- **Création de `docs/contexte/`** avec quatre fichiers de domaine, chacun
  cité dans l'index de `CONTEXTE.md` :
  - `serveur_local.md` (prototype un seul joueur, verrouillage du
    dictionnaire, limites de fréquence, journal des abus) ;
  - `donnees_dictionnaire.md` (dépôt manuel ODS8/Hunspell, cache du Trie
    dans `cache/dictionnaire/`, scripts de génération) ;
  - `tests.md` (commande par défaut, marqueur `lent`, skips en dossier
    isolé) ;
  - `build_distribution.md` (PyInstaller, build Windows/Inno Setup,
    `version.json`, dépendances figées au build v15).
- **Corrections de contenu périmé**, vérifiées contre le code avant
  report : le nombre de niveaux d'IA (6, et non 5 — `CHAMPION_DU_MONDE`
  ajouté en fin d'énumération par une issue antérieure, oublié dans
  l'ancien `CONTEXTE.md`) ; la pile technique (dépendances désormais
  figées à `==` aux versions du build v15, contrôlées par
  `tests/test_requirements_figees.py`).
- **Suppression du récit d'avancement** (nombre de commits, numéro
  d'issue courant, historique des refontes) : `CONTEXTE.md` et les
  fichiers de domaine ne portent plus que l'état actuel et les règles.
  La section de maintenance du fichier principal est retirée (déjà
  couverte par les consignes globales du bridge).
- Mise à jour des références à `CONTEXTE.md` devenues obsolètes dans les
  docstrings/commentaires de `src/scrabble/serveur/{__init__,cli,httpd,
  securite}.py` et de `scripts/{generer_classiques,generer_mots_courants,
  mesurer_force_niveaux}.py`, pour pointer vers le fichier de domaine qui
  porte maintenant le contenu cité (aucun changement de comportement :
  commentaires et docstrings uniquement).
- Non touchés (contenu déjà couvert ailleurs ou hors périmètre) :
  `SMOKE_TEST.md`, `TACHES.md`, `TODO.md`, `.audit.json`, `scrabble.spec`
  — cités par l'index ou par les fichiers de domaine, pas dupliqués.
- Vérifications : suite de tests `pytest -m "not lent"` → 1468 passed, 6
  skipped, 5 deselected (comportement inchangé, aucune ligne de code
  exécutable modifiée) ; `ruff check` → 25 erreurs avant et après
  (décompte inchangé) ; recherche de références à `CONTEXTE.md` et à ses
  anciens titres de section → plus aucune référence cassée.
