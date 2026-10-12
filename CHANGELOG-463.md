# Changelog — Issue #463

## Corrigé

- **Dictionnaires absents : message clair au lieu d'un jeu qui valide zéro
  mot ou d'une IA qui passe en silence.** Depuis que les dictionnaires ne
  sont plus embarqués dans l'archive ni dans l'installeur (issue #460), un
  nouveau PC — ou un PC dont `data\dictionnaire\` a été effacé — démarrait
  le jeu normalement tout en validant zéro mot, en violation de la règle
  d'Alain (le joueur humain a accès à tout le dictionnaire de la partie). La
  partie refuse désormais explicitement de démarrer ou de reprendre quand le
  dictionnaire de validation est absent ou vide.

  - **`src/scrabble/dictionnaire/dictionnaire.py`** : nouvelle fonction
    `message_dictionnaire_indisponible(dossier=DOSSIER_DICO)` — message
    convivial en français, sans vocabulaire technique, nommant le dossier
    exact où déposer les données et invitant à contacter Alain.
    `paliers_disponibles()` considère désormais aussi indisponible un
    fichier de vocabulaire de niveau **présent mais vide**
    (`stat().st_size > 0`, simple appel système — aucune lecture de
    contenu, donc aucun coût perceptible), pas seulement un fichier absent.
  - **`src/scrabble/ui/accueil.py`** : `lancer_partie()` et `reprendre()`
    vérifient, juste après `obtenir_trie(source, ...)`, que le Trie renvoyé
    n'est pas vide (`getattr(trie, "taille", None) == 0` — et non `len()`,
    pour rester neutre face aux doubles de test minimaux qui n'exposent que
    `contient()`). Si vide, la création/reprise est refusée avant toute
    autre opération, avec `message_dictionnaire_indisponible()` et une
    entrée `journal.erreur`. Sur un PC dont les données sont présentes (cas
    normal, PC déjà installés), le Trie est non vide et ce contrôle n'a
    aucun effet visible ni coût notable — il réutilise le Trie déjà construit
    par le chemin existant (cache disque inclus), sans lecture
    supplémentaire. Le vocabulaire par niveau (paliers) était déjà contrôlé
    en amont (issue #369, lot C, `_disponibilite_niveau`) : il bénéficie
    automatiquement du renforcement de `paliers_disponibles()` ci-dessus
    (fichier vide désormais traité comme absent), sans changement de code
    supplémentaire côté accueil.
  - **`src/scrabble/moteur/partie.py`** : défense en profondeur dans
    `Partie.jouer_tour_ia` — si l'ordinateur passe son tour (`coup is None`)
    alors que le Trie de son niveau a une `taille` de 0, l'anomalie est
    consignée dans le journal (`journal.erreur`, via l'alias `journal_app`
    pour ne pas masquer la variable locale `journal` du journal de décision
    IA) plutôt que de laisser l'ordinateur passer tous ses tours sans
    aucune trace. Ne change ni le moteur d'IA, ni les réglages par niveau,
    ni le comportement de jeu : seulement un `journal.erreur` en plus dans
    un cas qui ne devrait jamais se produire en pratique (le contrôle de
    l'accueil ci-dessus bloque déjà la création/reprise en amont).
  - **`installeur/scrabble.iss`** et **`data/dictionnaire/README.md`** :
    textes harmonisés — le message de fin d'installation et le README
    décrivent désormais le nouveau comportement (partie bloquée avec
    message, plus « démarre normalement en validant zéro mot »).

  Emplacement du contrôle : au lancement/reprise d'une partie (pas au
  démarrage de l'application), pour rester un garde-fou ciblé sans ajouter
  de vérification à l'ouverture de l'accueil (où rien ne charge encore de
  dictionnaire).

  Moteur d'IA, réglages par niveau et comportement du jeu quand les données
  sont présentes inchangés. 1400 tests avant ce lot : 1395 verts (5 échecs
  préexistants, sans rapport, confirmés par `git stash` : deux dans
  `test_journal_integration.py::TestJournalAccueil`, un dans
  `test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`,
  deux dans `test_application.py`) ; après ce lot, 1409 tests (9 nouveaux),
  1404 verts, mêmes 5 échecs préexistants seuls restants.
