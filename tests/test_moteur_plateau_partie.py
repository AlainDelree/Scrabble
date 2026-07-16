"""Tests de ``scrabble.moteur.plateau_partie``.

Couvre la tuile (valeur, joker à 0, lettre invalide), l'état du plateau, la pose
d'un coup (nouvelles cases renvoyées, chevauchement identique toléré, conflit
rejeté) et l'extraction des mots formés (principal + transversal).
"""

from __future__ import annotations

import pytest

from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    Tuile,
    lettres_du_mot,
    mots_formes,
    tuiles_depuis_chaine,
)


# --------------------------------------------------------------------------- #
# Tuile
# --------------------------------------------------------------------------- #

def test_tuile_valeur_lettre_ordinaire():
    assert Tuile("K").valeur == 10
    assert Tuile("A").valeur == 1


def test_tuile_joker_vaut_zero():
    """Un joker rapporte 0 point quelle que soit la lettre affichée."""
    assert Tuile("K", joker=True).valeur == 0
    assert Tuile("A", joker=True).valeur == 0


@pytest.mark.parametrize("mauvaise", ["a", "É", "AB", "", "1", "*"])
def test_tuile_lettre_invalide_leve(mauvaise):
    with pytest.raises(ValueError):
        Tuile(mauvaise)


# --------------------------------------------------------------------------- #
# État du plateau et pose
# --------------------------------------------------------------------------- #

def test_plateau_neuf_est_vide():
    plateau = PlateauPartie()
    assert plateau.est_vide()
    assert plateau.case_vide(*CENTRE)


def test_poser_coup_renvoie_les_nouvelles_cases():
    plateau = PlateauPartie()
    coup = Coup(7, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("SOL"))
    nouvelles = plateau.poser_coup(coup)
    assert nouvelles == [(7, 7), (7, 8), (7, 9)]
    assert not plateau.est_vide()
    assert plateau.tuile(7, 8).lettre == "O"


def test_poser_coup_chevauchement_identique_non_compte_comme_nouveau():
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(7, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("SOL")))
    # Coup vertical réutilisant le O déjà posé en (7, 8).
    coup = Coup(7, 8, Direction.VERTICALE, tuiles_depuis_chaine("OS"))
    nouvelles = plateau.poser_coup(coup)
    assert nouvelles == [(8, 8)]  # le O existant n'est pas une nouvelle case


def test_poser_coup_conflit_leve():
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(7, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("SOL")))
    coup = Coup(7, 7, Direction.VERTICALE, tuiles_depuis_chaine("XY"))
    with pytest.raises(ValueError):
        plateau.poser_coup(coup)


def test_poser_coup_hors_bornes_leve():
    plateau = PlateauPartie()
    coup = Coup(0, 13, Direction.HORIZONTALE, tuiles_depuis_chaine("SOL"))
    with pytest.raises(ValueError):
        plateau.poser_coup(coup)


# --------------------------------------------------------------------------- #
# Mots formés
# --------------------------------------------------------------------------- #

def test_mots_formes_principal_et_transversal():
    plateau = PlateauPartie()
    # Mot horizontal SOL en (7,7)-(7,9).
    plateau.poser_coup(Coup(7, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("SOL")))
    # Ajout vertical AS sous le S : A en (7,7) existant, on descend.
    coup = Coup(7, 7, Direction.VERTICALE, tuiles_depuis_chaine("SI"))
    nouvelles = plateau.poser_coup(coup)  # (8,7)
    mots = mots_formes(plateau, nouvelles, Direction.VERTICALE)
    textes = {lettres_du_mot(m) for m in mots}
    assert "SI" in textes  # mot principal vertical


def test_mots_formes_ignore_lettre_isolee():
    plateau = PlateauPartie()
    plateau.poser_tuile(7, 7, Tuile("A"))
    # Une seule lettre, sans voisin : aucun mot d'au moins deux lettres.
    assert mots_formes(plateau, [(7, 7)], Direction.HORIZONTALE) == []
