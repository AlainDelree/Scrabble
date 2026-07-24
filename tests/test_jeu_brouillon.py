"""Tests de vérification d'un mot du brouillon (issue #257).

Couvre la fonction ``verifier_mot_dictionnaire`` : lecture seule, sans
mutation de la partie ni du dictionnaire.

Classe extraite de ``test_jeu.py`` (issue #257).
"""

import json

import pytest

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.ui.jeu import ApiJeu, etat_public, verifier_mot_dictionnaire
from tests._aides_test_jeu import _DicoFactice, _partie_simple


class _DicoMots:
    """Dictionnaire de test acceptant uniquement un ensemble de mots donnés."""

    def __init__(self, *mots: str) -> None:
        self._mots = {mot.upper() for mot in mots}

    def contient(self, mot: str) -> bool:
        return mot.upper() in self._mots


class TestVerifierMotDictionnaire:
    """Vérification d'un mot du brouillon (lecture seule, sans mutation)."""

    def test_mot_valide(self):
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), ["C", "H", "A", "T"])
        assert res["succes"] is True
        assert res["mot"] == "CHAT"
        assert res["valide"] is True
        # La clé ``definition`` est toujours présente (issue #124).
        assert "definition" in res

    def test_mot_invalide(self):
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), ["X", "Y", "Z"])
        assert res["succes"] is True
        assert res["mot"] == "XYZ"
        assert res["valide"] is False
        # Un mot invalide n'a jamais de définition (issue #124).
        assert res["definition"] is None

    def test_definition_mot_ods8(self, tmp_path):
        # Mot valide ET présent dans l'index de définitions ODS8.
        fichier = tmp_path / "definitions.json"
        fichier.write_text(
            json.dumps({"CHAT": ["Petit félin domestique."]}),
            encoding="utf-8",
        )
        res = verifier_mot_dictionnaire(
            _DicoMots("CHAT"), ["C", "H", "A", "T"], fichier
        )
        assert res["valide"] is True
        assert res["definition"] == ["Petit félin domestique."]

    def test_definition_mot_hunspell_sans_definition(self, tmp_path):
        # Mot valide mais absent de l'index (cas Hunspell uniquement) : None.
        fichier = tmp_path / "definitions.json"
        fichier.write_text(json.dumps({"CHAT": ["Félin."]}), encoding="utf-8")
        res = verifier_mot_dictionnaire(
            _DicoMots("KWYJIBO"), ["K", "W", "Y", "J", "I", "B", "O"], fichier
        )
        assert res["valide"] is True
        assert res["definition"] is None

    def test_definition_non_calculee_si_invalide(self, tmp_path):
        # Même si le mot figure dans l'index, un mot invalide reste sans déf.
        fichier = tmp_path / "definitions.json"
        fichier.write_text(json.dumps({"XYZ": ["Bruit."]}), encoding="utf-8")
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), ["X", "Y", "Z"], fichier)
        assert res["valide"] is False
        assert res["definition"] is None

    def test_definition_ods_source_active(self, tmp_path):
        # Non-régression #124 : mot valide en ODS8, source active ODS →
        # définition renvoyée normalement.
        fichier = tmp_path / "definitions.json"
        fichier.write_text(
            json.dumps({"CHAT": ["Petit félin domestique."]}),
            encoding="utf-8",
        )
        res = verifier_mot_dictionnaire(
            _DicoMots("CHAT"), ["C", "H", "A", "T"], fichier, source="ods"
        )
        assert res["valide"] is True
        assert res["definition"] == ["Petit félin domestique."]

    def test_definition_jamais_en_source_hunspell(self, tmp_path):
        # Issue #127 : mot valide en Hunspell, présent PAR COÏNCIDENCE dans
        # l'index ODS8 → définition None malgré tout (source active ≠ ODS).
        fichier = tmp_path / "definitions.json"
        fichier.write_text(
            json.dumps({"CHAT": ["Petit félin domestique."]}),
            encoding="utf-8",
        )
        res = verifier_mot_dictionnaire(
            _DicoMots("CHAT"), ["C", "H", "A", "T"], fichier, source="hunspell"
        )
        assert res["valide"] is True
        assert res["definition"] is None

    def test_accepte_chaine_deja_assemblee(self):
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), "chat")
        assert res["mot"] == "CHAT"
        assert res["valide"] is True

    def test_ordre_des_lettres_respecte(self):
        # L'ordre du brouillon compte : "TACH" n'est pas "CHAT".
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), ["T", "A", "C", "H"])
        assert res["mot"] == "TACH"
        assert res["valide"] is False

    def test_brouillon_vide(self):
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), [])
        assert res["succes"] is False
        assert res.get("erreur")

    def test_joker_empeche_le_mot(self):
        # Un joker ('*') laissé dans le brouillon n'est pas une lettre fixe.
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), ["C", "H", "A", "*"])
        assert res["succes"] is True
        assert res["valide"] is False

    def test_lecture_seule_pas_de_mutation(self):
        # La vérification ne doit toucher NI la partie NI le dictionnaire.
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots("CHAT"), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list("CHATSER")
        api = ApiJeu(partie, None)

        avant = etat_public(partie, None)
        chevalet_avant = list(partie.joueurs[0].chevalet)
        sac_avant = partie.sac.jetons_restants()

        res = api.verifier_mot(["C", "H", "A", "T"])
        assert res["valide"] is True
        # Aucune mutation : tour, chevalet, sac et état public inchangés.
        assert partie.index_courant == 0
        assert list(partie.joueurs[0].chevalet) == chevalet_avant
        assert partie.sac.jetons_restants() == sac_avant
        assert etat_public(partie, None) == avant

    def test_api_definition_en_source_ods(self, monkeypatch):
        # Source active ODS : la définition est bien renvoyée (issue #124/#127).
        monkeypatch.setattr(
            "scrabble.ui.jeu.charger_config",
            lambda: {"source_dictionnaire": "ods"},
        )
        monkeypatch.setattr(
            "scrabble.ui.jeu.definition_mot",
            lambda mot, chemin=None: ["Petit félin domestique."],
        )
        api = ApiJeu(_partie_simple(), None)
        res = api.verifier_mot(["C", "H", "A", "T"])
        assert res["valide"] is True
        assert res["definition"] == ["Petit félin domestique."]

    def test_api_pas_de_definition_en_source_hunspell(self, monkeypatch):
        # Issue #127 : source active Hunspell → jamais de définition, même si le
        # mot valide est par coïncidence présent dans l'index ODS8.
        monkeypatch.setattr(
            "scrabble.ui.jeu.charger_config",
            lambda: {"source_dictionnaire": "hunspell"},
        )
        monkeypatch.setattr(
            "scrabble.ui.jeu.definition_mot",
            lambda mot, chemin=None: ["Petit félin domestique."],
        )
        api = ApiJeu(_partie_simple(), None)
        res = api.verifier_mot(["C", "H", "A", "T"])
        assert res["valide"] is True
        assert res["definition"] is None
