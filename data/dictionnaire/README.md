# Dictionnaires (dépôt manuel, hors git)

Ce dossier accueille les dictionnaires tiers utilisés par le projet Scrabble.
**Ces fichiers ne sont jamais commités dans le dépôt git** : leur redistribution
publique est à éviter (licence floue pour l'ODS8, licences propres pour Hunspell).

## Build et installeur : rien de ce dossier n'est embarqué (issue #460)

Le dépôt du jeu est **public** et l'updater Actualise télécharge les mises à
jour (archive de Release GitHub) sans identifiant : tout ce qui serait
embarqué dans l'archive serait donc public. Depuis l'issue #460, **aucun
fichier de `data/dictionnaire/`** (dictionnaires tiers ODS8/Hunspell,
`definitions.json`, `mots_courants*.txt`, caches `trie_cache*.pkl`,
`belgicismes_a_revoir.csv`, personnalisations `mots_ajoutes_*`/
`mots_retires_*`, listes `classiques_*`, ce `README.md` lui-même) n'est
embarqué ni dans l'archive `scrabble-vN.zip` d'Actualise, ni dans
`Scrabble-Setup.exe` (voir `scrabble.spec` et `installeur/scrabble.iss`). Ce
qui reste embarqué : les ressources de l'interface (`src/scrabble/ui/web/`),
l'icône, et le code. Les fichiers de `data/personnages/` ne sont pas
concernés par cette issue et suivent leur propre règle (voir ce dossier).

**Emplacement où déposer les données sur un PC** : à la main, après
installation du jeu, dans le dossier `data` situé à côté de `Scrabble.exe`
(`{dossier d'installation}\data\`, par défaut
`C:\Program Files\Scrabble\data\`) — mêmes sous-chemins que ci-dessous
(`French-Scrabble-ODS8-main\`, `hunspell-french-dictionaries-v7.7\`,
`Lexique383.tsv`, etc.). Sans cela, le jeu démarre normalement mais valide
zéro mot. L'installeur affiche un rappel de cet emplacement exact à la fin
de l'installation.

**Les mises à jour du jeu (Actualise) ne touchent pas aux données** :
Actualise extrait l'archive de mise à jour par-dessus le dossier
d'installation et ne supprime que les chemins listés dans le manifeste de
l'archive (`manifest.json`) — un fichier présent sur disque mais absent de
l'archive et du manifeste (c'est le cas de tout `data/dictionnaire/`,
puisqu'il n'y est jamais inclus) survit donc à toute mise à jour. Un
ordinateur déjà équipé garde ses dictionnaires d'une mise à jour à l'autre ;
seul un nouvel ordinateur demande un dépôt manuel.

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
