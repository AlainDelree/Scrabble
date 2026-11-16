# Changelog — Issue #498

## Sécurité

- **`dictionnaire.py` : justification écrite des trois `pickle.load` du
  cache du Trie, `# nosec B301` (issue #498).**
  - `src/scrabble/dictionnaire/dictionnaire.py` (`_cache_valide`,
    `_lire_trie_cache`) : les trois appels à `pickle.load` (lecture de
    l'en-tête dans `_cache_valide`, lecture de l'en-tête puis du Trie dans
    `_lire_trie_cache`) reçoivent chacun `# nosec B301`, précédé d'une
    ligne de raison rappelant que le fichier lu est le cache écrit par
    l'application elle-même dans son dossier réservé
    `DOSSIER_CACHE_DICO`, sans donnée externe désérialisée. Aucun autre
    changement : même format de cache, même logique de fraîcheur, même
    emplacement. `bandit` ne signale plus B301 sur ce fichier (réapparaît
    avec `--ignore-nosec`, preuve que seule la suppression les masque) ;
    décompte `ruff` inchangé ; suite de tests identique avant/après.
