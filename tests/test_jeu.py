"""Tests de la logique non-UI de l'écran de jeu (issue #28).

Couvre :
- la sérialisation du plateau (types de cases, tuiles posées, jokers) ;
- la sérialisation des infos publiques des joueurs (sans identité des lettres) ;
- la sérialisation d'un chevalet (lettres, valeurs, jokers) ;
- la règle de confidentialité : ``etat_public`` n'expose aucune lettre de
  chevalet, et ``ApiJeu.obtenir_chevalet`` n'expose qu'**un seul** chevalet
  à la fois (jamais tous en une fois).
"""

import json
from collections import Counter

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie, creer_partie
from scrabble.moteur.plateau_partie import Coup, Direction, Tuile
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.persistance import (
    STATUT_TERMINEE,
    demarrer_suivi,
    lister_parties,
    reprendre_partie,
)
from scrabble.regles.lettres import JOKER
from scrabble.regles.plateau import CENTRE, TAILLE, TypeCase
from scrabble.ui.jeu import (
    AVATARS,
    CHEVALET_HAUTEUR,
    CHEVALET_LARGEUR,
    ApiJeu,
    calculer_avatars,
    calculer_positions,
    compter_humains,
    construire_coup,
    construire_partie_demo,
    echanger_chevalet_complet,
    etat_public,
    index_humain_reference,
    index_panneau_interactif,
    jouer_placements,
    jouer_tours_ia_ui,
    nb_lignes_historique,
    passer_tour,
    serialiser_case,
    serialiser_historique,
    serialiser_chevalet,
    serialiser_detail_score,
    serialiser_joueur_public,
    serialiser_plateau,
    simuler_coup,
    verifier_mot_dictionnaire,
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


class TestThemePlateau:
    """Tests de la lecture du thème visuel de plateau exposée au JS."""

    def test_theme_valide_transmis(self, monkeypatch):
        """Un thème reconnu dans la config est renvoyé tel quel."""
        monkeypatch.setattr(
            "scrabble.ui.jeu.charger_config", lambda: {"theme_plateau": "vert"}
        )
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_theme_plateau() == "vert"

    def test_theme_inconnu_retombe_sur_classique(self, monkeypatch):
        """Une valeur imprévue (config trafiquée) est ramenée à « classique »."""
        monkeypatch.setattr(
            "scrabble.ui.jeu.charger_config", lambda: {"theme_plateau": "n_importe_quoi"}
        )
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_theme_plateau() == "classique"

    def test_theme_absent_retombe_sur_classique(self, monkeypatch):
        """Clé absente de la config : défaut « classique »."""
        monkeypatch.setattr("scrabble.ui.jeu.charger_config", lambda: {})
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_theme_plateau() == "classique"


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


# --------------------------------------------------------------------------- #
# Construction d'un Coup depuis des placements « clic-clic » (logique non-UI)
# --------------------------------------------------------------------------- #


class _DicoMots:
    """Dictionnaire de test acceptant uniquement un ensemble de mots donnés."""

    def __init__(self, *mots: str) -> None:
        self._mots = {mot.upper() for mot in mots}

    def contient(self, mot: str) -> bool:
        return mot.upper() in self._mots


def _placement(ligne: int, colonne: int, lettre: str, joker: bool = False) -> dict:
    """Fabrique un placement JS simulé (dict {ligne, colonne, lettre, joker})."""
    return {"ligne": ligne, "colonne": colonne, "lettre": lettre, "joker": joker}


class TestConstruireCoup:
    """Construction d'un :class:`Coup` à partir de placements simulés."""

    def test_mot_horizontal(self):
        partie = _partie_simple()
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        coup = construire_coup(partie.plateau, placements)
        assert (coup.ligne, coup.colonne) == (7, 7)
        assert coup.direction is Direction.HORIZONTALE
        assert "".join(t.lettre for t in coup.tuiles) == "CHAT"

    def test_direction_deduite_verticale(self):
        partie = _partie_simple()
        # Lettres placées dans le désordre : la direction se déduit de la colonne.
        placements = [
            _placement(9, 7, "T"),
            _placement(7, 7, "C"),
            _placement(8, 7, "A"),
        ]
        coup = construire_coup(partie.plateau, placements)
        assert coup.direction is Direction.VERTICALE
        assert (coup.ligne, coup.colonne) == (7, 7)
        assert "".join(t.lettre for t in coup.tuiles) == "CAT"

    def test_une_seule_lettre_direction_horizontale_fixee(self):
        # Issue #43 : plus aucun paramètre de sens. Pour une lettre unique, la
        # direction est fixée en interne à l'horizontale (choix arbitraire sans
        # conséquence sur la validation ni le score, cf.
        # TestSymetrieSensLettreUnique). Le coup couvre bien la seule case posée.
        partie = _partie_simple()
        coup = construire_coup(partie.plateau, [_placement(7, 7, "A")])
        assert coup.direction is Direction.HORIZONTALE
        assert (coup.ligne, coup.colonne) == (7, 7)
        assert len(coup.tuiles) == 1
        assert coup.tuiles[0].lettre == "A"

    def test_joker_conserve_le_drapeau(self):
        partie = _partie_simple()
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "A", joker=True),
            _placement(7, 9, "T"),
        ]
        coup = construire_coup(partie.plateau, placements)
        # La tuile centrale est un joker : lettre affichée 'A' mais valeur 0.
        assert coup.tuiles[1].joker is True
        assert coup.tuiles[1].lettre == "A"
        assert coup.tuiles[1].valeur == 0

    def test_enjambe_une_tuile_existante(self):
        """Le mot construit inclut une tuile déjà posée qu'il enjambe."""
        partie = _partie_simple()
        partie.plateau.poser_tuile(7, 8, Tuile("H"))
        # On pose C (7,7) et AT (7,9)(7,10) : le mot doit couvrir CHAT en reprenant
        # le H déjà présent.
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        coup = construire_coup(partie.plateau, placements)
        assert "".join(t.lettre for t in coup.tuiles) == "CHAT"

    def test_liste_vide(self):
        partie = _partie_simple()
        with pytest.raises(ValueError):
            construire_coup(partie.plateau, [])

    def test_case_deja_occupee(self):
        partie = _partie_simple()
        partie.plateau.poser_tuile(7, 7, Tuile("Z"))
        with pytest.raises(ValueError):
            construire_coup(partie.plateau, [_placement(7, 7, "A")])

    def test_lettres_non_alignees(self):
        partie = _partie_simple()
        placements = [_placement(7, 7, "A"), _placement(8, 8, "B")]
        with pytest.raises(ValueError):
            construire_coup(partie.plateau, placements)

    def test_trou_au_milieu(self):
        partie = _partie_simple()
        # C en (7,7) et T en (7,10) sans lettre entre les deux : trou interdit.
        placements = [_placement(7, 7, "C"), _placement(7, 10, "T")]
        with pytest.raises(ValueError):
            construire_coup(partie.plateau, placements)

    def test_position_hors_plateau(self):
        partie = _partie_simple()
        with pytest.raises(ValueError):
            construire_coup(partie.plateau, [_placement(7, 99, "A")])


class TestJouerPlacements:
    """Application d'un coup construit depuis des placements (succès et erreurs)."""

    def _partie_avec_chevalet(self, lettres: str, mots: tuple[str, ...]) -> Partie:
        """Partie déterministe dont le joueur courant a un chevalet imposé."""
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots(*mots), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list(lettres)
        return partie

    def test_coup_legal_met_a_jour_la_partie(self):
        partie = self._partie_avec_chevalet("CHATSER", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        resultat = jouer_placements(partie, placements)
        assert resultat["succes"] is True
        assert resultat["points"] > 0
        assert resultat["nom"] == "Alice"
        # Le plateau porte désormais le mot et le tour a changé.
        assert not partie.plateau.case_vide(7, 7)
        assert partie.index_courant == 1
        assert partie.joueurs[0].score > 0

    def test_mot_invalide_leve_coup_invalide(self):
        # Structure correcte (couvre le centre) mais mot absent du dictionnaire.
        partie = self._partie_avec_chevalet("XYZWKQJ", mots=("CHAT",))
        placements = [
            _placement(7, 7, "X"),
            _placement(7, 8, "Y"),
            _placement(7, 9, "Z"),
        ]
        resultat = jouer_placements(partie, placements)
        assert resultat["succes"] is False
        assert "erreur" in resultat
        # La partie n'a pas avancé : correction possible sans tout perdre.
        assert partie.index_courant == 0
        assert partie.plateau.case_vide(7, 7)

    def test_lettres_absentes_du_chevalet(self):
        # « CHAT » est un mot valide mais le chevalet ne contient pas ces lettres.
        partie = self._partie_avec_chevalet("BDFGKLM", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        resultat = jouer_placements(partie, placements)
        assert resultat["succes"] is False
        assert "erreur" in resultat
        assert partie.index_courant == 0

    def test_placements_incoherents(self):
        # Erreur de structure (non alignés) : traité comme échec, pas d'exception.
        partie = self._partie_avec_chevalet("ABCDEFG", mots=("AB",))
        placements = [_placement(7, 7, "A"), _placement(9, 9, "B")]
        resultat = jouer_placements(partie, placements)
        assert resultat["succes"] is False
        assert "erreur" in resultat


class TestSimulerCoup:
    """``simuler_coup`` : calcul du score d'un coup en attente SANS le jouer (issue #69)."""

    def _partie_avec_chevalet(self, lettres: str, mots: tuple[str, ...]) -> Partie:
        """Partie déterministe dont le joueur courant a un chevalet imposé."""
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots(*mots), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list(lettres)
        return partie

    def test_coup_valide_renvoie_le_bon_score(self):
        partie = self._partie_avec_chevalet("CHATSER", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        resultat = simuler_coup(partie, placements)
        assert resultat["succes"] is True
        assert resultat["nom"] == "Alice"
        # Le score simulé est exactement celui du même coup réellement joué.
        detail = resultat["detail"]
        assert detail["mots"][0]["texte"] == "CHAT"
        assert resultat["points"] == detail["total"]
        temoin = self._partie_avec_chevalet("CHATSER", mots=("CHAT",))
        joue = jouer_placements(temoin, placements)
        assert resultat["points"] == joue["points"]

    def test_coup_invalide_renvoie_message_sans_score(self):
        # Structure correcte (couvre le centre) mais mot absent du dictionnaire.
        partie = self._partie_avec_chevalet("XYZWKQJ", mots=("CHAT",))
        placements = [
            _placement(7, 7, "X"),
            _placement(7, 8, "Y"),
            _placement(7, 9, "Z"),
        ]
        resultat = simuler_coup(partie, placements)
        assert resultat["succes"] is False
        assert resultat.get("erreur")
        assert "points" not in resultat
        assert "detail" not in resultat

    def test_structure_incoherente_traitee_comme_echec(self):
        # Lettres non alignées : ValueError de construire_coup → échec propre.
        partie = self._partie_avec_chevalet("ABCDEFG", mots=("AB",))
        placements = [_placement(7, 7, "A"), _placement(9, 9, "B")]
        resultat = simuler_coup(partie, placements)
        assert resultat["succes"] is False
        assert resultat.get("erreur")

    def test_aucune_mutation_de_la_partie(self):
        partie = self._partie_avec_chevalet("CHATSER", mots=("CHAT",))
        chevalet_avant = list(partie.joueurs[0].chevalet)
        index_avant = partie.index_courant
        score_avant = partie.joueurs[0].score
        nb_historique_avant = len(partie.historique)
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        resultat = simuler_coup(partie, placements)
        assert resultat["succes"] is True
        # Rien n'a bougé : plateau, chevalet, tour, score, historique intacts.
        assert partie.plateau.case_vide(7, 7)
        assert partie.plateau.est_vide()
        assert partie.joueurs[0].chevalet == chevalet_avant
        assert partie.index_courant == index_avant
        assert partie.joueurs[0].score == score_avant
        assert len(partie.historique) == nb_historique_avant


class TestSymetrieSensLettreUnique:
    """Symétrie du sens pour une lettre unique (issue #43).

    Le contrôle de sens a été retiré de l'UI : pour une lettre unique, la
    direction est désormais fixée en interne (horizontale) sans intervention du
    joueur. Ces tests démontrent la propriété qui rend ce choix légitime : pour
    une lettre unique posée créant un mot valide dans les DEUX sens (une lettre
    reliant deux mots perpendiculaires existants), le résultat — validité ET
    score total — est rigoureusement identique quel que soit le sens joué. Le
    moteur calcule de toute façon le mot dans le sens choisi ET le mot
    transversal, tous deux devant être valides et étant comptés à l'identique.
    """

    def _partie_reliant_deux_mots(self) -> Partie:
        """Plateau où « E » en (7,7) forme LES (→) et DES (↓), tous deux valides.

        Deux mots incomplets se croisent sur la case centrale vide : « L_S »
        horizontal en (7,6)/(7,8) et « D_S » vertical en (6,7)/(8,7). Poser
        l'unique lettre « E » au croisement complète simultanément les deux.
        """
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots("LES", "DES"), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list("E")
        partie.plateau.poser_tuile(7, 6, Tuile("L"))
        partie.plateau.poser_tuile(7, 8, Tuile("S"))
        partie.plateau.poser_tuile(6, 7, Tuile("D"))
        partie.plateau.poser_tuile(8, 7, Tuile("S"))
        return partie

    def _jouer_dans_le_sens(self, direction: Direction) -> dict:
        """Joue la lettre unique « E » dans le sens imposé et renvoie le bilan."""
        partie = self._partie_reliant_deux_mots()
        if direction is Direction.HORIZONTALE:
            coup = Coup(
                7, 6, Direction.HORIZONTALE,
                (Tuile("L"), Tuile("E"), Tuile("S")),
            )
        else:
            coup = Coup(
                6, 7, Direction.VERTICALE,
                (Tuile("D"), Tuile("E"), Tuile("S")),
            )
        entree = partie.jouer_coup(coup)
        return {
            "score_coup": entree.detail.total,
            "score_joueur": partie.joueurs[0].score,
            "mots": sorted(mot.texte for mot in entree.detail.mots),
        }

    def test_validite_et_score_identiques_quel_que_soit_le_sens(self):
        # Cœur de l'issue #43 : jouer la même lettre unique à l'horizontale ou à
        # la verticale donne EXACTEMENT le même bilan (validité, score total, et
        # même ensemble de mots formés). Le sens fixé en interne est indifférent.
        resultat_h = self._jouer_dans_le_sens(Direction.HORIZONTALE)
        resultat_v = self._jouer_dans_le_sens(Direction.VERTICALE)
        assert resultat_h == resultat_v
        assert resultat_h["mots"] == ["DES", "LES"]

    def test_lettre_unique_sans_sens_reussit(self):
        # La direction fixée en interne (horizontale, aucun paramètre transmis)
        # produit un coup jouable dans ce scénario symétrique : jouer_placements
        # réussit et score les deux mots croisés.
        partie = self._partie_reliant_deux_mots()
        resultat = jouer_placements(partie, [_placement(7, 7, "E")])
        assert resultat["succes"] is True
        assert resultat["points"] > 0


class TestApiPoserMot:
    """API exposée au JS : ``ApiJeu.poser_mot`` (succès, erreur, confidentialité)."""

    def _api_avec_chevalet(self, lettres: str, mots: tuple[str, ...]) -> ApiJeu:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots(*mots), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list(lettres)
        return ApiJeu(partie, None)

    def test_succes_renvoie_etat_public(self):
        api = self._api_avec_chevalet("CHATSER", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        res = api.poser_mot(placements)
        assert res["succes"] is True
        assert "etat" in res
        # L'état renvoyé reste public : aucune lettre de chevalet exposée.
        for joueur_pub in res["etat"]["joueurs"]:
            assert "lettres" not in joueur_pub
            assert "chevalet" not in joueur_pub

    def test_echec_renvoie_message_sans_etat(self):
        api = self._api_avec_chevalet("XYZWKQJ", mots=("CHAT",))
        placements = [
            _placement(7, 7, "X"),
            _placement(7, 8, "Y"),
            _placement(7, 9, "Z"),
        ]
        res = api.poser_mot(placements)
        assert res["succes"] is False
        assert res.get("erreur")
        # Pas d'état renvoyé en cas d'échec : le JS conserve son attente.
        assert "etat" not in res

    def test_verifier_coup_valide_ne_joue_pas(self):
        # ApiJeu.verifier_coup (issue #69) : calcule les points sans jouer.
        api = self._api_avec_chevalet("CHATSER", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        res = api.verifier_coup(placements)
        assert res["succes"] is True
        assert res["points"] > 0
        assert res["detail"]["mots"][0]["texte"] == "CHAT"
        # Le coup n'a pas été joué : plateau vide, tour et chevalet inchangés.
        partie = api._partie
        assert partie.plateau.case_vide(7, 7)
        assert partie.index_courant == 0
        assert partie.joueurs[0].chevalet == list("CHATSER")

    def test_verifier_coup_invalide_renvoie_erreur(self):
        api = self._api_avec_chevalet("XYZWKQJ", mots=("CHAT",))
        placements = [
            _placement(7, 7, "X"),
            _placement(7, 8, "Y"),
            _placement(7, 9, "Z"),
        ]
        res = api.verifier_coup(placements)
        assert res["succes"] is False
        assert res.get("erreur")
        assert "points" not in res


# --------------------------------------------------------------------------- #
# Suite #29 (issue #31) : comptage des humains, vérification dictionnaire,
# échange complet du chevalet.
# --------------------------------------------------------------------------- #


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
    """Disposition spatiale des joueurs autour du plateau (issue #33)."""

    def _joueurs(self, *humains: bool) -> list[Joueur]:
        return _joueurs_humains(*humains)

    def test_un_seul_joueur_aucune_position_laterale(self):
        # 1 seul joueur au total : uniquement le panneau du bas.
        positions = calculer_positions(self._joueurs(True))
        assert positions == ["bas"]

    def test_un_adversaire_en_haut(self):
        # 1 adversaire → il est placé en haut (face à face avec le bas).
        positions = calculer_positions(self._joueurs(True, False))
        assert positions == ["bas", "haut"]

    def test_deux_adversaires_sens_horaire_gauche_puis_haut(self):
        # Sens horaire (issue #122) à partir du bas : le 1er adversaire va à
        # gauche, le 2e en haut.
        positions = calculer_positions(self._joueurs(True, False, False))
        assert positions == ["bas", "gauche", "haut"]

    def test_trois_adversaires_gauche_haut_droite(self):
        # Sens horaire complet à 4 joueurs : bas → gauche → haut → droite.
        positions = calculer_positions(self._joueurs(True, False, False, False))
        assert positions == ["bas", "gauche", "haut", "droite"]

    def test_humain_reference_toujours_en_bas(self):
        # Le joueur humain de référence est le premier humain de la liste : il
        # est en bas quel que soit l'ordre des joueurs dans la partie, et les
        # autres tournent dans le sens horaire à partir de son rang réel.
        positions = calculer_positions(self._joueurs(False, False, True, False))
        assert positions == ["haut", "droite", "bas", "gauche"]

    def test_plusieurs_humains_autres_repartis_sens_horaire(self):
        # Avec plusieurs humains, seul le premier va en bas ; les autres joueurs
        # (humains et ordinateurs) se répartissent dans le sens horaire selon
        # l'ordre de jeu.
        positions = calculer_positions(self._joueurs(True, True, False))
        assert positions == ["bas", "gauche", "haut"]

    def test_aucun_humain_premier_joueur_en_bas(self):
        # Cas théorique sans humain : le premier joueur tient le rôle de référence.
        positions = calculer_positions(self._joueurs(False, False))
        assert positions == ["bas", "haut"]

    def test_liste_vide(self):
        assert calculer_positions([]) == []

    def test_humain_non_premier_a_jouer_ordre_horaire(self):
        # Le tirage d'ordre a désigné un ordinateur en premier : l'humain de
        # référence (index 1) reste en bas, et les autres tournent dans le sens
        # horaire à partir de son rang réel — pas de l'index 0.
        # Ordre de jeu : [ordi, HUMAIN, ordi]. Réf. en bas ; le joueur suivant
        # dans l'ordre (index 2) va à gauche, le suivant (index 0) en haut.
        positions = calculer_positions(self._joueurs(False, True, False))
        assert positions == ["haut", "bas", "gauche"]

    def test_humain_troisieme_a_jouer_quatre_joueurs(self):
        # 4 joueurs, l'humain de référence ne joue qu'en 3e position (index 2) :
        # bas en index 2, puis sens horaire gauche/haut/droite pour les joueurs
        # d'index 3, 0 et 1 dans l'ordre de jeu.
        positions = calculer_positions(self._joueurs(False, False, True, False))
        assert positions == ["haut", "droite", "bas", "gauche"]
        # Cohérence : la référence est bien en bas quel que soit son rang.
        assert positions[index_humain_reference(self._joueurs(False, False, True, False))] == "bas"

    def test_humain_dernier_a_jouer_deux_joueurs(self):
        # Exception 2 joueurs conservée : face-à-face bas/haut même quand
        # l'humain joue en second.
        positions = calculer_positions(self._joueurs(False, True))
        assert positions == ["haut", "bas"]

    def test_ensembles_de_cotes_par_effectif_preserves(self):
        # Les *ensembles* de côtés utilisés par effectif sont inchangés par la
        # refonte #122 (seul l'ordre d'attribution change) : 1→bas, 2→bas/haut,
        # 3→bas/gauche/haut, 4→les quatre côtés.
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

    def test_reprise_partie_persistee_positions_horaires(self, tmp_path):
        # Une partie persistée fige l'ordre de jeu (établi par le tirage) dans
        # l'ordre de sa liste de joueurs. La reprendre recalcule des positions
        # conformes à la nouvelle règle horaire, sans toucher à l'ordre de jeu,
        # aux scores ni au plateau.
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
        # Positions recalculées selon la règle horaire à partir du rang réel de
        # l'humain de référence (Alice, index 1) : bas en index 1, puis le
        # joueur suivant dans l'ordre (Bob, index 2) à gauche, puis Robot
        # (index 0) en haut.
        positions = calculer_positions(reprise.joueurs)
        assert positions == ["haut", "bas", "gauche"]
        assert positions[index_humain_reference(reprise.joueurs)] == "bas"

    def test_position_exposee_dans_etat_public(self):
        partie = Partie(self._joueurs(True, False, False), _DicoFactice(), graine=3)
        etat = etat_public(partie, None)
        assert [j["position"] for j in etat["joueurs"]] == ["bas", "gauche", "haut"]


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

    def test_avatar_expose_dans_etat_public(self):
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=5)
        etat = etat_public(partie, None)
        avatars = [j["avatar"] for j in etat["joueurs"]]
        assert all(a in AVATARS for a in avatars)
        assert len(set(avatars)) == 2
        # Cohérent avec le calcul direct.
        assert avatars == calculer_avatars(joueurs)


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


class TestEchangerChevaletComplet:
    """Échange de la totalité du chevalet (remet tout et passe le tour)."""

    def _partie(self) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        return partie

    def test_succes_change_tout_et_passe_tour(self):
        partie = self._partie()
        chevalet_avant = list(partie.joueurs[0].chevalet)
        sac_avant = partie.sac.jetons_restants()

        res = echanger_chevalet_complet(partie, None)

        assert res["succes"] is True
        assert "etat" in res
        # Le tour a bien avancé (échange = consommation du tour).
        assert partie.index_courant == 1
        # Le chevalet reste plein mais son contenu a été renouvelé depuis le sac.
        assert len(partie.joueurs[0].chevalet) == len(chevalet_avant)
        # Le sac garde le même total (autant tiré que remis).
        assert partie.sac.jetons_restants() == sac_avant
        # L'état renvoyé reste public (aucune lettre de chevalet).
        for joueur_pub in res["etat"]["joueurs"]:
            assert "lettres" not in joueur_pub

    def test_echec_sac_trop_pauvre(self):
        partie = self._partie()
        # On vide le sac : plus assez de jetons pour échanger tout le chevalet.
        partie.sac.tirer(partie.sac.jetons_restants())
        chevalet_avant = list(partie.joueurs[0].chevalet)

        res = echanger_chevalet_complet(partie, None)

        assert res["succes"] is False
        assert res.get("erreur")
        assert "etat" not in res
        # Aucun effet de bord : ni le tour ni le chevalet ne bougent.
        assert partie.index_courant == 0
        assert list(partie.joueurs[0].chevalet) == chevalet_avant

    def test_api_echanger_tout_delegue(self):
        partie = self._partie()
        api = ApiJeu(partie, 42)
        res = api.echanger_tout()
        assert res["succes"] is True
        assert res["etat"]["id_partie"] == 42
        assert partie.index_courant == 1


class TestPasserTour:
    """Passage « sec » du tour (sans échange) — débloque un humain sac vide (#132)."""

    def _partie(self) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        return partie

    def test_passe_incremente_le_compteur_et_avance(self):
        partie = self._partie()
        assert partie.passes_consecutives == 0

        res = passer_tour(partie, None)

        assert res["succes"] is True
        assert "etat" in res
        # La passe a bien été comptée et le tour a avancé, sans terminer (2 joueurs).
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1
        assert partie.terminee is False
        # L'état renvoyé reste public (aucune lettre de chevalet).
        for joueur_pub in res["etat"]["joueurs"]:
            assert "lettres" not in joueur_pub

    def test_humain_sac_vide_peut_passer(self):
        # Cas moteur du rapport #130 : sac vide, l'humain ne peut ni poser ni
        # échanger, mais DOIT pouvoir passer.
        partie = self._partie()
        partie.sac.tirer(partie.sac.jetons_restants())
        assert partie.sac.jetons_restants() == 0

        res = passer_tour(partie, None)

        assert res["succes"] is True
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1

    def test_api_passer_delegue_et_incremente(self):
        partie = self._partie()
        api = ApiJeu(partie, 42)
        res = api.passer()
        assert res["succes"] is True
        assert res["etat"]["id_partie"] == 42
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1

    def test_passe_refusee_partie_terminee(self):
        partie = self._partie()
        partie.terminee = True

        res = passer_tour(partie, None)

        assert res["succes"] is False
        assert res.get("erreur")
        assert "etat" not in res

    def test_tous_passent_atteint_la_fin_par_blocage(self):
        # De bout en bout : une partie où TOUS les joueurs (ici deux humains)
        # passent consécutivement atteint la fin par blocage — le critère
        # ``passes_consecutives >= len(joueurs)`` est désormais atteignable même
        # avec des humains (via l'API), ce qui était impossible avant #132.
        partie = self._partie()
        api = ApiJeu(partie, id_partie=None)

        res1 = api.passer()
        assert res1["succes"] is True
        assert partie.terminee is False
        assert partie.passes_consecutives == 1

        res2 = api.passer()
        assert res2["succes"] is True
        # Deux joueurs, deux passes consécutives : partie bloquée → terminée.
        assert partie.passes_consecutives >= len(partie.joueurs)
        assert partie.terminee is True
        assert res2["etat"]["terminee"] is True


# --------------------------------------------------------------------------- #
# Correction du défaut d'exposition du tour IA (issue #35)
# --------------------------------------------------------------------------- #


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


class TestJouerToursIaUi:
    """Enchaînement des tours IA côté API (jouer_tours_ia_ui / faire_jouer_ia)."""

    def _partie_ia(self) -> Partie:
        """Humain (index 0) puis deux ordinateurs, sur un dictionnaire réel."""
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot1", humain=False, niveau=Niveau.EXPERT),
            Joueur(nom="Robot2", humain=False, niveau=Niveau.EXPERT),
        ]
        return Partie(joueurs, Trie.depuis_iterable(["CADRE"]), graine=1)

    def test_joueur_humain_courant_aucun_tour(self):
        partie = self._partie_ia()
        partie.index_courant = 0
        res = jouer_tours_ia_ui(partie, None)
        assert res["succes"] is True
        assert res["nb_tours"] == 0
        assert partie.index_courant == 0  # rien n'a bougé
        assert res["etat"]["index_courant"] == 0

    def test_un_seul_tour_ia_par_appel(self):
        partie = self._partie_ia()
        partie.index_courant = 1  # tour du premier ordinateur
        # Chevalets sans voyelle jouable : les IA passent leur tour (2 de 3 passes
        # consécutives ne terminent pas une partie à 3 joueurs).
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        # Un seul clic = un seul tour d'ordinateur (issue #55) : après cet appel,
        # c'est au tour du DEUXIÈME ordinateur, pas encore à l'humain.
        res = jouer_tours_ia_ui(partie, None)
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert partie.index_courant == 2
        assert partie.joueur_courant().humain is False
        assert res["etat"]["index_courant"] == 2
        assert res["etat"]["tour_humain"] is False
        # Deuxième clic : le second ordinateur joue, puis la main revient à
        # l'humain.
        res2 = jouer_tours_ia_ui(partie, None)
        assert res2["nb_tours"] == 1
        assert partie.index_courant == 0
        assert partie.joueur_courant().humain is True
        assert res2["etat"]["tour_humain"] is True

    def test_api_faire_jouer_ia_delegue(self):
        partie = self._partie_ia()
        partie.index_courant = 1
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        api = ApiJeu(partie, 99)
        # Un seul tour joué par appel (issue #55) : reste au tour du 2e ordinateur.
        res = api.faire_jouer_ia()
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert res["etat"]["id_partie"] == 99
        assert partie.index_courant == 2
        assert partie.joueur_courant().humain is False

    def test_api_faire_jouer_ia_sans_effet_si_humain(self):
        partie = self._partie_ia()
        partie.index_courant = 0
        api = ApiJeu(partie, None)
        res = api.faire_jouer_ia()
        assert res["nb_tours"] == 0
        assert partie.index_courant == 0


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


class TestNbLignesHistorique:
    """Nombre de lignes d'historique à afficher : min(nb_joueurs * 2, 8)."""

    def test_deux_joueurs(self):
        assert nb_lignes_historique(_partie_simple()) == 4

    def test_quatre_joueurs_plafonne_a_huit(self):
        assert nb_lignes_historique(_partie_quatre_joueurs()) == 8

    def test_un_seul_joueur(self):
        partie = Partie([Joueur(nom="Solo", humain=True)], _DicoFactice(), graine=1)
        assert nb_lignes_historique(partie) == 2


class TestSerialiserHistorique:
    """Exposition de la portion récente de l'historique (issue #37)."""

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

    def test_plafonne_a_huit_meme_a_quatre_joueurs(self):
        partie = _partie_quatre_joueurs()
        # Dix échanges (l'échange ne termine pas la partie) : historique tronqué.
        for _ in range(10):
            _echanger_une_lettre(partie)
        assert len(partie.historique) == 10
        historique = serialiser_historique(partie)
        assert len(historique) == 8

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
        # Même fenêtrage et même ordre que serialiser_historique.
        assert etat["historique"] == serialiser_historique(partie)
        assert len(etat["historique"]) == 8


class TestApiJeuRetourMenu:
    """Tests de ``ApiJeu.retour_menu`` (issue #74).

    Vérifie que la fenêtre de jeu est fermée depuis Python via
    ``window.destroy()`` (fiable sous GTK/WebKit, issues #53/#57) et que le
    drapeau ``_retour_menu`` est positionné pour que ``lancer_jeu`` rouvre
    l'accueil. Testé sans vraie fenêtre grâce à un objet factice.
    """

    def test_retour_menu_appelle_destroy_et_marque_le_drapeau(self):
        class FakeWindow:
            def __init__(self):
                self.detruite = False

            def destroy(self):
                self.detruite = True

        api = ApiJeu(_partie_simple(), id_partie=7)
        fake = FakeWindow()
        api.set_window(fake)

        resultat = api.retour_menu()

        assert resultat["succes"] is True
        assert fake.detruite is True
        assert api._retour_menu is True

    def test_retour_menu_sans_fenetre(self):
        api = ApiJeu(_partie_simple(), id_partie=None)
        resultat = api.retour_menu()

        assert resultat["succes"] is False
        assert "erreur" in resultat
        # Aucune fenêtre : pas de retour au menu déclenché.
        assert api._retour_menu is False

    def test_retour_menu_exception_destroy_naboutit_pas(self):
        class FakeWindow:
            def destroy(self):
                raise RuntimeError("backend HS")

        api = ApiJeu(_partie_simple(), id_partie=1)
        api.set_window(FakeWindow())

        resultat = api.retour_menu()

        assert resultat["succes"] is False
        assert "backend HS" in resultat["erreur"]
        # La fermeture a échoué : on ne rouvrira PAS l'accueil.
        assert api._retour_menu is False


class _FenetreFermable:
    """Fenêtre factice avec un vrai ``events.closing`` pywebview (issue #94).

    Reproduit fidèlement le mécanisme testé : ``events.closing`` est un
    ``webview.event.Event`` réel (donc ``+=`` et ``set()`` se comportent comme en
    production, y compris le passage de la fenêtre émettrice au handler). Et,
    comme le backend GTK où ``destroy()`` repasse par ``close_window`` et
    re-déclenche ``closing``, notre ``destroy()`` **re-émet** l'événement : c'est
    exactement le scénario que le garde-fou anti-boucle doit neutraliser.
    """

    def __init__(self, nom: str) -> None:
        from webview.event import Event

        self.nom = nom
        self.detruite = False
        self.events = type("_Ev", (), {})()
        self.events.closing = Event(self, True)

    def destroy(self) -> None:
        self.detruite = True
        # Comme GTK : la destruction programmatique repasse par ``closing``.
        self.events.closing.set()


def _api_deux_fenetres_fermables() -> tuple[ApiJeu, _FenetreFermable, _FenetreFermable]:
    api = ApiJeu(_partie_simple(), id_partie=3)
    plateau, chevalet = _FenetreFermable("plateau"), _FenetreFermable("chevalet")
    api.set_windows(plateau, chevalet)
    api.installer_fermeture_croisee()
    return api, plateau, chevalet


class TestFermetureCroisee:
    """Fermeture native (croix ✕) de l'une des deux fenêtres — issue #94.

    Fermer nativement une fenêtre doit détruire l'autre (plus d'orpheline) et
    **quitter** l'application (contrairement à « Retour au menu » qui rouvre
    l'accueil) : ``_retour_menu`` reste donc ``False``.
    """

    def test_fermer_plateau_detruit_le_chevalet(self):
        api, plateau, chevalet = _api_deux_fenetres_fermables()
        # Simule la croix sur la fenêtre plateau (GTK émet ``closing``).
        plateau.events.closing.set()
        assert chevalet.detruite is True
        assert api._fermeture_en_cours is True
        # Fermeture par la croix ≠ retour au menu : on ne rouvre pas l'accueil.
        assert api._retour_menu is False

    def test_fermer_chevalet_detruit_le_plateau(self):
        api, plateau, chevalet = _api_deux_fenetres_fermables()
        chevalet.events.closing.set()
        assert plateau.detruite is True
        assert api._retour_menu is False

    def test_pas_de_boucle_infinie(self):
        # ``destroy()`` de la fenêtre jumelle re-émet ``closing`` (comme GTK) : le
        # garde-fou doit empêcher de re-détruire la première fenêtre en retour.
        api, plateau, chevalet = _api_deux_fenetres_fermables()
        plateau.events.closing.set()  # ne doit ni boucler ni lever
        # Le chevalet est détruit une fois ; le plateau n'est pas re-détruit par le
        # handler (il se ferme de lui-même côté backend, pas via ``destroy`` ici).
        assert chevalet.detruite is True
        assert plateau.detruite is False

    def test_installer_tolere_une_fenetre_sans_events(self):
        # Fenêtre factice sans attribut ``events`` (comme les tests historiques) :
        # l'installation ne doit rien lever.
        api = ApiJeu(_partie_simple(), id_partie=None)

        class _Nue:
            def destroy(self):  # pragma: no cover - jamais appelée ici
                pass

        api.set_window(_Nue())
        api.installer_fermeture_croisee()  # ne doit pas lever

    def test_retour_menu_reste_prioritaire(self):
        # « Retour au menu » détruit les deux fenêtres ET rouvre l'accueil : le
        # garde-fou anti-boucle ne doit pas empêcher ``_retour_menu`` de rester vrai
        # malgré les ``closing`` re-émis par les ``destroy()``.
        api, plateau, chevalet = _api_deux_fenetres_fermables()
        resultat = api.retour_menu()
        assert resultat["succes"] is True
        assert plateau.detruite is True
        assert chevalet.detruite is True
        assert api._retour_menu is True


# --------------------------------------------------------------------------- #
# Suite #90 : séparation plateau/chevalet en deux fenêtres. État de pose
# centralisé côté Python (_selection / _en_attente) et diffusion vers la bonne
# fenêtre (payload public au plateau, payload privé au chevalet).
# --------------------------------------------------------------------------- #


class _FenetreEspionne:
    """Fenêtre pywebview factice qui enregistre les appels ``evaluate_js``."""

    def __init__(self) -> None:
        self.scripts: list[str] = []
        self.detruite = False

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)

    def destroy(self) -> None:
        self.detruite = True


def _api_pose(lettres: str = "CHATSER") -> tuple[ApiJeu, _FenetreEspionne, _FenetreEspionne]:
    """API prête pour la pose, avec deux fenêtres espionnes (plateau + chevalet).

    Le joueur 0 (humain, courant) porte le chevalet ``lettres``. Renvoie
    ``(api, fenetre_plateau, fenetre_chevalet)``.
    """
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
    ]
    partie = Partie(joueurs, _DicoMots("CHAT", "CHATS"), graine=1)
    partie.index_courant = 0
    partie.joueurs[0].chevalet = list(lettres)
    api = ApiJeu(partie, None)
    plateau, chevalet = _FenetreEspionne(), _FenetreEspionne()
    api.set_windows(plateau, chevalet)
    return api, plateau, chevalet


class TestApiJeuSelection:
    """``ApiJeu.selectionner_lettre`` : centralisation de ``_selection`` (issue #90)."""

    def test_selectionne_met_a_jour_et_diffuse(self):
        api, plateau, chevalet = _api_pose()
        res = api.selectionner_lettre(2)
        assert res["succes"] is True
        assert api._selection == 2
        # Chaque fenêtre a reçu exactement une diffusion, vers la bonne fonction.
        assert len(plateau.scripts) == 1
        assert len(chevalet.scripts) == 1
        assert "appliquerEtatPlateau" in plateau.scripts[-1]
        assert "appliquerEtatChevalet" in chevalet.scripts[-1]

    def test_reclic_meme_index_deselectionne(self):
        api, _plateau, _chevalet = _api_pose()
        api.selectionner_lettre(2)
        api.selectionner_lettre(2)
        assert api._selection is None

    def test_index_none_annule_la_selection(self):
        api, _plateau, _chevalet = _api_pose()
        api.selectionner_lettre(1)
        api.selectionner_lettre(None)
        assert api._selection is None


class TestApiJeuPoseEnAttente:
    """Pose/retrait d'une lettre en attente pilotés par l'état interne (issue #90)."""

    def test_pose_resout_la_lettre_depuis_la_selection(self):
        api, plateau, chevalet = _api_pose("CHATSER")
        api.selectionner_lettre(0)  # « C »
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert (place["ligne"], place["colonne"]) == (7, 7)
        assert place["lettre"] == "C"
        assert place["joker"] is False
        assert place["index"] == 0
        # La sélection est consommée et l'état rediffusé aux deux fenêtres.
        assert api._selection is None
        assert "appliquerEtatPlateau" in plateau.scripts[-1]
        assert "appliquerEtatChevalet" in chevalet.scripts[-1]

    def test_pose_sans_selection_refusee(self):
        api, _plateau, _chevalet = _api_pose()
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert api._en_attente == []

    def test_pose_sur_case_occupee_refusee(self):
        api, _plateau, _chevalet = _api_pose()
        api._partie.plateau.poser_tuile(7, 7, Tuile("Z"))
        api.selectionner_lettre(0)
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert api._en_attente == []

    def test_pose_hors_plateau_refusee(self):
        api, _plateau, _chevalet = _api_pose()
        api.selectionner_lettre(0)
        res = api.poser_lettre_en_attente(-1, 7)
        assert res["succes"] is False

    def test_deux_lettres_sur_la_meme_case_refusee(self):
        api, _plateau, _chevalet = _api_pose()
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert len(api._en_attente) == 1

    def test_retrait_supprime_le_placement_et_diffuse(self):
        api, plateau, chevalet = _api_pose()
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        avant_plateau = len(plateau.scripts)
        res = api.retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert api._en_attente == []
        # Le retrait effectif rediffuse l'état.
        assert len(plateau.scripts) == avant_plateau + 1

    def test_retrait_sans_placement_ne_diffuse_pas(self):
        api, plateau, _chevalet = _api_pose()
        avant = len(plateau.scripts)
        res = api.retirer_lettre_en_attente(0, 0)
        assert res["succes"] is True
        assert len(plateau.scripts) == avant  # aucune mutation, aucune diffusion

    def test_annuler_pose_vide_tout_et_diffuse(self):
        api, plateau, chevalet = _api_pose()
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        res = api.annuler_pose()
        assert res["succes"] is True
        assert api._en_attente == []
        assert api._selection is None
        assert "appliquerEtatPlateau" in plateau.scripts[-1]
        assert "appliquerEtatChevalet" in chevalet.scripts[-1]


class TestApiJeuPoseJoker:
    """Pose d'un joker : la modale de choix s'ouvre côté chevalet (issue #90)."""

    def test_clic_plateau_sur_joker_differe_la_pose(self):
        api, _plateau, _chevalet = _api_pose(JOKER + "CHATSE")
        api.selectionner_lettre(0)  # le joker
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert res["joker_requis"] is True
        # Rien n'est encore posé ; la case visée est mémorisée pour le chevalet.
        assert api._en_attente == []
        assert api._joker_demande == {"ligne": 7, "colonne": 7, "index": 0}

    def test_finalisation_joker_depuis_le_chevalet(self):
        api, _plateau, _chevalet = _api_pose(JOKER + "CHATSE")
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # Le chevalet renvoie la lettre choisie pour le joker.
        res = api.poser_lettre_en_attente(7, 7, lettre="E", joker=True, valeur=0, index=0)
        assert res["succes"] is True
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert place["lettre"] == "E"
        assert place["joker"] is True
        assert place["valeur"] == 0
        assert api._joker_demande is None


class TestApiJeuRemplacementEnAttente:
    """Remplacement d'une lettre en attente au clic, avec sélection (issue #129).

    Un clic sur une case portant une lettre en attente du tour courant passe
    désormais par ``remplacer_ou_retirer_lettre_en_attente`` : avec une lettre
    sélectionnée, la sélection prend la place et l'ancienne revient au chevalet ;
    sans sélection, le comportement de retrait simple est préservé.
    """

    def test_remplacement_avec_selection(self):
        api, plateau, chevalet = _api_pose("CHATSER")
        # « C » (index 0) posée en 7,7.
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # On sélectionne « H » (index 1) et on reclique la case : remplacement.
        api.selectionner_lettre(1)
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        # Une seule lettre en attente : la nouvelle, à la même place.
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert (place["ligne"], place["colonne"]) == (7, 7)
        assert place["lettre"] == "H"
        assert place["index"] == 1
        assert place["joker"] is False
        # L'ancienne lettre (index 0) n'est plus consommée : de nouveau disponible.
        assert all(p["index"] != 0 for p in api._en_attente)
        # La sélection est consommée et l'état rediffusé aux deux fenêtres.
        assert api._selection is None
        assert "appliquerEtatPlateau" in plateau.scripts[-1]
        assert "appliquerEtatChevalet" in chevalet.scripts[-1]

    def test_remplacement_ne_casse_pas_le_compteur(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        # Deux lettres posées : « C » (0) en 7,7 et « H » (1) en 7,8.
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        api.poser_lettre_en_attente(7, 8)
        # On remplace « C » par « A » (index 2) : le compteur reste à 2.
        api.selectionner_lettre(2)
        api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert len(api._en_attente) == 2
        indices = sorted(p["index"] for p in api._en_attente)
        assert indices == [1, 2]  # « C » (0) libérée, « A » (2) posée, « H » (1) intacte

    def test_sans_selection_retrait_simple(self):
        api, plateau, _chevalet = _api_pose("CHATSER")
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # Aucune sélection active au moment du clic : retrait simple (cas limite 1).
        assert api._selection is None
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert api._en_attente == []
        assert res.get("joker_requis") is None

    def test_remplacement_par_joker_ouvre_la_modale(self):
        api, _plateau, chevalet = _api_pose("C" + JOKER + "ATSER")
        # « C » (index 0) posée en 7,7, puis on sélectionne le joker (index 1).
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert res["joker_requis"] is True
        # La pose du joker est différée : l'ancienne lettre reste en place tant que
        # la modale n'est pas validée, et la case est mémorisée pour le chevalet.
        assert api._joker_demande == {"ligne": 7, "colonne": 7, "index": 1}
        assert len(api._en_attente) == 1
        assert api._en_attente[0]["lettre"] == "C"
        # Finalisation depuis le chevalet : le joker remplace l'ancienne lettre.
        api.poser_lettre_en_attente(7, 7, lettre="E", joker=True, valeur=0, index=1)
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert place["lettre"] == "E"
        assert place["joker"] is True
        assert place["index"] == 1
        assert api._joker_demande is None

    def test_case_sans_lettre_en_attente_sans_effet(self):
        api, plateau, _chevalet = _api_pose("CHATSER")
        api.selectionner_lettre(0)
        avant = len(plateau.scripts)
        res = api.remplacer_ou_retirer_lettre_en_attente(0, 0)
        assert res["succes"] is True
        assert api._en_attente == []
        # Aucune mutation : la sélection reste intacte, rien n'est rediffusé.
        assert api._selection == 0
        assert len(plateau.scripts) == avant

    def test_remplacement_hors_tour_refuse(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # On passe hors tour : la mutation doit être refusée sans toucher l'état.
        api._partie.index_courant = 1
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert len(api._en_attente) == 1


class TestApiJeuGardeDeTour:
    """Mutations de pose refusées hors du tour du joueur de référence (issue #99).

    Le chevalet est désormais toujours visible et sélectionnable, mais toute
    mutation de l'état de pose reste réservée au tour réel : la garde
    :meth:`ApiJeu._refuser_hors_tour` doit refuser proprement sans toucher à
    ``_selection`` / ``_en_attente``.
    """

    def _api_hors_tour(self):
        """API où le joueur de référence (index 0) n'est PAS courant (tour IA)."""
        api, plateau, chevalet = _api_pose("CHATSER")
        api._partie.index_courant = 1  # au tour de l'ordinateur
        return api, plateau, chevalet

    def test_selectionner_lettre_hors_tour_refusee(self):
        api, plateau, chevalet = self._api_hors_tour()
        avant_plateau = len(plateau.scripts)
        res = api.selectionner_lettre(0)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._selection is None  # état de pose intact
        # Aucune diffusion : l'état n'a pas bougé.
        assert len(plateau.scripts) == avant_plateau

    def test_poser_lettre_en_attente_hors_tour_refusee(self):
        api, _plateau, _chevalet = self._api_hors_tour()
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._en_attente == []

    def test_retirer_lettre_en_attente_hors_tour_refusee(self):
        api, _plateau, _chevalet = self._api_hors_tour()
        # On injecte un placement pour vérifier qu'il n'est PAS retiré hors tour.
        api._en_attente = [
            {"ligne": 7, "colonne": 7, "lettre": "C", "joker": False,
             "valeur": 3, "index": 0}
        ]
        res = api.retirer_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert len(api._en_attente) == 1  # placement intact

    def test_annuler_pose_hors_tour_refusee(self):
        api, _plateau, _chevalet = self._api_hors_tour()
        api._selection = 2
        api._en_attente = [
            {"ligne": 7, "colonne": 7, "lettre": "C", "joker": False,
             "valeur": 3, "index": 0}
        ]
        res = api.annuler_pose()
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._selection == 2  # état de pose intact
        assert len(api._en_attente) == 1

    def test_mutation_refusee_partie_terminee(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        api._partie.index_courant = 0  # c'est bien le tour du joueur de référence
        api._partie.terminee = True
        res = api.selectionner_lettre(0)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._selection is None

    def test_mutation_autorisee_au_tour_du_joueur_reference(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        api._partie.index_courant = 0  # tour du joueur de référence
        res = api.selectionner_lettre(0)
        assert res["succes"] is True
        assert api._selection == 0


class TestApiJeuDiffusionConfidentialite:
    """``_diffuser`` : payload public au plateau, payload privé au chevalet (#90)."""

    def test_payload_plateau_public_sans_lettres_de_chevalet(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        etat = api._etat_plateau()
        # Aucune identité de lettre de chevalet : ni au niveau racine, ni par joueur.
        assert "lettres" not in etat
        for joueur_pub in etat["joueurs"]:
            assert "lettres" not in joueur_pub
        # En revanche l'état de pose neutre (sélection, placements) y figure.
        assert "en_attente" in etat
        assert "selection" in etat

    def test_payload_chevalet_contient_les_lettres_privees(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        etat = api._etat_chevalet()
        lettres = [c["lettre"] for c in etat["lettres"]]
        assert lettres == list("CHATSER")
        assert etat["selection"] is None
        assert etat["en_attente"] == []
        # Au tour du joueur de référence : mon_tour est vrai (issue #99).
        assert etat["mon_tour"] is True
        assert etat["index_reference"] == 0
        # Champs supprimés (issue #99) : plus de tour_humain ni nb_humains.
        assert "tour_humain" not in etat
        assert "nb_humains" not in etat

    def test_chevalet_reference_toujours_expose_au_tour_ia(self):
        """Au tour de l'IA, le chevalet du joueur de référence reste exposé.

        Le panneau est toujours visible (issue #99) : ``lettres`` porte bien le
        chevalet du joueur humain de référence (jamais celui de l'IA) et
        ``mon_tour`` vaut ``False`` puisque ce n'est pas son tour.
        """
        api, _plateau, _chevalet = _api_pose("CHATSER")
        api._partie.index_courant = 1  # au tour de l'ordinateur
        etat = api._etat_chevalet()
        lettres = [c["lettre"] for c in etat["lettres"]]
        assert lettres == list("CHATSER")  # chevalet du joueur de référence
        assert etat["index_reference"] == 0  # jamais l'index de l'IA
        assert etat["mon_tour"] is False

    def test_chevalet_ordinateur_jamais_expose(self):
        """Le chevalet d'un ordinateur n'est jamais sérialisé (issue #35/#99).

        Même au tour de l'IA, ``lettres`` reste le chevalet du joueur de
        référence (index 0), jamais celui de l'ordinateur (index 1).
        """
        api, _plateau, _chevalet = _api_pose("CHATSER")
        api._partie.joueurs[1].chevalet = list("ZZZZZZZ")  # chevalet IA distinct
        api._partie.index_courant = 1  # au tour de l'ordinateur
        etat = api._etat_chevalet()
        lettres = [c["lettre"] for c in etat["lettres"]]
        assert lettres == list("CHATSER")  # celui du joueur de référence
        assert "Z" not in lettres  # jamais le chevalet de l'IA
        assert etat["mon_tour"] is False

    def test_diffusion_route_le_bon_payload_vers_la_bonne_fenetre(self):
        api, plateau, chevalet = _api_pose("CHATSER")
        api._diffuser()
        script_plateau = plateau.scripts[-1]
        script_chevalet = chevalet.scripts[-1]
        assert "appliquerEtatPlateau" in script_plateau
        assert "appliquerEtatChevalet" in script_chevalet
        # Le script du plateau ne transporte AUCUNE liste de lettres de chevalet ;
        # celui du chevalet, si (clé JSON "lettres").
        assert '"lettres"' not in script_plateau
        assert '"lettres"' in script_chevalet

    def test_fenetre_absente_ne_bloque_pas_la_diffusion(self):
        api, _plateau, _chevalet = _api_pose()
        api.set_windows(None, None)  # plus aucune fenêtre
        # Ne doit pas lever, même sans fenêtre à qui pousser l'état.
        api._diffuser()


class TestApiJeuPoseViaEtatInterne:
    """``poser_mot``/``verifier_coup`` lisent ``_en_attente`` (issue #90)."""

    def test_poser_mot_sans_argument_lit_l_etat_interne(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        for i, (lig, col, let) in enumerate(
            [(7, 7, "C"), (7, 8, "H"), (7, 9, "A"), (7, 10, "T")]
        ):
            api.selectionner_lettre(i)
            api.poser_lettre_en_attente(lig, col)
        res = api.poser_mot()  # aucun placement passé : lecture de _en_attente
        assert res["succes"] is True
        assert "etat" in res
        # Après un coup joué, l'état de pose est remis à zéro.
        assert api._en_attente == []
        assert api._selection is None

    def test_verifier_coup_sans_argument_lit_l_etat_interne(self):
        api, _plateau, _chevalet = _api_pose("CHATSER")
        for i, (lig, col, _let) in enumerate(
            [(7, 7, "C"), (7, 8, "H"), (7, 9, "A"), (7, 10, "T")]
        ):
            api.selectionner_lettre(i)
            api.poser_lettre_en_attente(lig, col)
        res = api.verifier_coup()  # non destructif : ne consomme pas l'attente
        assert res["succes"] is True
        assert res["detail"]["mots"][0]["texte"] == "CHAT"
        assert len(api._en_attente) == 4  # rien n'est consommé
        assert api._partie.plateau.case_vide(7, 7)

    def test_poser_mot_reussi_diffuse_le_nouvel_etat(self):
        api, plateau, chevalet = _api_pose("CHATSER")
        for i, (lig, col) in enumerate([(7, 7), (7, 8), (7, 9), (7, 10)]):
            api.selectionner_lettre(i)
            api.poser_lettre_en_attente(lig, col)  # « CHAT »
        avant = len(plateau.scripts)
        res = api.poser_mot()
        assert res["succes"] is True
        # Le coup joué rediffuse aux deux fenêtres.
        assert len(plateau.scripts) > avant
        assert "appliquerEtatChevalet" in chevalet.scripts[-1]


class TestApiJeuRetourMenuDeuxFenetres:
    """``retour_menu`` détruit les DEUX fenêtres (issue #90)."""

    def test_detruit_plateau_et_chevalet(self):
        api, plateau, chevalet = _api_pose()
        res = api.retour_menu()
        assert res["succes"] is True
        assert plateau.detruite is True
        assert chevalet.detruite is True
        assert api._retour_menu is True

    def test_retour_menu_avec_seule_fenetre_plateau(self):
        # Compat mono-fenêtre : set_window ne renseigne que le plateau.
        api = ApiJeu(_partie_simple(), id_partie=1)
        fake = _FenetreEspionne()
        api.set_window(fake)
        res = api.retour_menu()
        assert res["succes"] is True
        assert fake.detruite is True


# --------------------------------------------------------------------------- #
# Suite #81 : persistance des actions de jeu (branchement de enregistrer_action
# et finaliser_partie dans ApiJeu) et reprise fidèle de l'état.
# --------------------------------------------------------------------------- #

# Lexique de mots plausibles à poser en ouverture (partagé avec test_persistance
# dans l'esprit) : il en faut assez pour qu'une graine « ouvrable » — dont le
# chevalet initial forme l'un des mots — se trouve rapidement.
_MOTS_E2E = [
    "CADRE", "MAISON", "TOMATE", "AIRE", "POSER", "LIRE", "SEL", "OSE",
    "TON", "NOTE", "ROI", "SIROP", "RATE", "TIARE", "SATIRE", "RETINE",
    "OURS", "PORTE", "RAISON", "TISANE", "SENIOR", "RONDE", "AMIE", "RIDE",
]


def _trie_e2e() -> Trie:
    return Trie.depuis_iterable(_MOTS_E2E)


def _partie_ouvrable_e2e(trie: Trie, **kwargs) -> tuple[Partie, int, str]:
    """Partie dont le joueur 0 (humain) peut poser un mot de :data:`_MOTS_E2E`.

    Balaie les graines jusqu'à en trouver une où le chevalet initial du premier
    joueur contient les lettres d'un mot connu. Renvoie ``(partie, graine, mot)``.
    """
    for graine in range(2000):
        partie = creer_partie(["Alice"], trie, graine=graine, **kwargs)
        disponibles = Counter(partie.joueur_courant().chevalet)
        for mot in _MOTS_E2E:
            if all(disponibles[lettre] >= n for lettre, n in Counter(mot).items()):
                return partie, graine, mot
    raise AssertionError("Aucune graine ouvrable trouvée dans l'intervalle testé.")


def _placements_mot_horizontal(mot: str, ligne: int = 7, colonne: int = 7) -> list:
    """Placements JS simulés posant ``mot`` à l'horizontale depuis (ligne, colonne)."""
    return [_placement(ligne, colonne + i, lettre) for i, lettre in enumerate(mot)]


def _snapshot_partie(partie: Partie) -> dict:
    """Capture comparable de l'état vivant d'une partie (plateau, chevalets…)."""
    return {
        "cases": partie.plateau._cases,
        "chevalets": [list(j.chevalet) for j in partie.joueurs],
        "scores": [j.score for j in partie.joueurs],
        "sac": list(partie.sac._jetons),
        "index_courant": partie.index_courant,
        "passes": partie.passes_consecutives,
        "terminee": partie.terminee,
    }


class TestApiPersisteLesActions:
    """Chaque action réussie appelle ``enregistrer_action`` (espion, sans base)."""

    def _api_avec_chevalet(
        self, lettres: str, mots: tuple[str, ...], id_partie: int
    ) -> ApiJeu:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots(*mots), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list(lettres)
        return ApiJeu(partie, id_partie)

    def _espionner(self, monkeypatch) -> list:
        """Remplace ``enregistrer_action`` par un espion ; renvoie la liste d'appels."""
        appels: list = []
        monkeypatch.setattr(
            "scrabble.ui.jeu.enregistrer_action",
            lambda *args, **kw: appels.append(args),
        )
        return appels

    def test_poser_mot_enregistre_l_action(self, monkeypatch):
        appels = self._espionner(monkeypatch)
        api = self._api_avec_chevalet("CHATSER", ("CHAT",), id_partie=7)
        res = api.poser_mot(_placements_mot_horizontal("CHAT"))
        assert res["succes"] is True
        # Un seul appel, avec le bon id et l'entrée d'historique tout juste créée.
        assert len(appels) == 1
        id_partie, entree = appels[0][0], appels[0][1]
        assert id_partie == 7
        assert entree is api._partie.historique[-1]
        assert entree.action == "coup"

    def test_poser_mot_echec_ne_persiste_rien(self, monkeypatch):
        appels = self._espionner(monkeypatch)
        # « XYZ » n'est pas dans le dictionnaire : coup refusé, rien à persister.
        api = self._api_avec_chevalet("XYZWKQJ", ("CHAT",), id_partie=7)
        res = api.poser_mot(_placements_mot_horizontal("XYZ"))
        assert res["succes"] is False
        assert appels == []

    def test_echanger_tout_enregistre_l_action(self, monkeypatch):
        appels = self._espionner(monkeypatch)
        api = self._api_avec_chevalet("ABCDEFG", ("CHAT",), id_partie=9)
        res = api.echanger_tout()
        assert res["succes"] is True
        assert len(appels) == 1
        id_partie, entree = appels[0][0], appels[0][1]
        assert id_partie == 9
        assert entree is api._partie.historique[-1]
        assert entree.action == "echange"

    def test_faire_jouer_ia_enregistre_l_action(self, monkeypatch):
        appels = self._espionner(monkeypatch)
        trie = _trie_e2e()
        partie, _graine, _mot = _partie_ouvrable_e2e(trie, nb_ia=1)
        partie.index_courant = 1  # au tour de l'ordinateur
        api = ApiJeu(partie, id_partie=11)
        res = api.faire_jouer_ia()
        assert res["nb_tours"] == 1
        # Un tour d'ordinateur = exactement une entrée persistée (coup ou passe).
        assert len(appels) == 1
        id_partie, entree = appels[0][0], appels[0][1]
        assert id_partie == 11
        assert entree is api._partie.historique[-1]

    def test_mode_demo_sans_id_ne_persiste_pas(self, monkeypatch):
        appels = self._espionner(monkeypatch)
        # id_partie None (mode démonstration) : aucune écriture tentée.
        api = self._api_avec_chevalet("CHATSER", ("CHAT",), id_partie=None)
        res = api.poser_mot(_placements_mot_horizontal("CHAT"))
        assert res["succes"] is True
        assert appels == []


class TestApiRepriseBoutEnBout:
    """De bout en bout : actions via l'API → reprise fidèle depuis une vraie base."""

    def test_reprise_restitue_l_etat_reel(self, tmp_path):
        chemin = tmp_path / "parties.db"
        trie = _trie_e2e()
        partie, _graine, mot = _partie_ouvrable_e2e(trie, nb_ia=1)
        id_partie = demarrer_suivi(partie, chemin)
        api = ApiJeu(partie, id_partie, chemin)

        # 1) Le joueur humain pose le mot d'ouverture.
        res = api.poser_mot(_placements_mot_horizontal(mot))
        assert res["succes"] is True
        # 2) L'ordinateur joue son tour.
        res_ia = api.faire_jouer_ia()
        assert res_ia["nb_tours"] == 1

        # La reprise rejoue les actions persistées : état reconstruit identique.
        reprise = reprendre_partie(id_partie, trie, chemin)
        assert _snapshot_partie(reprise) == _snapshot_partie(api._partie)
        # Preuve que le plateau reconstruit n'est PAS vide (régression #81).
        assert not reprise.plateau.case_vide(7, 7)

    def test_reprise_sans_persistance_reconstruirait_un_plateau_vide(self, tmp_path):
        # Contre-preuve du bug d'origine : sans action enregistrée, la reprise
        # d'une partie tout juste suivie rend un plateau vide.
        chemin = tmp_path / "parties.db"
        trie = _trie_e2e()
        partie, _graine, _mot = _partie_ouvrable_e2e(trie, nb_ia=1)
        id_partie = demarrer_suivi(partie, chemin)
        reprise = reprendre_partie(id_partie, trie, chemin)
        assert reprise.plateau.case_vide(7, 7)


class TestApiFinaliseEnFinDePartie:
    """Fin de partie : ``finaliser_partie`` marque le statut et les scores finaux."""

    def _partie_qui_se_termine(self) -> Partie:
        """Partie où poser « LE » au centre vide le chevalet et le sac (→ terminée)."""
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoMots("LE"), graine=42)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = ["L", "E"]
        partie.joueurs[1].chevalet = ["A", "B"]
        # Sac vidé : après le coup, aucun réapprovisionnement → partie terminée.
        partie.sac._jetons = []
        return partie

    def test_fin_de_partie_marquee_en_base(self, tmp_path):
        chemin = tmp_path / "parties.db"
        partie = self._partie_qui_se_termine()
        id_partie = demarrer_suivi(partie, chemin)
        api = ApiJeu(partie, id_partie, chemin)

        res = api.poser_mot(_placements_mot_horizontal("LE"))
        assert res["succes"] is True
        assert api._partie.terminee is True

        resumes = {r.id: r for r in lister_parties(chemin)}
        resume = resumes[id_partie]
        assert resume.statut == STATUT_TERMINEE
        assert resume.scores_finaux == [j.score for j in partie.joueurs]

    def test_finaliser_appelee_une_seule_fois(self, tmp_path, monkeypatch):
        chemin = tmp_path / "parties.db"
        partie = self._partie_qui_se_termine()
        id_partie = demarrer_suivi(partie, chemin)
        api = ApiJeu(partie, id_partie, chemin)

        appels: list = []
        monkeypatch.setattr(
            "scrabble.ui.jeu.finaliser_partie",
            lambda *args, **kw: appels.append(args),
        )
        api.poser_mot(_placements_mot_horizontal("LE"))
        # Une action « sans effet » rejouée après la fin ne refinalise pas.
        api.faire_jouer_ia()
        assert len(appels) == 1
        assert appels[0][0] == id_partie


class TestPersistanceEchecResteVisible:
    """Un échec d'écriture est journalisé (visible), sans casser l'action de jeu."""

    def _api_avec_chevalet(self, lettres: str, mots: tuple[str, ...]) -> ApiJeu:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots(*mots), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list(lettres)
        return ApiJeu(partie, id_partie=5)

    def test_echec_ecriture_journalise_et_action_reste_valide(self, monkeypatch):
        erreurs: list = []
        monkeypatch.setattr(
            "scrabble.ui.jeu.journal.erreur",
            lambda message, exc=None: erreurs.append((message, exc)),
        )

        def _echoue(*args, **kw):
            raise RuntimeError("base indisponible")

        monkeypatch.setattr("scrabble.ui.jeu.enregistrer_action", _echoue)

        api = self._api_avec_chevalet("CHATSER", ("CHAT",))
        res = api.poser_mot(_placements_mot_horizontal("CHAT"))

        # L'action de jeu reste valide côté joueur malgré l'échec d'écriture…
        assert res["succes"] is True
        assert api._partie.index_courant == 1
        # … mais l'échec est visible dans le journal (pas avalé silencieusement).
        assert len(erreurs) == 1
        message, exc = erreurs[0]
        assert "partie #5" in message
        assert isinstance(exc, RuntimeError)


class _FenetreDeplacable:
    """Fenêtre pywebview factice avec position (x, y) et ``move`` (issue #91).

    Sert aux tests du déplacement applicatif de la fenêtre chevalet. ``move`` met à
    jour la position lue par ``x``/``y``, comme le fait réellement pywebview.
    """

    def __init__(self, x: int = 0, y: int = 0) -> None:
        self.x = x
        self.y = y

    def evaluate_js(self, script: str) -> None:  # pour _diffuser
        pass

    def move(self, x: int, y: int) -> None:
        self.x = int(x)
        self.y = int(y)


class TestDeplacementChevalet:
    """Déplacement applicatif de la fenêtre chevalet (issue #91 point 2)."""

    def _api(self):
        joueurs = [Joueur(nom="Alice", humain=True)]
        partie = Partie(joueurs, _DicoFactice(), graine=1)
        api = ApiJeu(partie, None)
        fen = _FenetreDeplacable(x=200, y=500)
        api.set_windows(_FenetreEspionne(), fen)
        return api, fen

    def test_debut_deplacement_renvoie_position_courante(self):
        api, fen = self._api()
        res = api.debut_deplacement_chevalet()
        assert res == {"succes": True, "x": 200, "y": 500}

    def test_debut_deplacement_sans_fenetre(self):
        joueurs = [Joueur(nom="Alice", humain=True)]
        api = ApiJeu(Partie(joueurs, _DicoFactice(), graine=1), None)
        assert api.debut_deplacement_chevalet()["succes"] is False

    def test_deplacer_deplace_la_fenetre_en_absolu(self):
        api, fen = self._api()
        res = api.deplacer_chevalet(340, 610)
        assert res["succes"] is True
        assert (fen.x, fen.y) == (340, 610)

    def test_deplacer_borne_en_entiers(self):
        api, fen = self._api()
        api.deplacer_chevalet(12.9, 30.2)
        assert (fen.x, fen.y) == (12, 30)

    def test_deplacer_sans_fenetre_echoue_proprement(self):
        joueurs = [Joueur(nom="Alice", humain=True)]
        api = ApiJeu(Partie(joueurs, _DicoFactice(), graine=1), None)
        assert api.deplacer_chevalet(1, 2)["succes"] is False


class _NatifEspion:
    """Faux ``Gtk.Window`` : espionne ``set_transient_for`` / ``set_type_hint``."""

    def __init__(self) -> None:
        self.transient_for = "NON-APPELE"
        self.type_hints: list = []

    def set_transient_for(self, parent) -> None:
        self.transient_for = parent

    def set_type_hint(self, hint) -> None:
        self.type_hints.append(hint)


class _FenetreNative:
    """Fenêtre factice dotée (ou non) d'un faux attribut ``.native`` — issue #105."""

    def __init__(self, native=None) -> None:
        if native is not None:
            self.native = native


class TestLierChevaletAuPlateau:
    """Liaison transiente chevalet↔plateau via ``set_transient_for`` (issue #105)."""

    def test_appelle_set_transient_for_avec_le_plateau_natif(self, monkeypatch):
        from scrabble.ui import jeu as mod

        # Neutralise l'attente de ``shown`` (fenêtres factices sans events).
        monkeypatch.setattr(mod, "_attendre_fenetre_affichee", lambda *a, **k: None)
        natif_plateau = _NatifEspion()
        natif_chevalet = _NatifEspion()
        plateau = _FenetreNative(natif_plateau)
        chevalet = _FenetreNative(natif_chevalet)

        mod._lier_chevalet_au_plateau(plateau, chevalet)

        # Le chevalet est déclaré transient de la fenêtre native du plateau.
        assert natif_chevalet.transient_for is natif_plateau

    def test_tolere_une_fenetre_sans_native(self, monkeypatch):
        from scrabble.ui import jeu as mod

        monkeypatch.setattr(mod, "_attendre_fenetre_affichee", lambda *a, **k: None)
        plateau = _FenetreNative()  # aucune ``.native``
        chevalet = _FenetreNative(_NatifEspion())

        # Ne doit pas lever : la liaison est simplement ignorée.
        mod._lier_chevalet_au_plateau(plateau, chevalet)


class TestDimensionsChevalet:
    """La fenêtre chevalet est assez large pour Brouillon + « À jouer » (point 4)."""

    def test_position_centree_et_basse_sur_ecran_connu(self, monkeypatch):
        from scrabble.ui import jeu as mod

        class _Ecran:
            width = 1920
            height = 1080

        monkeypatch.setattr(mod.webview, "screens", [_Ecran()])
        x, y = mod._position_chevalet()
        assert x == (1920 - CHEVALET_LARGEUR) // 2
        assert y == 1080 - CHEVALET_HAUTEUR - mod.CHEVALET_MARGE_BAS

    def test_repli_neutre_si_aucun_ecran(self, monkeypatch):
        from scrabble.ui import jeu as mod

        monkeypatch.setattr(mod.webview, "screens", [])
        assert mod._position_chevalet() == (100, 100)

    def test_largeur_suffisante_pour_le_contenu(self):
        # Garde-fou largeur (issue #94, épuré #102, resserré #104, #106) : le contenu
        # le plus large est le titre du panneau (~418 px, ~470 px paddings compris) ;
        # la rangée FIXE de 9 cases réclame 460 px — PLANCHER dur (mesuré : à 460 px la
        # rangée se comprime déjà, retombant à 406 px). #104 avait fixé 540 px, #106 a
        # resserré à 480 px : au-dessus de 470 px le titre reste sur une ligne, et
        # ~20 px de marge subsistent sur le plancher de 460 px. La borne basse (460 px)
        # interdit de compromettre la rangée ; la borne haute empêche un retour à
        # l'espace vide notable de #102/#104 (540-620 px) puis à la mise en page à deux
        # blocs (~880 px).
        assert 460 <= CHEVALET_LARGEUR <= 560

    def test_hauteur_suffisante_pour_le_contenu(self):
        # Garde-fou hauteur (issue #94, revu #100, épuré #102, resserré #104, #106) :
        # la fenêtre ne contient que la barre de déplacement (~35 px) et le panneau de
        # 9 cases (~98 px + padding) — le contenu descend à ~141 px sur une ligne de
        # titre, ~166 px si le titre se replie sur 2 lignes. #106 recentre le cadre
        # verticalement (``justify-content: center``) : avec les 16 px de padding
        # vertical, contenir le cas replié sans défilement impose ~173 px (35 + 122 +
        # 16). On garde 175 px (le recentrage rend le vert symétrique, il n'est plus
        # utile de rogner la hauteur). La borne basse (172 px) garantit l'absence de
        # coupe/défilement même titre replié ; la borne haute empêche un retour au vide
        # antérieur (~190/300 px).
        assert 172 <= CHEVALET_HAUTEUR <= 200


class _FenetreShown:
    """Fenêtre factice exposant ``events.shown.wait`` (comme pywebview) — issue #92."""

    class _Events:
        class _Shown:
            def __init__(self) -> None:
                self.attentes: list = []

            def wait(self, timeout=None):
                self.attentes.append(timeout)
                return True

        def __init__(self) -> None:
            self.shown = _FenetreShown._Events._Shown()

    def __init__(self, x: int = 0, y: int = 0) -> None:
        self.x = x
        self.y = y
        self.events = _FenetreShown._Events()
        self.moves: list = []

    def move(self, x: int, y: int) -> None:
        self.x, self.y = int(x), int(y)
        self.moves.append((self.x, self.y))


class TestRepositionnementChevalet:
    """Callback de repositionnement différé + attente d'affichage (issue #92 point 1)."""

    def _ecran(self, monkeypatch, larg=1920, haut=1080):
        from scrabble.ui import jeu as mod

        class _Ecran:
            width = larg
            height = haut

        monkeypatch.setattr(mod.webview, "screens", [_Ecran()])

    def _capturer_info(self, monkeypatch):
        infos: list = []
        monkeypatch.setattr(
            "scrabble.ui.jeu.journal.info", lambda message: infos.append(message)
        )
        return infos

    def test_callback_attendu_atteint_et_deplace(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)
        infos = self._capturer_info(monkeypatch)
        fen = _FenetreShown(x=100, y=100)
        mod._repositionner_chevalet(fen)
        # La fenêtre a bien été déplacée vers la position bas-centre calculée.
        x_attendu = (1920 - CHEVALET_LARGEUR) // 2
        y_attendu = 1080 - CHEVALET_HAUTEUR - mod.CHEVALET_MARGE_BAS
        assert fen.moves == [(x_attendu, y_attendu)]
        # Traces explicites : callback atteint + position lue après move.
        assert any("_repositionner_chevalet atteint" in m for m in infos)
        assert any("position lue après move" in m for m in infos)

    def test_attend_l_affichage_avant_de_deplacer(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)
        self._capturer_info(monkeypatch)
        fen = _FenetreShown()
        mod._repositionner_chevalet(fen)
        # On a bien attendu l'événement ``shown`` (au moins un appel à wait).
        assert fen.events.shown.attentes  # non vide

    def test_attente_toleree_sans_events(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)
        infos = self._capturer_info(monkeypatch)
        # _FenetreDeplacable n'a pas d'attribut ``events`` : pas d'attente, pas de plantage.
        fen = _FenetreDeplacable(x=100, y=100)
        mod._repositionner_chevalet(fen)
        assert any("'shown' indisponible" in m for m in infos)
        assert (fen.x, fen.y) != (100, 100)  # déplacée malgré tout


class TestTracesDeplacementChevalet:
    """Traces du glisser-déposer applicatif (issue #92 point 2)."""

    def _api(self):
        joueurs = [Joueur(nom="Alice", humain=True)]
        api = ApiJeu(Partie(joueurs, _DicoFactice(), graine=1), None)
        api.set_windows(_FenetreEspionne(), _FenetreDeplacable(x=200, y=500))
        return api

    def test_debut_journalise_et_premier_deplacement_seulement(self, monkeypatch):
        infos: list = []
        monkeypatch.setattr(
            "scrabble.ui.jeu.journal.info", lambda message: infos.append(message)
        )
        api = self._api()
        api.debut_deplacement_chevalet()
        api.deplacer_chevalet(210, 505)
        api.deplacer_chevalet(220, 510)
        api.deplacer_chevalet(230, 515)
        assert any("début de déplacement" in m for m in infos)
        # Une seule trace de déplacement (le premier), pas une par frame.
        assert sum("premier déplacement" in m for m in infos) == 1


class _FenetrePlateauFactice:
    """Fenêtre plateau factice : enregistre maximize/restore/resize/move (issue #95).

    Expose ``events.shown.wait`` comme pywebview pour vérifier que
    :func:`_maximiser_plateau` attend bien l'affichage avant d'agir, et journalise
    l'ordre des appels dans ``self.appels`` pour contrôler le contournement XWayland
    (dé-iconification, puis maximisation native, puis déploiement resize+move).
    """

    class _Events:
        class _Shown:
            def __init__(self) -> None:
                self.attentes: list = []

            def wait(self, timeout=None):
                self.attentes.append(timeout)
                return True

        def __init__(self) -> None:
            self.shown = _FenetrePlateauFactice._Events._Shown()

    def __init__(self) -> None:
        self.events = _FenetrePlateauFactice._Events()
        self.appels: list = []

    def restore(self) -> None:
        self.appels.append(("restore",))

    def maximize(self) -> None:
        self.appels.append(("maximize",))

    def resize(self, largeur, hauteur) -> None:
        self.appels.append(("resize", int(largeur), int(hauteur)))

    def move(self, x, y) -> None:
        self.appels.append(("move", int(x), int(y)))


class TestMaximiserPlateau:
    """Déploiement plein écran du plateau après démarrage (issue #95 point B)."""

    def test_deploie_sur_la_zone_de_travail(self, monkeypatch):
        from scrabble.ui import jeu as mod

        monkeypatch.setattr(mod, "_zone_travail_ecran", lambda: (66, 32, 1294, 736))
        fen = _FenetrePlateauFactice()
        mod._maximiser_plateau(fen)
        # Ordre attendu : dé-iconification → maximisation native → resize → move.
        assert fen.appels == [
            ("restore",),
            ("maximize",),
            ("resize", 1294, 736),
            ("move", 66, 32),
        ]
        # L'affichage a bien été attendu avant d'agir (fenêtre mappée).
        assert fen.events.shown.attentes

    def test_maximise_meme_sans_zone_de_travail(self, monkeypatch):
        from scrabble.ui import jeu as mod

        monkeypatch.setattr(mod, "_zone_travail_ecran", lambda: None)
        fen = _FenetrePlateauFactice()
        mod._maximiser_plateau(fen)
        # Sans zone connue : au moins la demande native (restore + maximize), pas de
        # resize/move « à l'aveugle ».
        assert ("maximize",) in fen.appels
        assert not any(a[0] in ("resize", "move") for a in fen.appels)

    def test_tolere_fenetre_sans_methodes(self, monkeypatch):
        from scrabble.ui import jeu as mod

        monkeypatch.setattr(mod, "_zone_travail_ecran", lambda: (0, 0, 800, 600))

        class _Nue:
            pass

        # Aucune méthode maximize/restore/resize/move : ne doit rien lever.
        mod._maximiser_plateau(_Nue())


class TestFinaliserFenetres:
    """Enchaînement maximisation plateau + repositionnement chevalet (issue #95)."""

    def test_finalise_les_deux_fenetres(self, monkeypatch):
        from scrabble.ui import jeu as mod

        appels: list = []
        monkeypatch.setattr(
            mod, "_maximiser_plateau", lambda w: appels.append(("plateau", w))
        )
        monkeypatch.setattr(
            mod, "_repositionner_chevalet", lambda w: appels.append(("chevalet", w))
        )
        monkeypatch.setattr(
            mod,
            "_lier_chevalet_au_plateau",
            lambda p, c: appels.append(("liaison", p, c)),
        )
        mod._finaliser_fenetres("PLAT", "CHEV")
        assert appels == [
            ("plateau", "PLAT"),
            ("chevalet", "CHEV"),
            ("liaison", "PLAT", "CHEV"),
        ]


class TestZoneTravailEcran:
    """Repli de la zone de travail sur ``webview.screens`` si GDK indisponible (#95)."""

    def test_repli_sur_webview_screens(self, monkeypatch):
        from scrabble.ui import jeu as mod

        # Force l'échec de l'import GDK : le repli lit webview.screens.
        import builtins

        vrai_import = builtins.__import__

        def _refuse_gi(nom, *args, **kw):
            if nom == "gi":
                raise ImportError("gi indisponible (test)")
            return vrai_import(nom, *args, **kw)

        monkeypatch.setattr(builtins, "__import__", _refuse_gi)

        class _Ecran:
            x = 5
            y = 7
            width = 1000
            height = 800

        monkeypatch.setattr(mod.webview, "screens", [_Ecran()])
        assert mod._zone_travail_ecran() == (5, 7, 1000, 800)

    def test_none_si_rien_interrogeable(self, monkeypatch):
        from scrabble.ui import jeu as mod

        import builtins

        vrai_import = builtins.__import__

        def _refuse_gi(nom, *args, **kw):
            if nom == "gi":
                raise ImportError("gi indisponible (test)")
            return vrai_import(nom, *args, **kw)

        monkeypatch.setattr(builtins, "__import__", _refuse_gi)
        monkeypatch.setattr(mod.webview, "screens", [])
        assert mod._zone_travail_ecran() is None


class TestMemoriserPositionChevalet:
    """Mémorisation/restauration de la position de la fenêtre chevalet (issue #135)."""

    def _api(self, x=200, y=500):
        joueurs = [Joueur(nom="Alice", humain=True)]
        api = ApiJeu(Partie(joueurs, _DicoFactice(), graine=1), None)
        fen = _FenetreDeplacable(x=x, y=y)
        api.set_windows(_FenetreEspionne(), fen)
        return api, fen

    def _ecran(self, monkeypatch, larg=1920, haut=1080):
        from scrabble.ui import jeu as mod

        class _Ecran:
            width = larg
            height = haut

        monkeypatch.setattr(mod.webview, "screens", [_Ecran()])

    # --- Persistance à la fin d'un déplacement -----------------------------

    def test_fin_deplacement_persiste_la_position(self, tmp_path, monkeypatch):
        """À la fin d'un drag, la position est écrite via le mécanisme de réglages."""
        from scrabble.ui import jeu as mod
        from scrabble.reglages import lire_reglage
        from scrabble.reglages import modifier_reglage as vrai_modifier

        chemin = tmp_path / "config.json"
        # Redirige l'écriture du réglage vers un fichier de test (round-trip réel
        # sur disque via scrabble.reglages/config, auto-réparation + écriture atomique).
        monkeypatch.setattr(
            mod,
            "modifier_reglage",
            lambda cle, valeur: vrai_modifier(cle, valeur, chemin),
        )
        api, _ = self._api(x=340, y=610)

        res = api.fin_deplacement_chevalet()

        assert res == {"succes": True, "x": 340, "y": 610}
        assert lire_reglage("position_chevalet", chemin) == {"x": 340, "y": 610}

    def test_fin_deplacement_journalise(self, tmp_path, monkeypatch):
        from scrabble.ui import jeu as mod
        from scrabble.reglages import modifier_reglage as vrai_modifier

        chemin = tmp_path / "config.json"
        monkeypatch.setattr(
            mod,
            "modifier_reglage",
            lambda cle, valeur: vrai_modifier(cle, valeur, chemin),
        )
        infos: list = []
        monkeypatch.setattr(
            "scrabble.ui.jeu.journal.info", lambda message: infos.append(message)
        )
        api, _ = self._api(x=12, y=34)

        api.fin_deplacement_chevalet()

        assert any("position du chevalet mémorisée" in m for m in infos)

    def test_fin_deplacement_sans_fenetre_echoue_proprement(self):
        joueurs = [Joueur(nom="Alice", humain=True)]
        api = ApiJeu(Partie(joueurs, _DicoFactice(), graine=1), None)
        assert api.fin_deplacement_chevalet()["succes"] is False

    def test_fin_deplacement_erreur_reglage_non_bloquante(self, monkeypatch):
        """Un échec d'écriture du réglage est remonté sans planter le jeu."""
        from scrabble.ui import jeu as mod

        def _explose(cle, valeur):
            raise RuntimeError("disque plein (test)")

        monkeypatch.setattr(mod, "modifier_reglage", _explose)
        monkeypatch.setattr("scrabble.ui.jeu.journal.erreur", lambda *a, **k: None)
        api, _ = self._api()

        res = api.fin_deplacement_chevalet()

        assert res["succes"] is False

    # --- Lecture de la position mémorisée au lancement ---------------------

    def test_memorisee_valide_utilisee(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)  # 1920×1080
        monkeypatch.setattr(mod, "lire_reglage", lambda cle: {"x": 500, "y": 700})
        assert mod._position_chevalet_memorisee() == (500, 700)

    def test_memorisee_absente_repli_none(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)
        monkeypatch.setattr(mod, "lire_reglage", lambda cle: None)
        assert mod._position_chevalet_memorisee() is None

    def test_memorisee_ecran_non_mesurable_repli_none(self, monkeypatch):
        from scrabble.ui import jeu as mod

        # Aucun écran interrogeable (avant démarrage de la boucle GUI) : on ne
        # peut pas vérifier les limites, on retombe sur le calcul par défaut.
        monkeypatch.setattr(mod.webview, "screens", [])
        reinit: list = []
        monkeypatch.setattr(mod, "lire_reglage", lambda cle: {"x": 500, "y": 700})
        monkeypatch.setattr(
            mod, "modifier_reglage", lambda cle, valeur: reinit.append((cle, valeur))
        )
        assert mod._position_chevalet_memorisee() is None
        # Écran non mesurable : on ne réinitialise PAS (position peut-être bonne).
        assert reinit == []

    def test_memorisee_hors_ecran_repli_et_reinitialisee(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch, larg=1280, haut=720)
        reinit: list = []
        monkeypatch.setattr(mod, "lire_reglage", lambda cle: {"x": 5000, "y": 5000})
        monkeypatch.setattr(
            mod, "modifier_reglage", lambda cle, valeur: reinit.append((cle, valeur))
        )
        assert mod._position_chevalet_memorisee() is None
        # Le réglage périmé (hors écran actuel) est réinitialisé à None.
        assert reinit == [("position_chevalet", None)]

    # --- Intégration via _repositionner_chevalet ---------------------------

    def test_repositionner_utilise_position_memorisee(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)  # 1920×1080
        monkeypatch.setattr("scrabble.ui.jeu.journal.info", lambda m: None)
        monkeypatch.setattr(mod, "lire_reglage", lambda cle: {"x": 500, "y": 700})
        fen = _FenetreShown(x=100, y=100)

        mod._repositionner_chevalet(fen)

        # La position mémorisée valide prime sur le calcul bas-centre.
        assert fen.moves == [(500, 700)]

    def test_repositionner_hors_ecran_retombe_sur_defaut(self, monkeypatch):
        from scrabble.ui import jeu as mod

        self._ecran(monkeypatch)  # 1920×1080
        monkeypatch.setattr("scrabble.ui.jeu.journal.info", lambda m: None)
        monkeypatch.setattr(mod, "lire_reglage", lambda cle: {"x": 9000, "y": 9000})
        monkeypatch.setattr(mod, "modifier_reglage", lambda cle, valeur: None)
        fen = _FenetreShown(x=100, y=100)

        mod._repositionner_chevalet(fen)

        # Position hors écran → repli sur le calcul bas-centre par défaut.
        x_attendu = (1920 - CHEVALET_LARGEUR) // 2
        y_attendu = 1080 - CHEVALET_HAUTEUR - mod.CHEVALET_MARGE_BAS
        assert fen.moves == [(x_attendu, y_attendu)]
