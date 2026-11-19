# Changelog — Projet Scrabble (issue #509)

## Issue #509 — Cache du dictionnaire : la dernière ligne du commentaire du second pickle.load doit porter toute la raison

- **Un seul commentaire modifié**, dans `_lire_trie_cache`
  (`src/scrabble/dictionnaire/dictionnaire.py:1101-1102`), précédant le
  second `pickle.load` (celui qui charge le Trie lui-même, ligne 1104).
  L'ancien bloc de trois lignes finissait sur « désérialisée. » seule,
  dépendante des deux lignes précédentes pour être comprise — l'audit
  SEC-003 ne retient que la dernière ligne comme raison et la jugeait
  insuffisante. Nouvelle dernière ligne, autonome et complète : « Fichier
  d'appli, DOSSIER_CACHE_DICO réservé : rien d'externe désérialisé. »,
  qui porte à elle seule les deux faits requis (fichier écrit par
  l'application elle-même, dans son dossier réservé, donc rien d'externe
  n'est désérialisé).
- Le premier `pickle.load` de `_lire_trie_cache` (ligne 1100) et celui de
  `_cache_valide` (ligne 1073), déjà jugés conformes, n'ont pas été
  touchés ; aucune ligne de code, aucun `# nosec B301` ni `.audit.json`
  modifiés.
- `ruff check --no-cache .` : 0 erreur. `pytest -m "not lent"` : 1468
  passed, 6 skipped, 5 deselected, aucun test modifié.
