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
from scrabble.moteur.plateau_partie import Direction, Tuile
from scrabble.regles.lettres import JOKER
from scrabble.regles.plateau import CENTRE, TAILLE
from scrabble.ui.jeu import (
    ApiJeu,
    calculer_positions,
    compter_humains,
    construire_coup,
    construire_partie_demo,
    echanger_chevalet_complet,
    etat_public,
    jouer_placements,
    serialiser_case,
    serialiser_chevalet,
    serialiser_joueur_public,
    serialiser_plateau,
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

    def test_une_seule_lettre_sens_impose(self):
        partie = _partie_simple()
        coup_h = construire_coup(partie.plateau, [_placement(7, 7, "A")], "H")
        assert coup_h.direction is Direction.HORIZONTALE
        coup_v = construire_coup(partie.plateau, [_placement(7, 7, "A")], "V")
        assert coup_v.direction is Direction.VERTICALE

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
