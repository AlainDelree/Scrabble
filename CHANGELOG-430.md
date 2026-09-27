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
