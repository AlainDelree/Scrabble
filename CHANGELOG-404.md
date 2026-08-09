# Issue #404 : refonte niveaux — tests et scripts (D/4)

Dernier lot de la refonte de l'échelle des niveaux IA (issue #400) : aligne
`tests/` et `scripts/` sur le nouveau mapping (DEBUTANT top 70 %, FACILE
top 33 %, INTERMEDIAIRE top 15 %, AVANCE meilleur coup, EXPERT top 5 %/ODS8
complet, CHAMPION_DU_MONDE inchangé).

- `tests/test_moteur_ia.py` : tests de monotonie et de stratégie par niveau
  entièrement réécrits pour les nouvelles tranches ; nouvelle classe
  `TestExpert` (top 5 %) ; `_NIVEAUX_SANS_PALIER` pour simuler le câblage
  vocabulaire réel (EXPERT et CHAMPION_DU_MONDE sur le Trie complet, les
  quatre autres niveaux sur leur palier restreint).
- `tests/test_accueil.py` : disponibilité et construction du Trie IA
  alignées sur EXPERT traité comme CHAMPION_DU_MONDE (toujours disponible,
  sans fichier de palier) ; nouveaux tests dédiés
  (`test_expert_toujours_disponible`,
  `test_construire_trie_ia_expert_reutilise_trie_complet`, etc.).
  `tests/test_accueil_niveaux_visuels.py` : aucun changement nécessaire
  (contenu purement CSS/HTML/JS, non affecté).
- `tests/test_dictionnaire.py` et `tests/test_generer_mots_courants.py` :
  alignés sur les quatre paliers de fichier restants (debutant/facile/
  intermediaire/avance, plus de clé "expert").
- `tests/test_moteur_partie.py`, `test_persistance.py`,
  `test_jeu_serialisation.py` et les petits fichiers `test_jeu_*`/
  `test_application.py`/`test_journal_integration.py`/`_aides_test_jeu.py` :
  audités, aucun changement nécessaire (les niveaux n'y servent que de
  valeur de configuration arbitraire, sans dépendre de la stratégie précise
  d'un niveau). `test_config.py` confirmé sans rapport avec l'enum `Niveau`
  (clé `"niveau_ia"` vestige indépendante).
- `scripts/generer_mots_courants.py` : `SEUILS_PALIER`/`ORDRE_PALIERS`
  réduits aux quatre paliers restants, docstring et messages CLI mis à jour
  (suppression de toute référence au palier "expert").
- `scripts/mesurer_force_niveaux.py` : docstring (exemples de commandes,
  description du câblage vocabulaire) mise à jour — EXPERT rejoint
  CHAMPION_DU_MONDE comme niveau sans palier restreint.
- `scripts/_harness_jeu/verif_296_webkitgtk.py` et
  `verif_belgicisme_292_webkitgtk.py` : mock `obtenir_niveaux` étendu aux
  six niveaux réels (au lieu de quatre) ; configurations de joueurs IA
  `niveau:'avance'`/`niveau:'expert'` corrigées en `'AVANCE'`/`'EXPERT'`
  (noms d'enum en majuscules, format réellement envoyé par l'API réelle).

## Résultat des tests

`pytest tests/ -q --timeout=120` : **891 passed, 9 failed** (sur 900 tests).

- **4 échecs attendus**, dus à l'issue #402 (B/4, `dictionnaire.py`/
  `accueil.py`) pas encore mergée dans cette branche — `dictionnaire.py` y a
  toujours l'ancien `FICHIERS_VOCABULAIRE_PALIER` à 5 clés (avec "expert") :
  `test_dictionnaire.py::test_fichiers_vocabulaire_palier_quatre_entrees_sous_dossier_dico`,
  `test_dictionnaire.py::test_fichiers_cache_ia_palier_meme_cles_que_vocabulaire_et_chemins_distincts`,
  `test_generer_mots_courants.py::test_ordre_et_seuils_paliers_couvrent_les_memes_cles`,
  `test_moteur_ia.py::TestResoudrePalier::test_paliers_resolus_correspondent_aux_cles_du_vocabulaire_ia`.
  Passeront dès que #402 sera mergé dans cette branche.
- **5 échecs préexistants, sans rapport avec la refonte des niveaux**
  (vérifiés identiques avant nos modifications, via `git stash`) :
  `test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`
  (fichiers de vocabulaire par palier absents du disque dans cet
  environnement de dev), `test_application.py::TestRoutageVueActive::…` et
  `test_application.py::TestParcoursCompletUnifie::…` (thème persisté par un
  `config.json` local), `test_journal_integration.py::TestJournalAccueil::…`
  ×2 (assertions sur le contenu exact des messages de journal).
