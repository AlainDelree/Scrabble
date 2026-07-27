# Tâches en attente — Projet Scrabble

## À vérifier avant implémentation

- **Évaluation de la partie** : afficher en fin de jeu une évaluation
  du score selon une échelle (< 300 pts : débutant, 300-400 : intermédiaire,
  400-500 : bon niveau, > 500 : expert). Vérifier si l'échelle doit varier
  selon le nombre de joueurs (1v1, 1v2, 1v3).

- **Fichier meilleurs scores** : 3 catégories (1v1, 1v2, 1v3) × 5 niveaux
  (Débutant, Facile, Intermédiaire, Avancé, Expert), top 10 par combinaison.
  Vérifier l'état actuel avant de chiffrer le chantier.

- **Gestion d'erreurs silencieuses dans accueil.py** : plusieurs
  `except` avalent les erreurs sans log (ex. `sauvegarder_prenom_principal`).
  Pas bloquant, mais à durcir/logger si un bug de sauvegarde apparaît.

## À implémenter

- **TextField dictionnaire constamment visible** : remplacer le bouton
  loupe dans l'écran de jeu par un champ de recherche directement
  accessible, sans clic préalable.
