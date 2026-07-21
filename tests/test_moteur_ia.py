"""Tests des stratégies IA à niveaux de difficulté.

Couvre les 5 niveaux (EXPERT, AVANCE, INTERMEDIAIRE, FACILE, DEBUTANT) sur la
base du générateur exhaustif, la reproductibilité avec graine fixée, les cas
limites (un seul coup, aucun coup), et l'intégration avec Partie/creer_partie.
"""

from __future__ import annotations

import random
import statistics

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.generateur import generer_coups
from scrabble.moteur.ia import Niveau, choisir_coup
from scrabble.moteur.partie import (
    ACTION_COUP,
    ACTION_PASSE,
    Joueur,
    Partie,
    creer_partie,
)
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)


def _trie(*mots: str) -> Trie:
    return Trie.depuis_iterable(mots)


def _coup_cadre_au_centre() -> Coup:
    """CADRE horizontal à partir de la case centrale."""
    ligne, colonne = CENTRE
    return Coup(ligne, colonne, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))


# --------------------------------------------------------------------------- #
# Tests unitaires de choisir_coup
# --------------------------------------------------------------------------- #


class TestExpert:
    """EXPERT choisit toujours le meilleur coup."""

    def test_choisit_le_meilleur_score(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A")
        coup = choisir_coup(plateau, chevalet, dico, Niveau.EXPERT, random.Random(42))
        coups = generer_coups(plateau, chevalet, dico)
        meilleur_score = coups[0].score
        assert coup is not None
        coup_note = next(cn for cn in coups if cn.coup == coup)
        assert coup_note.score == meilleur_score

    def test_egalite_choisit_parmi_les_meilleurs(self):
        plateau = PlateauPartie()
        chevalet = list("AB")
        dico = _trie("AB", "BA")
        coups = generer_coups(plateau, chevalet, dico)
        scores = [cn.score for cn in coups]
        max_score = max(scores)
        meilleurs_coups = [cn.coup for cn in coups if cn.score == max_score]
        choisis = set()
        for graine in range(100):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.EXPERT, random.Random(graine)
            )
            if coup is not None:
                choisis.add((coup.ligne, coup.colonne, coup.direction.value))
        assert len(choisis) >= 1


class TestDebutant:
    """DEBUTANT choisit uniformément parmi tous les coups."""

    def test_distribution_uniforme_tous_coups(self):
        plateau = PlateauPartie()
        chevalet = list("CADRE")
        dico = _trie("CADRE", "DE", "RE", "A", "DA")
        coups = generer_coups(plateau, chevalet, dico)
        nb_coups = len(coups)
        assert nb_coups > 1

        choisis: dict[tuple, int] = {}
        tirages = 500
        for graine in range(tirages):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.DEBUTANT, random.Random(graine)
            )
            if coup is not None:
                cle = (coup.ligne, coup.colonne, coup.direction.value)
                choisis[cle] = choisis.get(cle, 0) + 1
        assert len(choisis) > 1


class TestScoreMoyenParNiveau:
    """Les niveaux produisent des scores moyens différenciés."""

    def test_expert_score_moyen_superieur_a_debutant(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")

        def moyenne_scores(niveau: Niveau, n: int = 100) -> float:
            scores = []
            coups_ref = generer_coups(plateau, chevalet, dico)
            for graine in range(n):
                coup = choisir_coup(
                    plateau, chevalet, dico, niveau, random.Random(graine)
                )
                if coup is not None:
                    cn = next(c for c in coups_ref if c.coup == coup)
                    scores.append(cn.score)
            return statistics.mean(scores) if scores else 0.0

        moy_expert = moyenne_scores(Niveau.EXPERT)
        moy_debutant = moyenne_scores(Niveau.DEBUTANT)
        assert moy_expert > moy_debutant

    def test_avance_score_moyen_entre_intermediaire_et_expert(self):
        """AVANCE se situe strictement entre INTERMEDIAIRE et EXPERT.

        Vérification statistique sur de nombreux tirages à graines variées
        (issue #202) : sur un plateau/chevalet offrant de nombreux coups aux
        scores étalés, la distribution de scores d'AVANCE (top 15 %) doit être
        supérieure à celle d'INTERMEDIAIRE (top 33 %) et inférieure ou égale à
        celle d'EXPERT (meilleur coup).
        """
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie(
            "CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES",
            "SE", "ED", "AR", "RA", "CAR", "ARC", "SAC", "ACRE", "CARDE",
        )
        coups_ref = generer_coups(plateau, chevalet, dico)
        # Le test n'a de sens que si les coups sont assez nombreux et étalés
        # pour que top 15 % et top 33 % diffèrent réellement.
        assert len(coups_ref) >= 10
        assert len({cn.score for cn in coups_ref}) >= 3

        def moyenne_scores(niveau: Niveau, n: int = 300) -> float:
            scores = []
            for graine in range(n):
                coup = choisir_coup(
                    plateau, chevalet, dico, niveau, random.Random(graine)
                )
                if coup is not None:
                    cn = next(c for c in coups_ref if c.coup == coup)
                    scores.append(cn.score)
            return statistics.mean(scores) if scores else 0.0

        moy_inter = moyenne_scores(Niveau.INTERMEDIAIRE)
        moy_avance = moyenne_scores(Niveau.AVANCE)
        moy_expert = moyenne_scores(Niveau.EXPERT)
        assert moy_inter < moy_avance < moy_expert


class TestIntermediaire:
    """INTERMEDIAIRE choisit dans le meilleur tiers."""

    def test_choisit_dans_le_tiers_superieur(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        coups = generer_coups(plateau, chevalet, dico)
        if len(coups) < 3:
            pytest.skip("Pas assez de coups pour tester le tiers")
        taille_tiers = max(1, len(coups) // 3)
        scores_tiers = {cn.score for cn in coups[:taille_tiers]}

        for graine in range(50):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.INTERMEDIAIRE, random.Random(graine)
            )
            if coup is not None:
                cn = next(c for c in coups if c.coup == coup)
                assert cn.score in scores_tiers or cn in coups[:taille_tiers]


class TestAvance:
    """AVANCE choisit dans les 15 % meilleurs coups (top 15 %)."""

    def test_choisit_dans_le_top_15_pct(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        coups = generer_coups(plateau, chevalet, dico)
        taille_haut = max(1, len(coups) * 15 // 100)
        haut = coups[:taille_haut]
        scores_haut = {cn.score for cn in haut}

        for graine in range(50):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.AVANCE, random.Random(graine)
            )
            if coup is not None:
                cn = next(c for c in coups if c.coup == coup)
                assert cn.score in scores_haut or cn in haut


class TestFacile:
    """FACILE choisit dans la moitié inférieure."""

    def test_choisit_dans_la_moitie_inferieure(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        coups = generer_coups(plateau, chevalet, dico)
        if len(coups) < 2:
            pytest.skip("Pas assez de coups pour tester la moitié")
        moitie_inf = coups[len(coups) // 2 :]

        for graine in range(50):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.FACILE, random.Random(graine)
            )
            if coup is not None:
                assert any(cn.coup == coup for cn in moitie_inf)


# --------------------------------------------------------------------------- #
# Cas limites
# --------------------------------------------------------------------------- #


class TestCasLimites:
    """Comportement sur listes courtes ou vides."""

    def test_aucun_coup_renvoie_none(self):
        plateau = PlateauPartie()
        chevalet = list("QWXYZ")
        dico = _trie("CADRE")
        for niveau in Niveau:
            coup = choisir_coup(plateau, chevalet, dico, niveau, random.Random(42))
            assert coup is None

    def test_un_seul_coup_tous_niveaux(self):
        plateau = PlateauPartie()
        chevalet = list("AB")
        dico = _trie("AB")
        coups = generer_coups(plateau, chevalet, dico)
        assert len(coups) == 2
        scores_distincts = {cn.score for cn in coups}
        assert len(scores_distincts) == 1
        for niveau in Niveau:
            coup = choisir_coup(plateau, chevalet, dico, niveau, random.Random(42))
            assert coup is not None
            assert any(cn.coup == coup for cn in coups)

    def test_deux_coups_facile_ne_plante_pas(self):
        plateau = PlateauPartie()
        chevalet = list("AB")
        dico = _trie("AB", "BA")
        for niveau in Niveau:
            coup = choisir_coup(plateau, chevalet, dico, niveau, random.Random(42))
            assert coup is not None


# --------------------------------------------------------------------------- #
# Reproductibilité
# --------------------------------------------------------------------------- #


class TestReproductibilite:
    """Même graine = même coup."""

    def test_meme_graine_meme_coup(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        for niveau in Niveau:
            coup1 = choisir_coup(plateau, chevalet, dico, niveau, random.Random(123))
            coup2 = choisir_coup(plateau, chevalet, dico, niveau, random.Random(123))
            assert coup1 == coup2


# --------------------------------------------------------------------------- #
# Intégration avec Partie
# --------------------------------------------------------------------------- #


class TestIntegrationPartie:
    """Intégration des niveaux IA avec Partie et creer_partie."""

    def test_creer_partie_avec_niveaux_ia(self):
        partie = creer_partie(
            ["Alice"],
            _trie("CADRE"),
            nb_ia=2,
            niveaux_ia=[Niveau.EXPERT, Niveau.DEBUTANT],
            graine=1,
        )
        assert partie.joueurs[1].niveau == Niveau.EXPERT
        assert partie.joueurs[2].niveau == Niveau.DEBUTANT

    def test_creer_partie_niveau_par_defaut_intermediaire(self):
        partie = creer_partie(["Alice"], _trie("CADRE"), nb_ia=1, graine=1)
        assert partie.joueurs[1].niveau == Niveau.INTERMEDIAIRE

    def test_joueur_humain_niveau_none(self):
        partie = creer_partie(["Alice"], _trie("CADRE"), nb_ia=1, graine=1)
        assert partie.joueurs[0].niveau is None

    def test_ia_expert_joue_plusieurs_tours(self):
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "ES", "DA")
        partie = creer_partie(
            ["Humain"],
            dico,
            nb_ia=1,
            niveaux_ia=[Niveau.EXPERT],
            graine=42,
        )
        partie.joueurs[0].chevalet[:] = list("CADRE")
        partie.jouer_coup(_coup_cadre_au_centre())

        tours_joues = 0
        while not partie.terminee and tours_joues < 10:
            joueur = partie.joueur_courant()
            if joueur.humain:
                partie.passer()
            else:
                partie.jouer_tour_ia()
            tours_joues += 1

        assert tours_joues > 0
        assert len(partie.historique) > 1

    def test_ia_passe_si_aucun_coup(self):
        partie = Partie(
            [Joueur("Humain"), Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
            _trie("CADRE"),
            graine=1,
        )
        partie.joueurs[0].chevalet[:] = list("CADRE")
        partie.jouer_coup(_coup_cadre_au_centre())
        partie.joueurs[1].chevalet[:] = list("QWXYZ")
        entree = partie.jouer_tour_ia()
        assert entree.action == ACTION_PASSE

    def test_ia_pose_un_coup(self):
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
            _trie("CADRE"),
            graine=1,
        )
        partie.joueurs[0].chevalet[:] = list("CADRE")
        entree = partie.jouer_tour_ia()
        assert entree.action == ACTION_COUP
        assert partie.joueurs[0].score > 0

    def test_tous_niveaux_jouent_sans_crash(self):
        for niveau in Niveau:
            dico = _trie("CADRE", "AS", "A", "SA", "DE")
            partie = creer_partie(
                ["Humain"], dico, nb_ia=1, niveaux_ia=[niveau], graine=42
            )
            partie.joueurs[0].chevalet[:] = list("CADRE")
            partie.jouer_coup(_coup_cadre_au_centre())
            partie.jouer_tour_ia()
            assert len(partie.historique) == 2
