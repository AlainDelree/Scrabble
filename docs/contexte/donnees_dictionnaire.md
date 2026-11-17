# Données et cache du dictionnaire

À lire avant de toucher `data/dictionnaire/`, `cache/dictionnaire/` ou les
scripts de génération (`scripts/generer_classiques.py`,
`scripts/generer_mots_courants.py`, `scripts/mesurer_force_niveaux.py`).

`data/dictionnaire/` (gitignoré) reçoit **manuellement** les dictionnaires
tiers — **ODS8** (défaut) ou **Hunspell** déplié — nécessaires pour
**jouer** (pas pour construire l'installeur, qui ne les embarque pas),
sans quoi le jeu refuse de démarrer/reprendre une partie. Contient aussi :

- `definitions.json` ;
- personnalisations `mots_ajoutes_*`/`mots_retires_*` (une paire par
  source) ;
- la liste des « classiques du jeu »
  `classiques_ajoutes.txt`/`classiques_retires.txt` (étiquette sur le mot
  lui-même, gérée depuis l'onglet Dictionnaire des réglages, amorcée par
  `scripts/generer_classiques.py`) ;
- `Lexique383.tsv` (Lexique 3, base de fréquence lexicale, CC-BY-SA 4.0,
  déposé manuellement), croisé avec l'ODS8 par
  `scripts/generer_mots_courants.py` pour produire `mots_courants.txt`
  (vocabulaire « humain » de l'IA — croisement **désaccentué** car l'ODS8
  est stocké sans accents ; consommé par le futur filtre de vocabulaire
  par niveau d'IA, encore à faire — voir `TODO.md`).

Le cache du Trie (`trie_cache.pkl`, `trie_ia_cache*.pkl`, désérialisés par
`pickle.load`) vit dans `cache/dictionnaire/` — un dossier **séparé**,
jamais celui où l'on dépose les dictionnaires tiers, pour qu'un fichier
déposé à la main ne puisse jamais être rechargé comme cache.

`scripts/mesurer_force_niveaux.py` (mesure manuelle de la force relative
des niveaux IA sur parties complètes) nécessite lui aussi le dictionnaire
réellement installé dans `data/dictionnaire/` et s'arrête avec un message
clair s'il est absent, plutôt que de mesurer sur un dictionnaire vide.
