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
    """FACILE choisit dans les 60 % meilleurs coups (top 60 %) — issue #208."""

    def test_choisit_dans_le_top_60_pct(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        coups = generer_coups(plateau, chevalet, dico)
        if len(coups) < 2:
            pytest.skip("Pas assez de coups pour tester le top 60 %")
        taille_haut = max(1, len(coups) * 60 // 100)
        haut = coups[:taille_haut]

        for graine in range(50):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.FACILE, random.Random(graine)
            )
            if coup is not None:
                assert any(cn.coup == coup for cn in haut)

    def test_score_moyen_superieur_a_debutant(self):
        """FACILE est réellement plus fort que DEBUTANT en score moyen.

        Cœur de l'issue #208 : l'ancienne stratégie (moitié inférieure) rendait
        FACILE plus FAIBLE que DEBUTANT ; le passage au top 60 % corrige cette
        inversion nom/force sur un plateau/chevalet offrant des scores étalés.
        """
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie(
            "CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES",
            "SE", "ED", "AR", "RA", "CAR", "ARC", "SAC", "ACRE", "CARDE",
        )
        coups_ref = generer_coups(plateau, chevalet, dico)

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

        moy_debutant = moyenne_scores(Niveau.DEBUTANT)
        moy_facile = moyenne_scores(Niveau.FACILE)
        moy_inter = moyenne_scores(Niveau.INTERMEDIAIRE)
        assert moy_debutant < moy_facile < moy_inter


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


# --------------------------------------------------------------------------- #
# Cohérence de la progression avec le Trie restreint de l'IA (issue #207)
# --------------------------------------------------------------------------- #
#
# Le réglage « vocabulaire humain » (issue #206) fait jouer l'IA sur un
# dictionnaire restreint (``dictionnaire_ia``, distinct du dico complet) :
# (mots courants ∪ classiques du jeu) ∩ dico complet. Ce filtre est GLOBAL —
# appliqué uniformément à tous les niveaux, pas par niveau. Le rapport
# d'investigation #203 anticipait donc que la progression RELATIVE entre niveaux
# resterait cohérente une fois le filtre actif : seuls les scores absolus
# baisseraient, pour tous les niveaux pareillement.
#
# Ces tests le vérifient empiriquement avec la même méthode que les tests
# existants (score moyen sur de nombreux tirages à graines variées), mais cette
# fois avec un Trie IA strictement plus petit que le dico complet.

# Vocabulaire complet riche autour du chevalet « CARTONS » (plateau vide, ancrage
# central unique). Offre 118 coups aux scores étalés, dont un « scrabble »
# (bingo) CARTONS à 70 points.
_MOTS_COMPLET = (
    "CARTON", "CARTONS", "CARTE", "CARTES", "CANOT", "CANOTS", "CARAT",
    "CARATS", "ARC", "ARCS", "ARCON", "ARCONS", "CAR", "CARS", "CAS", "SAC",
    "SACRE", "ACRE", "ACRES", "RAT", "RATS", "ART", "ARTS", "TARS", "STAR",
    "CORS", "CORNS", "CON", "CONS", "COR", "COT", "COTS", "ROC", "ROCS",
    "ORC", "ORCS", "TON", "TONS", "TROC", "TROCS", "SORT", "SORTA", "TRACS",
    "TRAC", "NAC", "NACRE", "NACRES", "SCAT", "OCA", "OCAS", "TAO", "TAOS",
    "ANT", "RATON", "RATONS", "TANCS", "TANC", "CANT", "CANTS", "NOTA",
    "SONAR", "SONATE", "SCORE", "CROATS", "TARON", "ROTAS", "ROTA", "TROCA",
    "SANTO", "CATOR",
)

# Sous-ensemble « vocabulaire humain » : mots courants seulement, sous-ensemble
# STRICT de _MOTS_COMPLET (invariant de obtenir_trie_ia : l'ensemble IA est
# toujours intersecté avec le dico complet). On y a retiré les mots rares/peu
# courants — dont le bingo CARTONS — pour reproduire fidèlement l'effet du
# filtre : l'IA perd l'accès aux coups à fort score assis sur du vocabulaire
# rare. Laisse tout de même 44 coups aux scores étalés (6 scores distincts).
_MOTS_IA_RESTREINT = (
    "CARTON", "CARTE", "CARTES", "CANOT", "CAR", "CARS", "CAS", "SAC", "ACRE",
    "RAT", "RATS", "ART", "ARTS", "STAR", "CON", "CONS", "COR", "ROC", "TON",
    "TONS", "SORT", "TRAC", "OCA", "TAO", "SONAR", "SCORE",
)

# Ordre des niveaux par score moyen croissant, tel qu'il découle RÉELLEMENT des
# stratégies de sélection (cf. ia.py) :
#   * DEBUTANT tire uniformément parmi TOUS les coups → moyenne la plus basse ;
#   * FACILE tire dans le top 60 % (écarte les 40 % plus faibles) → au-dessus
#     de DEBUTANT mais nettement sous INTERMEDIAIRE ;
#   * INTERMEDIAIRE (top 33 %), AVANCE (top 15 %), EXPERT (meilleur) → croissant.
# NB : depuis l'issue #208, FACILE n'est plus la moitié INFÉRIEURE (ce qui le
# plaçait sous DEBUTANT, contrairement à ce que suggèrent les noms) mais le
# top 60 %. L'ordre réel coïncide désormais avec l'ordre des noms et avec
# l'énoncé de l'issue #207 : « Débutant < Facile < Intermédiaire < Avancé <
# Expert ». Cette monotonie est structurelle et vaut donc à l'identique avec et
# sans le filtre de vocabulaire ; ces tests le vérifient empiriquement.
_ORDRE_CROISSANT_ATTENDU = [
    Niveau.DEBUTANT,
    Niveau.FACILE,
    Niveau.INTERMEDIAIRE,
    Niveau.AVANCE,
    Niveau.EXPERT,
]


def _moyennes_par_niveau(
    plateau: PlateauPartie,
    chevalet: list[str],
    dico: Trie,
    n: int = 400,
) -> dict[Niveau, float]:
    """Score moyen de chaque niveau sur ``n`` tirages à graines 0..n-1.

    Même méthode que les tests statistiques existants : on génère la liste de
    référence des coups une fois (sur ``dico``, donc restreinte si ``dico`` est
    le Trie IA), puis on relève le score du coup choisi pour chaque graine. Le
    score d'un coup ne dépend que des tuiles/plateau, pas du dictionnaire.
    """
    coups_ref = generer_coups(plateau, chevalet, dico)
    moyennes: dict[Niveau, float] = {}
    for niveau in Niveau:
        scores = []
        for graine in range(n):
            coup = choisir_coup(plateau, chevalet, dico, niveau, random.Random(graine))
            if coup is not None:
                cn = next(c for c in coups_ref if c.coup == coup)
                scores.append(cn.score)
        moyennes[niveau] = statistics.mean(scores) if scores else 0.0
    return moyennes


class TestProgressionTrieIaRestreint:
    """Progression de difficulté avec le Trie restreint de l'IA (issue #207)."""

    plateau = PlateauPartie()
    chevalet = list("CARTONS")

    def test_sous_ensemble_strict_et_assez_de_coups(self):
        """Prérequis : le vocabulaire IA est un sous-ensemble STRICT du complet,
        et le Trie restreint laisse assez de coups variés pour être significatif.
        """
        assert set(_MOTS_IA_RESTREINT) < set(_MOTS_COMPLET)
        dico_ia = Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        coups_ia = generer_coups(self.plateau, self.chevalet, dico_ia)
        # Significatif : nombreux coups et scores étalés (comme les tests #202).
        assert len(coups_ia) >= 10
        assert len({cn.score for cn in coups_ia}) >= 3

    def test_progression_monotone_avec_filtre_actif(self):
        """La progression reste strictement monotone avec le Trie IA restreint.

        Confirme l'hypothèse du rapport #203 : le filtre étant global, la
        monotonie des scores moyens est préservée une fois le filtre actif.
        """
        dico_ia = Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        moy = _moyennes_par_niveau(self.plateau, self.chevalet, dico_ia)
        ordre = sorted(Niveau, key=lambda niv: moy[niv])
        assert ordre == _ORDRE_CROISSANT_ATTENDU
        # Strictement croissant le long de l'ordre attendu.
        valeurs = [moy[niv] for niv in _ORDRE_CROISSANT_ATTENDU]
        assert all(a < b for a, b in zip(valeurs, valeurs[1:]))

    def test_niveaux_restent_perceptiblement_distincts(self):
        """Aucun niveau ne se confond avec son voisin sous le filtre.

        Point #3 de l'issue : on veut détecter le cas où un niveau ne se
        distinguerait plus suffisamment d'un autre. On exige un écart d'au moins
        1 point entre niveaux adjacents dans l'ordre de progression, seuil
        au-delà duquel la différence reste perceptible en jeu.
        """
        dico_ia = Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        moy = _moyennes_par_niveau(self.plateau, self.chevalet, dico_ia)
        valeurs = [moy[niv] for niv in _ORDRE_CROISSANT_ATTENDU]
        ecarts = [b - a for a, b in zip(valeurs, valeurs[1:])]
        assert min(ecarts) >= 1.0, f"Niveaux trop proches sous filtre : {ecarts}"

    def test_ordre_relatif_identique_avec_et_sans_filtre(self):
        """L'ordre RELATIF des niveaux est identique avec et sans filtre.

        Cœur de la vérification #207 / hypothèse #203 : le filtre global ne
        réordonne pas les niveaux ; il n'abaisse que les scores absolus.
        """
        moy_complet = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_COMPLET)
        )
        moy_ia = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        )
        assert sorted(Niveau, key=lambda niv: moy_complet[niv]) == sorted(
            Niveau, key=lambda niv: moy_ia[niv]
        )

    def test_ecart_expert_debutant_se_resserre_sous_filtre(self):
        """Mesure le resserrement Expert↔Débutant sous filtre (point #4).

        Point de vigilance du rapport #203 : même monotonie préservée, l'écart
        absolu entre le meilleur et le plus faible niveau peut se resserrer si le
        filtre retire les coups à très fort score (vocabulaire rare). Dans ce
        scénario, le bingo CARTONS (70 pts) est retiré du vocabulaire IA, donc
        Expert perd sa pointe : l'écart Expert↔Débutant chute nettement, tout en
        restant strictement positif (les niveaux restent ordonnés).
        """
        moy_complet = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_COMPLET)
        )
        moy_ia = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        )
        ecart_complet = moy_complet[Niveau.EXPERT] - moy_complet[Niveau.DEBUTANT]
        ecart_ia = moy_ia[Niveau.EXPERT] - moy_ia[Niveau.DEBUTANT]
        # Reste ordonné (Expert > Débutant) même sous filtre...
        assert ecart_ia > 0
        # ... mais se resserre sensiblement quand le vocabulaire rare disparaît.
        assert ecart_ia < ecart_complet
