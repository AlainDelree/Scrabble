"""Tests de la configuration auto-réparante (``scrabble.config``)."""

from __future__ import annotations

import json

import pytest

from scrabble.config import (
    CONFIG_DEFAUT,
    THEMES_PLATEAU,
    charger_config,
    sauvegarder_config,
)


def test_fichier_absent_cree_defauts(tmp_path):
    """Fichier absent : renvoie les défauts ET écrit un fichier propre."""
    chemin = tmp_path / "config.json"

    config = charger_config(chemin)

    assert config == CONFIG_DEFAUT
    assert config["niveau_ia"] == "amateur"
    assert config["mode_saisie"] == "clic"
    assert config["source_dictionnaire"] == "ods"
    assert config["prenom_principal"] == ""
    # Un fichier propre et relisible a bien été créé.
    assert chemin.exists()
    assert json.loads(chemin.read_text(encoding="utf-8")) == CONFIG_DEFAUT


def test_fichier_corrompu_repare(tmp_path):
    """Fichier corrompu (JSON invalide) : réparé avec les valeurs par défaut."""
    chemin = tmp_path / "config.json"
    chemin.write_text("{ceci n'est pas du JSON valide", encoding="utf-8")

    config = charger_config(chemin)

    assert config == CONFIG_DEFAUT
    # Après réparation, le fichier est de nouveau du JSON valide.
    assert json.loads(chemin.read_text(encoding="utf-8")) == CONFIG_DEFAUT


def test_contenu_non_objet_repare(tmp_path):
    """Contenu JSON valide mais du mauvais type (liste) : réparé."""
    chemin = tmp_path / "config.json"
    chemin.write_text("[1, 2, 3]", encoding="utf-8")

    config = charger_config(chemin)

    assert config == CONFIG_DEFAUT
    assert json.loads(chemin.read_text(encoding="utf-8")) == CONFIG_DEFAUT


def test_cle_manquante_completee(tmp_path):
    """Clé manquante : complétée par le défaut et fichier réécrit."""
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps({"niveau_ia": "expert"}), encoding="utf-8")

    config = charger_config(chemin)

    assert config["niveau_ia"] == "expert"
    assert config["mode_saisie"] == "clic"
    assert config["source_dictionnaire"] == "ods"
    assert json.loads(chemin.read_text(encoding="utf-8"))["mode_saisie"] == "clic"


def test_valeur_mauvais_type_reparee(tmp_path):
    """Valeur du mauvais type : remplacée par le défaut."""
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps({"niveau_ia": 42, "mode_saisie": ""}), encoding="utf-8")

    config = charger_config(chemin)

    assert config == CONFIG_DEFAUT


def test_cle_inconnue_nettoyee(tmp_path):
    """Clé inconnue : supprimée et fichier réécrit proprement."""
    chemin = tmp_path / "config.json"
    valeur = {"niveau_ia": "amateur", "mode_saisie": "clic", "obsolete": True}
    chemin.write_text(json.dumps(valeur), encoding="utf-8")

    config = charger_config(chemin)

    assert config == CONFIG_DEFAUT
    assert "obsolete" not in json.loads(chemin.read_text(encoding="utf-8"))


def test_fichier_valide_non_reecrit(tmp_path):
    """Fichier déjà propre : aucune réécriture inutile (mtime inchangé)."""
    chemin = tmp_path / "config.json"
    valeur = {
        "niveau_ia": "expert",
        "mode_saisie": "clavier",
        "source_dictionnaire": "hunspell",
        "prenom_principal": "Marie",
        "theme_plateau": "vert",
    }
    chemin.write_text(json.dumps(valeur), encoding="utf-8")
    mtime_avant = chemin.stat().st_mtime_ns

    config = charger_config(chemin)

    assert config == valeur
    assert chemin.stat().st_mtime_ns == mtime_avant


def test_sauvegarder_puis_recharger(tmp_path):
    """Aller-retour : ce qui est sauvegardé se relit à l'identique."""
    chemin = tmp_path / "config.json"

    sauvegarder_config(
        {
            "niveau_ia": "debutant",
            "mode_saisie": "clavier",
            "source_dictionnaire": "hunspell",
            "prenom_principal": "Alice",
            "theme_plateau": "abrege",
        },
        chemin,
    )
    config = charger_config(chemin)

    assert config == {
        "niveau_ia": "debutant",
        "mode_saisie": "clavier",
        "source_dictionnaire": "hunspell",
        "prenom_principal": "Alice",
        "theme_plateau": "abrege",
    }


def test_prenom_principal_vide_par_defaut_non_reecrit(tmp_path):
    """Un prénom vide est légitime : aucune réparation ni réécriture."""
    chemin = tmp_path / "config.json"
    valeur = {
        "niveau_ia": "amateur",
        "mode_saisie": "clic",
        "source_dictionnaire": "ods",
        "prenom_principal": "",
        "theme_plateau": "classique",
    }
    chemin.write_text(json.dumps(valeur), encoding="utf-8")
    mtime_avant = chemin.stat().st_mtime_ns

    config = charger_config(chemin)

    assert config["prenom_principal"] == ""
    # Le vide ne déclenche pas de réparation (contrairement aux autres champs).
    assert chemin.stat().st_mtime_ns == mtime_avant


def test_prenom_principal_conserve(tmp_path):
    """Un prénom renseigné est conservé tel quel."""
    chemin = tmp_path / "config.json"
    chemin.write_text(
        json.dumps({"prenom_principal": "Marie"}), encoding="utf-8"
    )

    config = charger_config(chemin)

    assert config["prenom_principal"] == "Marie"


def test_prenom_principal_mauvais_type_repare(tmp_path):
    """Un prénom du mauvais type retombe sur le vide par défaut."""
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps({"prenom_principal": 42}), encoding="utf-8")

    config = charger_config(chemin)

    assert config["prenom_principal"] == ""
    assert json.loads(chemin.read_text(encoding="utf-8"))["prenom_principal"] == ""


def test_theme_plateau_defaut_classique(tmp_path):
    """Le thème de plateau par défaut est « classique »."""
    chemin = tmp_path / "config.json"

    config = charger_config(chemin)

    assert config["theme_plateau"] == "classique"
    assert CONFIG_DEFAUT["theme_plateau"] == "classique"
    # Le défaut fait partie des thèmes reconnus.
    assert CONFIG_DEFAUT["theme_plateau"] in THEMES_PLATEAU


@pytest.mark.parametrize("theme", THEMES_PLATEAU)
def test_theme_plateau_valeurs_valides_conservees(tmp_path, theme):
    """Chaque thème reconnu est conservé tel quel, sans réparation."""
    chemin = tmp_path / "config.json"
    chemin.write_text(
        json.dumps({"theme_plateau": theme}), encoding="utf-8"
    )

    config = charger_config(chemin)

    assert config["theme_plateau"] == theme


def test_theme_plateau_valeur_invalide_reparee(tmp_path):
    """Un thème inconnu retombe sur le défaut « classique » et le fichier est réparé."""
    chemin = tmp_path / "config.json"
    chemin.write_text(
        json.dumps({"theme_plateau": "fluo-arc-en-ciel"}), encoding="utf-8"
    )

    config = charger_config(chemin)

    assert config["theme_plateau"] == "classique"
    # La réparation est persistée sur disque.
    releu = json.loads(chemin.read_text(encoding="utf-8"))
    assert releu["theme_plateau"] == "classique"


def test_theme_plateau_vide_repare(tmp_path):
    """Une chaîne vide n'est pas un thème valide : réparée vers le défaut."""
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps({"theme_plateau": ""}), encoding="utf-8")

    config = charger_config(chemin)

    assert config["theme_plateau"] == "classique"


def test_theme_plateau_mauvais_type_repare(tmp_path):
    """Un thème du mauvais type retombe sur le défaut « classique »."""
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps({"theme_plateau": 7}), encoding="utf-8")

    config = charger_config(chemin)

    assert config["theme_plateau"] == "classique"
