# Changelog — Projet Scrabble (issue #504)

## Issue #504 — Cache du dictionnaire : placer la raison juste au-dessus de chacun des deux pickle.load de _lire_trie_cache

- **`src/scrabble/dictionnaire/dictionnaire.py`, fonction `_lire_trie_cache`
  (lignes ~1095-1103)** : le commentaire explicatif unique placé avant le
  premier `pickle.load` (et le commentaire en fin de ligne du premier appel)
  sont remplacés par deux blocs de commentaires distincts, chacun juste
  au-dessus du `pickle.load` qu'il justifie — fichier écrit par
  l'application elle-même dans son dossier réservé `DOSSIER_CACHE_DICO`,
  aucune donnée externe désérialisée ; le premier précise en plus qu'il ne
  sert qu'à consommer l'en-tête pour avancer jusqu'au Trie. Les deux
  `# nosec B301` existants sont inchangés. `_cache_valide` n'est pas
  touchée (déjà conforme). Aucun changement de comportement ni de logique :
  commentaires uniquement.
- Vérifications : `ruff check` et `bandit` sur le fichier (tous deux
  disponibles dans l'environnement, aucune installation requise) →
  aucun défaut nouveau ; suite de tests `pytest -m "not lent"` → 1468
  passed, 6 skipped, 5 deselected.
