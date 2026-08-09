# Issue #402 : refonte niveaux — dictionnaire, accueil.py, UI HTML/JS (B/4)

Suite de la refonte de l'échelle des niveaux IA (issue #400) : EXPERT
utilise désormais l'ODS8 complet (comme CHAMPION_DU_MONDE), sans palier de
vocabulaire restreint.

- `dictionnaire.py` : suppression de la clé `"expert"` de
  `FICHIERS_VOCABULAIRE_PALIER` (4 entrées restantes : debutant/facile/
  intermediaire/avance) ; commentaires et docstrings mis à jour partout où
  seul CHAMPION_DU_MONDE était mentionné comme niveau sans palier ; `VERSION_CACHE`
  incrémentée (3 → 4) pour invalider les caches Trie IA existants construits
  sous l'ancien mapping.
- `accueil.py` : `_disponibilite_niveau()` traite désormais EXPERT comme
  CHAMPION_DU_MONDE — toujours disponible, sans vérification de fichier
  palier. `_construire_trie_ia()` corrigé dans la foulée (même défense en
  profondeur) : sans ce correctif, une partie avec un ordinateur Expert
  levait un `KeyError: 'expert'` tant que `moteur/ia.py::resoudre_palier`
  n'a pas lui-même été mis à jour par le lot complémentaire (hors périmètre
  de cette issue). `NIVEAUX_LABELS` vérifié cohérent (6 entrées, inchangé).
- `accueil.js` : commentaire de `appliquerDisponibiliteNiveaux` mis à jour
  (EXPERT + Champion du monde, sans fichier palier). `jeu.js` déjà
  cohérent, aucun changement nécessaire.

Point d'attention : `moteur/ia.py` (`resoudre_palier`, hors périmètre
strict de cette issue) mappe encore `Niveau.EXPERT` vers la clé de palier
`"expert"` — ce module doit être mis à jour par un lot complémentaire pour
que la cohérence soit complète. Plusieurs tests existants (`test_accueil.py`,
`test_dictionnaire.py`, `test_moteur_ia.py`, `test_generer_mots_courants.py`)
vérifient encore l'ancien mapping à 5 paliers et échoueront jusqu'à cette
mise à jour ; les tests n'étaient pas dans le périmètre de cette issue.
