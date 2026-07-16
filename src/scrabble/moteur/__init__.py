"""Sous-paquet moteur : cœur du Scrabble (placement, validation, score, tirage).

Briques bas niveau, **sans notion de joueur** :

* :mod:`scrabble.moteur.plateau_partie` — état vivant des 225 cases, pose d'un
  mot, extraction des mots formés ;
* :mod:`scrabble.moteur.validation` — légalité d'un coup (case centrale,
  contiguïté, chevauchements, appartenance au dictionnaire) ;
* :mod:`scrabble.moteur.score` — calcul du score (bonus de case, bonus
  « scrabble », jokers à 0 point) ;
* :mod:`scrabble.moteur.tirage` — gestion du sac de jetons (pioche, remise).

Couche « partie » construite au-dessus, sans modifier les briques ci-dessus :

* :mod:`scrabble.moteur.partie` — joueurs, chevalets, déroulement des tours,
  historique et fin de partie ;
* :mod:`scrabble.moteur.ia` — adversaire artificiel minimal (stub) pilotant les
  joueurs IA au sein de la boucle de partie.

Ces modules s'appuient sur la géométrie figée de :mod:`scrabble.regles.plateau`,
les jetons de :mod:`scrabble.regles.lettres` et le Trie de
:mod:`scrabble.dictionnaire`.
"""
