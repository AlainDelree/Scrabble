# Changelog — Projet Scrabble (issue #507)

## Issue #507 — Linter : poser 12 noqa motivés (9 BLE001, 2 TRY004, 1 SIM115) et journaliser l'erreur de lister_parties_en_cours

- **12 `# noqa` motivés posés**, chacun avec une raison propre au code exact
  du bloc, sans rétrécissement d'exception : `main.py` (1 BLE001),
  `src/scrabble/actualise.py` (1 BLE001), `src/scrabble/journal.py` (1
  SIM115), `src/scrabble/ui/accueil.py` (6 BLE001),
  `src/scrabble/ui/jeu.py` (2 TRY004, `_lire_placement`, raison imposée :
  `jouer_placements` et `simuler_coup` rattrapent `ValueError`, le type
  d'exception ne doit pas changer).
- **SIM115 (`journal.py:108`)** : raison imposée — le fichier de session
  est gardé ouvert pendant toute la session, fermé explicitement par
  `cloturer()`, donc un gestionnaire de contexte ne convient pas.
- **Seul changement de comportement** : `lister_parties_en_cours`
  (`ui/accueil.py`) journalise désormais l'erreur (`journal.erreur(...)`)
  avant de retomber sur une liste vide ; elle ne journalisait rien
  auparavant.
- `ruff check --no-cache .` : 0 erreur, aucun `RUF100`. `pytest -m "not
  lent"` : 1468 passed, 6 skipped, 5 deselected, aucun test modifié.
