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

from dataclasses import dataclass, field

from scrabble.moteur.plateau_partie import (
    Direction,
    PlateauPartie,
    Tuile,
    lettres_du_mot,
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


@dataclass(frozen=True)
class DetailMot:
    """Détail du score d'un mot formé par un coup.

    Attributs
    ---------
    texte:
        Chaîne des lettres affichées du mot (jokers inclus).
    score:
        Points marqués par ce mot, bonus de case déjà appliqués.
    cases_bonus:
        Cases bonus **effectivement utilisées** pour ce mot, c'est-à-dire les
        nouvelles cases posées sur une case à multiplicateur (hors
        :attr:`TypeCase.NORMALE`). Chaque élément est
        ``(ligne, colonne, type_case)``.
    """

    texte: str
    score: int
    cases_bonus: list[tuple[int, int, TypeCase]] = field(default_factory=list)


@dataclass(frozen=True)
class DetailScore:
    """Détail complet du score d'un coup, destiné à une explication à l'écran.

    Attributs
    ---------
    mots:
        Détail par mot formé (principal puis transversaux).
    bonus_scrabble:
        Points du bonus « scrabble » ajoutés (0 ou :data:`BONUS_SCRABBLE`).
    total:
        Score total du coup : ``sum(m.score for m in mots) + bonus_scrabble``.
    """

    mots: list[DetailMot]
    bonus_scrabble: int
    total: int


def _detailler_mot(
    mot: list[tuple[int, int, Tuile]],
    nouvelles_positions: set[tuple[int, int]],
) -> DetailMot:
    """Détail (texte, score, cases bonus) d'un mot formé.

    ``mot`` est une liste ``(ligne, colonne, tuile)`` (voir
    :func:`scrabble.moteur.plateau_partie.mots_formes`). Les cases présentes
    dans ``nouvelles_positions`` déclenchent leurs bonus ; les autres apportent
    la valeur nue de leur tuile. C'est **l'unique** endroit où la logique de
    comptage d'un mot est implémentée.
    """
    total_lettres = 0
    facteur_mot = 1
    cases_bonus: list[tuple[int, int, TypeCase]] = []
    for ligne, colonne, tuile in mot:
        valeur = tuile.valeur
        if (ligne, colonne) in nouvelles_positions:
            case = type_case(ligne, colonne)
            facteur_lettre, facteur_mot_case = _MULTIPLICATEURS[case]
            valeur *= facteur_lettre
            facteur_mot *= facteur_mot_case
            if case is not TypeCase.NORMALE:
                cases_bonus.append((ligne, colonne, case))
        total_lettres += valeur
    return DetailMot(
        texte=lettres_du_mot(mot),
        score=total_lettres * facteur_mot,
        cases_bonus=cases_bonus,
    )


def score_mot(
    mot: list[tuple[int, int, Tuile]],
    nouvelles_positions: set[tuple[int, int]],
) -> int:
    """Score d'un mot formé, bonus de case appliqués aux seules cases nouvelles.

    Enveloppe de :func:`_detailler_mot` ne conservant que le score (conservée
    pour compatibilité). Voir :func:`_detailler_mot` pour le détail des règles.
    """
    return _detailler_mot(mot, nouvelles_positions).score


def detailler_score(
    plateau: PlateauPartie,
    nouvelles_positions: list[tuple[int, int]],
    direction: Direction,
) -> DetailScore:
    """Détail complet du score d'un coup déjà posé sur ``plateau``.

    Même signature d'entrée que :func:`score_coup`, mais renvoie un
    :class:`DetailScore` exposant le détail par mot et le bonus scrabble
    séparément. Constitue la source unique du calcul : :func:`score_coup`
    s'appuie sur son ``.total``.
    """
    ensemble_nouvelles = set(nouvelles_positions)
    mots = [
        _detailler_mot(mot, ensemble_nouvelles)
        for mot in mots_formes(plateau, nouvelles_positions, direction)
    ]
    bonus_scrabble = (
        BONUS_SCRABBLE if len(ensemble_nouvelles) == LETTRES_CHEVALET else 0
    )
    total = sum(detail.score for detail in mots) + bonus_scrabble
    return DetailScore(mots=mots, bonus_scrabble=bonus_scrabble, total=total)


def score_coup(
    plateau: PlateauPartie,
    nouvelles_positions: list[tuple[int, int]],
    direction: Direction,
) -> int:
    """Score total d'un coup déjà posé sur ``plateau``.

    ``nouvelles_positions`` sont les cases posées lors de ce coup (renvoyées par
    :meth:`PlateauPartie.poser_coup`) et ``direction`` celle du mot principal.
    Additionne le score de tous les mots formés puis, si les 7 lettres du
    chevalet ont été posées, ajoute :data:`BONUS_SCRABBLE`. S'appuie sur
    :func:`detailler_score` pour ne pas dupliquer la logique de calcul.
    """
    return detailler_score(plateau, nouvelles_positions, direction).total
