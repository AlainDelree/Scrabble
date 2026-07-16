"""Tests du module lettres (``scrabble.regles.lettres``).

Vérifie la constitution du sac officiel français (102 jetons dont 2 jokers), la
cohérence de la somme pondérée (test de non-régression sur le compte), et les
valeurs de points de quelques lettres représentatives ainsi que le rejet des
lettres invalides.
"""

from __future__ import annotations

import pytest

from scrabble.regles.lettres import (
    JOKER,
    REPARTITION,
    TOTAL_JETONS,
    constituer_sac,
    valeur_lettre,
)


# --------------------------------------------------------------------------- #
# Constitution du sac
# --------------------------------------------------------------------------- #

def test_sac_contient_102_jetons():
    """Le sac initial compte exactement 102 jetons."""
    sac = constituer_sac()
    assert len(sac) == 102
    assert TOTAL_JETONS == 102


def test_sac_contient_2_jokers():
    """Le sac contient exactement 2 jokers."""
    sac = constituer_sac()
    assert sac.count(JOKER) == 2


def test_sac_couvre_tout_l_alphabet():
    """Les 26 lettres A-Z sont présentes, plus le joker."""
    sac = set(constituer_sac())
    for code in range(ord("A"), ord("Z") + 1):
        assert chr(code) in sac
    assert JOKER in sac
    assert len(sac) == 27  # 26 lettres + joker


def test_somme_ponderee_coherente():
    """Non-régression : la somme pondérée (valeur × nombre) reste stable.

    Somme des points de tous les jetons du sac. Les 2 jokers valant 0, ils ne
    contribuent pas. Le total de l'édition française vaut 197 (à distinguer des
    187 de l'édition anglaise, dont la répartition diffère).
    """
    total = sum(jeton.valeur * jeton.nombre for jeton in REPARTITION.values())
    total_via_sac = sum(valeur_lettre(j) for j in constituer_sac())
    assert total == total_via_sac
    assert total == 197


# --------------------------------------------------------------------------- #
# Valeurs des lettres
# --------------------------------------------------------------------------- #

def test_valeurs_representatives():
    """Valeurs de points d'une voyelle courante, consonnes rares, joker."""
    assert valeur_lettre("E") == 1   # voyelle courante
    assert valeur_lettre("A") == 1
    assert valeur_lettre("K") == 10  # consonne rare
    assert valeur_lettre("Q") == 8
    assert valeur_lettre(JOKER) == 0  # joker


@pytest.mark.parametrize("mauvaise", ["a", "1", "", "AB", "É", "*joker", "é"])
def test_valeur_lettre_invalide_leve(mauvaise):
    """Une lettre hors alphabet français majuscule (ou joker) lève ValueError."""
    with pytest.raises(ValueError):
        valeur_lettre(mauvaise)
