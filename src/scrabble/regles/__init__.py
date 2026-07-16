"""Sous-paquet règles.

Rôle : fournir les **données fondamentales** du jeu de Scrabble — géométrie du
plateau et cases bonus (:mod:`scrabble.regles.plateau`), répartition officielle
des jetons et valeur des lettres (:mod:`scrabble.regles.lettres`).

Ce paquet est un **socle de données pur** : il ne contient aucune notion de tour
de jeu, de tirage aléatoire ni de nombre de joueurs. Il reste ainsi réutilisable
tel quel par de futures variantes (Duplicate, variante Joker, etc.), lesquelles
seront portées par un futur moteur de jeu et non par ce paquet.

À ne pas confondre avec ``scrabble.moteur`` (déroulement d'une partie, calcul de
score d'un coup), qui s'appuiera sur ces données mais introduit, lui, l'état de
la partie.
"""
