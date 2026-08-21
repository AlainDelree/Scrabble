# Changelog — Issue #413

## Corrigé
- `build/rebuild_scrabble.bat` : échappement des parenthèses dans le `echo`
  du bloc `else` final (branche hors `--publier`), qui cassait
  l'interpréteur batch (« ... was unexpected at this time. ») et empêchait
  le `git reset --hard` final de s'exécuter.
