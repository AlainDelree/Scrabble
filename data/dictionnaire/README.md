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
  `mots_courants_intermediaire.txt`, `mots_courants_avance.txt` — vocabulaire
  IA par palier de difficulté (issue #366, lot A ; refonte de l'échelle de
  niveaux issue #401/#404), même croisement ODS8 × Lexique 3 à quatre seuils
  de fréquence différents (respectivement ≥ 3,0, ≥ 2,0, ≥ 1,0 et ≥ 0,5). Se
  produisent **tous en une seule commande** :

      python scripts/generer_mots_courants.py --tous

  Expert et Champion du monde ne nécessitent **aucun fichier** : ils
  correspondent à l'ODS8 complet, servi directement depuis le Trie déjà
  chargé (`obtenir_trie()`). Ces quatre fichiers sont des sorties purement
  dérivées (jamais éditées à la main) : la commande ci-dessus les réécrit
  systématiquement, sans confirmation ni `--force`.

## Le joueur humain a accès à tout le dictionnaire (issue #457)

Règle absolue : **le joueur humain a accès à tous les mots du dictionnaire
complet de la partie**, quel que soit le niveau ou le personnage de
l'ordinateur adverse. Le dictionnaire de validation d'un coup humain (pose de
mot, vérification de coup, boîte « Dictionnaire ») est toujours le Trie
complet construit par `obtenir_trie(source, mode_belgicisme=...)` — jamais un
sous-ensemble filtré par niveau ou personnage.

Les fichiers de vocabulaire restreint ci-dessus (`mots_courants*.txt`) et les
Tries qu'ils produisent via `obtenir_trie_ia` ne servent **qu'à la
génération** des coups candidats de l'ordinateur
(`scrabble.moteur.ia.choisir_coup`) : ils n'interviennent jamais dans
`scrabble.moteur.validation.valider_coup`, qui reçoit toujours le Trie
complet (`Partie.dictionnaire`, voir sa docstring et celle de
`scrabble.moteur.personnages`). Si l'humain apprend un mot rare joué par un
personnage (ex. le Lettré), il peut toujours le rejouer ensuite contre
n'importe quel autre adversaire. Les belgicismes restent une option séparée,
choisie par le joueur au lancement (`mode_belgicisme`) : cette règle ne les
active ni ne les désactive, elle s'applique identiquement dans les deux
états.

## Règle git

Le fichier `.gitignore` à la racine ignore **tout** le contenu de
`data/dictionnaire/` (fichiers et sous-dossiers), à la seule exception de ce
`README.md`. Vérifiez avec `git status` qu'aucun fichier de dictionnaire
n'apparaît comme non suivi avant de committer.
