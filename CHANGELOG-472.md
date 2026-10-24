# Changelog — Issue #472

## Modifié

- **`build\rebuild_scrabble.bat` : syntaxe harmonisée avec Rummikub et
  Actualise, `[--publier] [--build N]`.** Les deux options sont acceptables
  dans n'importe quel ordre. L'ancienne forme `--publier N` (numéro accolé
  à `--publier`) n'est plus acceptée : `N` seul après `--publier` est
  désormais un argument inconnu, refusé avec un message qui indique la
  nouvelle syntaxe. Tout argument inconnu, ou `--build` sans valeur, est
  refusé (code de sortie non nul, avant toute construction) au lieu d'être
  ignoré. Sans `--build`, le numéro de build par défaut est désormais le
  build de `version.json` + 1 dans tous les modes, y compris sans
  `--publier` (auparavant, hors `--publier`, le build utilisé était celui
  de `version.json` sans incrément). Conséquence assumée : un lancement
  sans argument — dont celui de `rebuild_scrabble_manuel.bat`, non modifié
  — construit désormais le build suivant.
- **Garde-fou du numéro de build, dans tous les modes.** Dès l'analyse des
  arguments, avant toute copie, construction ou écriture, le script lit le
  build de `version.json` à la racine du worktree et refuse tout numéro
  (fourni ou par défaut) qui n'est pas un entier strictement supérieur à ce
  build. Un refus ne laisse aucune trace (aucun fichier écrit, aucun
  dossier créé).
- **Copie des artefacts hors du worktree.** Nouvelle étape `[9/9]`, juste
  après la recopie vers `installeur\output` du worktree et avant le bloc
  `--publier` : l'installeur et l'archive sont également copiés dans
  `C:\CCW_Share\_derniers_builds\scrabble\` (créé si absent), pour survivre
  à la suppression du worktree (`installeur\output` est ignoré par git —
  perte constatée sur l'installeur Rummikub v13). Mêmes variables de nom
  que le reste du script, jamais de numéro ni de nom codé en dur. Le
  script affiche les noms exacts et les tailles en octets des deux
  fichiers copiés. Une copie qui échoue arrête le script avant l'écriture
  de `version.json`. Numérotation des étapes et commentaire d'en-tête mis
  à jour en conséquence.

## Essais

- Essai nominal `build\rebuild_scrabble.bat --build 99` (sans `--publier`,
  99 fictif) : build complet, artefacts copiés et affichés dans le dossier
  fixe, `version.json` inchangé.
- Refus vérifiés, chacun avant toute construction, sans aucun fichier
  écrit : `--build 13` (égal au build courant), un numéro inférieur, une
  valeur non numérique, `--build` sans valeur, un argument inconnu,
  l'ancienne forme `--publier 14`, et `--publier --build 13`.
