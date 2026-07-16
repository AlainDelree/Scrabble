"""Sous-paquet moteur : cœur du Scrabble (placement, validation, score, tirage).

Ce paquet fournit les briques du moteur de jeu, **sans boucle de tour ni notion
de joueurs** :

* :mod:`scrabble.moteur.plateau_partie` — état vivant des 225 cases, pose d'un
  mot, extraction des mots formés ;
* :mod:`scrabble.moteur.validation` — légalité d'un coup (case centrale,
  contiguïté, chevauchements, appartenance au dictionnaire) ;
* :mod:`scrabble.moteur.score` — calcul du score (bonus de case, bonus
  « scrabble », jokers à 0 point) ;
* :mod:`scrabble.moteur.tirage` — gestion du sac de jetons (pioche, remise).

Ces modules s'appuient sur la géométrie figée de :mod:`scrabble.regles.plateau`,
les jetons de :mod:`scrabble.regles.lettres` et le Trie de
:mod:`scrabble.dictionnaire`.
"""
