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
from scrabble.moteur.score import (
    BONUS_SCRABBLE,
    LETTRES_CHEVALET,
    DetailMot,
    DetailScore,
    detailler_score,
    score_coup,
)


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


def test_detailler_score_cadre():
    """Le détail du même coup CADRE expose un seul mot cohérent avec le total."""
    plateau = PlateauPartie()
    coup = Coup(
        7, 3, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE", jokers=frozenset({0}))
    )
    nouvelles = plateau.poser_coup(coup)
    detail = detailler_score(plateau, nouvelles, Direction.HORIZONTALE)

    assert isinstance(detail, DetailScore)
    # Un unique mot formé (le principal), aucun transversal.
    assert len(detail.mots) == 1
    mot = detail.mots[0]
    assert isinstance(mot, DetailMot)
    assert mot.texte == "CADRE"
    assert mot.score == 10
    # Pas de bonus scrabble (5 lettres < 7) et total = score du mot.
    assert detail.bonus_scrabble == 0
    assert detail.total == 10
    # Cohérence : somme des scores par mot + bonus = total.
    assert sum(m.score for m in detail.mots) + detail.bonus_scrabble == detail.total
    # Total du détail == valeur historique de score_coup.
    assert detail.total == score_coup(plateau, nouvelles, Direction.HORIZONTALE)
    # Cases bonus effectivement utilisées : lettre double (7,3) et centre (7,7).
    positions_bonus = {(l, c) for l, c, _ in mot.cases_bonus}
    assert positions_bonus == {(7, 3), (7, 7)}


def test_detailler_score_bonus_scrabble():
    """Le bonus scrabble apparaît séparément dans le détail (mots ×2 + 50)."""
    plateau = PlateauPartie()
    coup = Coup(7, 4, Direction.HORIZONTALE, tuiles_depuis_chaine("AAAAAAA"))
    nouvelles = plateau.poser_coup(coup)
    detail = detailler_score(plateau, nouvelles, Direction.HORIZONTALE)

    assert detail.bonus_scrabble == BONUS_SCRABBLE
    assert [m.texte for m in detail.mots] == ["AAAAAAA"]
    assert detail.mots[0].score == 14
    assert sum(m.score for m in detail.mots) + detail.bonus_scrabble == detail.total
    assert detail.total == 14 + BONUS_SCRABBLE
    assert detail.total == score_coup(plateau, nouvelles, Direction.HORIZONTALE)
