"""Tests de ``scrabble.moteur.tirage``.

Couvre la constitution du sac (102 jetons), le tirage épuisant progressivement
le sac (y compris le dernier tirage incomplet), la remise en jeu, le rejet d'un
nombre négatif et le déterminisme du mélange avec graine.
"""

from __future__ import annotations

import pytest

from scrabble.moteur.tirage import Sac


def test_sac_initial_contient_102_jetons():
    sac = Sac(graine=0)
    assert len(sac) == 102
    assert not sac.est_vide()


def test_tirage_epuise_progressivement_le_sac():
    """Tirer par paquets de 7 vide le sac ; le dernier tirage est incomplet."""
    sac = Sac(graine=1)
    total_tires = 0
    dernier = None
    while not sac.est_vide():
        dernier = sac.tirer(7)
        total_tires += len(dernier)
    assert total_tires == 102
    assert len(dernier) == 102 % 7  # 102 = 14×7 + 4 → dernier paquet de 4
    assert sac.tirer(7) == []  # sac vide : tirage rend une liste vide, sans lever


def test_tirer_plus_que_le_reste_rend_le_reste():
    sac = Sac(graine=2)
    sac.tirer(100)
    reste = sac.tirer(10)  # il ne reste que 2 jetons
    assert len(reste) == 2
    assert sac.est_vide()


def test_remettre_reintroduit_les_jetons():
    sac = Sac(graine=3)
    tires = sac.tirer(7)
    assert len(sac) == 95
    sac.remettre(tires)
    assert len(sac) == 102


def test_tirer_negatif_leve():
    sac = Sac(graine=4)
    with pytest.raises(ValueError):
        sac.tirer(-1)


def test_meme_graine_donne_meme_tirage():
    assert Sac(graine=42).tirer(10) == Sac(graine=42).tirer(10)
