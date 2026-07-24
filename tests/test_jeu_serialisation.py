"""Tests de la sérialisation de l'état de jeu (issue #255).

Couvre :
- la sérialisation du plateau (types de cases, tuiles posées, jokers) ;
- la sérialisation des infos publiques des joueurs (sans identité des lettres) ;
- la sérialisation d'un chevalet (lettres, valeurs, jokers) ;
- l'état public global (aucune lettre de chevalet exposée) ;
- le comptage des humains et l'index de référence ;
- le calcul des positions et des avatars des joueurs ;
- l'exposition du tour humain courant (index_panneau) ;
- la sérialisation du détail de score et de l'historique ;
- la classification et l'évaluation du score total.
"""

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import Tuile
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.persistance import demarrer_suivi, reprendre_partie
from scrabble.regles.lettres import JOKER
from scrabble.regles.plateau import CENTRE, TAILLE, TypeCase
from scrabble.ui.jeu import (
    AVATARS,
    calculer_avatars,
    calculer_positions,
    classer_score_total,
    compter_humains,
    etat_public,
    evaluer_score_total,
    index_humain_reference,
    index_panneau_interactif,
    jouer_placements,
    serialiser_case,
    serialiser_chevalet,
    serialiser_detail_score,
    serialiser_historique,
    serialiser_joueur_public,
    serialiser_plateau,
)
from tests._aides_test_jeu import _DicoFactice, _partie_simple


class TestSerialiserCase:
    """Tests de la sérialisation d'une case du plateau."""

    def test_case_normale_vide(self):
        partie = _partie_simple()
        case = serialiser_case(partie.plateau, 4, 0)
        assert case["type"] == "normale"
        assert case["lettre"] is None
        assert case["joker"] is False
        # Case vide : valeur nulle (aucune tuile à afficher, issue #56).
        assert case["valeur"] == 0

    def test_case_centrale(self):
        partie = _partie_simple()
        case = serialiser_case(partie.plateau, CENTRE[0], CENTRE[1])
        assert case["type"] == "centre"

    def test_case_mot_triple(self):
        partie = _partie_simple()
        assert serialiser_case(partie.plateau, 0, 0)["type"] == "MT"

    def test_case_lettre_double(self):
        partie = _partie_simple()
        assert serialiser_case(partie.plateau, 0, 3)["type"] == "LD"

    def test_case_avec_tuile(self):
        partie = _partie_simple()
        partie.plateau.poser_tuile(7, 7, Tuile("A"))
        case = serialiser_case(partie.plateau, 7, 7)
        assert case["lettre"] == "A"
        assert case["joker"] is False
        # Le type de bonus reste connu même sous une tuile.
        assert case["type"] == "centre"
        # Valeur en points de la lettre posée (issue #56) : A vaut 1.
        assert case["valeur"] == 1

    def test_case_avec_joker(self):
        partie = _partie_simple()
        partie.plateau.poser_tuile(7, 8, Tuile("B", joker=True))
        case = serialiser_case(partie.plateau, 7, 8)
        assert case["lettre"] == "B"
        assert case["joker"] is True
        # Un joker posé vaut toujours 0 point, même s'il affiche une lettre
        # normalement valorisée (issue #56, cohérent avec le chevalet).
        assert case["valeur"] == 0


class TestSerialiserPlateau:
    """Tests de la sérialisation de la grille complète."""

    def test_dimensions(self):
        partie = _partie_simple()
        grille = serialiser_plateau(partie.plateau)
        assert len(grille) == TAILLE
        assert all(len(ligne) == TAILLE for ligne in grille)

    def test_chaque_case_a_un_type(self):
        partie = _partie_simple()
        grille = serialiser_plateau(partie.plateau)
        types_valides = {"normale", "MT", "MD", "LT", "LD", "centre"}
        for ligne in grille:
            for case in ligne:
                assert case["type"] in types_valides


class TestSerialiserJoueurPublic:
    """Tests des infos publiques d'un joueur (aucune lettre révélée)."""

    def test_infos_de_base(self):
        joueur = Joueur(nom="Alice", humain=True, chevalet=["A", "B", "C"], score=12)
        pub = serialiser_joueur_public(joueur, index=0, courant=True)
        assert pub["index"] == 0
        assert pub["nom"] == "Alice"
        assert pub["humain"] is True
        assert pub["niveau"] is None
        assert pub["score"] == 12
        assert pub["nb_lettres"] == 3
        assert pub["courant"] is True

    def test_niveau_ordinateur(self):
        joueur = Joueur(nom="Robot", humain=False, niveau=Niveau.EXPERT)
        pub = serialiser_joueur_public(joueur, index=1, courant=False)
        assert pub["niveau"] == "EXPERT"

    def test_aucune_lettre_exposee(self):
        """Les infos publiques ne contiennent jamais l'identité des lettres."""
        joueur = Joueur(nom="Alice", humain=True, chevalet=["A", "Z", "E"])
        pub = serialiser_joueur_public(joueur, index=0, courant=False)
        assert "chevalet" not in pub
        assert "lettres" not in pub
        # Seul le nombre est exposé.
        assert pub["nb_lettres"] == 3


class TestSerialiserChevalet:
    """Tests de la sérialisation d'un chevalet (contenu détaillé)."""

    def test_lettres_et_valeurs(self):
        joueur = Joueur(nom="Alice", chevalet=["A", "K"])
        chevalet = serialiser_chevalet(joueur)
        assert chevalet[0] == {"lettre": "A", "valeur": 1, "joker": False}
        assert chevalet[1] == {"lettre": "K", "valeur": 10, "joker": False}

    def test_joker(self):
        joueur = Joueur(nom="Alice", chevalet=[JOKER])
        chevalet = serialiser_chevalet(joueur)
        assert chevalet[0]["lettre"] == JOKER
        assert chevalet[0]["valeur"] == 0
        assert chevalet[0]["joker"] is True

    def test_chevalet_vide(self):
        joueur = Joueur(nom="Alice", chevalet=[])
        assert serialiser_chevalet(joueur) == []


class TestEtatPublic:
    """Tests de l'état public global (règle : aucune lettre de chevalet)."""

    def test_structure(self):
        partie = _partie_simple()
        etat = etat_public(partie, id_partie=7)
        assert etat["id_partie"] == 7
        assert etat["taille"] == TAILLE
        assert len(etat["plateau"]) == TAILLE
        assert len(etat["joueurs"]) == 2
        assert etat["index_courant"] == 0
        assert etat["terminee"] is False
        assert etat["gagnants"] == []
        # L'évaluation du score n'existe qu'en fin de partie (issue #137).
        assert etat["evaluation_score"] is None

    def test_evaluation_score_en_fin_de_partie(self):
        """En fin de partie, ``etat_public`` porte l'évaluation du total (issue #137)."""
        partie = _partie_simple()
        partie.joueurs[0].score = 320
        partie.joueurs[1].score = 300
        partie.terminee = True
        etat = etat_public(partie, id_partie=1)
        assert etat["evaluation_score"] == {
            "total": 620,
            "nb_joueurs": 2,
            "moyenne": 310,
            "qualificatif": "Très bon score",
        }

    def test_jetons_sac_coherent(self):
        """Le sac reflète les 102 jetons moins ceux distribués (7 par joueur)."""
        partie = _partie_simple()
        etat = etat_public(partie, id_partie=1)
        assert etat["jetons_sac"] == partie.sac.jetons_restants()
        assert etat["jetons_sac"] == 102 - 2 * 7

    def test_aucune_lettre_de_chevalet_dans_etat(self):
        """RÈGLE : l'état public n'expose l'identité d'aucune lettre de chevalet."""
        partie = _partie_simple()
        etat = etat_public(partie, id_partie=1)
        for joueur_pub in etat["joueurs"]:
            assert "chevalet" not in joueur_pub
            assert "lettres" not in joueur_pub
            assert "nb_lettres" in joueur_pub

    def test_joueur_courant_marque(self):
        partie = _partie_simple()
        partie.index_courant = 1
        etat = etat_public(partie, id_partie=1)
        assert etat["joueurs"][0]["courant"] is False
        assert etat["joueurs"][1]["courant"] is True


class TestCompterHumains:
    """Comptage des joueurs humains (bouton « voir mes lettres » conditionnel)."""

    def _partie(self, *humains: bool) -> Partie:
        joueurs = [
            Joueur(
                nom=f"J{i}",
                humain=h,
                niveau=None if h else Niveau.FACILE,
            )
            for i, h in enumerate(humains)
        ]
        return Partie(joueurs, _DicoFactice(), graine=7)

    def test_un_seul_humain(self):
        # Un humain + un ordinateur : un seul humain à qui rien n'est à cacher.
        assert compter_humains(self._partie(True, False)) == 1

    def test_deux_humains(self):
        assert compter_humains(self._partie(True, True)) == 2

    def test_aucun_humain(self):
        assert compter_humains(self._partie(False, False)) == 0

    def test_expose_dans_etat_public(self):
        partie = self._partie(True, True, False)
        etat = etat_public(partie, None)
        assert etat["nb_humains"] == 2


def _joueurs_humains(*humains: bool) -> list[Joueur]:
    """Liste de joueurs dont chaque booléen fixe le drapeau ``humain``."""
    return [
        Joueur(nom=f"J{i}", humain=h, niveau=None if h else Niveau.FACILE)
        for i, h in enumerate(humains)
    ]


class TestIndexHumainReference:
    """``index_humain_reference`` : premier joueur humain de la liste (issue #99)."""

    def test_un_seul_humain_en_premier(self):
        assert index_humain_reference(_joueurs_humains(True, False, False)) == 0

    def test_humain_en_deuxieme_position(self):
        # Le premier humain est en index 1 : c'est lui la référence.
        assert index_humain_reference(_joueurs_humains(False, True, False)) == 1

    def test_premier_humain_parmi_plusieurs(self):
        # Avec plusieurs humains, seul le premier compte.
        assert index_humain_reference(_joueurs_humains(False, True, True)) == 1

    def test_aucun_humain_renvoie_zero(self):
        # Cas théorique sans humain : l'index 0 tient le rôle de référence.
        assert index_humain_reference(_joueurs_humains(False, False)) == 0

    def test_liste_vide_renvoie_zero(self):
        assert index_humain_reference([]) == 0

    def test_coherent_avec_calculer_positions(self):
        # Une seule source de vérité : l'index de référence est bien celui qui
        # reçoit la position « bas » dans calculer_positions.
        joueurs = _joueurs_humains(False, False, True, False)
        positions = calculer_positions(joueurs)
        assert positions[index_humain_reference(joueurs)] == "bas"


class TestCalculerPositions:
    """Ordre d'empilement vertical des fiches joueurs (issues #33, #122, #195).

    Depuis la refonte en 4 zones (#186), les slots ``haut``/``gauche``/
    ``droite``/``bas`` ne désignent plus un côté du plateau mais un RANG vertical
    dans la marge gauche (de haut en bas : haut → gauche → droite → bas). La
    lecture de haut en bas doit suivre l'ordre de jeu, l'humain de référence
    toujours en bas (issue #195).
    """

    def _joueurs(self, *humains: bool) -> list[Joueur]:
        return _joueurs_humains(*humains)

    def test_un_seul_joueur_aucune_autre_fiche(self):
        # 1 seul joueur au total : uniquement la fiche du bas.
        positions = calculer_positions(self._joueurs(True))
        assert positions == ["bas"]

    def test_un_adversaire_en_haut(self):
        # 1 adversaire → il est placé en haut (au-dessus de l'humain, en bas).
        positions = calculer_positions(self._joueurs(True, False))
        assert positions == ["bas", "haut"]

    def test_deux_adversaires_ordre_de_jeu_haut_puis_gauche(self):
        # Ordre de jeu (issue #195), du haut vers le bas : le 1er adversaire va
        # en haut, le 2e juste en dessous (gauche), l'humain en bas.
        positions = calculer_positions(self._joueurs(True, False, False))
        assert positions == ["bas", "haut", "gauche"]

    def test_trois_adversaires_haut_gauche_droite(self):
        # 4 joueurs, de haut en bas : 1er → haut, 2e → gauche, 3e → droite,
        # humain de référence en bas.
        positions = calculer_positions(self._joueurs(True, False, False, False))
        assert positions == ["bas", "haut", "gauche", "droite"]

    def test_humain_reference_toujours_en_bas(self):
        # Le joueur humain de référence est le premier humain de la liste : il
        # est en bas quel que soit l'ordre des joueurs dans la partie, et les
        # autres s'empilent dans l'ordre de jeu à partir de son rang réel.
        positions = calculer_positions(self._joueurs(False, False, True, False))
        assert positions == ["gauche", "droite", "bas", "haut"]

    def test_plusieurs_humains_autres_dans_ordre_de_jeu(self):
        # Avec plusieurs humains, seul le premier va en bas ; les autres joueurs
        # (humains et ordinateurs) s'empilent dans l'ordre de jeu.
        positions = calculer_positions(self._joueurs(True, True, False))
        assert positions == ["bas", "haut", "gauche"]

    def test_aucun_humain_premier_joueur_en_bas(self):
        # Cas théorique sans humain : le premier joueur tient le rôle de référence.
        positions = calculer_positions(self._joueurs(False, False))
        assert positions == ["bas", "haut"]

    def test_liste_vide(self):
        assert calculer_positions([]) == []

    def test_humain_non_premier_a_jouer_ordre_de_jeu(self):
        # Le tirage d'ordre a désigné un ordinateur en premier : l'humain de
        # référence (index 1) reste en bas, et les autres s'empilent dans l'ordre
        # de jeu à partir de son rang réel — pas de l'index 0.
        # Ordre de jeu : [ordi, HUMAIN, ordi]. Réf. en bas ; le joueur suivant
        # dans l'ordre (index 2) va en haut, le suivant (index 0) en gauche.
        positions = calculer_positions(self._joueurs(False, True, False))
        assert positions == ["gauche", "bas", "haut"]

    def test_humain_troisieme_a_jouer_quatre_joueurs(self):
        # 4 joueurs, l'humain de référence ne joue qu'en 3e position (index 2) :
        # bas en index 2, puis haut/gauche/droite (du haut vers le bas) pour les
        # joueurs d'index 3, 0 et 1 dans l'ordre de jeu.
        positions = calculer_positions(self._joueurs(False, False, True, False))
        assert positions == ["gauche", "droite", "bas", "haut"]
        # Cohérence : la référence est bien en bas quel que soit son rang.
        assert positions[index_humain_reference(self._joueurs(False, False, True, False))] == "bas"

    def test_humain_dernier_a_jouer_deux_joueurs(self):
        # 2 joueurs : face-à-face haut/bas même quand l'humain joue en second.
        positions = calculer_positions(self._joueurs(False, True))
        assert positions == ["haut", "bas"]

    def test_ensembles_de_slots_par_effectif_preserves(self):
        # Les *ensembles* de slots utilisés par effectif sont inchangés par la
        # refonte #195 (seul l'ordre d'attribution change) : 1→bas, 2→bas/haut,
        # 3→bas/gauche/haut, 4→les quatre slots.
        assert set(calculer_positions(self._joueurs(True))) == {"bas"}
        assert set(calculer_positions(self._joueurs(True, False))) == {"bas", "haut"}
        assert set(calculer_positions(self._joueurs(True, False, False))) == {
            "bas",
            "gauche",
            "haut",
        }
        assert set(calculer_positions(self._joueurs(True, False, False, False))) == {
            "bas",
            "gauche",
            "haut",
            "droite",
        }

    def test_reprise_partie_persistee_positions_ordre_de_jeu(self, tmp_path):
        # Une partie persistée fige l'ordre de jeu (établi par le tirage) dans
        # l'ordre de sa liste de joueurs. La reprendre recalcule des positions
        # conformes à la règle d'ordre de jeu (#195), sans toucher à l'ordre de
        # jeu, aux scores ni au plateau.
        trie = Trie.depuis_iterable(["AS"])
        # Ordre de jeu figé : un ordinateur joue en premier, l'humain de
        # référence n'est que deuxième (cas typique d'un tirage d'ordre).
        joueurs = [
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, trie, graine=7)
        chemin = tmp_path / "parties.db"
        id_partie = demarrer_suivi(partie, chemin)

        reprise = reprendre_partie(id_partie, trie, chemin)

        # L'ordre de jeu (donc la liste des joueurs) est intact.
        assert [j.nom for j in reprise.joueurs] == ["Robot", "Alice", "Bob"]
        # Scores et plateau intacts (aucune action rejouée).
        assert [j.score for j in reprise.joueurs] == [0, 0, 0]
        assert reprise.plateau.est_vide()
        # Positions recalculées selon l'ordre de jeu à partir du rang réel de
        # l'humain de référence (Alice, index 1) : bas en index 1, puis le
        # joueur suivant dans l'ordre (Bob, index 2) en haut, puis Robot
        # (index 0) en gauche.
        positions = calculer_positions(reprise.joueurs)
        assert positions == ["gauche", "bas", "haut"]
        assert positions[index_humain_reference(reprise.joueurs)] == "bas"

    def test_position_exposee_dans_etat_public(self):
        partie = Partie(self._joueurs(True, False, False), _DicoFactice(), graine=3)
        etat = etat_public(partie, None)
        assert [j["position"] for j in etat["joueurs"]] == ["bas", "haut", "gauche"]


class TestCalculerAvatars:
    """Attribution déterministe d'un avatar par joueur (issue #34)."""

    def _joueurs(self, *noms: str) -> list[Joueur]:
        return [Joueur(nom=nom, humain=True) for nom in noms]

    def test_liste_vide(self):
        assert calculer_avatars([]) == []

    def test_identifiants_connus(self):
        # Chaque avatar attribué appartient à la bibliothèque.
        avatars = calculer_avatars(self._joueurs("Alice", "Bob", "Chloé", "David"))
        assert len(avatars) == 4
        assert all(a in AVATARS for a in avatars)

    def test_deterministe_appels_repetes(self):
        # Même partie -> mêmes avatars à chaque appel (pas de ré-tirage).
        joueurs = self._joueurs("Alice", "Bob", "Chloé")
        premier = calculer_avatars(joueurs)
        for _ in range(5):
            assert calculer_avatars(joueurs) == premier

    def test_aucun_doublon_jusqu_a_quatre_joueurs(self):
        for noms in [
            ("Alice",),
            ("Alice", "Bob"),
            ("Alice", "Bob", "Chloé"),
            ("Alice", "Bob", "Chloé", "David"),
        ]:
            avatars = calculer_avatars(self._joueurs(*noms))
            assert len(set(avatars)) == len(avatars), noms

    def test_homonymes_avatars_distincts(self):
        # Deux joueurs de même nom : l'index départage, pas de doublon.
        avatars = calculer_avatars(self._joueurs("Alice", "Alice"))
        assert avatars[0] != avatars[1]

    def test_humain_et_ordinateur_traites_pareil(self):
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        avatars = calculer_avatars(joueurs)
        assert len(set(avatars)) == 2
        assert all(a in AVATARS for a in avatars)

    def test_plus_de_joueurs_que_d_avatars_ne_plante_pas(self):
        # Cas théorique impossible en jeu (max 4 joueurs) : on tolère les
        # doublons au lieu de planter. On construit N = nb avatars + 3 joueurs.
        joueurs = self._joueurs(*[f"J{i}" for i in range(len(AVATARS) + 3)])
        avatars = calculer_avatars(joueurs)
        assert len(avatars) == len(joueurs)
        assert all(a in AVATARS for a in avatars)
        # Les avatars distincts saturent la bibliothèque avant les doublons.
        assert len(set(avatars)) == len(AVATARS)

    def test_avatar_expose_dans_etat_public(self, monkeypatch):
        # On isole le test du config.json réel de la machine : etat_public lit
        # avatar_principal de la config (issue #143) et un poste de dév peut y
        # avoir un avatar choisi, ce qui ferait diverger l'attribution du calcul
        # direct par défaut ci-dessous (avatar_principal absent = "").
        import scrabble.ui.jeu as jeu

        monkeypatch.setattr(jeu, "charger_config", lambda: {})
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=5)
        etat = etat_public(partie, None)
        avatars = [j["avatar"] for j in etat["joueurs"]]
        assert all(a in AVATARS for a in avatars)
        assert len(set(avatars)) == 2
        # Cohérent avec le calcul direct (avatar_principal absent = "").
        assert avatars == calculer_avatars(joueurs)

    # ---- Choix d'avatar du joueur humain (issue #143) ----

    def _mixte(self, *specs: tuple[str, bool]) -> list[Joueur]:
        """Construit des joueurs (nom, humain) — humain=True/False."""
        return [
            Joueur(
                nom=nom,
                humain=humain,
                niveau=None if humain else Niveau.FACILE,
            )
            for nom, humain in specs
        ]

    def test_avatar_principal_attribue_a_l_humain(self):
        # L'avatar choisi va au joueur humain de référence (le premier humain).
        joueurs = self._mixte(
            ("Robot1", False), ("Alice", True), ("Robot2", False)
        )
        avatars = calculer_avatars(joueurs, "avatar-07")
        assert avatars[1] == "avatar-07"  # Alice, l'humaine de référence

    def test_avatar_principal_exclu_des_ordinateurs(self):
        # Aucun ordinateur ne peut recevoir l'avatar choisi par l'humaine, quel
        # que soit l'avatar imposé (on les essaie tous).
        for avatar in AVATARS:
            joueurs = self._mixte(
                ("Alice", True),
                ("Robot1", False),
                ("Robot2", False),
                ("Robot3", False),
            )
            avatars = calculer_avatars(joueurs, avatar)
            assert avatars[0] == avatar
            # Les ordinateurs (index 1..3) n'ont jamais l'avatar réservé.
            assert avatar not in avatars[1:]
            assert len(set(avatars)) == len(avatars)  # toujours sans doublon

    def test_avatar_principal_inconnu_ignore(self):
        # Une valeur inconnue laisse l'attribution historique inchangée.
        joueurs = self._mixte(("Alice", True), ("Robot", False))
        assert calculer_avatars(joueurs, "avatar-999") == calculer_avatars(joueurs)
        assert calculer_avatars(joueurs, "") == calculer_avatars(joueurs)

    def test_avatar_principal_sans_humain_ignore(self):
        # Partie sans humain (cas théorique) : l'avatar n'est réservé à personne.
        joueurs = self._mixte(("Robot1", False), ("Robot2", False))
        avatars = calculer_avatars(joueurs, "avatar-03")
        assert avatars == calculer_avatars(joueurs)

    def test_avatar_principal_deterministe(self):
        joueurs = self._mixte(("Alice", True), ("Robot", False))
        premier = calculer_avatars(joueurs, "avatar-05")
        for _ in range(5):
            assert calculer_avatars(joueurs, "avatar-05") == premier

    def test_avatar_principal_applique_dans_etat_public(self, monkeypatch):
        # etat_public lit avatar_principal de la config et le passe au calcul.
        import scrabble.ui.jeu as jeu

        monkeypatch.setattr(
            jeu, "charger_config", lambda: {"avatar_principal": "avatar-09"}
        )
        joueurs = self._mixte(("Alice", True), ("Robot", False))
        partie = Partie(joueurs, _DicoFactice(), graine=5)
        etat = etat_public(partie, None)
        avatars = [j["avatar"] for j in etat["joueurs"]]
        assert avatars[0] == "avatar-09"  # Alice
        assert "avatar-09" not in avatars[1:]  # pas l'ordinateur


class TestIndexPanneauInteractif:
    """Le panneau interactif suit le joueur humain courant, jamais un ordinateur."""

    def test_tour_humain_unique_renvoie_son_index(self):
        # Un seul humain (index 0) : quand c'est son tour, le panneau est à lui.
        partie = _partie_simple()
        partie.index_courant = 0
        assert partie.joueur_courant().humain is True
        assert index_panneau_interactif(partie) == 0

    def test_tour_ordinateur_renvoie_none(self):
        # Tour de l'ordinateur (index 1) : aucun chevalet exposé (None).
        partie = _partie_simple()
        partie.index_courant = 1
        assert partie.joueur_courant().humain is False
        assert index_panneau_interactif(partie) is None

    def test_multi_humains_suit_l_humain_courant(self):
        # Deux humains + un ordinateur : le panneau suit l'humain à qui c'est le
        # tour, pas un humain fixe unique.
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=7)
        partie.index_courant = 1  # tour de Bob (2ᵉ humain)
        assert index_panneau_interactif(partie) == 1
        partie.index_courant = 0  # tour d'Alice
        assert index_panneau_interactif(partie) == 0

    def test_multi_humains_ordinateur_courant_renvoie_none(self):
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=7)
        partie.index_courant = 2  # tour de l'ordinateur
        assert index_panneau_interactif(partie) is None

    def test_ne_designe_jamais_un_ordinateur(self):
        # Garantie structurelle : pour tout index courant, la valeur renvoyée est
        # None ou l'index d'un joueur humain — jamais celui d'un ordinateur.
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot1", humain=False, niveau=Niveau.FACILE),
            Joueur(nom="Bob", humain=True),
            Joueur(nom="Robot2", humain=False, niveau=Niveau.EXPERT),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=11)
        for index in range(len(joueurs)):
            partie.index_courant = index
            resultat = index_panneau_interactif(partie)
            if resultat is not None:
                assert partie.joueurs[resultat].humain is True


class TestEtatPublicExpositionTour:
    """L'état public expose correctement tour_humain / index_panneau (issue #35)."""

    def test_tour_humain_expose_index_panneau(self):
        partie = _partie_simple()
        partie.index_courant = 0
        etat = etat_public(partie, None)
        assert etat["tour_humain"] is True
        assert etat["index_panneau"] == 0

    def test_tour_ordinateur_index_panneau_none(self):
        partie = _partie_simple()
        partie.index_courant = 1
        etat = etat_public(partie, None)
        assert etat["tour_humain"] is False
        assert etat["index_panneau"] is None
        # L'état reste public : aucune lettre exposée, même pendant un tour IA.
        for joueur_pub in etat["joueurs"]:
            assert "lettres" not in joueur_pub
            assert "chevalet" not in joueur_pub


class TestSerialiserDetailScore:
    """Sérialisation du détail de score exposé à la modale (issue #35)."""

    def test_structure_mots_scores_et_total(self):
        detail = DetailScore(
            mots=[
                DetailMot(
                    texte="MAISON",
                    score=14,
                    cases_bonus=[(7, 7, TypeCase.CENTRE)],
                ),
                DetailMot(texte="OS", score=2, cases_bonus=[]),
            ],
            bonus_scrabble=50,
            total=66,
        )
        serialise = serialiser_detail_score(detail)

        # Chaque mot est présent avec son texte et son score individuel.
        assert [m["texte"] for m in serialise["mots"]] == ["MAISON", "OS"]
        assert [m["score"] for m in serialise["mots"]] == [14, 2]
        # Le total et le bonus scrabble sont exposés tels quels.
        assert serialise["total"] == 66
        assert serialise["bonus_scrabble"] == 50
        # Les cases bonus utilisées portent ligne, colonne et type sérialisable.
        cases = serialise["mots"][0]["cases_bonus"]
        assert cases == [{"ligne": 7, "colonne": 7, "type": TypeCase.CENTRE.value}]
        assert serialise["mots"][1]["cases_bonus"] == []

    def test_sans_bonus_scrabble(self):
        detail = DetailScore(
            mots=[DetailMot(texte="CHAT", score=9, cases_bonus=[])],
            bonus_scrabble=0,
            total=9,
        )
        serialise = serialiser_detail_score(detail)
        assert serialise["bonus_scrabble"] == 0
        assert serialise["total"] == 9
        assert len(serialise["mots"]) == 1

    def test_poser_mot_expose_le_detail(self):
        # Intégration : un coup réussi renvoie un détail sérialisé cohérent.
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list("CHATSER")
        placements = [
            {"ligne": 7, "colonne": 7, "lettre": "C"},
            {"ligne": 7, "colonne": 8, "lettre": "H"},
            {"ligne": 7, "colonne": 9, "lettre": "A"},
            {"ligne": 7, "colonne": 10, "lettre": "T"},
        ]
        res = jouer_placements(partie, placements)
        assert res["succes"] is True
        assert res["detail"] is not None
        detail = res["detail"]
        assert any(m["texte"] == "CHAT" for m in detail["mots"])
        assert detail["total"] == res["points"]
        assert detail["total"] == sum(m["score"] for m in detail["mots"]) + detail[
            "bonus_scrabble"
        ]


def _partie_quatre_joueurs(graine: int = 7) -> Partie:
    """Partie déterministe à quatre joueurs (1 humain + 3 ordinateurs)."""
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot A", humain=False, niveau=Niveau.FACILE),
        Joueur(nom="Robot B", humain=False, niveau=Niveau.FACILE),
        Joueur(nom="Robot C", humain=False, niveau=Niveau.FACILE),
    ]
    return Partie(joueurs, _DicoFactice(), graine=graine)


def _echanger_une_lettre(partie: Partie) -> None:
    """Fait échanger une lettre au joueur courant (action sans détail, score 0).

    Un échange ne compte pas comme une passe : enchaîner des échanges permet de
    remplir l'historique sans terminer la partie (contrairement aux passes, qui
    la clôturent après un tour de table complet).
    """
    joueur = partie.joueur_courant()
    partie.echanger([joueur.chevalet[0]])


def _poser_chat_au_centre(partie: Partie) -> None:
    """Fait poser « CHAT » horizontalement en passant par le centre (7, 7)."""
    partie.joueur_courant().chevalet = list("CHATSER")
    placements = [
        {"ligne": 7, "colonne": 7, "lettre": "C"},
        {"ligne": 7, "colonne": 8, "lettre": "H"},
        {"ligne": 7, "colonne": 9, "lettre": "A"},
        {"ligne": 7, "colonne": 10, "lettre": "T"},
    ]
    resultat = jouer_placements(partie, placements)
    assert resultat["succes"] is True


class TestSerialiserHistorique:
    """Exposition de l'intégralité de l'historique (issue #37, #144)."""

    def test_partie_neuve_historique_vide(self):
        partie = _partie_simple()
        assert serialiser_historique(partie) == []

    def test_moins_de_lignes_en_debut_de_partie(self):
        # 2 joueurs -> plafond 4, mais une seule action jouée : une seule ligne.
        partie = _partie_simple()
        _echanger_une_lettre(partie)
        historique = serialiser_historique(partie)
        assert len(historique) == 1
        assert historique[0]["action"] == "echange"

    def test_expose_tout_l_historique(self):
        # Issue #144 : plus de plafond d'affichage — l'intégralité de l'historique
        # est exposée (l'UI la rend scrollable, la plus récente en haut).
        partie = _partie_quatre_joueurs()
        # Dix échanges (l'échange ne termine pas la partie).
        for _ in range(10):
            _echanger_une_lettre(partie)
        assert len(partie.historique) == 10
        historique = serialiser_historique(partie)
        assert len(historique) == 10

    def test_ordre_plus_recent_en_premier(self):
        partie = _partie_quatre_joueurs()
        for _ in range(5):
            _echanger_une_lettre(partie)
        historique = serialiser_historique(partie)
        # La première ligne renvoyée est la plus récente ; l'index le confirme.
        indices = [entree["index"] for entree in historique]
        assert indices == sorted(indices, reverse=True)
        assert indices[0] == len(partie.historique) - 1

    def test_index_stable_vers_l_historique_complet(self):
        partie = _partie_quatre_joueurs()
        for _ in range(10):
            _echanger_une_lettre(partie)
        for entree in serialiser_historique(partie):
            # L'index pointe bien vers l'entrée d'origine (identifiant du coup).
            origine = partie.historique[entree["index"]]
            assert origine.nom_joueur == entree["nom_joueur"]
            assert origine.action == entree["action"]

    def test_action_sans_detail_signalee(self):
        partie = _partie_simple()
        _echanger_une_lettre(partie)  # échange : ni mot, ni détail, score 0
        partie.passer()               # passe : idem
        historique = serialiser_historique(partie)
        for entree in historique:
            assert entree["detail"] is None
            assert entree["score_action"] == 0
            assert entree["mot"] is None
        assert {e["action"] for e in historique} == {"echange", "passe"}

    def test_coup_associe_a_son_detail(self):
        partie = _partie_simple()
        partie.index_courant = 0
        _poser_chat_au_centre(partie)
        historique = serialiser_historique(partie)
        # Le coup est la plus récente (et unique) entrée : détail cliquable.
        entree = historique[0]
        assert entree["action"] == "coup"
        assert entree["nom_joueur"] == "Alice"
        assert entree["humain"] is True
        assert entree["mot"] == "CHAT"
        assert entree["detail"] is not None
        assert entree["score_action"] == entree["detail"]["total"]
        assert any(m["texte"] == "CHAT" for m in entree["detail"]["mots"])

    def test_coup_expose_les_positions_posees(self):
        # Issue #58 : un coup expose les cases nouvellement posées pour que l'UI
        # puisse mettre en surbrillance le dernier coup d'un ordinateur. CHAT est
        # posé horizontalement de (7, 7) à (7, 10).
        partie = _partie_simple()
        partie.index_courant = 0
        _poser_chat_au_centre(partie)
        entree = serialiser_historique(partie)[0]
        assert entree["positions"] == [
            {"ligne": 7, "colonne": 7},
            {"ligne": 7, "colonne": 8},
            {"ligne": 7, "colonne": 9},
            {"ligne": 7, "colonne": 10},
        ]

    def test_passe_et_echange_sans_positions(self):
        # Une passe ou un échange ne pose aucune tuile : positions vides (issue #58).
        partie = _partie_simple()
        _echanger_une_lettre(partie)  # échange
        partie.passer()               # passe
        for entree in serialiser_historique(partie):
            assert entree["positions"] == []

    def test_flag_humain_distingue_joueurs(self):
        partie = _partie_simple()  # Alice (humaine) puis Robot (ordinateur)
        _echanger_une_lettre(partie)  # Alice
        _echanger_une_lettre(partie)  # Robot
        historique = serialiser_historique(partie)
        par_nom = {e["nom_joueur"]: e for e in historique}
        assert par_nom["Alice"]["humain"] is True
        assert par_nom["Robot"]["humain"] is False

    def test_expose_dans_etat_public(self):
        partie = _partie_quatre_joueurs()
        for _ in range(10):
            _echanger_une_lettre(partie)
        etat = etat_public(partie, id_partie=3)
        assert "historique" in etat
        # Même contenu et même ordre que serialiser_historique (tout l'historique).
        assert etat["historique"] == serialiser_historique(partie)
        assert len(etat["historique"]) == 10


class TestClasserScoreTotal:
    """Classification officielle du total combiné (issue #137, Jeux Spear p.10).

    Seuils : < 500 → aucun qualificatif ; 500-599 → « Bon score » ;
    600-699 → « Très bon score » ; >= 700 → « Excellent score ».
    """

    def test_en_dessous_de_500_aucun_qualificatif(self):
        assert classer_score_total(0) is None
        assert classer_score_total(300) is None
        assert classer_score_total(499) is None

    def test_bon_score(self):
        assert classer_score_total(500) == "Bon score"
        assert classer_score_total(550) == "Bon score"
        assert classer_score_total(599) == "Bon score"

    def test_tres_bon_score(self):
        assert classer_score_total(600) == "Très bon score"
        assert classer_score_total(650) == "Très bon score"
        assert classer_score_total(699) == "Très bon score"

    def test_excellent_score(self):
        assert classer_score_total(700) == "Excellent score"
        assert classer_score_total(900) == "Excellent score"

    def test_bornes_exactes(self):
        # Les frontières appartiennent à la catégorie supérieure.
        assert classer_score_total(499) is None
        assert classer_score_total(500) == "Bon score"
        assert classer_score_total(599) == "Bon score"
        assert classer_score_total(600) == "Très bon score"
        assert classer_score_total(699) == "Très bon score"
        assert classer_score_total(700) == "Excellent score"


class TestEvaluerScoreTotal:
    """Évaluation complète du total combiné (issue #137)."""

    @staticmethod
    def _joueurs(scores):
        return [Joueur(nom=f"J{i}", score=s) for i, s in enumerate(scores)]

    def test_total_et_moyenne(self):
        ev = evaluer_score_total(self._joueurs([260, 240]))
        assert ev["total"] == 500
        assert ev["nb_joueurs"] == 2
        assert ev["moyenne"] == 250
        assert ev["qualificatif"] == "Bon score"

    def test_moyenne_arrondie(self):
        # 550 / 3 = 183.33… → arrondi à 183.
        ev = evaluer_score_total(self._joueurs([200, 200, 150]))
        assert ev["total"] == 550
        assert ev["moyenne"] == 183

    def test_sans_qualificatif_sous_500(self):
        ev = evaluer_score_total(self._joueurs([200, 150]))
        assert ev["total"] == 350
        assert ev["qualificatif"] is None

    def test_aucun_joueur_moyenne_zero_sans_division(self):
        ev = evaluer_score_total([])
        assert ev == {
            "total": 0,
            "nb_joueurs": 0,
            "moyenne": 0,
            "qualificatif": None,
        }

    @pytest.mark.parametrize(
        "total, qualificatif",
        [
            (450, None),
            (500, "Bon score"),
            (599, "Bon score"),
            (600, "Très bon score"),
            (699, "Très bon score"),
            (700, "Excellent score"),
            (820, "Excellent score"),
        ],
    )
    @pytest.mark.parametrize("nb_joueurs", [2, 3, 4])
    def test_classification_independante_du_nombre_de_joueurs(
        self, total, qualificatif, nb_joueurs
    ):
        # À total combiné égal, la classification ne doit PAS dépendre du
        # nombre de joueurs : on répartit le total en `nb_joueurs` parts.
        base, reste = divmod(total, nb_joueurs)
        scores = [base] * nb_joueurs
        for k in range(reste):
            scores[k] += 1
        assert sum(scores) == total  # garde-fou de répartition
        ev = evaluer_score_total(self._joueurs(scores))
        assert ev["total"] == total
        assert ev["nb_joueurs"] == nb_joueurs
        assert ev["qualificatif"] == qualificatif
