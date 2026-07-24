"""Tests de chargement différé d'ApiJeu (issue #179, issue #262).

Ces classes ont été extraites de ``test_jeu.py`` pour réduire la taille de ce
fichier.
"""

from tests._aides_test_jeu import _DicoFactice, _partie_simple
from scrabble.ui.jeu import ApiJeu


class TestApiJeuChargementDiffere:
    """Instanciation sans partie puis chargement différé (issue #179).

    Dans le modèle mono-fenêtre, une même instance d'``ApiJeu`` sert plusieurs
    parties successives : le constructeur accepte donc une absence de partie, et
    ``charger_partie`` installe une partie en remettant **tout** l'état à zéro.
    """

    def test_instanciation_sans_partie(self):
        """``ApiJeu()`` sans argument crée une instance « vide » cohérente."""
        api = ApiJeu()
        assert api._partie is None
        assert api._id_partie is None
        assert api._infos_tirage is None
        # Aucun tirage à mener tant qu'aucune partie n'est chargée.
        assert api._tirage_termine is True
        assert api._selection is None
        assert api._en_attente == []

    def test_getters_etat_gardes_contre_absence_de_partie(self):
        """Les getters exposés au JS renvoient une erreur plutôt que de planter."""
        api = ApiJeu()
        for charge in (
            api.obtenir_etat(),
            api.obtenir_etat_plateau(),
            api.obtenir_etat_chevalet(),
            api.obtenir_chevalet(0),
        ):
            assert charge["succes"] is False
            assert "Aucune partie" in charge["erreur"]

    def test_charger_partie_installe_la_partie(self):
        """``charger_partie`` renseigne partie, id et infos de tirage."""
        api = ApiJeu()
        partie = _partie_simple()
        infos = {
            "noms_creation": ["Alice", "Robot"],
            "graine": 42,
            "noms_humains": ["Alice"],
        }
        api.charger_partie(partie, 7, infos_tirage=infos)
        assert api._partie is partie
        assert api._id_partie == 7
        assert api._infos_tirage == infos
        # Nouvelle partie (infos fournies) : tirage à mener.
        assert api._tirage_termine is False
        # L'état est désormais servi normalement.
        assert "joueurs" in api.obtenir_etat()

    def test_charger_partie_remet_tout_l_etat_a_zero(self):
        """Un état « sali » est intégralement réinitialisé au chargement suivant.

        Vérifie explicitement chaque champ listé par l'issue #179 : sélection,
        placements en attente, mode/sélection d'échange, joker en attente, et les
        drapeaux de fin/retour/recommencer.
        """
        api = ApiJeu(_partie_simple(), id_partie=1)
        # Salir l'ensemble de l'état interne.
        api._selection = 3
        api._en_attente = [{"ligne": 7, "colonne": 7, "lettre": "A"}]
        api._mode_echange = True
        api._selection_echange = [1, 2]
        api._joker_demande = {"ligne": 0, "colonne": 0, "index": 0}
        api._tirage_termine = False
        api._fin_journalisee = True
        api._fin_persistee = True
        api._retour_menu = True
        api._recommencer = True
        api._nouvelle_partie = _partie_simple()
        api._nouvel_id_partie = 123
        api._nouvelles_infos_tirage = {"x": 1}

        # Recharger une AUTRE partie (reprise : pas d'infos de tirage).
        nouvelle = _partie_simple(graine=99)
        api.charger_partie(nouvelle, 2, infos_tirage=None)

        assert api._partie is nouvelle
        assert api._id_partie == 2
        assert api._selection is None
        assert api._en_attente == []
        assert api._mode_echange is False
        assert api._selection_echange == []
        assert api._joker_demande is None
        # Reprise (infos None) : plus de tirage à mener.
        assert api._tirage_termine is True
        assert api._infos_tirage is None
        assert api._fin_journalisee is False
        assert api._fin_persistee is False
        assert api._retour_menu is False
        assert api._recommencer is False
        assert api._nouvelle_partie is None
        assert api._nouvel_id_partie is None
        assert api._nouvelles_infos_tirage is None

    def test_charger_partie_preserve_les_fenetres(self):
        """La fenêtre physique (partagée) n'est PAS remise à zéro par un chargement.

        C'est l'invariant central du modèle mono-fenêtre : la même fenêtre sert
        plusieurs parties successives.
        """
        api = ApiJeu()
        fenetre_plateau = object()
        api.set_window(fenetre_plateau)
        api.charger_partie(_partie_simple(), 5)
        assert api._window_plateau is fenetre_plateau
