"""Tests de la configuration auto-réparante (``scrabble.config``)."""

from __future__ import annotations

import json

from scrabble.config import CONFIG_DEFAUT, charger_config, sauvegarder_config


def test_fichier_absent_cree_defauts(tmp_path):
    """Fichier absent : renvoie les défauts ET écrit un fichier propre."""
    chemin = tmp_path / "config.json"

    config = charger_config(chemin)

    assert config == CONFIG_DEFAUT
    assert config["niveau_ia"] == "amateur"
    assert config["mode_saisie"] == "clic"
    assert config["source_dictionnaire"] == "ods"
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
        },
        chemin,
    )
    config = charger_config(chemin)

    assert config == {
        "niveau_ia": "debutant",
        "mode_saisie": "clavier",
        "source_dictionnaire": "hunspell",
    }
