# Idées et tâches en attente — Projet Scrabble

Notes diverses à traiter plus tard, pour ne pas perdre le fil entre les
sessions.

## Fenêtre de réglages avec onglets (dictionnaire)

Nouvelle fenêtre graphique de réglages (pywebview, séparée de l'écran de
jeu), avec au moins 2 onglets :
- **Général** : réglages existants (prénom, thème, mode de saisie...)
- **Dictionnaire** : recherche d'un mot, affichage par source (ODS /
  Hunspell) avec statut présent/absent + bouton Ajouter/Supprimer +
  définition

Prérequis : séparer `mots_ajoutes.txt`/`mots_retires.txt` par source (une
paire par source : ODS et Hunspell) pour que les personnalisations
restent indépendantes entre les deux sources.

## Point de vigilance : gestion d'erreurs dans accueil.py

Dans `src/scrabble/ui/accueil.py`, plusieurs `except (KeyError, TypeError,
Exception)` avalent les erreurs silencieusement (ex.
`sauvegarder_prenom_principal` retourne juste `False` sur toute erreur,
sans log). Pas bloquant, mais à durcir/logger si un bug de sauvegarde
apparaît en pratique.
