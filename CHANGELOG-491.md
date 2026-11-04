# Changelog — Issue #491

## Tests

- **Suite de tests isolée du disque réel (issue #491).**
  - `tests/test_serveur.py` — la fixture `serveur_test` monkeypatch désormais
    `obtenir_trie`/`obtenir_trie_ia` (côté `scrabble.ui.accueil`) par un Trie
    factice en mémoire. C'était le seul test de la suite à passer par un
    vrai `ApiAccueil.lancer_partie()` (plutôt qu'une injection d'état directe),
    donc le seul à atteindre ces fonctions à leurs chemins par défaut réels —
    ce qui écrivait un cache dans le vrai `cache/dictionnaire/` du dépôt à
    chaque exécution de la suite. Le test `test_serveur_diffuse_l_etat_via_sse`
    lui-même n'est pas modifié (échec intermittent connu, hors périmètre).
  - `tests/test_moteur_personnages.py` et
    `tests/test_garde_dictionnaire_humain.py` — les tests qui exerçaient le
    profil réel de Titeuf substituent maintenant sa liste de mots favoris par
    une liste factice fixée dans le test (`dataclasses.replace` sur le
    profil), au lieu de lire le fichier local facultatif
    `titeuf_mots_favoris.txt` — non suivi par git depuis l'issue #487, donc
    absent d'un clone neuf ou d'un worktree isolé. Le test qui vérifie
    spécifiquement le chargement depuis ce fichier
    (`test_liste_de_depart_chargee_depuis_le_fichier_du_depot`) est ignoré
    proprement (`pytest.skip`) quand le fichier est absent, plutôt que de
    supposer son contenu.
  - `tests/test_jeu_echange.py`, `tests/test_jeu_tour_fin_partie.py` — les
    trois tests qui déclenchent une action persistée (`echanger_tout`,
    `passer`, `faire_jouer_ia`) avec un `id_partie` réel passent maintenant un
    `chemin_persistance` explicite vers `tmp_path`, au lieu du chemin par
    défaut (`data/parties.db` du dépôt).
  - `tests/test_application.py` — la valeur locale `theme_plateau` lue une
    fois au chargement du module (pour ignorer deux tests sans rapport avec
    le `config.json` réel du poste) n'appelle plus `charger_config()` quand
    `config.json` est absent : cet appel est auto-réparant et aurait sinon
    écrit un fichier neuf à l'emplacement réel du dépôt dans un worktree
    isolé.
  - Vérification : suite complète exécutée (`pytest`, 1471 passés, 6 ignorés
    — dont les skips déjà connus de l'issue #464, sans rapport) ; aucun
    fichier nouveau n'apparaît dans `cache/`, `data/`, `logs/` ni à la racine
    du dépôt après exécution (`git status` reste identique, hors les fichiers
    de test modifiés eux-mêmes).
  - Tests relus par ailleurs (`tests/test_dictionnaire.py` et les tests
    passant par `scrabble.ui.accueil.obtenir_trie`/`obtenir_trie_ia` dans
    `tests/test_accueil.py`, `tests/test_journal_integration.py`,
    `tests/test_jeu_pose.py`) : déjà isolés via `tmp_path` ou monkeypatch,
    aucune correction nécessaire.
