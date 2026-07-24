"""Tests de la logique non-UI de l'écran de jeu (issue #28).

Couvre :
- la règle de confidentialité : ``etat_public`` n'expose aucune lettre de
  chevalet, et ``ApiJeu.obtenir_chevalet`` n'expose qu'**un seul** chevalet
  à la fois (jamais tous en une fois).

Note : ce fichier historique a été découpé en 10 fichiers spécialisés
(issues #255 à #264). Les tests se trouvent désormais dans :

- test_jeu_chevalet.py — tests du chevalet et de son affichage
- test_jeu_core_diffusion.py — tests du cœur de jeu et diffusion d'état
- test_jeu_echange.py — tests de l'échange de lettres
- test_jeu_etat_public.py — tests de confidentialité de l'état public
- test_jeu_fenetre.py — tests de la gestion de fenêtre pywebview
- test_jeu_integration.py — tests de bout en bout (pose/persistance/reprise)
- test_jeu_joker.py — tests spécifiques aux jokers
- test_jeu_point_entree.py — tests du point d'entrée de l'écran de jeu
- test_jeu_pose.py — tests de la pose de mots
- test_jeu_tour_fin_partie.py — tests de gestion des tours et fin de partie
"""
