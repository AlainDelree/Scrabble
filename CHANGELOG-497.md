# Changelog — Issue #497

## Sécurité

- **`stockage.py` : suppression de la construction de requête SQL par
  chaîne pour la relecture du journal de l'IA (issue #497).**
  - `src/scrabble/persistance/stockage.py` (`lire_actions_journalisees`) :
    la requête `SELECT` qui insérait par formatage soit le nom de la
    colonne `journal_ia`, soit un `NULL` de remplacement, est remplacée par
    deux requêtes complètes et entièrement écrites en dur, choisies selon
    le résultat (déjà calculé) de la vérification d'existence de la
    colonne. Plus aucun signalement `ruff` S608 / Bandit B608 sur ce
    fichier. Comportement inchangé : mêmes colonnes dans le même ordre,
    même tri par `indice` croissant, `journal_ia` toujours `None` quand la
    colonne n'existe pas.
  - `tests/test_journal_decision_ia.py` : ajoute un cas manquant, partie
    d'identifiant inexistant pour cette même fonction (`KeyError` attendu).
    Les cas base avec colonne et base sans colonne étaient déjà couverts.
