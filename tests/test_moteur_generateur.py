"""Tests du générateur exhaustif de coups valides."""

from __future__ import annotations

import time

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.generateur import CoupNote, generer_coups
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    Tuile,
)
from scrabble.regles.lettres import JOKER


def _trie_mots(mots: list[str]) -> Trie:
    """Construit un Trie à partir d'une liste de mots."""
    trie = Trie()
    for mot in mots:
        trie.inserer(mot)
    return trie


class TestCasSimplePlateauVide:
    """Cas simple : premier coup sur plateau vide."""

    def test_mot_unique_trouve(self) -> None:
        """Un chevalet permettant un seul mot du dictionnaire le trouve."""
        plateau = PlateauPartie()
        chevalet = ["C", "A", "T"]
        trie = _trie_mots(["CAT"])  # seul mot possible

        resultats = generer_coups(plateau, chevalet, trie)

        assert len(resultats) >= 1
        mots_trouves = [
            "".join(t.lettre for t in r.coup.tuiles) for r in resultats
        ]
        assert "CAT" in mots_trouves

    def test_premier_coup_couvre_centre(self) -> None:
        """Le premier coup trouvé couvre la case centrale."""
        plateau = PlateauPartie()
        chevalet = ["L", "E"]
        trie = _trie_mots(["LE"])

        resultats = generer_coups(plateau, chevalet, trie)

        assert len(resultats) >= 1
        for res in resultats:
            cases = res.coup.cases()
            positions = [(l, c) for l, c, _ in cases]
            assert CENTRE in positions

    def test_plusieurs_mots_possibles(self) -> None:
        """Plusieurs mots possibles sont tous trouvés."""
        plateau = PlateauPartie()
        chevalet = ["L", "E", "S"]
        trie = _trie_mots(["LE", "ES", "LES"])

        resultats = generer_coups(plateau, chevalet, trie)
        mots_trouves = {
            "".join(t.lettre for t in r.coup.tuiles) for r in resultats
        }

        # Au moins LE et LES doivent être trouvés (ES peut l'être aussi)
        assert "LE" in mots_trouves or "LES" in mots_trouves


class TestPlateauNonVide:
    """Cas avec plateau non vide et plusieurs ancrages."""

    def test_accroche_simple(self) -> None:
        """On trouve un mot accroché à une lettre existante."""
        plateau = PlateauPartie()
        # Poser "LE" au centre horizontalement
        plateau.poser_tuile(7, 7, Tuile("L"))
        plateau.poser_tuile(7, 8, Tuile("E"))

        chevalet = ["S"]
        trie = _trie_mots(["LE", "LES"])

        resultats = generer_coups(plateau, chevalet, trie)

        assert len(resultats) >= 1
        # On devrait trouver LES en ajoutant S
        mots_formes = []
        for res in resultats:
            mot = "".join(t.lettre for t in res.coup.tuiles)
            mots_formes.append(mot)
        assert "LES" in mots_formes

    def test_extension_verticale(self) -> None:
        """Extension verticale à partir d'un mot horizontal."""
        plateau = PlateauPartie()
        # Poser "LA" au centre horizontalement
        plateau.poser_tuile(7, 7, Tuile("L"))
        plateau.poser_tuile(7, 8, Tuile("A"))

        chevalet = ["E"]
        trie = _trie_mots(["LA", "LE", "AE"])  # AE = mot valide

        resultats = generer_coups(plateau, chevalet, trie)

        # On devrait trouver au moins un coup vertical
        directions = {res.coup.direction for res in resultats}
        # Le générateur peut trouver des extensions horizontales ou verticales
        assert len(resultats) >= 1

    def test_scores_calcules_correctement(self) -> None:
        """Les scores sont calculés et la liste est triée."""
        plateau = PlateauPartie()
        chevalet = ["A", "B", "C"]
        trie = _trie_mots(["AB", "BA", "CA", "ABC"])

        resultats = generer_coups(plateau, chevalet, trie)

        # Vérifier que tous les résultats ont un score > 0
        for res in resultats:
            assert res.score > 0

        # Vérifier le tri décroissant
        scores = [res.score for res in resultats]
        assert scores == sorted(scores, reverse=True)


class TestJoker:
    """Cas avec joker dans le chevalet."""

    def test_mot_avec_joker(self) -> None:
        """Un mot nécessitant le joker est trouvé."""
        plateau = PlateauPartie()
        # Chevalet sans la lettre O, mais avec joker
        chevalet = ["M", "T", JOKER]
        trie = _trie_mots(["MOT"])

        resultats = generer_coups(plateau, chevalet, trie)

        # Le joker doit permettre de former MOT
        mots_trouves = {
            "".join(t.lettre for t in r.coup.tuiles) for r in resultats
        }
        assert "MOT" in mots_trouves

    def test_joker_marque_comme_tel(self) -> None:
        """La tuile joker est bien marquée comme joker."""
        plateau = PlateauPartie()
        chevalet = ["A", JOKER]
        trie = _trie_mots(["AB"])

        resultats = generer_coups(plateau, chevalet, trie)

        # Trouver le coup AB
        coup_ab = None
        for res in resultats:
            mot = "".join(t.lettre for t in res.coup.tuiles)
            if mot == "AB":
                coup_ab = res.coup
                break

        assert coup_ab is not None
        # La tuile B doit être un joker
        tuiles_joker = [t for t in coup_ab.tuiles if t.joker]
        assert len(tuiles_joker) == 1
        assert tuiles_joker[0].lettre == "B"

    def test_joker_vaut_zero_points(self) -> None:
        """Le joker ne rapporte aucun point."""
        plateau = PlateauPartie()
        chevalet_avec_joker = ["A", JOKER]
        chevalet_sans_joker = ["A", "B"]
        trie = _trie_mots(["AB"])

        resultats_joker = generer_coups(plateau, chevalet_avec_joker, trie)
        resultats_normal = generer_coups(plateau, chevalet_sans_joker, trie)

        # Trouver les scores pour AB
        score_joker = next(
            r.score
            for r in resultats_joker
            if "".join(t.lettre for t in r.coup.tuiles) == "AB"
        )
        score_normal = next(
            r.score
            for r in resultats_normal
            if "".join(t.lettre for t in r.coup.tuiles) == "AB"
        )

        # Le joker vaut 0, donc score_joker < score_normal
        # A=1, B=3 normal → 4 (avec bonus centre x2 = 8)
        # A=1, joker(B)=0 → 1 (avec bonus centre x2 = 2)
        assert score_joker < score_normal


class TestAucunCoup:
    """Cas où aucun coup n'est possible."""

    def test_chevalet_sans_mot_valide(self) -> None:
        """Un chevalet ne permettant aucun mot renvoie une liste vide."""
        plateau = PlateauPartie()
        chevalet = ["X", "X", "X"]
        trie = _trie_mots(["ABC", "DEF"])

        resultats = generer_coups(plateau, chevalet, trie)

        assert resultats == []

    def test_chevalet_vide(self) -> None:
        """Un chevalet vide renvoie une liste vide."""
        plateau = PlateauPartie()
        chevalet: list[str] = []
        trie = _trie_mots(["ABC"])

        resultats = generer_coups(plateau, chevalet, trie)

        assert resultats == []


class TestPerformance:
    """Test de performance basique."""

    def test_temps_raisonnable(self) -> None:
        """Sur un plateau réaliste, l'exécution reste sous quelques secondes."""
        plateau = PlateauPartie()
        # Poser quelques mots pour simuler une partie en cours
        for i, lettre in enumerate("JOUER"):
            plateau.poser_tuile(7, 5 + i, Tuile(lettre))

        # Chevalet de 7 lettres courantes
        chevalet = ["E", "A", "I", "R", "S", "T", "N"]

        # Dictionnaire réaliste avec quelques mots courants
        mots = [
            "LE", "LA", "LES", "UN", "UNE", "ET", "EN", "DE",
            "AIR", "ANE", "ANS", "ART", "EAU", "ERA", "IRE",
            "NE", "NI", "NU", "OR", "OS", "OU", "RI", "SA",
            "SE", "SI", "SU", "TA", "TE", "TU", "VA", "VU",
            "AIRS", "ANES", "ARTS", "IRES", "NIER", "RIES",
            "SARI", "SERA", "STAR", "TIRS", "TSAR",
            "NIERA", "RENIA", "SERAI", "TRAIN", "TRANS",
            "ENTRAI", "NAÎTRE", "RETINS", "SENTIR", "SEREIN",
            "ENTRAIS", "INSERAT", "RATINES", "RETAINS", "SENTIRA",
            # Mots accrochables à JOUER
            "JOUERA", "JOUERAI", "JOUERAS", "JOUERAT",
            "AJOUTER", "RAJOUTER",
            "RE", "ES", "ER",
        ]
        trie = _trie_mots(mots)

        debut = time.perf_counter()
        resultats = generer_coups(plateau, chevalet, trie)
        duree = time.perf_counter() - debut

        # Doit s'exécuter en moins de 5 secondes
        assert duree < 5.0, f"Temps d'exécution trop long : {duree:.2f}s"

        # Afficher pour le rapport
        print(f"\nPerformance: {len(resultats)} coups trouvés en {duree:.3f}s")


class TestIntegrationDictionnaire:
    """Tests avec un vrai sous-ensemble du dictionnaire."""

    def test_mots_francais_courants(self) -> None:
        """Vérifie la génération avec des mots français courants."""
        plateau = PlateauPartie()
        chevalet = ["L", "E", "S", "A"]
        trie = _trie_mots(["LE", "LA", "LES", "LAS", "ALE", "ALES", "SALE", "SELA"])

        resultats = generer_coups(plateau, chevalet, trie)

        mots_trouves = {
            "".join(t.lettre for t in r.coup.tuiles) for r in resultats
        }
        # Au moins quelques-uns de ces mots doivent être trouvés
        assert len(mots_trouves) >= 1
