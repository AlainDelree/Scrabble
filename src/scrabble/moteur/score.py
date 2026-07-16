"""Calcul du score d'un coup de Scrabble.

Rôle : à partir d'un plateau **où le coup vient d'être posé** et de la liste des
cases nouvellement occupées, calculer les points marqués. On applique les bonus
de case (:func:`scrabble.regles.plateau.type_case`), on additionne tous les mots
formés (principal + transversaux) et on ajoute le bonus « scrabble » si les 7
lettres du chevalet ont été posées en un seul coup.

Règles de comptage
------------------
* Un bonus de case (lettre/mot compte double ou triple) ne s'applique que si la
  lettre y est posée **pour la première fois lors de ce coup** : une tuile déjà
  présente d'un tour précédent apporte sa valeur nue, sans bonus.
* La case centrale compte comme un mot double (au premier coup).
* Chaque mot formé est scoré indépendamment, avec ses propres bonus de case.
* Un joker rapporte 0 point quelle que soit la lettre qu'il représente (la
  valeur est portée par :attr:`Tuile.valeur`).
"""

from __future__ import annotations

from scrabble.moteur.plateau_partie import (
    Direction,
    PlateauPartie,
    Tuile,
    mots_formes,
)
from scrabble.regles.plateau import TypeCase, type_case

#: Bonus « scrabble » : points ajoutés quand les 7 lettres du chevalet sont
#: posées en un seul coup.
BONUS_SCRABBLE = 50

#: Nombre de lettres d'un chevalet plein (seuil déclenchant le bonus scrabble).
LETTRES_CHEVALET = 7

# Multiplicateurs induits par le type de case (facteur lettre, facteur mot).
_MULTIPLICATEURS: dict[TypeCase, tuple[int, int]] = {
    TypeCase.NORMALE: (1, 1),
    TypeCase.LETTRE_DOUBLE: (2, 1),
    TypeCase.LETTRE_TRIPLE: (3, 1),
    TypeCase.MOT_DOUBLE: (1, 2),
    TypeCase.MOT_TRIPLE: (1, 3),
    TypeCase.CENTRE: (1, 2),  # l'étoile centrale compte comme un mot double
}


def score_mot(
    mot: list[tuple[int, int, Tuile]],
    nouvelles_positions: set[tuple[int, int]],
) -> int:
    """Score d'un mot formé, bonus de case appliqués aux seules cases nouvelles.

    ``mot`` est une liste ``(ligne, colonne, tuile)`` (voir
    :func:`scrabble.moteur.plateau_partie.mots_formes`). Les cases présentes
    dans ``nouvelles_positions`` déclenchent leurs bonus ; les autres apportent
    la valeur nue de leur tuile.
    """
    total_lettres = 0
    facteur_mot = 1
    for ligne, colonne, tuile in mot:
        valeur = tuile.valeur
        if (ligne, colonne) in nouvelles_positions:
            facteur_lettre, facteur_mot_case = _MULTIPLICATEURS[
                type_case(ligne, colonne)
            ]
            valeur *= facteur_lettre
            facteur_mot *= facteur_mot_case
        total_lettres += valeur
    return total_lettres * facteur_mot


def score_coup(
    plateau: PlateauPartie,
    nouvelles_positions: list[tuple[int, int]],
    direction: Direction,
) -> int:
    """Score total d'un coup déjà posé sur ``plateau``.

    ``nouvelles_positions`` sont les cases posées lors de ce coup (renvoyées par
    :meth:`PlateauPartie.poser_coup`) et ``direction`` celle du mot principal.
    Additionne le score de tous les mots formés puis, si les 7 lettres du
    chevalet ont été posées, ajoute :data:`BONUS_SCRABBLE`.
    """
    ensemble_nouvelles = set(nouvelles_positions)
    total = sum(
        score_mot(mot, ensemble_nouvelles)
        for mot in mots_formes(plateau, nouvelles_positions, direction)
    )
    if len(ensemble_nouvelles) == LETTRES_CHEVALET:
        total += BONUS_SCRABBLE
    return total
