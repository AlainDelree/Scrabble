# Changelog — Issue #481

## Modifié

- **`build\rebuild_scrabble.bat` : harmonisation avec les scripts de build de
  Rummikub et d'Actualise (manifeste, reset, rappel final, arrêt de
  processus).**
  - **Manifeste (étape 7/9).** `manifest.json` écrit désormais le vrai
    numéro de build (`!NOUVEAU_BUILD!`, déjà défini à l'étape 0bis) au lieu
    du `1` fixe précédent. Le champ `supprimer` et l'absence de BOM UTF-8
    sont inchangés.
  - **Retrait du reset obsolète.** Le bloc de fin de script qui calculait
    les commits locaux non poussés et exécutait
    `git -C %ORIGDIR% reset --hard origin/master` (reste de l'ancien modèle
    de clone partagé) est supprimé, avec son bandeau « RESET IGNORE » et la
    mention « aucun reset » du mode `--publier`. Dans un worktree, ce reset
    pouvait effacer des modifications non commitées.
  - **Rappel de fin de `--publier`.** Remplacé par un rappel détaillant
    l'ordre des trois étapes manuelles restantes (fusion de la branche sans
    pousser, création de la Release avec les deux fichiers attachés,
    push de `master`).
  - **Étape 3/9 (Scrabble.exe).** Le script ne force plus la fermeture de
    `Scrabble.exe` (`taskkill /im Scrabble.exe /f`) : le build se déroule
    entièrement dans `C:\Temp\ScrabbleBuild` (recréé à l'étape 1), une
    instance installée ailleurs ne bloque aucun fichier du build. L'étape se
    limite désormais à signaler une éventuelle instance en cours, sans
    l'arrêter, sur le modèle d'Actualise ; l'attente de deux secondes qui
    suivait l'arrêt est retirée.
