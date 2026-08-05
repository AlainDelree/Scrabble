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
- `Lexique383.tsv` — base de fréquence lexicale **Lexique 3** (version 3.83,
  ~25 Mo), source de fréquence pour le vocabulaire « humain » de l'IA
  (issues #203/#205). Téléchargement : <https://www.lexique.org> (rubrique
  téléchargements → *Lexique383*). Licence **CC-BY-SA 4.0** (libre de
  redistribution, mais on ne le commite pas — même règle que les autres
  dictionnaires). Colonnes utilisées : `ortho`, `freqlivres`, `freqfilms2`.

## Fichiers générés (également hors git)

- `mots_courants.txt` — ensemble des mots ODS8 jugés « courants » d'après
  Lexique 3, un mot par ligne (normalisé comme l'ODS8 : MAJUSCULES, **sans
  accent**). Produit par `scripts/generer_mots_courants.py` (issue #205) par
  croisement ODS8 × `Lexique383.tsv`, au seuil par défaut (1 occ./million).
  Se régénère à tout moment ; n'a pas à être déposé manuellement.

- `mots_courants_debutant.txt`, `mots_courants_facile.txt`,
  `mots_courants_intermediaire.txt`, `mots_courants_avance.txt`,
  `mots_courants_expert.txt` — vocabulaire IA par palier de difficulté (issue
  #366, lot A), même croisement ODS8 × Lexique 3 à cinq seuils de fréquence
  différents (respectivement ≥ 3,0, ≥ 2,0, ≥ 1,0, ≥ 0,5 et l'intersection
  brute sans seuil pour Expert). Se produisent **tous en une seule commande** :

      python scripts/generer_mots_courants.py --tous

  Le sixième palier, **Champion du monde**, ne nécessite **aucun fichier** :
  il correspond à l'ODS8 complet, servi directement depuis le Trie déjà
  chargé (`obtenir_trie()`). Ces cinq fichiers sont des sorties purement
  dérivées (jamais éditées à la main) : la commande ci-dessus les réécrit
  systématiquement, sans confirmation ni `--force`.

## Règle git

Le fichier `.gitignore` à la racine ignore **tout** le contenu de
`data/dictionnaire/` (fichiers et sous-dossiers), à la seule exception de ce
`README.md`. Vérifiez avec `git status` qu'aucun fichier de dictionnaire
n'apparaît comme non suivi avant de committer.
