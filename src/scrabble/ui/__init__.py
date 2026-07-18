"""Sous-paquet des éléments d'interface utilisateur.

À ce stade, il ne contient que de la logique Python pure (aucune dépendance
à pywebview) : génération de prénoms pour les joueurs « ordinateur », etc.
Les vues proprement dites viendront dans des issues UI ultérieures.
"""

# Couleur du tapis vert, source de vérité côté Python (issue #113).
# Doit rester synchronisée avec la variable CSS ``--tapis-vert`` définie dans
# ``ui/web/*.css``. Passée en ``background_color`` à chaque ``create_window``
# afin que pywebview affiche ce vert (au lieu du blanc par défaut) pendant la
# phase de chargement initial de la fenêtre, ce qui réduit fortement le flash
# perçu lors des transitions (noir→vert au lieu de noir→blanc→vert).
TAPIS_VERT = "#35654d"
