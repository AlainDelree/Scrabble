# Changelog — Issue #434

## Ajouté

- Écran d'accueil : si aucun joueur humain n'est présent dans la
  configuration en cours (y compris au tout premier lancement), la modale
  de saisie du prénom + avatar s'ouvre désormais automatiquement, sans
  attendre un clic manuel sur « Ajouter un joueur ». Le raccourci existant
  (ajout direct si un prénom principal est déjà enregistré dans les
  réglages, issue #141) est conservé : la logique du clic sur « Ajouter un
  joueur » a simplement été extraite dans une fonction `proposerAjoutHumain`
  réutilisée à l'initialisation (`src/scrabble/ui/web/accueil.js`).
