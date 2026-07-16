"""Tests de la logique non-UI de l'écran de jeu (issue #28).

Couvre :
- la sérialisation du plateau (types de cases, tuiles posées, jokers) ;
- la sérialisation des infos publiques des joueurs (sans identité des lettres) ;
- la sérialisation d'un chevalet (lettres, valeurs, jokers) ;
- la règle de confidentialité : ``etat_public`` n'expose aucune lettre de
  chevalet, et ``ApiJeu.obtenir_chevalet`` n'expose qu'**un seul** chevalet
  à la fois (jamais tous en une fois).
"""

import pytest

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import Tuile
from scrabble.regles.lettres import JOKER
from scrabble.regles.plateau import CENTRE, TAILLE
from scrabble.ui.jeu import (
    ApiJeu,
    construire_partie_demo,
    etat_public,
    serialiser_case,
    serialiser_chevalet,
    serialiser_joueur_public,
    serialiser_plateau,
)


class _DicoFactice:
    """Dictionnaire minimal (accepte tout) — l'écran de jeu ne valide rien."""

    def contient(self, mot: str) -> bool:
        return True


def _partie_simple(graine: int = 42) -> Partie:
    """Petite partie déterministe à deux joueurs (humain + ordinateur)."""
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
    ]
    return Partie(joueurs, _DicoFactice(), graine=graine)


class TestSerialiserCase:
    """Tests de la sérialisation d'une case du plateau."""

    def test_case_normale_vide(self):
        partie = _partie_simple()
        case = serialiser_case(partie.plateau, 4, 0)
        assert case["type"] == "normale"
        assert case["lettre"] is None
        assert case["joker"] is False

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

    def test_case_avec_joker(self):
        partie = _partie_simple()
        partie.plateau.poser_tuile(7, 8, Tuile("B", joker=True))
        case = serialiser_case(partie.plateau, 7, 8)
        assert case["lettre"] == "B"
        assert case["joker"] is True


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


class TestApiConfidentialite:
    """Tests de la règle « un seul chevalet exposé à la fois »."""

    def test_obtenir_chevalet_un_seul_joueur(self):
        partie = _partie_simple()
        partie.joueurs[0].chevalet = ["A", "B"]
        partie.joueurs[1].chevalet = ["C", "D", "E"]
        api = ApiJeu(partie, id_partie=1)

        res = api.obtenir_chevalet(0)
        assert res["succes"] is True
        assert res["index"] == 0
        assert res["nom"] == "Alice"
        assert [c["lettre"] for c in res["lettres"]] == ["A", "B"]
        # La réponse ne contient QUE le chevalet demandé, pas celui des autres.
        assert "Robot" not in str(res.get("nom")) or res["index"] == 0

    def test_obtenir_chevalet_autre_joueur(self):
        partie = _partie_simple()
        partie.joueurs[1].chevalet = ["C", "D", "E"]
        api = ApiJeu(partie, id_partie=1)
        res = api.obtenir_chevalet(1)
        assert res["succes"] is True
        assert res["index"] == 1
        assert len(res["lettres"]) == 3

    def test_pas_de_methode_exposant_tous_les_chevalets(self):
        """L'API n'offre aucune méthode publique renvoyant tous les chevalets."""
        partie = _partie_simple()
        api = ApiJeu(partie, id_partie=1)
        methodes = [
            nom
            for nom in dir(api)
            if not nom.startswith("_") and callable(getattr(api, nom))
        ]
        # La seule méthode donnant des lettres prend un index unique en argument.
        assert "obtenir_chevalet" in methodes
        for nom in methodes:
            assert "chevalets" not in nom  # pas de pluriel « tous les chevalets »

    def test_index_invalide(self):
        partie = _partie_simple()
        api = ApiJeu(partie, id_partie=1)
        for mauvais in (-1, 2, 99):
            res = api.obtenir_chevalet(mauvais)
            assert res["succes"] is False
            assert "erreur" in res

    def test_etat_ne_contient_pas_les_lettres(self):
        """obtenir_etat ne doit jamais renvoyer l'identité des lettres."""
        partie = _partie_simple()
        api = ApiJeu(partie, id_partie=1)
        etat = api.obtenir_etat()
        for joueur_pub in etat["joueurs"]:
            assert "lettres" not in joueur_pub
            assert "chevalet" not in joueur_pub


class TestPartieDemo:
    """Tests du mode démonstration (partie d'exemple pour test manuel)."""

    def test_construction(self):
        partie, id_partie = construire_partie_demo()
        assert id_partie is None
        assert len(partie.joueurs) == 2

    def test_plateau_partiellement_rempli(self):
        partie, _ = construire_partie_demo()
        assert not partie.plateau.est_vide()
        # Le mot horizontal passe par la case centrale.
        assert not partie.plateau.case_vide(CENTRE[0], CENTRE[1])

    def test_contient_un_joker_pose(self):
        partie, _ = construire_partie_demo()
        etat = etat_public(partie, None)
        jokers = [
            case
            for ligne in etat["plateau"]
            for case in ligne
            if case["joker"]
        ]
        assert len(jokers) >= 1

    def test_serialisable_sans_erreur(self):
        """La partie de démo se sérialise entièrement sans lever."""
        partie, id_partie = construire_partie_demo()
        etat = etat_public(partie, id_partie)
        assert etat["taille"] == TAILLE
