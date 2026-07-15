# Dictionnaires (dépôt manuel, hors git)

Ce dossier accueille les dictionnaires tiers utilisés par le projet Scrabble.
**Ces fichiers ne sont jamais commités dans le dépôt git** : leur redistribution
publique est à éviter (licence floue pour l'ODS8, licences propres pour Hunspell).

## Contenu attendu

Déposez manuellement ici, à cet emplacement, sans les ajouter au suivi git :

- `French-Scrabble-ODS8-main/` — dictionnaire officiel ODS8 (mots valides au
  Scrabble francophone).
- `hunspell-french-dictionaries-v7.7/` — dictionnaire Hunspell
  `fr-toutesvariantes` (fichiers `.aff` / `.dic`).

## Règle git

Le fichier `.gitignore` à la racine ignore **tout** le contenu de
`data/dictionnaire/` (fichiers et sous-dossiers), à la seule exception de ce
`README.md`. Vérifiez avec `git status` qu'aucun fichier de dictionnaire
n'apparaît comme non suivi avant de committer.
