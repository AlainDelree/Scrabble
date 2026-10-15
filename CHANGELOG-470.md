# Changelog — Issue #470

## Build

- **Build 13 construit (mode publication, sans publication effective).**
  `build\rebuild_scrabble.bat --publier 13` exécuté avec succès depuis le
  worktree. Archive `scrabble-v13.zip` (77 fichiers, aucun dictionnaire ni
  liste de mots) et installeur `Scrabble-Setup-v13.exe` générés dans
  `installeur\output\`. `version.json` mis à jour et committé localement
  par le script (`51b503d`). Ni `git push` ni `gh release create` exécutés :
  ces étapes restent manuelles pour Alain (voir issue #470 pour le détail
  des vérifications effectuées).
