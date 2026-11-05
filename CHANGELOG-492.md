# Changelog — Issue #492

## Qualité du code

- **Propreté du code : `except` silencieux documentés, et nettoyage `ruff`
  sans risque fonctionnel (issue #492).**
  - `src/scrabble/journal.py` (`Journal.cloturer`) et
    `src/scrabble/serveur/cli.py` (`main`) : le corps des deux `except` au
    comportement déjà volontaire (fichier déjà absent ; arrêt par Ctrl+C)
    porte désormais un commentaire expliquant pourquoi l'erreur est ignorée.
    Comportement inchangé.
  - Recherche de code mort en commentaire sur les 7 blocs signalés
    (`ui/accueil.py` ×2, `main.py`, `ui/application.py`, `ui/api_echange.py`,
    `moteur/personnages.py`, `scripts/mesurer_force_niveaux.py`) : après
    relecture intégrale de chacun des 6 fichiers (mécanique puis humaine,
    doublée par agent indépendant), aucun des commentaires visés ne contient
    de code Python désactivé — uniquement de la prose explicative (style du
    projet : justification du pourquoi, références d'issues). Rien n'a donc
    été supprimé sur cette partie.
  - Nettoyage `ruff` (imports non triés, annotations entre guillemets
    inutiles, imports inutilisés, `dict()`/`list()` remplaçables par un
    littéral, et une sélection d'autres règles à faible nombre d'occurrences
    et sans risque comportemental) sur `src/` et `scripts/` hors
    `actualise.py` et `_harness_jeu/`. Aucune suppression `RUF100` (`noqa`
    inutile) : la règle a été explicitement exclue du nettoyage, conformément
    à la consigne de ne jamais toucher une suppression déjà présente.
  - Quelques violations restent volontairement en l'état (détail dans le
    rapport de clôture de l'issue) : trois imports de
    `src/scrabble/ui/jeu.py` nécessaires à un rebranchement de test par
    monkeypatch, un `except Exception` large par fichier (hors scope de
    cette issue), les scripts sans permission d'exécution malgré leur
    shebang, un fichier ouvert sans gestionnaire de contexte parce que sa
    durée de vie dépasse une seule fonction, et deux ou trois cas où la
    correction mécanique aurait réduit la couverture d'un test ou nécessité
    un choix de typage non trivial.
  - Suite de tests inchangée avant/après ce nettoyage.
