"""Tests de ``scrabble.moteur.score``.

Couvre un exemple calculé à la main (bonus de case + centre + joker à 0 point),
le bonus « scrabble » de 50 points, et le fait qu'un bonus de case ne compte que
lors de la première pose (pas pour une tuile d'un tour précédent).
"""

from __future__ import annotations

from scrabble.moteur.plateau_partie import (
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)
from scrabble.moteur.score import BONUS_SCRABBLE, LETTRES_CHEVALET, score_coup


def test_score_bonus_case_joker_et_centre():
    """CADRE en (7,3) avec le C en joker : lettre double sur joker (=0), centre.

    Détail : C(joker=0)×LD=0, A=1, D=2, R=1, E=1(sur centre) ; somme=5, mot
    double (centre) ⇒ 5 × 2 = 10.
    """
    plateau = PlateauPartie()
    coup = Coup(
        7, 3, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE", jokers=frozenset({0}))
    )
    nouvelles = plateau.poser_coup(coup)
    assert score_coup(plateau, nouvelles, Direction.HORIZONTALE) == 10


def test_bonus_scrabble_sur_sept_lettres():
    """Poser les 7 lettres du chevalet en un coup ajoute BONUS_SCRABBLE."""
    plateau = PlateauPartie()
    # 7 A de (7,4) à (7,10) : seule la case centrale (7,7) porte un bonus (mot ×2).
    coup = Coup(7, 4, Direction.HORIZONTALE, tuiles_depuis_chaine("AAAAAAA"))
    nouvelles = plateau.poser_coup(coup)
    assert len(nouvelles) == LETTRES_CHEVALET
    # 7 × A(1) = 7, ×2 (centre) = 14, + 50 (scrabble) = 64.
    assert score_coup(plateau, nouvelles, Direction.HORIZONTALE) == 14 + BONUS_SCRABBLE


def test_bonus_case_non_recompte_pour_tuile_ancienne():
    """Une tuile déjà posée (sur une case bonus) n'en redéclenche pas le bonus."""
    plateau = PlateauPartie()
    # Tour 1 : CADRE ; le C tombe sur une lettre double en (7,3).
    plateau.poser_coup(
        Coup(7, 3, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))
    )
    # Tour 2 : CU vertical réutilisant le C existant ; seule la case (8,3) est neuve.
    nouvelles = plateau.poser_coup(
        Coup(7, 3, Direction.VERTICALE, tuiles_depuis_chaine("CU"))
    )
    assert nouvelles == [(8, 3)]
    # C(3) sans bonus (ancien) + U(1) sans bonus = 4.
    assert score_coup(plateau, nouvelles, Direction.VERTICALE) == 4
