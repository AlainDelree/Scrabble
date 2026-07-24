"""Tests de construction et de jeu d'un coup (extraits de test_jeu.py, issue #256).

Couvre :
- ``construire_coup`` : construction d'un :class:`Coup` depuis des placements JS.
- ``jouer_placements`` : application d'un coup construit (succès et erreurs).
- ``simuler_coup`` : calcul du score sans jouer (issue #69).
- Symétrie du sens pour une lettre unique (issue #43).
"""

import pytest

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import Coup, Direction, Tuile
from scrabble.ui.jeu import construire_coup, jouer_placements, simuler_coup
from tests._aides_test_jeu import _DicoFactice, _partie_simple


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
