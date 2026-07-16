"""Tests du module plateau (``scrabble.regles.plateau``).

Vérifie le type de bonus à quelques positions connues du plateau standard
officiel (centre, coins, cases lettre/mot double/triple), la cohérence globale
du décompte des cases bonus, et le rejet des positions hors bornes.
"""

from __future__ import annotations

import pytest

from scrabble.regles.plateau import (
    CENTRE,
    TAILLE,
    TypeCase,
    type_case,
)


# --------------------------------------------------------------------------- #
# Positions connues
# --------------------------------------------------------------------------- #

def test_centre_est_etoile():
    """La case centrale (7, 7) est l'étoile de départ."""
    assert CENTRE == (7, 7)
    assert type_case(7, 7) == TypeCase.CENTRE


def test_coins_sont_mots_triples():
    """Les quatre coins du plateau sont des cases mot triple."""
    for coin in [(0, 0), (0, 14), (14, 0), (14, 14)]:
        assert type_case(*coin) == TypeCase.MOT_TRIPLE


def test_cases_bonus_representatives():
    """Un exemple de chaque type de bonus à une position officielle."""
    assert type_case(0, 3) == TypeCase.LETTRE_DOUBLE
    assert type_case(1, 5) == TypeCase.LETTRE_TRIPLE
    assert type_case(1, 1) == TypeCase.MOT_DOUBLE
    assert type_case(0, 7) == TypeCase.MOT_TRIPLE


def test_case_normale():
    """Une case sans bonus renvoie NORMALE."""
    assert type_case(0, 1) == TypeCase.NORMALE
    assert type_case(7, 7 - 1) == TypeCase.NORMALE  # voisine du centre


# --------------------------------------------------------------------------- #
# Cohérence globale du décompte officiel
# --------------------------------------------------------------------------- #

def test_decompte_officiel_des_cases():
    """Le plateau standard compte le bon nombre de cases de chaque type."""
    compteur: dict[TypeCase, int] = {t: 0 for t in TypeCase}
    for ligne in range(TAILLE):
        for colonne in range(TAILLE):
            compteur[type_case(ligne, colonne)] += 1

    assert compteur[TypeCase.MOT_TRIPLE] == 8
    assert compteur[TypeCase.MOT_DOUBLE] == 16
    assert compteur[TypeCase.LETTRE_TRIPLE] == 12
    assert compteur[TypeCase.LETTRE_DOUBLE] == 24
    assert compteur[TypeCase.CENTRE] == 1
    # Total des 225 cases réparti entre bonus et cases normales.
    assert sum(compteur.values()) == TAILLE * TAILLE


def test_symetrie_par_rotation():
    """Le plateau est symétrique par rotation d'un quart de tour."""
    for ligne in range(TAILLE):
        for colonne in range(TAILLE):
            attendu = type_case(ligne, colonne)
            # Rotation 90° : (l, c) -> (c, TAILLE-1-l).
            tourne = type_case(colonne, TAILLE - 1 - ligne)
            assert tourne == attendu


# --------------------------------------------------------------------------- #
# Bornes
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "ligne, colonne",
    [(-1, 0), (0, -1), (15, 0), (0, 15), (15, 15), (100, 3)],
)
def test_bornes_invalides_levent(ligne, colonne):
    """Une position hors 0-14 lève IndexError (pas de case normale muette)."""
    with pytest.raises(IndexError):
        type_case(ligne, colonne)
