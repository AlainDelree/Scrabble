# Changelog — Issue #457

## Ajouté

- **Tests de garde : le joueur humain a accès à tous les mots du
  dictionnaire de la partie, quel que soit le personnage ou le niveau de
  l'ordinateur.** Lecture de code (`scrabble.moteur.partie.Partie`,
  `scrabble.ui.accueil.ApiAccueil.lancer_partie`, `scrabble.ui.jeu.
  simuler_coup`/`verifier_mot_dictionnaire`) confirmant qu'aucun écart
  n'existe : `Partie.dictionnaire` (le Trie complet construit par
  `obtenir_trie(source, mode_belgicisme=...)`) valide **toujours** un coup,
  humain ou IA, dans `Partie.jouer_coup` → `valider_coup(..., self.
  dictionnaire)` ; `Partie.dictionnaires_ia`/`ProfilPersonnage` (vocabulaire
  par palier, `vocabulaire_long`, `mots_favoris`) ne pilotent QUE la
  génération des coups candidats de l'ordinateur
  (`scrabble.moteur.ia.choisir_coup`), jamais la validation. La boîte
  « Dictionnaire » (`ApiJeu.verifier_mot` → `verifier_mot_dictionnaire`)
  reçoit elle aussi systématiquement `self._partie.dictionnaire`.

  - **`tests/test_garde_dictionnaire_humain.py`** (nouveau, 74 tests) :
    dictionnaires fabriqués (le dictionnaire réel est absent de ce worktree
    isolé). Pour chaque combinaison niveau × personnage disponible du
    registre (`personnages_disponibles_a_niveau`), et pour les deux états
    de l'option belgicismes, vérifie qu'une partie construite avec cette
    configuration d'ordinateur valide un échantillon de mots (vocabulaire
    courant, mot hors vocabulaire restreint, mot favori, mot court, mot de
    7 lettres hors vocabulaire du niveau, mot absent) exactement comme une
    partie sans ordinateur. Vérifie aussi l'identité de l'objet
    `Partie.dictionnaire` (jamais substitué par un Trie restreint) et que
    tout mot réellement joué par Titeuf/Lettré/Chasseur de scrabbles grâce
    à `mots_favoris`/`vocabulaire_long` (donc absent du vocabulaire
    restreint de son niveau) est accepté par cette même validation.

  - **`src/scrabble/moteur/personnages.py`** : nouvelle section dans la
    docstring du module énonçant la règle et renvoyant à
    `data/dictionnaire/README.md`.

  - **`data/dictionnaire/README.md`** : nouvelle section « Le joueur
    humain a accès à tout le dictionnaire (issue #457) ».

  Aucun écart constaté ; aucune modification de comportement du jeu ou des
  personnages. Tests : 1275 → 1349 verts (+74), les 11 échecs déjà présents
  avant ce lot (confirmés par `git stash`, notamment
  `TestPersonnageLettre`/`TestPartVocabulaireCourtChasseur` dans
  `tests/test_moteur_personnages.py`) restent inchangés et hors périmètre.
