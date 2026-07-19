"""Tests de l'utilitaire de réglages (``scrabble.reglages``)."""

from __future__ import annotations

import json

import pytest

from scrabble.reglages import (
    lire_reglage,
    lister_reglages,
    main,
    modifier_reglage,
)


def test_lister_reglages_defauts(tmp_path):
    """Sans fichier, on obtient les réglages par défaut (dont le prénom vide)."""
    chemin = tmp_path / "config.json"

    reglages = lister_reglages(chemin)

    assert reglages["prenom_principal"] == ""
    assert reglages["niveau_ia"] == "amateur"


def test_lire_reglage_connu(tmp_path):
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps({"prenom_principal": "Marie"}), encoding="utf-8")

    assert lire_reglage("prenom_principal", chemin) == "Marie"


def test_lire_reglage_inconnu(tmp_path):
    chemin = tmp_path / "config.json"
    with pytest.raises(KeyError):
        lire_reglage("inexistant", chemin)


def test_modifier_prenom_principal(tmp_path):
    """On peut renseigner puis relire le prénom principal."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("prenom_principal", "Alice", chemin)

    assert retenue == "Alice"
    assert lire_reglage("prenom_principal", chemin) == "Alice"
    # Le fichier sur disque reflète bien la modification.
    assert json.loads(chemin.read_text(encoding="utf-8"))["prenom_principal"] == "Alice"


def test_modifier_prenom_principal_vide(tmp_path):
    """On peut effacer le prénom en écrivant une chaîne vide (texte libre)."""
    chemin = tmp_path / "config.json"
    modifier_reglage("prenom_principal", "Alice", chemin)

    retenue = modifier_reglage("prenom_principal", "", chemin)

    assert retenue == ""
    assert lire_reglage("prenom_principal", chemin) == ""


def test_modifier_champ_contraint_invalide_retombe_sur_defaut(tmp_path):
    """Une valeur vide sur un champ contraint est normalisée vers le défaut."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("niveau_ia", "   ", chemin)

    assert retenue == "amateur"


def test_modifier_theme_plateau_valide(tmp_path):
    """On peut choisir un thème de plateau reconnu via les réglages."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("theme_plateau", "vert", chemin)

    assert retenue == "vert"
    assert lire_reglage("theme_plateau", chemin) == "vert"
    assert json.loads(chemin.read_text(encoding="utf-8"))["theme_plateau"] == "vert"


def test_modifier_theme_plateau_invalide_retombe_sur_defaut(tmp_path):
    """Un thème inconnu est normalisé vers le défaut « classique »."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("theme_plateau", "inexistant", chemin)

    assert retenue == "classique"
    assert lire_reglage("theme_plateau", chemin) == "classique"


@pytest.mark.parametrize("valeur", [True, False])
def test_modifier_bonus_fin_partie_booleen(tmp_path, valeur):
    """Le réglage booléen bonus_fin_partie accepte et conserve un vrai booléen."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("bonus_fin_partie", valeur, chemin)

    assert retenue is valeur
    assert lire_reglage("bonus_fin_partie", chemin) is valeur
    assert json.loads(chemin.read_text(encoding="utf-8"))["bonus_fin_partie"] is valeur


def test_modifier_bonus_fin_partie_non_booleen_rejete(tmp_path):
    """Une valeur non booléenne pour un réglage booléen lève TypeError."""
    chemin = tmp_path / "config.json"
    with pytest.raises(TypeError):
        modifier_reglage("bonus_fin_partie", "true", chemin)


def test_modifier_position_chevalet_dict(tmp_path):
    """position_chevalet accepte et conserve un dictionnaire {"x", "y"} (issue #135)."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("position_chevalet", {"x": 340, "y": 610}, chemin)

    assert retenue == {"x": 340, "y": 610}
    assert lire_reglage("position_chevalet", chemin) == {"x": 340, "y": 610}
    releu = json.loads(chemin.read_text(encoding="utf-8"))
    assert releu["position_chevalet"] == {"x": 340, "y": 610}


def test_modifier_position_chevalet_none_efface(tmp_path):
    """On peut réinitialiser la position mémorisée à None."""
    chemin = tmp_path / "config.json"
    modifier_reglage("position_chevalet", {"x": 12, "y": 34}, chemin)

    retenue = modifier_reglage("position_chevalet", None, chemin)

    assert retenue is None
    assert lire_reglage("position_chevalet", chemin) is None


def test_modifier_position_chevalet_dict_invalide_repare_en_none(tmp_path):
    """Un dictionnaire mal formé est accepté par le type mais réparé en None."""
    chemin = tmp_path / "config.json"

    retenue = modifier_reglage("position_chevalet", {"x": 340}, chemin)

    assert retenue is None


def test_modifier_position_chevalet_type_invalide_rejete(tmp_path):
    """Un type autre que dict/None (ex. chaîne) est rejeté par TypeError."""
    chemin = tmp_path / "config.json"
    with pytest.raises(TypeError):
        modifier_reglage("position_chevalet", "340,610", chemin)


def test_modifier_reglage_inconnu(tmp_path):
    chemin = tmp_path / "config.json"
    with pytest.raises(KeyError):
        modifier_reglage("inexistant", "valeur", chemin)


def test_modifier_reglage_valeur_non_chaine(tmp_path):
    chemin = tmp_path / "config.json"
    with pytest.raises(TypeError):
        modifier_reglage("prenom_principal", 42, chemin)


def test_main_sans_argument_affiche_tout(tmp_path, capsys, monkeypatch):
    """``main`` sans argument liste tous les réglages."""
    chemin = tmp_path / "config.json"
    monkeypatch.setattr("scrabble.reglages.CHEMIN_CONFIG", chemin)

    code = main([])

    assert code == 0
    sortie = capsys.readouterr().out
    assert "prenom_principal" in sortie
    assert "niveau_ia" in sortie


def test_main_lecture_puis_ecriture(tmp_path, capsys, monkeypatch):
    """``main`` lit puis modifie une valeur via la CLI."""
    chemin = tmp_path / "config.json"
    monkeypatch.setattr("scrabble.reglages.CHEMIN_CONFIG", chemin)

    assert main(["prenom_principal", "Marie"]) == 0
    assert lire_reglage("prenom_principal", chemin) == "Marie"

    capsys.readouterr()  # vide le tampon
    assert main(["prenom_principal"]) == 0
    assert "Marie" in capsys.readouterr().out


def test_main_cle_inconnue_code_erreur(tmp_path, capsys, monkeypatch):
    chemin = tmp_path / "config.json"
    monkeypatch.setattr("scrabble.reglages.CHEMIN_CONFIG", chemin)

    assert main(["inexistant"]) == 1
    assert "inconnu" in capsys.readouterr().err.lower()
