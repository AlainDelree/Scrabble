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

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import Coup, Direction, Tuile
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.regles.lettres import JOKER
from scrabble.regles.plateau import CENTRE, TAILLE, TypeCase
from scrabble.ui.jeu import (
    AVATARS,
    ApiJeu,
    calculer_avatars,
    calculer_positions,
    compter_humains,
    construire_coup,
    construire_partie_demo,
    echanger_chevalet_complet,
    etat_public,
    index_panneau_interactif,
    jouer_placements,
    jouer_tours_ia_ui,
    nb_lignes_historique,
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


class TestCalculerPositions:
    """Disposition spatiale des joueurs autour du plateau (issue #33)."""

    def _joueurs(self, *humains: bool) -> list[Joueur]:
        return [
            Joueur(
                nom=f"J{i}",
                humain=h,
                niveau=None if h else Niveau.FACILE,
            )
            for i, h in enumerate(humains)
        ]

    def test_un_seul_joueur_aucune_position_laterale(self):
        # 1 seul joueur au total : uniquement le panneau du bas.
        positions = calculer_positions(self._joueurs(True))
        assert positions == ["bas"]

    def test_un_adversaire_en_haut(self):
        # 1 adversaire → il est placé en haut (face à face avec le bas).
        positions = calculer_positions(self._joueurs(True, False))
        assert positions == ["bas", "haut"]

    def test_deux_adversaires_haut_puis_gauche(self):
        positions = calculer_positions(self._joueurs(True, False, False))
        assert positions == ["bas", "haut", "gauche"]

    def test_trois_adversaires_haut_gauche_droite(self):
        positions = calculer_positions(self._joueurs(True, False, False, False))
        assert positions == ["bas", "haut", "gauche", "droite"]

    def test_humain_reference_toujours_en_bas(self):
        # Le joueur humain de référence est le premier humain de la liste : il
        # est en bas quel que soit l'ordre des joueurs dans la partie.
        positions = calculer_positions(self._joueurs(False, False, True, False))
        assert positions == ["haut", "gauche", "bas", "droite"]

    def test_plusieurs_humains_autres_repartis_dans_l_ordre(self):
        # Avec plusieurs humains, seul le premier va en bas ; les autres joueurs
        # (humains et ordinateurs) se répartissent dans l'ordre de la liste.
        positions = calculer_positions(self._joueurs(True, True, False))
        assert positions == ["bas", "haut", "gauche"]

    def test_aucun_humain_premier_joueur_en_bas(self):
        # Cas théorique sans humain : le premier joueur tient le rôle de référence.
        positions = calculer_positions(self._joueurs(False, False))
        assert positions == ["bas", "haut"]

    def test_liste_vide(self):
        assert calculer_positions([]) == []

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
        assert res == {"succes": True, "mot": "CHAT", "valide": True}

    def test_mot_invalide(self):
        res = verifier_mot_dictionnaire(_DicoMots("CHAT"), ["X", "Y", "Z"])
        assert res["succes"] is True
        assert res["mot"] == "XYZ"
        assert res["valide"] is False

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
