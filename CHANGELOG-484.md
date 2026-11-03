# Changelog — Issue #484

## Sécurité

- **Validation des chemins lus dans `actualise_update.flag` avant tout
  lancement de processus (issue #482).**
  - Nouveau module `src/scrabble/actualise.py` : `chemin_actualise_valide`
    (le chemin doit exister, être un fichier, avoir l'extension `.bat` ou
    `.exe`, et se trouver dans le dossier d'Actualise — `C:\Actualise` — sans
    évasion via `..`) et `traiter_flag_actualise(contexte)` qui lit le flag,
    valide les chemins (`bat`, `actualise_ui`) puis lance le même processus
    qu'avant si le flag est légitime. Tout refus ou erreur est journalisé
    (motif seulement, jamais le contenu complet du flag) sans jamais lever
    d'exception ni bloquer démarrage/fermeture.
  - `main.py` (bloc de démarrage, ~L52-57) et
    `src/scrabble/ui/application.py` (`_handler_fermeture_actualise`,
    ~L566-570) appellent désormais tous les deux cette fonction partagée au
    lieu de dupliquer la lecture du flag et le `subprocess.Popen` sans
    validation.
  - Comportement inchangé pour un flag légitime déposé par Actualise.
  - Tests : `tests/test_actualise.py` (chemin autorisé, hors dossier, hors
    dossier via `..`, extension refusée, chemin inexistant, absence de
    fichier, dossier au lieu d'un fichier, et `traiter_flag_actualise` avec
    un espion remplaçant `subprocess.Popen` — aucun vrai processus lancé).
