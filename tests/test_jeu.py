"""Tests de la logique non-UI de l'écran de jeu (issue #28).

Couvre :
- la règle de confidentialité : ``etat_public`` n'expose aucune lettre de
  chevalet, et ``ApiJeu.obtenir_chevalet`` n'expose qu'**un seul** chevalet
  à la fois (jamais tous en une fois).

Note : ce fichier historique a été découpé en 10 fichiers spécialisés
(issues #255 à #264). Les tests se trouvent désormais dans :

- test_jeu_brouillon.py — tests du brouillon de coup en cours de saisie
- test_jeu_core_diffusion.py — tests du cœur de jeu et diffusion d'état
- test_jeu_coup.py — tests de la validation et soumission d'un coup
- test_jeu_echange.py — tests de l'échange de lettres
- test_jeu_integration.py — tests de bout en bout (pose/persistance/reprise)
- test_jeu_point_entree.py — tests du point d'entrée de l'écran de jeu
- test_jeu_pose.py — tests de la pose de mots sur le plateau
- test_jeu_serialisation.py — tests de sérialisation/désérialisation de l'état
- test_jeu_tirage_ordre.py — tests du tirage initial et de l'ordre des joueurs
- test_jeu_tour_fin_partie.py — tests de gestion des tours et fin de partie
"""
