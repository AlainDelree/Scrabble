"""Prototype de serveur HTTP local, un seul joueur (issue #475).

Sert l'interface web existante (``scrabble.ui.web``) dans un navigateur, en
s'appuyant sur le routeur d'API déjà en place (``scrabble.ui.application.
ApiRouteur``) plutôt que sur une fenêtre pywebview. Ni le moteur
(``scrabble.moteur``), ni le dictionnaire, ni les règles, ni la persistance ne
sont modifiés : ce sous-paquet se contente de brancher une bibliothèque
standard (``http.server``) à la place de pywebview.

Lancement ::

    python -m scrabble.serveur

Voir ``CONTEXTE.md`` pour les options et l'avertissement de sécurité (aucune
authentification : réseau local de confiance uniquement, jamais Internet).
"""

from __future__ import annotations
