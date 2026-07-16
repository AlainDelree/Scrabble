"""Tests du tirage de prénoms pour les joueurs « ordinateur »."""

from __future__ import annotations

import random

import pytest

from scrabble.ui.noms_ordinateur import (
    PRENOMS_ORDINATEUR,
    TropDePrenomsDemandes,
    prenoms_disponibles,
    tirer_prenoms,
)


def test_beatrice_exclue_de_la_liste():
    """« Béatrice » ne doit jamais figurer dans la liste des prénoms."""
    assert all(p.casefold() != "béatrice" for p in PRENOMS_ORDINATEUR)


def test_liste_sans_doublon_et_taille_raisonnable():
    """La liste est cohérente (pas de doublon, une vingtaine de prénoms)."""
    assert len(PRENOMS_ORDINATEUR) == len(set(PRENOMS_ORDINATEUR))
    assert len(PRENOMS_ORDINATEUR) >= 20


def test_tirage_nombre_demande():
    prenoms = tirer_prenoms(3)
    assert len(prenoms) == 3


def test_tirage_sans_doublon():
    """Les prénoms tirés sont tous distincts."""
    random.seed(1)
    prenoms = tirer_prenoms(len(PRENOMS_ORDINATEUR))
    assert len(prenoms) == len(set(prenoms))
    assert set(prenoms) == set(PRENOMS_ORDINATEUR)


def test_tirage_zero():
    assert tirer_prenoms(0) == []


def test_exclusion_deja_utilises():
    """Un prénom déjà pris ne peut pas être retiré."""
    random.seed(2)
    deja = {"Marc"}
    prenoms = tirer_prenoms(len(PRENOMS_ORDINATEUR) - 1, deja)
    assert "Marc" not in prenoms


def test_exclusion_insensible_a_la_casse_et_espaces():
    """La comparaison des prénoms déjà pris ignore casse et espaces."""
    dispo = prenoms_disponibles({"  marc  "})
    assert "Marc" not in dispo
    # Les autres prénoms restent disponibles.
    assert len(dispo) == len(PRENOMS_ORDINATEUR) - 1


def test_erreur_si_trop_demande():
    """Demander plus que le total lève une erreur explicite (pas de boucle)."""
    with pytest.raises(TropDePrenomsDemandes):
        tirer_prenoms(len(PRENOMS_ORDINATEUR) + 1)


def test_erreur_si_trop_demande_apres_exclusion():
    """L'exclusion réduit le stock disponible et peut déclencher l'erreur."""
    disponible = len(PRENOMS_ORDINATEUR) - 1
    with pytest.raises(TropDePrenomsDemandes):
        tirer_prenoms(len(PRENOMS_ORDINATEUR), {"Marc"})
    # Juste ce qu'il reste : OK.
    assert len(tirer_prenoms(disponible, {"Marc"})) == disponible


def test_erreur_si_nombre_negatif():
    with pytest.raises(ValueError):
        tirer_prenoms(-1)


def test_erreur_si_nombre_non_entier():
    with pytest.raises(TypeError):
        tirer_prenoms(2.5)
    # Un booléen n'est pas accepté comme entier de tirage.
    with pytest.raises(TypeError):
        tirer_prenoms(True)


def test_deja_utilises_none_equivaut_a_vide():
    assert prenoms_disponibles(None) == list(PRENOMS_ORDINATEUR)
