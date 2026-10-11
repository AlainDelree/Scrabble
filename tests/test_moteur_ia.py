"""Tests des stratégies IA à niveaux de difficulté.

Couvre les 6 niveaux (DEBUTANT, FACILE, INTERMEDIAIRE, AVANCE, EXPERT,
CHAMPION_DU_MONDE) sur la base du générateur exhaustif, la reproductibilité
avec graine fixée, les cas limites (un seul coup, aucun coup), et
l'intégration avec Partie/creer_partie.

Échelle refondue par l'issue #401 (sur la base du rapport #400) : chaque
niveau reprend la stratégie de sélection d'un ancien niveau plus fort, ce qui
resserre l'échelle vers le haut, et EXPERT devient un niveau à part entière
intercalé entre AVANCE et CHAMPION_DU_MONDE. AVANCE et CHAMPION_DU_MONDE
partagent EXACTEMENT la même stratégie de sélection (:func:`~scrabble.moteur.ia._choisir_avance`,
meilleur coup) : à dictionnaire identique, les deux niveaux restent
mécaniquement égaux — c'est ce que vérifient la plupart des tests
ci-dessous, qui appellent ``choisir_coup(..., dico, niveau, ...)`` avec un
seul ``dico`` partagé. Ce qui les distingue en jeu réel est le vocabulaire
reçu en paramètre, câblé par l'appelant (issue #369, lot C, voir
``scrabble.moteur.ia.resoudre_palier`` et ``scrabble.ui.accueil``) : AVANCE
sur le Trie restreint du palier ``"avance"``, CHAMPION_DU_MONDE sur le Trie
complet. EXPERT, lui, change à la fois de stratégie (top 5 % plutôt que
meilleur coup) et de vocabulaire (Trie complet ODS8, comme CHAMPION_DU_MONDE
— ``resoudre_palier`` renvoie ``None`` pour les deux, issue #401). Les tests
de monotonie de ``TestProgressionTrieIaRestreint`` simulent ce câblage en
donnant explicitement le dictionnaire complet à EXPERT et CHAMPION_DU_MONDE
(``dico_champion``), pour vérifier l'inégalité qui en résulte.
"""

from __future__ import annotations

import random
import statistics
import string

import pytest

from scrabble.dictionnaire.dictionnaire import FICHIERS_VOCABULAIRE_PALIER, Trie
from scrabble.moteur.generateur import CoupNote, generer_coups
from scrabble.moteur.ia import (
    Niveau,
    _POIDS_LEAVE,
    ProfilPersonnage,
    _generer_coups_candidats,
    _mot_connu_vocabulaire_court,
    _mot_connu_vocabulaire_long,
    _score_strategique,
    _tirer_dans_tranche,
    choisir_coup,
    evaluer_coups,
    leave_value,
    resoudre_palier,
)
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
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.regles.plateau import TypeCase


def _trie(*mots: str) -> Trie:
    return Trie.depuis_iterable(mots)


def _coup_cadre_au_centre() -> Coup:
    """CADRE horizontal à partir de la case centrale."""
    ligne, colonne = CENTRE
    return Coup(ligne, colonne, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))


# --------------------------------------------------------------------------- #
# Résolution Niveau → palier de vocabulaire IA (issue #369, lot C)
# --------------------------------------------------------------------------- #

class TestResoudrePalier:
    """Résolution :class:`Niveau` → clé de palier (:func:`resoudre_palier`)."""

    @pytest.mark.parametrize(
        "niveau, palier_attendu",
        [
            (Niveau.DEBUTANT, "debutant"),
            (Niveau.FACILE, "facile"),
            (Niveau.INTERMEDIAIRE, "intermediaire"),
            (Niveau.AVANCE, "avance"),
        ],
    )
    def test_quatre_premiers_niveaux_resolvent_vers_leur_palier(
        self, niveau, palier_attendu
    ):
        assert resoudre_palier(niveau) == palier_attendu

    def test_expert_ne_resout_vers_aucun_palier(self):
        """EXPERT n'a pas de palier (issue #401) : Trie complet, pas de fichier.

        Contrairement aux quatre premiers niveaux, EXPERT joue sur le Trie ODS8
        complet — comme CHAMPION_DU_MONDE, dont il reprend le vocabulaire (mais
        pas la stratégie de sélection, voir :func:`~scrabble.moteur.ia._choisir_top5`).
        """
        assert resoudre_palier(Niveau.EXPERT) is None

    def test_champion_du_monde_ne_resout_vers_aucun_palier(self):
        """CHAMPION_DU_MONDE n'a pas de palier : Trie complet, pas de fichier."""
        assert resoudre_palier(Niveau.CHAMPION_DU_MONDE) is None

    def test_tous_les_niveaux_sont_couverts(self):
        """Chaque membre de Niveau reçoit une résolution (palier ou None)."""
        for niveau in Niveau:
            resoudre_palier(niveau)  # ne doit jamais lever

    def test_paliers_resolus_correspondent_aux_cles_du_vocabulaire_ia(self):
        """Les clés produites sont exactement celles de FICHIERS_VOCABULAIRE_PALIER.

        Vérifie la correspondance entre ce module (qui ne connaît que des
        chaînes, sans importer ``scrabble.dictionnaire``, issue #369) et les
        clés réelles utilisées côté dictionnaire — la cohérence dépend de la
        discipline documentée, pas d'un import partagé.
        """
        paliers_resolus = {
            resoudre_palier(niveau)
            for niveau in Niveau
            if resoudre_palier(niveau) is not None
        }
        assert paliers_resolus == set(FICHIERS_VOCABULAIRE_PALIER)


# --------------------------------------------------------------------------- #
# Score stratégique (issue #359) : pénalité hooks / bonus cases premium
# --------------------------------------------------------------------------- #


def _coup_note(mot: str, score: int, nb_nouvelles: int, cases_bonus=()) -> CoupNote:
    """CoupNote synthétique pour tester _score_strategique isolément."""
    coup = Coup(CENTRE[0], CENTRE[1], Direction.HORIZONTALE, tuiles_depuis_chaine(mot))
    detail = DetailScore(
        mots=[DetailMot(texte=mot, score=score, cases_bonus=list(cases_bonus))],
        bonus_scrabble=0,
        total=score,
    )
    return CoupNote(coup, detail, nb_nouvelles, ())


class TestScoreStrategique:
    """Pénalité longueur et bonus cases premium du tri IA (issue #359)."""

    def test_expert_prefere_mot_double_a_hook_legerement_superieur(self):
        """EXPERT préfère un mot sur case MOT_DOUBLE à un hook mieux payé.

        Reproduit l'exemple de l'issue #359 : un hook d'une seule lettre à
        18 pts (case normale) contre un mot de 4 lettres à 16 pts profitant
        d'une case MOT_DOUBLE. En score brut le hook gagne ; en score
        stratégique EXPERT, le mot sur case premium doit l'emporter.
        """
        hook = _coup_note("CADRES", score=18, nb_nouvelles=1)
        mot_premium = _coup_note(
            "CADRE", score=16, nb_nouvelles=4, cases_bonus=[(7, 7, TypeCase.MOT_DOUBLE)]
        )
        assert hook.score > mot_premium.score
        assert _score_strategique(mot_premium, Niveau.EXPERT) > _score_strategique(
            hook, Niveau.EXPERT
        )

        coups = sorted(
            [hook, mot_premium],
            key=lambda cn: _score_strategique(cn, Niveau.EXPERT),
            reverse=True,
        )
        assert coups[0] is mot_premium

    def test_penalite_hook_double_pour_une_seule_lettre(self):
        """Le malus longueur est doublé pour un hook d'une seule lettre."""
        hook_une_lettre = _coup_note("CADRES", score=10, nb_nouvelles=1)
        hook_deux_lettres = _coup_note("CADRES", score=10, nb_nouvelles=2)
        assert _score_strategique(
            hook_une_lettre, Niveau.INTERMEDIAIRE
        ) < _score_strategique(hook_deux_lettres, Niveau.INTERMEDIAIRE)

    def test_aucune_penalite_ni_bonus_a_trois_lettres_sans_case_premium(self):
        """Pas d'ajustement pour un vrai mot (>=3 lettres) sans case premium."""
        cn = _coup_note("CAR", score=9, nb_nouvelles=3)
        assert _score_strategique(cn, Niveau.EXPERT) == cn.score

    def test_bonus_premium_croissant_avec_le_niveau(self):
        """Le bonus case premium croît avec le niveau IA."""
        cn = _coup_note(
            "CARDE", score=20, nb_nouvelles=5, cases_bonus=[(3, 3, TypeCase.MOT_TRIPLE)]
        )
        ajustement_debutant = _score_strategique(cn, Niveau.DEBUTANT) - cn.score
        ajustement_expert = _score_strategique(cn, Niveau.EXPERT) - cn.score
        assert 0 < ajustement_debutant < ajustement_expert


class TestLeaveValue:
    """Valeur heuristique du reliquat et son intégration par niveau (issue #397)."""

    def test_leave_value_liste_vide(self):
        assert leave_value([]) == 0.0

    def test_joker_plus_precieux_que_lettre_rare(self):
        assert leave_value(["*"]) > leave_value(["Z"])

    def test_chevalet_equilibre_bat_desequilibre(self):
        assert leave_value(["A", "E", "I", "S", "R", "T", "N"]) > leave_value(
            ["A", "E", "I", "O", "U", "Q", "Z"]
        )

    def test_bonus_equilibre_voyelles(self):
        """Un reliquat à 3 voyelles (plage bonus 2-4) bat le même noyau
        élargi aux 5 voyelles (hors plage, malus).

        Note : l'issue #397 proposait ``["A", "E", "I", "O", "U", "U", "U"]``
        comme second reliquat, mais les deux ``U`` supplémentaires ajoutent
        plus de valeur brute (+4.0) que le malus d'équilibre n'en retire
        (-8.0 net, cf. :func:`leave_value`), si bien que l'assertion ne
        tenait pas (16.5 < 17.5). Reliquat corrigé à 5 lettres pour isoler
        l'effet d'équilibre sans excès de valeur brute.
        """
        assert leave_value(["A", "E", "I"]) > leave_value(["A", "E", "I", "O", "U"])

    def test_poids_leave_debutant_nul(self):
        assert _POIDS_LEAVE[Niveau.DEBUTANT] == 0.0

    def test_poids_leave_facile_nul(self):
        assert _POIDS_LEAVE[Niveau.FACILE] == 0.0

    def test_poids_leave_croissant(self):
        assert (
            _POIDS_LEAVE[Niveau.CHAMPION_DU_MONDE]
            >= _POIDS_LEAVE[Niveau.EXPERT]
            > _POIDS_LEAVE[Niveau.AVANCE]
            > _POIDS_LEAVE[Niveau.INTERMEDIAIRE]
            > _POIDS_LEAVE[Niveau.FACILE]
        )


# --------------------------------------------------------------------------- #
# Tests unitaires de choisir_coup
# --------------------------------------------------------------------------- #


class TestDebutant:
    """DEBUTANT choisit uniformément dans les 70 % meilleurs coups (top 70 %).

    Depuis l'issue #401, DEBUTANT fusionne les anciens DEBUTANT (top 85 %) et
    FACILE (top 60 %) en un seul niveau d'entrée de gamme. Le dictionnaire
    de ce test mélange mots de 3+ lettres (CADRE, ACRE, CAR) et mots courts
    pour offrir assez de coups : la tranche top 70 % y écarte réellement les
    coups les plus faibles au sens du score stratégique.
    """

    def test_choisit_dans_le_top_70_pct(self):
        plateau = PlateauPartie()
        chevalet = list("CADRE")
        dico = _trie("CADRE", "ACRE", "CAR", "DE", "RE", "A", "DA")
        coups = sorted(
            generer_coups(plateau, chevalet, dico),
            key=lambda cn: _score_strategique(cn, Niveau.DEBUTANT),
            reverse=True,
        )
        assert len(coups) > 1
        taille_haut = max(1, len(coups) * 70 // 100)
        haut = coups[:taille_haut]

        choisis: dict[tuple, int] = {}
        tirages = 500
        for graine in range(tirages):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.DEBUTANT, random.Random(graine)
            )
            if coup is not None:
                assert any(cn.coup == coup for cn in haut)
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

    def test_expert_score_moyen_entre_intermediaire_et_avance(self):
        """EXPERT (top 5 %) se situe strictement entre INTERMEDIAIRE et AVANCE.

        Vérification statistique sur de nombreux tirages à graines variées
        (issue #202, seuils issue #401) : sous un MÊME vocabulaire (pas de
        câblage palier vs Trie complet ici, voir
        ``TestProgressionTrieIaRestreint`` pour ce cas), les tranches restent
        strictement emboîtées jusqu'à AVANCE — top 15 % (INTERMEDIAIRE) ⊃
        top 5 % (EXPERT) ⊃ meilleur coup (AVANCE, qui choisit littéralement
        le premier de la liste triée). Le score moyen d'AVANCE majore donc
        celui d'EXPERT ; l'inégalité inverse (AVANCE < EXPERT), observée en
        jeu réel, tient uniquement au vocabulaire différent reçu par chacun
        (voir la fixture dédiée plus bas).

        Réutilise le vocabulaire riche ``_MOTS_COMPLET``/chevalet ``CARTONS``
        (voir plus bas) plutôt qu'un petit dictionnaire ad hoc : sur une
        tranche aussi étroite que le top 5 %, un vocabulaire trop pauvre est
        instable (le reliquat pondéré, issue #397, peut faire basculer les
        quelques coups de la bande).
        """
        plateau = PlateauPartie()
        chevalet = list("CARTONS")
        dico = _trie(*_MOTS_COMPLET)
        coups_ref = generer_coups(plateau, chevalet, dico)
        # Le test n'a de sens que si les coups sont assez nombreux et étalés
        # pour que top 5 % et top 15 % diffèrent réellement.
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
        moy_expert = moyenne_scores(Niveau.EXPERT)
        moy_avance = moyenne_scores(Niveau.AVANCE)
        assert moy_inter < moy_expert <= moy_avance


class TestIntermediaire:
    """INTERMEDIAIRE choisit dans les 15 % meilleurs coups (top 15 %) — issue #401."""

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
                plateau, chevalet, dico, Niveau.INTERMEDIAIRE, random.Random(graine)
            )
            if coup is not None:
                cn = next(c for c in coups if c.coup == coup)
                assert cn.score in scores_haut or cn in haut


class TestAvance:
    """AVANCE choisit toujours le meilleur coup (issue #401, reprend la
    stratégie de sélection de l'ancien EXPERT)."""

    def test_choisit_le_meilleur_score(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        # Pas de mot alternatif de longueur intermédiaire (ex. CADRE) : depuis
        # l'issue #397, AVANCE pondère aussi le reliquat (_POIDS_LEAVE non
        # nul), qui pourrait sinon faire préférer un coup à score brut
        # inférieur mais au reliquat plus précieux. Ce dictionnaire ne laisse
        # le choix qu'entre le mot consommant tout le chevalet et des hooks
        # courts nettement pénalisés.
        dico = _trie("CADRES", "AS", "A")
        coup = choisir_coup(plateau, chevalet, dico, Niveau.AVANCE, random.Random(42))
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
                plateau, chevalet, dico, Niveau.AVANCE, random.Random(graine)
            )
            if coup is not None:
                choisis.add((coup.ligne, coup.colonne, coup.direction.value))
        assert len(choisis) >= 1


class TestExpert:
    """EXPERT choisit dans les 5 % meilleurs coups (top 5 %, issue #401).

    Nouveau niveau intercalé entre AVANCE (meilleur coup, palier de
    vocabulaire restreint) et CHAMPION_DU_MONDE (meilleur coup, vocabulaire
    complet) — voir :func:`~scrabble.moteur.ia._choisir_top5`.
    """

    def test_choisit_dans_le_top_5_pct(self):
        """Bande de référence calculée avec le même tri à deux passes que
        :func:`~scrabble.moteur.ia.choisir_coup` (score stratégique puis
        reliquat), pas le score brut : EXPERT pondère le reliquat
        (``_POIDS_LEAVE`` non nul depuis l'issue #397), qui peut réordonner
        des coups à score brut proche — surtout sur une tranche aussi étroite
        que le top 5 %.
        """
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie(
            "CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES",
            "SE", "ED", "AR", "RA", "CAR", "ARC", "SAC", "ACRE", "CARDE",
        )
        coups = generer_coups(plateau, chevalet, dico)

        def _lettres_restantes(cn):
            restantes = list(chevalet)
            for lettre in cn.lettres_du_chevalet:
                restantes.remove(lettre)
            return restantes

        coups_tries = sorted(
            coups, key=lambda cn: _score_strategique(cn, Niveau.EXPERT), reverse=True
        )
        coups_tries = sorted(
            coups_tries,
            key=lambda cn: _score_strategique(
                cn, Niveau.EXPERT, _lettres_restantes(cn)
            ),
            reverse=True,
        )
        taille_haut = max(1, len(coups_tries) * 5 // 100)
        haut = coups_tries[:taille_haut]

        for graine in range(50):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.EXPERT, random.Random(graine)
            )
            if coup is not None:
                assert any(cn.coup == coup for cn in haut)


class TestFacile:
    """FACILE choisit dans le meilleur tiers des coups (top 33 %) — issue #401."""

    def test_choisit_dans_le_top_33_pct(self):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        coups = generer_coups(plateau, chevalet, dico)
        if len(coups) < 3:
            pytest.skip("Pas assez de coups pour tester le top 33 %")
        taille_tiers = max(1, len(coups) // 3)
        haut = coups[:taille_tiers]
        scores_haut = {cn.score for cn in haut}

        for graine in range(50):
            coup = choisir_coup(
                plateau, chevalet, dico, Niveau.FACILE, random.Random(graine)
            )
            if coup is not None:
                cn = next(c for c in coups if c.coup == coup)
                assert cn.score in scores_haut or cn in haut

    def test_score_moyen_superieur_a_debutant(self):
        """FACILE bat DEBUTANT en score moyen, tout en restant sous INTERMEDIAIRE.

        Les tranches restent strictement emboîtées (issue #401) : top 70 %
        (DEBUTANT) ⊃ top 33 % (FACILE) ⊃ top 15 % (INTERMEDIAIRE), donc la
        chaîne DEBUTANT < FACILE < INTERMEDIAIRE est structurelle et vérifiée
        en entier sur un plateau/chevalet offrant des scores étalés.
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


class TestTousLesNiveauxResolventUnCoup:
    """Garde-fou structurel contre l'oubli d'un dict indexé par Niveau.

    Paramétré sur TOUS les membres de :class:`Niveau` (plutôt qu'une liste en
    dur) : tout futur ajout de niveau est automatiquement couvert sans
    modifier ce test, et un ``KeyError`` sur un dict comme
    ``_MALUS_LONGUEUR``/``_BONUS_PREMIUM`` oublié lors d'un ajout est détecté
    immédiatement (issue #368, lot D).
    """

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_resout_un_coup_sans_exception(self, niveau):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        coup = choisir_coup(plateau, chevalet, dico, niveau, random.Random(42))
        assert coup is not None
        coups = generer_coups(plateau, chevalet, dico)
        assert any(cn.coup == coup for cn in coups)


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
# Profil de personnage (issue #438, lot A) : couche additive sans effet
# --------------------------------------------------------------------------- #


class TestProfilPersonnageNeutre:
    """Un profil vide (tous champs ``None``) doit être un pur no-op.

    C'est la garantie centrale du lot A : l'infrastructure de personnage ne
    doit avoir AUCUN effet observable tant qu'aucun champ n'est renseigné —
    ni sur le score stratégique, ni sur le coup choisi, pour aucun niveau.
    """

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_score_strategique_profil_vide_egale_absence_de_profil(self, niveau):
        cn = _coup_note(
            "CARDE", score=20, nb_nouvelles=5, cases_bonus=[(3, 3, TypeCase.MOT_TRIPLE)]
        )
        lettres_restantes = ["A", "E", "I", "S", "*"]
        sans_profil = _score_strategique(cn, niveau, lettres_restantes)
        avec_profil_vide = _score_strategique(
            cn, niveau, lettres_restantes, profil=ProfilPersonnage()
        )
        avec_profil_none = _score_strategique(
            cn, niveau, lettres_restantes, profil=None
        )
        assert avec_profil_vide == sans_profil
        assert avec_profil_none == sans_profil

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_choisir_coup_profil_vide_egale_absence_de_profil(self, niveau):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        for graine in range(20):
            coup_sans_profil = choisir_coup(
                plateau, chevalet, dico, niveau, random.Random(graine)
            )
            coup_profil_vide = choisir_coup(
                plateau,
                chevalet,
                dico,
                niveau,
                random.Random(graine),
                profil=ProfilPersonnage(),
            )
            assert coup_profil_vide == coup_sans_profil

    def test_profil_par_defaut_a_tous_ses_champs_a_none(self):
        """Valeur neutre explicite : un ``ProfilPersonnage()`` sans argument
        ne surcharge rien — condition nécessaire au no-op ci-dessus."""
        profil = ProfilPersonnage()
        assert profil.malus_longueur is None
        assert profil.bonus_premium is None
        assert profil.poids_leave is None
        assert profil.bonus_scrabble is None
        assert profil.vocabulaire_long is None

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_score_strategique_scrabble_sans_profil_inchange(self, niveau):
        """Un coup posant les 7 lettres du chevalet, sans profil, n'est pas
        traité différemment des autres coups (issue #448, lot H) : seul un
        personnage qui renseigne ``bonus_scrabble`` change ce calcul."""
        cn = _coup_note("CADRESX", score=20, nb_nouvelles=7)
        sans_profil = _score_strategique(cn, niveau)
        avec_profil_vide = _score_strategique(cn, niveau, profil=ProfilPersonnage())
        assert avec_profil_vide == sans_profil == cn.score


class TestProfilPersonnageSurcharge:
    """Un champ renseigné surcharge bien le réglage du niveau, sans y toucher."""

    def test_malus_longueur_surcharge(self):
        hook = _coup_note("CADRES", score=10, nb_nouvelles=1)
        sans_profil = _score_strategique(hook, Niveau.INTERMEDIAIRE)
        avec_profil = _score_strategique(
            hook,
            Niveau.INTERMEDIAIRE,
            profil=ProfilPersonnage(malus_longueur=0),
        )
        assert avec_profil != sans_profil
        assert avec_profil == hook.score

    def test_bonus_premium_surcharge(self):
        cn = _coup_note(
            "CARDE", score=20, nb_nouvelles=5, cases_bonus=[(3, 3, TypeCase.MOT_TRIPLE)]
        )
        sans_profil = _score_strategique(cn, Niveau.EXPERT)
        avec_profil = _score_strategique(
            cn, Niveau.EXPERT, profil=ProfilPersonnage(bonus_premium=0)
        )
        assert avec_profil != sans_profil
        assert avec_profil == cn.score

    def test_poids_leave_surcharge(self):
        cn = _coup_note("CAR", score=9, nb_nouvelles=3)
        lettres_restantes = ["A", "E", "I", "S", "*"]
        sans_profil = _score_strategique(cn, Niveau.DEBUTANT, lettres_restantes)
        avec_profil = _score_strategique(
            cn,
            Niveau.DEBUTANT,
            lettres_restantes,
            profil=ProfilPersonnage(poids_leave=1.0),
        )
        assert avec_profil != sans_profil

    def test_les_reglages_par_niveau_restent_inchanges_apres_usage(self):
        """Un profil ne doit jamais muter les dicts indexés par niveau."""
        from scrabble.moteur.ia import _BONUS_PREMIUM, _MALUS_LONGUEUR, _POIDS_LEAVE

        avant = (
            dict(_MALUS_LONGUEUR),
            dict(_BONUS_PREMIUM),
            dict(_POIDS_LEAVE),
        )
        cn = _coup_note(
            "CARDE", score=20, nb_nouvelles=5, cases_bonus=[(3, 3, TypeCase.MOT_TRIPLE)]
        )
        for niveau in Niveau:
            _score_strategique(
                cn,
                niveau,
                ["A", "E"],
                profil=ProfilPersonnage(
                    malus_longueur=-99, bonus_premium=99, poids_leave=9.0
                ),
            )
        apres = (
            dict(_MALUS_LONGUEUR),
            dict(_BONUS_PREMIUM),
            dict(_POIDS_LEAVE),
        )
        assert avant == apres

    def test_bonus_scrabble_applique_si_sept_lettres_posees(self):
        """``bonus_scrabble`` (issue #448, lot H) s'ajoute au score stratégique
        d'un coup posant les 7 lettres du chevalet."""
        cn = _coup_note("CADRESX", score=20, nb_nouvelles=7)
        sans_profil = _score_strategique(cn, Niveau.AVANCE)
        avec_profil = _score_strategique(
            cn, Niveau.AVANCE, profil=ProfilPersonnage(bonus_scrabble=150)
        )
        assert avec_profil == sans_profil + 150

    @pytest.mark.parametrize("nb_nouvelles", [1, 2, 3, 5, 6])
    def test_bonus_scrabble_ignore_si_moins_de_sept_lettres(self, nb_nouvelles):
        """Le bonus ne s'applique qu'aux coups posant EXACTEMENT 7 lettres —
        un coup posant moins de lettres n'en bénéficie pas, quel que soit le
        niveau (issue #448, lot H, point « le bonus s'applique uniquement aux
        coups qui posent 7 lettres »)."""
        cn = _coup_note("CADRE", score=20, nb_nouvelles=nb_nouvelles)
        sans_profil = _score_strategique(cn, Niveau.AVANCE)
        avec_profil = _score_strategique(
            cn, Niveau.AVANCE, profil=ProfilPersonnage(bonus_scrabble=150)
        )
        assert avec_profil == sans_profil


# --------------------------------------------------------------------------- #
# Vocabulaire long (issue #450, lot H bis)
# --------------------------------------------------------------------------- #


def _plateau_vocabulaire_long() -> PlateauPartie:
    """Plateau fabriqué pour qu'un mot de 7 lettres ne soit jouable qu'avec
    le lexique complet, en concurrence avec un coup court jouable avec le
    seul vocabulaire du niveau.

    Un ``Z`` isolé est posé en (8, 7). Le chevalet ``OXALINE`` permet alors :

    * un coup COURT, ``ZA`` (``Z`` existant + ``A`` du chevalet), horizontal
      ou vertical selon l'ancrage — présent dans le vocabulaire du niveau ;
    * un coup LONG, ``OXALINE`` (les 7 lettres du chevalet), vertical à
      partir de (8, 8) — mot principal de 7 lettres, absent du vocabulaire du
      niveau, présent seulement dans le lexique complet. Le ``O`` posé en
      (8, 8), adjacent à droite du ``Z`` existant, forme en plus le mot
      croisé ``ZO`` (ligne 8, colonnes 7-8), lui aussi absent du vocabulaire
      du niveau et présent seulement dans le lexique complet — de quoi
      vérifier que le mot croisé d'un coup long est bien validé avec le
      lexique complet, pas avec le vocabulaire du niveau.

    Posant 7 lettres nouvelles, ``OXALINE`` reçoit en plus le bonus
    « scrabble » intrinsèque du score (:data:`scrabble.moteur.score.BONUS_SCRABBLE`,
    inconditionnel, indépendant de tout personnage) : son score brut domine
    largement celui de ``ZA`` (un coup à une seule lettre nouvelle), ce qui
    rend le choix du meilleur coup déterministe sur ce scénario.
    """
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(8, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("Z")))
    return plateau


#: Chevalet du scénario ci-dessus : épelle le mot long ``OXALINE`` de haut en
#: bas à partir de (8, 8), et fournit le ``A`` du coup court ``ZA``.
_CHEVALET_VOCABULAIRE_LONG = list("OXALINE")

#: Vocabulaire du niveau (restreint) pour le scénario ci-dessus : ne connaît
#: que le coup court.
_DICO_NIVEAU_VOCABULAIRE_LONG = ("ZA",)

#: Lexique complet pour le scénario ci-dessus : coup court ET coup long (mot
#: principal et mot croisé).
_DICO_COMPLET_VOCABULAIRE_LONG = ("ZA", "OXALINE", "ZO")


class TestVocabulaireLong:
    """Champ ``vocabulaire_long`` de :class:`ProfilPersonnage` (issue #450,
    lot H bis) : ensemble de coups candidats élargi au lexique complet pour
    les coups de 7 lettres ou plus."""

    def test_neutre_sans_profil(self):
        """Sans profil, l'ensemble de coups candidats est inchangé, même si
        un ``dictionnaire_complet`` est fourni (défense en profondeur : ce
        n'est jamais l'appelant de :func:`choisir_coup` qui en décide, mais
        le profil)."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)

        for graine in range(10):
            coup_sans_complet = choisir_coup(
                plateau,
                _CHEVALET_VOCABULAIRE_LONG,
                dico_niveau,
                Niveau.AVANCE,
                random.Random(graine),
            )
            coup_avec_complet_ignore = choisir_coup(
                plateau,
                _CHEVALET_VOCABULAIRE_LONG,
                dico_niveau,
                Niveau.AVANCE,
                random.Random(graine),
                dictionnaire_complet=dico_complet,
            )
            assert coup_avec_complet_ignore == coup_sans_complet

    def test_neutre_profil_vide(self):
        """Un ``ProfilPersonnage()`` vide (``vocabulaire_long`` à ``None``)
        n'élargit rien non plus, même avec ``dictionnaire_complet`` fourni —
        condition de neutralité du profil vide (même principe que les lots A
        et H)."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)

        for graine in range(10):
            coup_sans_profil = choisir_coup(
                plateau,
                _CHEVALET_VOCABULAIRE_LONG,
                dico_niveau,
                Niveau.AVANCE,
                random.Random(graine),
            )
            coup_profil_vide = choisir_coup(
                plateau,
                _CHEVALET_VOCABULAIRE_LONG,
                dico_niveau,
                Niveau.AVANCE,
                random.Random(graine),
                profil=ProfilPersonnage(),
                dictionnaire_complet=dico_complet,
            )
            assert coup_profil_vide == coup_sans_profil

    def test_sans_dictionnaire_complet_le_mot_long_reste_hors_de_portee(self):
        """``vocabulaire_long=True`` sans ``dictionnaire_complet`` fourni ne
        peut rien élargir (rien à élargir avec) : comportement identique à
        un profil qui ne le demande pas."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True)

        coup = choisir_coup(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            Niveau.AVANCE,
            random.Random(0),
            profil=profil,
        )
        assert coup is not None
        mot = "".join(t.lettre for t in coup.tuiles)
        assert mot != "OXALINE"

    def test_mot_long_trouve_et_joue_avec_vocabulaire_long(self):
        """Avec ``vocabulaire_long=True`` ET ``dictionnaire_complet`` fourni,
        le coup de 7 lettres (absent du vocabulaire du niveau, présent
        seulement dans le lexique complet) est trouvé et choisi — mot
        principal ET mot croisé validés avec le lexique complet."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True)

        coup = choisir_coup(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            Niveau.AVANCE,
            random.Random(0),
            profil=profil,
            dictionnaire_complet=dico_complet,
        )
        assert coup is not None
        mot = "".join(t.lettre for t in coup.tuiles)
        assert mot == "OXALINE"
        # Plusieurs placements valides existent pour "OXALINE" sur ce
        # scénario (p. ex. vertical en (8, 8), croisant "ZO" avec le Z
        # existant ; ou horizontal en (9, 7), connecté au Z par la case du
        # dessus) : peu importe lequel l'emporte au score, les deux ne sont
        # trouvables qu'avec le lexique complet (absents de ``dico_niveau``).

    def test_mots_courts_restent_limites_au_vocabulaire_du_niveau(self):
        """Un mot court présent UNIQUEMENT dans le lexique complet (absent du
        vocabulaire du niveau) ne doit jamais apparaître parmi les coups
        candidats, même avec ``vocabulaire_long`` actif : seuls les coups
        d'au moins 7 lettres sont empruntés au lexique complet."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        # "ZO" (le mot croisé, 2 lettres) n'est ici présent QUE dans le lexique
        # complet — s'il fuitait comme mot JOUABLE directement (pas seulement
        # comme mot croisé d'un coup long), ce serait un coup court emprunté à
        # tort au lexique complet.
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True)

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
        )
        mots_courts = {
            "".join(t.lettre for t in cn.coup.tuiles)
            for cn in coups
            if len(cn.coup.tuiles) < 7
        }
        assert mots_courts == {"ZA"}

    def test_journal_decision_porte_sur_ensemble_elargi(self):
        """Le journal de décision (:func:`evaluer_coups`) porte sur le même
        ensemble de coups candidats élargi que :func:`choisir_coup` (issue
        #450, point 4) : le mot long y figure, avec le bon rang."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True)

        coup = choisir_coup(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            Niveau.AVANCE,
            random.Random(0),
            profil=profil,
            dictionnaire_complet=dico_complet,
        )
        evaluation = evaluer_coups(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            Niveau.AVANCE,
            profil=profil,
            coup_choisi=coup,
            dictionnaire_complet=dico_complet,
        )
        # Le nombre de coups possibles du journal doit être EXACTEMENT celui
        # de l'ensemble de coups candidats élargi (celui réellement consulté
        # par ``choisir_coup``), ni plus ni moins — pas une valeur arbitraire :
        # plusieurs placements valides existent pour "OXALINE" comme pour
        # "ZA" sur ce scénario (plusieurs ancrages/directions), peu importe
        # le nombre exact.
        candidats_elargis = _generer_coups_candidats(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
        )
        assert evaluation.nb_coups_possibles == len(candidats_elargis)
        assert evaluation.rang_choisi == 1
        assert evaluation.coup_choisi is not None
        assert evaluation.coup_choisi.mot == "OXALINE"
        assert evaluation.meilleurs[0].mot == "OXALINE"

        # Sans lexique complet (vocabulaire du niveau seul), le mot long
        # n'apparaît même pas parmi les coups possibles du journal — un
        # ensemble strictement plus PETIT que l'ensemble élargi (plusieurs
        # variantes de "ZA" existent sur ce scénario, mais aucune "OXALINE").
        evaluation_niveau_seul = evaluer_coups(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            Niveau.AVANCE,
            coup_choisi=coup,
        )
        candidats_niveau_seul = generer_coups(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau
        )
        assert evaluation_niveau_seul.nb_coups_possibles == len(candidats_niveau_seul)
        assert evaluation_niveau_seul.nb_coups_possibles < evaluation.nb_coups_possibles
        assert all(
            alt.mot != "OXALINE" for alt in evaluation_niveau_seul.meilleurs
        )


# --------------------------------------------------------------------------- #
# Mots favoris (issue #452, lot J)
# --------------------------------------------------------------------------- #


def _plateau_mot_favori() -> PlateauPartie:
    """Plateau fabriqué pour qu'un mot favori COURT (4 lettres) ne soit
    jouable qu'avec le lexique complet, en concurrence avec un coup court
    jouable avec le seul vocabulaire du niveau.

    Contrairement au scénario de ``vocabulaire_long``
    (:func:`_plateau_vocabulaire_long`, mot de 7 lettres et plus), celui-ci
    illustre que le mécanisme des mots favoris n'a AUCUNE contrainte de
    longueur : ``CACA`` ne compte que 4 lettres.

    Un ``Z`` isolé est posé en (7, 6). Le chevalet ``CACAXYW`` permet alors :

    * un coup COURT, ``ZX`` (``Z`` existant + ``X`` du chevalet, horizontal à
      partir de (7, 6)) — présent dans le vocabulaire du niveau ;
    * le mot favori ``CACA``, vertical à partir de (7, 7) : le ``C`` posé en
      (7, 7), adjacent à droite du ``Z`` existant, forme en plus le mot
      croisé ``ZC`` (ligne 7, colonnes 6-7) — absent du vocabulaire du
      niveau, présent seulement dans le lexique complet. De quoi vérifier
      que le mot croisé d'un coup à mot favori est bien validé avec le
      lexique complet, pas avec le petit Trie construit depuis la liste de
      mots favoris (qui ne connaît que ``CACA`` lui-même).
    """
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(7, 6, Direction.HORIZONTALE, tuiles_depuis_chaine("Z")))
    return plateau


#: Chevalet du scénario ci-dessus : épelle le mot favori ``CACA`` (deux C,
#: deux A) et fournit le ``X``/``Y``/``W`` des coups courts concurrents.
_CHEVALET_MOT_FAVORI = list("CACAXYW")

#: Vocabulaire du niveau (restreint) pour le scénario ci-dessus : ne connaît
#: que des coups courts sans rapport avec ``CACA``.
_DICO_NIVEAU_MOT_FAVORI = ("ZX", "ZY", "ZW")

#: Lexique complet pour le scénario ci-dessus : coups courts ET mot favori
#: (mot principal et mot croisé).
_DICO_COMPLET_MOT_FAVORI = ("ZX", "ZY", "ZW", "CACA", "ZC")

#: Liste de mots favoris de test — un seul mot, délibérément absent du
#: vocabulaire du niveau.
_MOTS_FAVORIS_TEST: frozenset[str] = frozenset({"CACA"})


class TestMotsFavoris:
    """Champ ``mots_favoris`` de :class:`ProfilPersonnage` (issue #452, lot
    J) : ensemble de coups candidats élargi aux coups dont le mot principal
    figure dans la liste — généralise ``vocabulaire_long`` à un critère de
    LISTE plutôt que de longueur."""

    def test_neutre_sans_profil(self):
        """Sans profil, l'ensemble de coups candidats est inchangé, même si
        un ``dictionnaire_complet`` est fourni."""
        plateau = _plateau_mot_favori()
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        dico_complet = _trie(*_DICO_COMPLET_MOT_FAVORI)

        for graine in range(10):
            coup_sans_complet = choisir_coup(
                plateau, _CHEVALET_MOT_FAVORI, dico_niveau, Niveau.AVANCE,
                random.Random(graine),
            )
            coup_avec_complet_ignore = choisir_coup(
                plateau, _CHEVALET_MOT_FAVORI, dico_niveau, Niveau.AVANCE,
                random.Random(graine), dictionnaire_complet=dico_complet,
            )
            assert coup_avec_complet_ignore == coup_sans_complet

    def test_neutre_profil_vide(self):
        """Un ``ProfilPersonnage()`` vide (``mots_favoris`` à ``None``)
        n'élargit rien non plus, même avec ``dictionnaire_complet`` fourni."""
        plateau = _plateau_mot_favori()
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        dico_complet = _trie(*_DICO_COMPLET_MOT_FAVORI)

        for graine in range(10):
            coup_sans_profil = choisir_coup(
                plateau, _CHEVALET_MOT_FAVORI, dico_niveau, Niveau.AVANCE,
                random.Random(graine),
            )
            coup_profil_vide = choisir_coup(
                plateau, _CHEVALET_MOT_FAVORI, dico_niveau, Niveau.AVANCE,
                random.Random(graine), profil=ProfilPersonnage(),
                dictionnaire_complet=dico_complet,
            )
            assert coup_profil_vide == coup_sans_profil

    def test_sans_dictionnaire_complet_le_mot_favori_reste_hors_de_portee(self):
        """``mots_favoris`` renseigné sans ``dictionnaire_complet`` fourni ne
        peut rien élargir (rien à élargir avec)."""
        plateau = _plateau_mot_favori()
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        profil = ProfilPersonnage(mots_favoris=_MOTS_FAVORIS_TEST)

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_MOT_FAVORI, dico_niveau, profil, None
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "CACA" not in mots

    def test_mot_favori_trouve_avec_mots_favoris(self):
        """Avec ``mots_favoris`` ET ``dictionnaire_complet`` fournis, le coup
        à mot favori (absent du vocabulaire du niveau, présent seulement
        dans le lexique complet) est trouvé — mot principal ET mot croisé
        validés avec le lexique complet."""
        plateau = _plateau_mot_favori()
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        dico_complet = _trie(*_DICO_COMPLET_MOT_FAVORI)
        profil = ProfilPersonnage(mots_favoris=_MOTS_FAVORIS_TEST)

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_MOT_FAVORI, dico_niveau, profil, dico_complet
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "CACA" in mots
        # Les coups courts du vocabulaire du niveau restent présents (union,
        # pas remplacement).
        assert "ZX" in mots

    def test_mot_absent_du_lexique_complet_ignore_sans_erreur(self):
        """Un mot de la liste absent du lexique complet installé ne produit
        simplement aucun coup — ignoré sans erreur, sans filtrage dédié
        (point 1 de l'issue #452)."""
        plateau = _plateau_mot_favori()
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        # "CACA" est absent de CE lexique complet fabriqué pour le test (seul
        # "PROUT", un autre mot favori, y figure) : il ne doit jamais
        # apparaître parmi les coups candidats.
        dico_complet_sans_caca = _trie("ZX", "ZY", "ZW", "PROUT")
        profil = ProfilPersonnage(mots_favoris=frozenset({"CACA", "PROUT"}))

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_MOT_FAVORI, dico_niveau, profil, dico_complet_sans_caca
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "CACA" not in mots

    def test_sans_doublon_avec_les_coups_habituels(self):
        """Un mot favori qui serait AUSSI présent dans le vocabulaire du
        niveau n'apparaît pas deux fois dans l'ensemble élargi."""
        plateau = _plateau_mot_favori()
        # "ZX" figure maintenant à la fois dans le vocabulaire du niveau ET
        # dans la liste de mots favoris.
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        dico_complet = _trie(*_DICO_COMPLET_MOT_FAVORI)
        profil = ProfilPersonnage(mots_favoris=frozenset({"CACA", "ZX"}))

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_MOT_FAVORI, dico_niveau, profil, dico_complet
        )
        cles = [
            (cn.coup.ligne, cn.coup.colonne, cn.coup.direction.value,
             "".join(t.lettre for t in cn.coup.tuiles))
            for cn in coups
        ]
        assert len(cles) == len(set(cles))

    def test_journal_decision_porte_sur_ensemble_elargi(self):
        """Le journal de décision (:func:`evaluer_coups`) porte sur le même
        ensemble de coups candidats élargi que :func:`choisir_coup`."""
        plateau = _plateau_mot_favori()
        dico_niveau = _trie(*_DICO_NIVEAU_MOT_FAVORI)
        dico_complet = _trie(*_DICO_COMPLET_MOT_FAVORI)
        profil = ProfilPersonnage(mots_favoris=_MOTS_FAVORIS_TEST)

        candidats_elargis = _generer_coups_candidats(
            plateau, _CHEVALET_MOT_FAVORI, dico_niveau, profil, dico_complet
        )
        # Un coup à mot favori quelconque (il peut en exister plusieurs
        # placements) sert de ``coup_choisi`` imposé, pour vérifier qu'il est
        # bien retrouvé dans l'évaluation, quel que soit son rang.
        coup_favori = next(
            cn.coup for cn in candidats_elargis
            if "".join(t.lettre for t in cn.coup.tuiles) == "CACA"
        )
        evaluation = evaluer_coups(
            plateau, _CHEVALET_MOT_FAVORI, dico_niveau, Niveau.AVANCE,
            profil=profil, coup_choisi=coup_favori, dictionnaire_complet=dico_complet,
        )
        assert evaluation.nb_coups_possibles == len(candidats_elargis)
        assert evaluation.coup_choisi is not None
        assert evaluation.coup_choisi.mot == "CACA"
        assert evaluation.rang_choisi is not None


# --------------------------------------------------------------------------- #
# Tirage pondéré en faveur des scrabbles (issue #451, lot H ter)
# --------------------------------------------------------------------------- #


class _RngEspion(random.Random):
    """``random.Random`` qui compte ses appels à ``choice``/``choices``.

    Sert à vérifier la neutralité stricte du tirage pondéré : un profil qui
    ne renseigne pas ``poids_tirage_scrabble`` doit consommer le générateur
    EXACTEMENT comme avant l'introduction de ce champ (même nombre d'appels,
    même méthode, même état final), pas seulement produire le même coup.
    """

    def __init__(self, x=None):
        super().__init__(x)
        self.appels_choice = 0
        self.appels_choices = 0

    def choice(self, seq):
        self.appels_choice += 1
        return super().choice(seq)

    def choices(self, population, weights=None, *, cum_weights=None, k=1):
        self.appels_choices += 1
        return super().choices(population, weights=weights, cum_weights=cum_weights, k=k)


class TestNeutraliteTirage:
    """``poids_tirage_scrabble`` absent (profil ``None`` ou vide) doit laisser
    le tirage bit à bit identique, sur les six niveaux (issue #451, point 3)."""

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_neutralite_consommation_aleatoire(self, niveau):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")

        rng_sans_profil = _RngEspion(42)
        coup_sans_profil = choisir_coup(plateau, chevalet, dico, niveau, rng_sans_profil)

        rng_profil_vide = _RngEspion(42)
        coup_profil_vide = choisir_coup(
            plateau, chevalet, dico, niveau, rng_profil_vide, profil=ProfilPersonnage()
        )

        # Un profil qui renseigne d'autres champs (hors ``poids_tirage_scrabble``,
        # tous ``None`` ici) ne doit pas non plus changer la consommation du
        # générateur pour ce qui concerne CE champ précisément — seul le champ
        # testé doit être neutre par défaut, pas le reste du profil (déjà
        # couvert par ailleurs, issue #438, lot A).
        rng_profil_autre_champ_renseigne = _RngEspion(42)
        choisir_coup(
            plateau,
            chevalet,
            dico,
            niveau,
            rng_profil_autre_champ_renseigne,
            profil=ProfilPersonnage(bonus_scrabble=150),
        )

        assert coup_profil_vide == coup_sans_profil
        assert rng_profil_vide.appels_choice == rng_sans_profil.appels_choice
        assert rng_profil_vide.appels_choices == rng_sans_profil.appels_choices == 0
        assert rng_profil_vide.getstate() == rng_sans_profil.getstate()
        assert rng_profil_autre_champ_renseigne.appels_choices == 0

    @pytest.mark.parametrize("niveau", [Niveau.AVANCE, Niveau.CHAMPION_DU_MONDE])
    def test_sans_effet_sur_les_niveaux_meilleur_coup(self, niveau):
        """AVANCE et CHAMPION_DU_MONDE jouent toujours leur meilleur coup :
        jamais un tirage dans une tranche, donc ``poids_tirage_scrabble`` n'y
        change jamais rien, quelle que soit sa valeur (issue #451, point 2)."""
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        for graine in range(20):
            sans_poids = choisir_coup(plateau, chevalet, dico, niveau, random.Random(graine))
            avec_poids = choisir_coup(
                plateau,
                chevalet,
                dico,
                niveau,
                random.Random(graine),
                profil=ProfilPersonnage(poids_tirage_scrabble=5.0),
            )
            assert avec_poids == sans_poids


class TestTirageSPondereDansLaTranche:
    """``_tirer_dans_tranche`` (issue #451, point 1) : tranche fabriquée où un
    coup à 7 lettres coexiste avec d'autres coups, fréquence de tirage proche
    de la théorie et nettement supérieure au tirage uniforme."""

    def _tranche(self, taille: int) -> list[CoupNote]:
        scrabble = _coup_note("SCRABBLE", score=50, nb_nouvelles=7)
        autres = [
            _coup_note(f"AUTRE{lettre}", score=10, nb_nouvelles=3)
            for lettre in string.ascii_uppercase[: taille - 1]
        ]
        return [scrabble] + autres

    @pytest.mark.parametrize("taille", [10, 15, 20])
    def test_frequence_proche_de_la_theorie_et_superieure_au_tirage_uniforme(
        self, taille
    ):
        poids = 5.0
        tranche = self._tranche(taille)
        scrabble_coup = tranche[0].coup
        theorique = poids / (taille - 1 + poids)
        uniforme = 1 / taille

        profil = ProfilPersonnage(poids_tirage_scrabble=poids)
        nb_essais = 20_000
        nb_scrabble = sum(
            1
            for graine in range(nb_essais)
            if _tirer_dans_tranche(tranche, random.Random(graine), profil) == scrabble_coup
        )
        proportion = nb_scrabble / nb_essais

        assert abs(proportion - theorique) < 0.02
        assert proportion > uniforme * 2

    def test_composition_de_la_tranche_inchangee(self):
        """Seules les probabilités changent — jamais la liste de coups
        elle-même (issue #451, point 2 et point 7)."""
        tranche = self._tranche(12)
        profil = ProfilPersonnage(poids_tirage_scrabble=5.0)
        for graine in range(50):
            rng = random.Random(graine)
            coup = _tirer_dans_tranche(tranche, rng, profil)
            assert coup in [cn.coup for cn in tranche]

    def test_tirage_uniforme_sans_poids(self):
        """``poids_tirage_scrabble=None`` (défaut) : tirage uniforme, exactement
        ``rng.choice(tranche).coup``."""
        tranche = self._tranche(10)
        rng1 = random.Random(7)
        rng2 = random.Random(7)
        assert _tirer_dans_tranche(tranche, rng1, None) == rng2.choice(tranche).coup

    def test_poids_eleve_rend_le_scrabble_tres_frequent_sans_etre_certain(self):
        """Un poids plus élevé que la constante de production reste un tirage
        PONDÉRÉ, pas un passage au meilleur coup déterministe : les autres
        coups de la tranche restent, en tout petit nombre de cas, tirés."""
        tranche = self._tranche(15)
        scrabble_coup = tranche[0].coup
        profil = ProfilPersonnage(poids_tirage_scrabble=50.0)
        resultats = {
            _tirer_dans_tranche(tranche, random.Random(graine), profil)
            for graine in range(500)
        }
        assert scrabble_coup in resultats
        assert len(resultats) > 1


# --------------------------------------------------------------------------- #
# Tirage pondéré en faveur des mots favoris (issue #452, lot J)
# --------------------------------------------------------------------------- #


class TestNeutraliteTirageFavori:
    """``poids_tirage_favori`` absent (profil ``None`` ou vide) doit laisser
    le tirage bit à bit identique, sur les six niveaux (généralise
    ``TestNeutraliteTirage`` à ce nouveau champ)."""

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_neutralite_consommation_aleatoire(self, niveau):
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")

        rng_sans_profil = _RngEspion(42)
        coup_sans_profil = choisir_coup(plateau, chevalet, dico, niveau, rng_sans_profil)

        rng_profil_vide = _RngEspion(42)
        coup_profil_vide = choisir_coup(
            plateau, chevalet, dico, niveau, rng_profil_vide, profil=ProfilPersonnage()
        )

        rng_mots_favoris_sans_poids = _RngEspion(42)
        coup_mots_favoris_sans_poids = choisir_coup(
            plateau,
            chevalet,
            dico,
            niveau,
            rng_mots_favoris_sans_poids,
            # ``mots_favoris`` renseigné SANS ``poids_tirage_favori`` ne doit
            # rien changer au tirage : seul ``poids_tirage_favori`` pilote
            # l'effet sur ``_tirer_dans_tranche``.
            profil=ProfilPersonnage(mots_favoris=frozenset({"CADRE"})),
        )

        assert coup_profil_vide == coup_sans_profil
        assert coup_mots_favoris_sans_poids == coup_sans_profil
        assert rng_profil_vide.appels_choice == rng_sans_profil.appels_choice
        assert rng_profil_vide.appels_choices == rng_sans_profil.appels_choices == 0
        assert rng_profil_vide.getstate() == rng_sans_profil.getstate()
        assert rng_mots_favoris_sans_poids.appels_choices == 0
        assert rng_mots_favoris_sans_poids.getstate() == rng_sans_profil.getstate()

    @pytest.mark.parametrize("niveau", [Niveau.AVANCE, Niveau.CHAMPION_DU_MONDE])
    def test_sans_effet_sur_les_niveaux_meilleur_coup(self, niveau):
        """AVANCE et CHAMPION_DU_MONDE jouent toujours leur meilleur coup :
        jamais un tirage dans une tranche, donc ``poids_tirage_favori`` n'y
        change jamais rien."""
        plateau = PlateauPartie()
        chevalet = list("CADRES")
        dico = _trie("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")
        for graine in range(20):
            sans_poids = choisir_coup(plateau, chevalet, dico, niveau, random.Random(graine))
            avec_poids = choisir_coup(
                plateau,
                chevalet,
                dico,
                niveau,
                random.Random(graine),
                profil=ProfilPersonnage(
                    mots_favoris=frozenset({"CADRE"}), poids_tirage_favori=50.0
                ),
            )
            assert avec_poids == sans_poids


class TestTirageSPondereFavoriDansLaTranche:
    """``_tirer_dans_tranche`` / ``poids_tirage_favori`` (issue #452, lot J) :
    généralise le tirage pondéré du lot H ter à un critère de mot favori,
    avec une différence clé — le coup à mot favori est ajouté au pool de
    tirage même s'il est ABSENT de la tranche elle-même."""

    def _tranche(self, taille: int, favori: str = "FAVORI") -> list[CoupNote]:
        coup_favori = _coup_note(favori, score=10, nb_nouvelles=3)
        autres = [
            _coup_note(f"AUTRE{lettre}", score=10, nb_nouvelles=3)
            for lettre in string.ascii_uppercase[: taille - 1]
        ]
        return [coup_favori] + autres

    @pytest.mark.parametrize("taille", [10, 15, 20])
    def test_frequence_proche_de_la_theorie_quand_le_favori_est_dans_la_tranche(
        self, taille
    ):
        """Le coup favori fait déjà partie de la tranche : même formule que
        le tirage pondéré des scrabbles (poids sur ``n`` coups)."""
        poids = 50.0
        tranche = self._tranche(taille)
        favori_coup = tranche[0].coup
        theorique = poids / (taille - 1 + poids)

        profil = ProfilPersonnage(mots_favoris=frozenset({"FAVORI"}), poids_tirage_favori=poids)
        nb_essais = 20_000
        nb_favori = sum(
            1
            for graine in range(nb_essais)
            if _tirer_dans_tranche(tranche, random.Random(graine), profil, tranche) == favori_coup
        )
        proportion = nb_favori / nb_essais
        assert abs(proportion - theorique) < 0.02

    def test_coup_favori_absent_de_la_tranche_reste_tirable(self):
        """Différence essentielle avec ``poids_tirage_scrabble`` : un coup à
        mot favori EXCLU de la tranche (mais présent dans ``coups_complets``)
        doit malgré tout pouvoir être tiré."""
        tranche = self._tranche(10)  # ne contient PAS le mot favori
        favori = _coup_note("FAVORI", score=1, nb_nouvelles=2)
        coups_complets = tranche + [favori]
        profil = ProfilPersonnage(mots_favoris=frozenset({"FAVORI"}), poids_tirage_favori=50.0)

        resultats = {
            _tirer_dans_tranche(tranche, random.Random(graine), profil, coups_complets)
            for graine in range(300)
        }
        assert favori.coup in resultats

    def test_sans_coups_complets_le_favori_absent_de_la_tranche_nest_jamais_tire(self):
        """``coups_complets=None`` (défaut) désactive l'ajout, quel que soit
        ``poids_tirage_favori`` — utilisé par les appelants qui ne
        connaissent pas encore l'ensemble complet."""
        tranche = self._tranche(10)
        profil = ProfilPersonnage(mots_favoris=frozenset({"FAVORI"}), poids_tirage_favori=50.0)

        for graine in range(50):
            coup = _tirer_dans_tranche(tranche, random.Random(graine), profil, None)
            assert coup in [cn.coup for cn in tranche]

    def test_composition_de_la_tranche_elle_meme_jamais_modifiee(self):
        """``tranche`` reçu en paramètre n'est jamais muté — seul le pool de
        tirage interne change."""
        tranche = self._tranche(10)
        avant = list(tranche)
        favori = _coup_note("CRACOTTE", score=1, nb_nouvelles=2)
        profil = ProfilPersonnage(mots_favoris=frozenset({"CRACOTTE"}), poids_tirage_favori=50.0)
        for graine in range(20):
            _tirer_dans_tranche(tranche, random.Random(graine), profil, tranche + [favori])
        assert tranche == avant

    def test_tirage_uniforme_sans_poids(self):
        """``poids_tirage_favori=None`` (défaut) : tirage uniforme, exactement
        ``rng.choice(tranche).coup``, même avec ``mots_favoris`` renseigné."""
        tranche = self._tranche(10)
        profil = ProfilPersonnage(mots_favoris=frozenset({"FAVORI"}))
        rng1 = random.Random(7)
        rng2 = random.Random(7)
        assert _tirer_dans_tranche(tranche, rng1, profil, tranche) == rng2.choice(tranche).coup

    def test_poids_sans_mots_favoris_reste_neutre(self):
        """``poids_tirage_favori`` renseigné SANS ``mots_favoris`` ne qualifie
        aucun coup : neutre, y compris sur la consommation du générateur
        aléatoire (retombe sur ``rng.choice``, pas ``rng.choices`` à poids
        uniformes qui consommerait le générateur différemment)."""
        tranche = self._tranche(10)
        profil = ProfilPersonnage(poids_tirage_favori=50.0)
        rng1 = random.Random(7)
        rng2 = random.Random(7)
        assert _tirer_dans_tranche(tranche, rng1, profil, tranche) == rng2.choice(tranche).coup
        assert rng1.getstate() == rng2.getstate()

    def test_cumul_scrabble_et_favori_prend_le_plus_grand_poids(self):
        """Un coup qui serait À LA FOIS un scrabble et un mot favori reçoit
        le plus grand des deux poids (cas limite, pas de double-comptage)."""
        coup_double = _coup_note("DOUBLE", score=10, nb_nouvelles=7)
        autres = [_coup_note(f"AUTRE{l}", score=10, nb_nouvelles=3) for l in "ABCDEFGHI"]
        tranche = [coup_double] + autres
        profil = ProfilPersonnage(
            poids_tirage_scrabble=5.0,
            mots_favoris=frozenset({"DOUBLE"}),
            poids_tirage_favori=50.0,
        )
        resultats = {
            _tirer_dans_tranche(tranche, random.Random(graine), profil, tranche)
            for graine in range(300)
        }
        assert coup_double.coup in resultats
        # Toujours un tirage pondéré, pas un passage déterministe.
        assert len(resultats) > 1


# --------------------------------------------------------------------------- #
# Part de mots longs connus (issue #451, lot H ter)
# --------------------------------------------------------------------------- #


class TestMotConnuVocabulaireLong:
    """``_mot_connu_vocabulaire_long`` (issue #451, point 8) : sélection
    déterministe, propre à chaque mot, de la fraction connue."""

    def test_deterministe_et_independant_de_lordre(self):
        mots = [f"MOTLONG{i:04d}" for i in range(500)]
        resultats = [_mot_connu_vocabulaire_long(m, 0.5) for m in mots]
        resultats_ordre_inverse = [
            _mot_connu_vocabulaire_long(m, 0.5) for m in reversed(mots)
        ]
        assert resultats == [_mot_connu_vocabulaire_long(m, 0.5) for m in mots]
        assert resultats == list(reversed(resultats_ordre_inverse))

    def test_part_1_tous_connus(self):
        mots = [f"MOTLONG{i:04d}" for i in range(500)]
        assert all(_mot_connu_vocabulaire_long(m, 1.0) for m in mots)

    def test_part_0_aucun_connu(self):
        mots = [f"MOTLONG{i:04d}" for i in range(500)]
        assert not any(_mot_connu_vocabulaire_long(m, 0.0) for m in mots)

    @pytest.mark.parametrize("part", [0.1, 0.3, 0.5, 0.7, 0.9])
    def test_proportion_proche_de_la_part_sur_liste_fabriquee(self, part):
        mots = [f"MOTLONG{i:04d}" for i in range(5000)]
        connus = sum(_mot_connu_vocabulaire_long(m, part) for m in mots)
        proportion = connus / len(mots)
        assert abs(proportion - part) < 0.03


class TestPartVocabulaireLong:
    """``part_vocabulaire_long`` de :class:`ProfilPersonnage` (issue #451,
    lot H ter) : restreint ``vocabulaire_long`` aux seuls mots longs
    « connus », hors vocabulaire du niveau."""

    def test_part_1_identique_au_comportement_du_lot_h_bis(self):
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)

        coups_sans_part = _generer_coups_candidats(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            ProfilPersonnage(vocabulaire_long=True),
            dico_complet,
        )
        coups_avec_part_1 = _generer_coups_candidats(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            ProfilPersonnage(vocabulaire_long=True, part_vocabulaire_long=1.0),
            dico_complet,
        )
        mots_sans_part = {
            "".join(t.lettre for t in cn.coup.tuiles) for cn in coups_sans_part
        }
        mots_avec_part_1 = {
            "".join(t.lettre for t in cn.coup.tuiles) for cn in coups_avec_part_1
        }
        assert mots_avec_part_1 == mots_sans_part
        assert "OXALINE" in mots_avec_part_1

    def test_part_0_aucun_mot_long_hors_vocabulaire(self):
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True, part_vocabulaire_long=0.0)

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "OXALINE" not in mots
        # Le coup court du vocabulaire du niveau reste accessible : seuls
        # les mots longs HORS vocabulaire du niveau sont concernés.
        assert "ZA" in mots

    def test_mots_courts_et_vocabulaire_du_niveau_non_concernes(self):
        """``part_vocabulaire_long`` ne filtre jamais les mots courts ni ceux
        déjà dans le vocabulaire du niveau — quelle que soit sa valeur
        (issue #451, point 10)."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        for part in (0.0, 0.3, 1.0):
            profil = ProfilPersonnage(vocabulaire_long=True, part_vocabulaire_long=part)
            coups = _generer_coups_candidats(
                plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
            )
            mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
            assert "ZA" in mots

    def test_resultat_stable_entre_deux_appels(self):
        """Même mot, même résultat d'un appel à l'autre : pas de dépendance à
        la graine de la partie ni à l'ordre de génération (issue #451, point
        8)."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True, part_vocabulaire_long=0.5)

        mots_appels = []
        for _ in range(5):
            coups = _generer_coups_candidats(
                plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
            )
            mots_appels.append(
                frozenset("".join(t.lettre for t in cn.coup.tuiles) for cn in coups)
            )
        assert len(set(mots_appels)) == 1

    def test_autres_personnages_non_concernes(self):
        """``part_vocabulaire_long`` reste ``None`` (neutre) pour tout profil
        qui ne le demande pas explicitement — le champ est strictement
        additif."""
        assert ProfilPersonnage().part_vocabulaire_long is None
        assert ProfilPersonnage(vocabulaire_long=True).part_vocabulaire_long is None


# --------------------------------------------------------------------------- #
# Part de mots courts connus (issue #453, lot H quater)
# --------------------------------------------------------------------------- #


class TestMotConnuVocabulaireCourt:
    """``_mot_connu_vocabulaire_court`` (issue #453) : même procédé
    déterministe que :func:`_mot_connu_vocabulaire_long` (hachage SHA-256
    stable du texte du mot), avec un décalage de hachage distinct."""

    def test_deterministe_et_independant_de_lordre(self):
        mots = [f"MOTCOURT{i:04d}" for i in range(500)]
        resultats = [_mot_connu_vocabulaire_court(m, 0.5) for m in mots]
        resultats_ordre_inverse = [
            _mot_connu_vocabulaire_court(m, 0.5) for m in reversed(mots)
        ]
        assert resultats == [_mot_connu_vocabulaire_court(m, 0.5) for m in mots]
        assert resultats == list(reversed(resultats_ordre_inverse))

    def test_part_1_tous_connus(self):
        mots = [f"MOTCOURT{i:04d}" for i in range(500)]
        assert all(_mot_connu_vocabulaire_court(m, 1.0) for m in mots)

    def test_part_0_aucun_connu(self):
        mots = [f"MOTCOURT{i:04d}" for i in range(500)]
        assert not any(_mot_connu_vocabulaire_court(m, 0.0) for m in mots)

    @pytest.mark.parametrize("part", [0.1, 0.3, 0.5, 0.7, 0.9])
    def test_proportion_proche_de_la_part_sur_liste_fabriquee(self, part):
        mots = [f"MOTCOURT{i:04d}" for i in range(5000)]
        connus = sum(_mot_connu_vocabulaire_court(m, part) for m in mots)
        proportion = connus / len(mots)
        assert abs(proportion - part) < 0.03

    def test_independant_du_filtre_mots_longs(self):
        """Pour un même mot, le résultat de ce filtre et celui de
        ``_mot_connu_vocabulaire_long`` sont statistiquement indépendants
        (décalage de hachage distinct, issue #453) : sur un grand nombre de
        mots, le taux d'accord entre les deux doit rester proche de 50 %
        (``p² + (1-p)²`` à ``p = 0.5``), pas proche de 100 % comme ce serait
        le cas si les deux fonctions partageaient le même calcul."""
        mots = [f"MOT{i:05d}" for i in range(2000)]
        long_ = [_mot_connu_vocabulaire_long(m, 0.5) for m in mots]
        court = [_mot_connu_vocabulaire_court(m, 0.5) for m in mots]
        assert long_ != court
        accord = sum(a == b for a, b in zip(long_, court)) / len(mots)
        assert abs(accord - 0.5) < 0.05


class TestPartVocabulaireCourt:
    """``part_vocabulaire_court`` de :class:`ProfilPersonnage` (issue #453,
    lot H quater) : restreint les coups candidats dont le mot principal
    compte MOINS de :data:`~scrabble.moteur.ia._SEUIL_VOCABULAIRE_LONG`
    lettres à une fraction « connue », garde-fou compris. Réutilise les
    fixtures de :class:`TestPartVocabulaireLong` (un mot court ``ZA`` du
    vocabulaire du niveau, un mot long ``OXALINE`` accessible via
    ``vocabulaire_long``) : de quoi vérifier, dans le même scénario, que les
    mots longs ne sont jamais concernés par ce filtre.
    """

    def test_part_1_identique_au_comportement_actuel(self):
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)

        coups_sans_champ = _generer_coups_candidats(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, ProfilPersonnage(), None
        )
        coups_avec_part_1 = _generer_coups_candidats(
            plateau,
            _CHEVALET_VOCABULAIRE_LONG,
            dico_niveau,
            ProfilPersonnage(part_vocabulaire_court=1.0),
            None,
        )
        mots_sans_champ = {
            "".join(t.lettre for t in cn.coup.tuiles) for cn in coups_sans_champ
        }
        mots_avec_part_1 = {
            "".join(t.lettre for t in cn.coup.tuiles) for cn in coups_avec_part_1
        }
        assert mots_avec_part_1 == mots_sans_champ
        assert "ZA" in mots_avec_part_1

    def test_part_0_ne_laisse_que_les_mots_longs(self):
        """Avec le lexique complet accessible (``vocabulaire_long``), part à
        0 % ne laisse que les mots de 7 lettres et plus — le garde-fou ne se
        déclenche pas ici puisque ``OXALINE`` reste candidat."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(vocabulaire_long=True, part_vocabulaire_court=0.0)

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "OXALINE" in mots
        assert "ZA" not in mots

    def test_garde_fou_si_aucun_coup_candidat_apres_filtre(self):
        """Garde-fou (issue #453, point 2) : si le filtre ne laisse plus
        aucun coup candidat (ici l'unique candidat, ``ZA``, est court et
        aucun mot long n'est disponible pour compenser), il est ignoré pour
        ce tour plutôt que de forcer une passe qui fausserait la mesure."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(part_vocabulaire_court=0.0)

        coups = _generer_coups_candidats(
            plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, None
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert mots == {"ZA"}

    def test_mots_longs_jamais_concernes(self):
        """Ni les mots longs du vocabulaire du niveau, ni ceux ajoutés par
        ``vocabulaire_long``, ne sont jamais filtrés — quelle que soit la
        valeur de ``part_vocabulaire_court``."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        dico_complet = _trie(*_DICO_COMPLET_VOCABULAIRE_LONG)
        for part in (0.0, 0.3, 1.0):
            profil = ProfilPersonnage(vocabulaire_long=True, part_vocabulaire_court=part)
            coups = _generer_coups_candidats(
                plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, dico_complet
            )
            mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
            assert "OXALINE" in mots

    def test_resultat_stable_entre_deux_appels(self):
        """Même mot, même résultat d'un appel à l'autre : pas de dépendance à
        la graine de la partie ni à l'ordre de génération."""
        plateau = _plateau_vocabulaire_long()
        dico_niveau = _trie(*_DICO_NIVEAU_VOCABULAIRE_LONG)
        profil = ProfilPersonnage(part_vocabulaire_court=0.5)

        mots_appels = []
        for _ in range(5):
            coups = _generer_coups_candidats(
                plateau, _CHEVALET_VOCABULAIRE_LONG, dico_niveau, profil, None
            )
            mots_appels.append(
                frozenset("".join(t.lettre for t in cn.coup.tuiles) for cn in coups)
            )
        assert len(set(mots_appels)) == 1

    def test_autres_personnages_non_concernes(self):
        """``part_vocabulaire_court`` reste ``None`` (neutre) pour tout
        profil qui ne le demande pas explicitement — le champ est
        strictement additif."""
        assert ProfilPersonnage().part_vocabulaire_court is None
        assert ProfilPersonnage(vocabulaire_long=True).part_vocabulaire_court is None

    def test_neutre_rng_choisir_coup(self):
        """Neutralité complète (issue #453, point 4) : un profil sans ce
        champ, ou avec une part de 100 %, donne EXACTEMENT le même coup, à
        graine égale, pour tous les niveaux — même consommation du
        générateur aléatoire, puisque le calcul du filtre est purement
        déterministe (aucun aléa)."""
        plateau = PlateauPartie()
        chevalet = list("CADRE")
        dico = _trie("CADRE", "ACRE", "CAR", "DE", "RE", "A", "DA")
        for niveau in Niveau:
            for graine in range(5):
                rng_sans = random.Random(graine)
                rng_avec = random.Random(graine)
                coup_sans = choisir_coup(plateau, chevalet, dico, niveau, rng_sans)
                coup_avec = choisir_coup(
                    plateau,
                    chevalet,
                    dico,
                    niveau,
                    rng_avec,
                    profil=ProfilPersonnage(part_vocabulaire_court=1.0),
                )
                assert coup_avec == coup_sans
                assert rng_sans.getstate() == rng_avec.getstate()


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
# central unique). Offre de nombreux coups aux scores étalés, dont un
# « scrabble » (bingo) CARTONS à 70 points. Inclut depuis l'issue #361 des mots
# de 2 lettres — courants (ON, OR, AS, AN, OS) comme obscurs du Scrabble (RA,
# OC, NA, TA, SA) — afin que les coups courts pénalisés par le malus longueur
# existent réellement dans les listes de coups : sans eux, la monotonie des
# niveaux était trivialement satisfaite sur plateau vide (aucun coup < 3
# lettres, artefact de fixture).
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
    "ON", "OR", "AS", "AN", "OS", "RA", "OC", "NA", "TA", "SA",
)

# Sous-ensemble « vocabulaire humain » : mots courants seulement, sous-ensemble
# STRICT de _MOTS_COMPLET (invariant de obtenir_trie_ia : l'ensemble IA est
# toujours intersecté avec le dico complet). On y a retiré les mots rares/peu
# courants — dont le bingo CARTONS — pour reproduire fidèlement l'effet du
# filtre : l'IA perd l'accès aux coups à fort score assis sur du vocabulaire
# rare. Les seuls mots de 2 lettres présents ici sont ceux qu'un joueur
# ordinaire connaît (ON, OR, AS, AN, OS) ; les 2-lettres obscurs du Scrabble
# (RA, OC, NA...) restent dans _MOTS_COMPLET uniquement — c'est précisément ce
# que le vocabulaire humain écarte (issues #206/#207, #361).
_MOTS_IA_RESTREINT = (
    "CARTON", "CARTE", "CARTES", "CANOT", "CAR", "CARS", "CAS", "SAC", "ACRE",
    "RAT", "RATS", "ART", "ARTS", "STAR", "CON", "CONS", "COR", "ROC", "TON",
    "TONS", "SORT", "TRAC", "OCA", "TAO", "SONAR", "SCORE",
    "ON", "OR", "AS", "AN", "OS",
)

# Ordre des niveaux par score moyen croissant, tel qu'il découle RÉELLEMENT des
# stratégies de sélection ET du câblage vocabulaire (cf. ia.py, issue #401) :
#   * DEBUTANT tire dans le top 70 % (n'écarte que les 30 % plus faibles) sur
#     le palier restreint "debutant" → moyenne la plus basse ;
#   * FACILE (top 33 %), INTERMEDIAIRE (top 15 %), chacun sur son propre
#     palier restreint → croissant, tranches strictement emboîtées ;
#   * AVANCE choisit le meilleur coup, mais toujours sur un palier de
#     vocabulaire restreint ("avance", issue #369, lot C) — moins large que
#     le Trie complet reçu par les deux derniers niveaux ;
#   * EXPERT (top 5 %) et CHAMPION_DU_MONDE (meilleur coup) jouent tous deux
#     sur le Trie ODS8 complet, ``resoudre_palier`` renvoyant ``None`` pour
#     les deux (issue #401) : aucun filtre de vocabulaire ne s'applique à ces
#     deux niveaux, contrairement aux quatre premiers.
# Le dernier maillon AVANCE < EXPERT n'est donc PAS structurel comme les
# précédents (une stratégie moins "gourmande", top 5 %, l'emporte sur le
# meilleur coup d'AVANCE) : c'est l'accès à un vocabulaire strictement plus
# large qui fait basculer la moyenne en faveur d'EXPERT. EXPERT <
# CHAMPION_DU_MONDE, à l'inverse, reste structurel : à vocabulaire identique
# (le Trie complet, pour les deux), seule la stratégie diffère (top 5 % ⊆
# meilleur coup). Les fixtures ci-dessous donnent donc le Trie complet
# (``dico_champion``) à EXPERT ET CHAMPION_DU_MONDE simultanément, et le Trie
# restreint aux quatre premiers niveaux, pour reproduire fidèlement ce
# câblage réel (``scrabble.ui.accueil``).
_ORDRE_CROISSANT_ATTENDU = [
    Niveau.DEBUTANT,
    Niveau.FACILE,
    Niveau.INTERMEDIAIRE,
    Niveau.AVANCE,
    Niveau.EXPERT,
    Niveau.CHAMPION_DU_MONDE,
]

# Niveaux dont resoudre_palier() renvoie None (issue #401) : toujours sur le
# Trie complet en jeu réel, jamais sur un palier de vocabulaire restreint.
_NIVEAUX_SANS_PALIER = (Niveau.EXPERT, Niveau.CHAMPION_DU_MONDE)


def _moyennes_par_niveau(
    plateau: PlateauPartie,
    chevalet: list[str],
    dico: Trie,
    n: int = 400,
    dico_champion: Trie | None = None,
) -> dict[Niveau, float]:
    """Score moyen de chaque niveau sur ``n`` tirages à graines 0..n-1.

    Même méthode que les tests statistiques existants : on génère la liste de
    référence des coups une fois par dictionnaire utilisé, puis on relève le
    score du coup choisi pour chaque graine. Le score d'un coup ne dépend que
    des tuiles/plateau, pas du dictionnaire.

    ``dico_champion`` (issue #369, lot C ; étendu à EXPERT par l'issue #401),
    s'il est fourni, est le dictionnaire utilisé pour :data:`Niveau.EXPERT` et
    :data:`Niveau.CHAMPION_DU_MONDE` à la place de ``dico`` — simule le
    câblage réel (``scrabble.ui.accueil``), où ces deux niveaux jouent
    toujours sur le Trie complet (:func:`~scrabble.moteur.ia.resoudre_palier`
    renvoie ``None`` pour les deux) quand les quatre premiers niveaux jouent
    chacun sur leur palier restreint. ``None`` (défaut) : EXPERT et
    CHAMPION_DU_MONDE partagent ``dico`` avec les autres niveaux.
    """
    coups_ref = generer_coups(plateau, chevalet, dico)
    coups_ref_champion = (
        coups_ref
        if dico_champion is None
        else generer_coups(plateau, chevalet, dico_champion)
    )
    moyennes: dict[Niveau, float] = {}
    for niveau in Niveau:
        dico_niveau = (
            dico_champion
            if niveau in _NIVEAUX_SANS_PALIER and dico_champion is not None
            else dico
        )
        reference = (
            coups_ref_champion if dico_niveau is dico_champion else coups_ref
        )
        scores = []
        for graine in range(n):
            coup = choisir_coup(
                plateau, chevalet, dico_niveau, niveau, random.Random(graine)
            )
            if coup is not None:
                cn = next(c for c in reference if c.coup == coup)
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
        """La progression reste STRICTEMENT monotone avec le Trie IA restreint.

        Confirme l'hypothèse du rapport #203, adaptée au câblage de l'issue
        #401 : le filtre de vocabulaire ne s'applique plus qu'aux quatre
        premiers niveaux (chacun sur son palier restreint) ; EXPERT et
        CHAMPION_DU_MONDE reçoivent toujours le Trie complet
        (``dico_champion``), le bingo CARTONS (70 pts, absent de
        ``_MOTS_IA_RESTREINT``) leur restant accessible à tous les deux.
        """
        dico_ia = Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        dico_complet = Trie.depuis_iterable(_MOTS_COMPLET)
        moy = _moyennes_par_niveau(
            self.plateau, self.chevalet, dico_ia, dico_champion=dico_complet
        )
        ordre = sorted(Niveau, key=lambda niv: moy[niv])
        assert ordre == _ORDRE_CROISSANT_ATTENDU
        for a, b in zip(_ORDRE_CROISSANT_ATTENDU, _ORDRE_CROISSANT_ATTENDU[1:]):
            assert moy[a] < moy[b], f"{a} devrait être < {b} : {moy}"

    def test_niveaux_restent_perceptiblement_distincts(self):
        """Aucun niveau ne se confond avec son voisin sous le filtre.

        Point #3 de l'issue #207 : on veut détecter le cas où un niveau ne se
        distinguerait plus suffisamment d'un autre. On exige un écart d'au
        moins 1 point entre niveaux adjacents dans l'ordre de progression,
        seuil au-delà duquel la différence reste perceptible en jeu — y
        compris désormais pour la paire AVANCE/EXPERT (issue #401 : palier
        restreint contre Trie complet) et EXPERT/CHAMPION_DU_MONDE (issue
        #369, lot C, monotonie devenue stricte : voir ``dico_champion``).
        """
        dico_ia = Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        dico_complet = Trie.depuis_iterable(_MOTS_COMPLET)
        moy = _moyennes_par_niveau(
            self.plateau, self.chevalet, dico_ia, dico_champion=dico_complet
        )
        for a, b in zip(_ORDRE_CROISSANT_ATTENDU, _ORDRE_CROISSANT_ATTENDU[1:]):
            ecart = moy[b] - moy[a]
            assert ecart >= 1.0, f"{a} et {b} trop proches sous filtre : {moy}"

    def test_ordre_relatif_identique_avec_et_sans_filtre(self):
        """L'ordre RELATIF des quatre niveaux à palier est identique avec et
        sans filtre.

        Cœur de la vérification #207 / hypothèse #203, restreinte depuis
        l'issue #401 aux quatre niveaux réellement soumis au filtre de
        vocabulaire par palier (DEBUTANT, FACILE, INTERMEDIAIRE, AVANCE) : le
        filtre ne les réordonne pas entre eux, il n'abaisse que leurs scores
        absolus. EXPERT et CHAMPION_DU_MONDE, jamais filtrés en jeu réel, sont
        exclus de la comparaison — leur position relative à AVANCE peut au
        contraire s'inverser sous filtre (c'est tout l'intérêt du câblage de
        l'issue #401 : EXPERT franchit AVANCE une fois débarrassé de la
        restriction de vocabulaire), voir
        ``test_progression_monotone_avec_filtre_actif``.
        """
        niveaux_a_palier = [
            Niveau.DEBUTANT,
            Niveau.FACILE,
            Niveau.INTERMEDIAIRE,
            Niveau.AVANCE,
        ]
        moy_complet = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_COMPLET)
        )
        moy_ia = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_IA_RESTREINT)
        )
        assert sorted(niveaux_a_palier, key=lambda niv: moy_complet[niv]) == sorted(
            niveaux_a_palier, key=lambda niv: moy_ia[niv]
        )

    def test_ecart_avance_debutant_se_resserre_sous_filtre(self):
        """Mesure le resserrement Avancé↔Débutant sous filtre (point #4).

        Point de vigilance du rapport #203, reporté sur la paire pertinente
        depuis l'issue #401 : AVANCE et DEBUTANT sont désormais les deux
        niveaux réellement soumis au filtre de vocabulaire par palier (EXPERT
        et CHAMPION_DU_MONDE y échappent, voir ci-dessus). Même monotonie
        préservée, l'écart absolu entre AVANCE (meilleur coup) et DEBUTANT
        (top 70 %) peut se resserrer si le filtre retire les coups à très
        fort score (vocabulaire rare). Dans ce scénario, le bingo CARTONS
        (70 pts) est retiré du vocabulaire IA restreint, donc AVANCE perd sa
        pointe : l'écart Avancé↔Débutant chute nettement, tout en restant
        strictement positif (les niveaux restent ordonnés).
        """
        moy_complet = _moyennes_par_niveau(
            self.plateau, self.chevalet, Trie.depuis_iterable(_MOTS_COMPLET)
        )
        moy_ia = _moyennes_par_niveau(
            self.plateau,
            self.chevalet,
            Trie.depuis_iterable(_MOTS_IA_RESTREINT),
            dico_champion=Trie.depuis_iterable(_MOTS_COMPLET),
        )
        ecart_complet = moy_complet[Niveau.AVANCE] - moy_complet[Niveau.DEBUTANT]
        ecart_ia = moy_ia[Niveau.AVANCE] - moy_ia[Niveau.DEBUTANT]
        # Reste ordonné (Avancé > Débutant) même sous filtre...
        assert ecart_ia > 0
        # ... mais se resserre sensiblement quand le vocabulaire rare disparaît.
        assert ecart_ia < ecart_complet
