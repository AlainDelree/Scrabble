"""Tests de vérification d'un mot du brouillon (issue #257).

Couvre la fonction ``verifier_mot_dictionnaire`` : lecture seule, sans
mutation de la partie ni du dictionnaire.

Classe extraite de ``test_jeu.py`` (issue #257).
"""

import csv
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
            _DicoMots("CHAT"),
            ["C", "H", "A", "T"],
            fichier,
            chemin_belgicismes=tmp_path / "absent_belges.csv",
        )
        assert res["valide"] is True
        assert res["definition"] == [
            {"texte": "Petit félin domestique.", "origine": "standard"}
        ]

    def test_definition_mot_hunspell_sans_definition(self, tmp_path):
        # Mot valide mais absent de l'index (cas Hunspell uniquement) : None.
        fichier = tmp_path / "definitions.json"
        fichier.write_text(json.dumps({"CHAT": ["Félin."]}), encoding="utf-8")
        res = verifier_mot_dictionnaire(
            _DicoMots("KWYJIBO"),
            ["K", "W", "Y", "J", "I", "B", "O"],
            fichier,
            chemin_belgicismes=tmp_path / "absent_belges.csv",
        )
        assert res["valide"] is True
        assert res["definition"] is None

    def test_definition_non_calculee_si_invalide(self, tmp_path):
        # Même si le mot figure dans l'index, un mot invalide reste sans déf.
        fichier = tmp_path / "definitions.json"
        fichier.write_text(json.dumps({"XYZ": ["Bruit."]}), encoding="utf-8")
        res = verifier_mot_dictionnaire(
            _DicoMots("CHAT"),
            ["X", "Y", "Z"],
            fichier,
            chemin_belgicismes=tmp_path / "absent_belges.csv",
        )
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
            _DicoMots("CHAT"),
            ["C", "H", "A", "T"],
            fichier,
            source="ods",
            chemin_belgicismes=tmp_path / "absent_belges.csv",
        )
        assert res["valide"] is True
        assert res["definition"] == [
            {"texte": "Petit félin domestique.", "origine": "standard"}
        ]

    def test_definition_jamais_en_source_hunspell(self, tmp_path):
        # Issue #127 : mot valide en Hunspell, présent PAR COÏNCIDENCE dans
        # l'index ODS8 → définition None malgré tout (source active ≠ ODS).
        fichier = tmp_path / "definitions.json"
        fichier.write_text(
            json.dumps({"CHAT": ["Petit félin domestique."]}),
            encoding="utf-8",
        )
        res = verifier_mot_dictionnaire(
            _DicoMots("CHAT"),
            ["C", "H", "A", "T"],
            fichier,
            source="hunspell",
            chemin_belgicismes=tmp_path / "absent_belges.csv",
        )
        assert res["valide"] is True
        assert res["definition"] is None

    def test_definition_belge_affichee_independamment_de_la_source(self, tmp_path):
        # Issue #276 : une glose belge non dupliquée reste affichée même en
        # source Hunspell — seules les gloses standards sont filtrées par la
        # source active, jamais les gloses belges (permanent).
        fichier_defs = tmp_path / "definitions.json"
        fichier_defs.write_text(
            json.dumps({"CHAT": ["Petit félin domestique."]}), encoding="utf-8"
        )
        fichier_belges = tmp_path / "belgicismes.csv"
        fichier_belges.write_text(
            "mot,définition(s) belge(s),origine_wallonne,existe_sens_standard\n"
            "chat,Loquet de porte.,non,oui\n",
            encoding="utf-8",
        )
        res = verifier_mot_dictionnaire(
            _DicoMots("CHAT"),
            ["C", "H", "A", "T"],
            fichier_defs,
            source="hunspell",
            chemin_belgicismes=fichier_belges,
        )
        assert res["valide"] is True
        # La glose standard est filtrée (source Hunspell), la glose belge reste.
        assert res["definition"] == [{"texte": "Loquet de porte.", "origine": "belge"}]

    def test_definition_academique_deduplique_sans_doublon(self, tmp_path):
        # Cas académique (issues #276/#278) : les deux gloses belges sont déjà
        # mot pour mot dans le Wiktionnaire filtré — aucun doublon de texte,
        # mais les gloses standards partagées portent aussi_belge (drapeau).
        fichier_defs = tmp_path / "definitions.json"
        fichier_defs.write_text(
            json.dumps(
                {
                    "ACADEMIQUE": [
                        "Qui se rapporte aux académies.",
                        "Universitaire.",
                        "Relatif à un retard toléré.",
                    ]
                }
            ),
            encoding="utf-8",
        )
        fichier_belges = tmp_path / "belgicismes.csv"
        fichier_belges.write_text(
            "mot,définition(s) belge(s),origine_wallonne,existe_sens_standard\n"
            "academique,Universitaire. | Relatif à un retard toléré.,non,oui\n",
            encoding="utf-8",
        )
        res = verifier_mot_dictionnaire(
            _DicoMots("ACADEMIQUE"),
            list("ACADEMIQUE"),
            fichier_defs,
            chemin_belgicismes=fichier_belges,
        )
        assert res["valide"] is True
        assert res["definition"] == [
            {"texte": "Qui se rapporte aux académies.", "origine": "standard"},
            {
                "texte": "Universitaire.",
                "origine": "standard",
                "aussi_belge": True,
            },
            {
                "texte": "Relatif à un retard toléré.",
                "origine": "standard",
                "aussi_belge": True,
            },
        ]
        assert all(glose["origine"] == "standard" for glose in res["definition"])
        assert sum(1 for g in res["definition"] if g.get("aussi_belge")) == 2

    def test_definition_mot_belge_sans_equivalent_standard(self, tmp_path):
        # « sketter » : aucune glose standard, uniquement des gloses belges.
        fichier_defs = tmp_path / "definitions.json"
        fichier_defs.write_text(json.dumps({}), encoding="utf-8")
        fichier_belges = tmp_path / "belgicismes.csv"
        with open(fichier_belges, "w", encoding="utf-8", newline="") as fichier:
            ecrivain = csv.writer(fichier)
            ecrivain.writerow(
                ["mot", "définition(s) belge(s)", "origine_wallonne", "existe_sens_standard"]
            )
            ecrivain.writerow(["sketter", "Casser, fatiguer.", "non", "non"])
        res = verifier_mot_dictionnaire(
            _DicoMots("SKETTER"),
            list("SKETTER"),
            fichier_defs,
            chemin_belgicismes=fichier_belges,
        )
        assert res["valide"] is True
        assert res["definition"] == [{"texte": "Casser, fatiguer.", "origine": "belge"}]

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
            "scrabble.ui.jeu.definitions_annotees",
            lambda mot, chemin_definitions=None, chemin_belgicismes=None: [
                {"texte": "Petit félin domestique.", "origine": "standard"}
            ],
        )
        api = ApiJeu(_partie_simple(), None)
        res = api.verifier_mot(["C", "H", "A", "T"])
        assert res["valide"] is True
        assert res["definition"] == [
            {"texte": "Petit félin domestique.", "origine": "standard"}
        ]

    def test_api_pas_de_definition_en_source_hunspell(self, monkeypatch):
        # Issue #127 : source active Hunspell → jamais de définition STANDARD,
        # même si le mot valide est par coïncidence présent dans l'index ODS8.
        monkeypatch.setattr(
            "scrabble.ui.jeu.charger_config",
            lambda: {"source_dictionnaire": "hunspell"},
        )
        monkeypatch.setattr(
            "scrabble.ui.jeu.definitions_annotees",
            lambda mot, chemin_definitions=None, chemin_belgicismes=None: [
                {"texte": "Petit félin domestique.", "origine": "standard"}
            ],
        )
        api = ApiJeu(_partie_simple(), None)
        res = api.verifier_mot(["C", "H", "A", "T"])
        assert res["valide"] is True
        assert res["definition"] is None
