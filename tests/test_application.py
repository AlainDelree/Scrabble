"""Tests de la coquille mono-fenêtre et du routeur d'API (issue #179).

Couvre, en isolation (sans ouvrir de fenêtre pywebview) :
- le routage d'un appel vers la bonne sous-API selon la vue active, y compris
  pour ``obtenir_etat`` (présente dans ``ApiAccueil`` ET ``ApiJeu``) ;
- le refus explicite (``AttributeError``) d'une méthode absente de la vue active ;
- la propagation de la fenêtre unique aux deux sous-API (``set_window``) ;
- l'exposition dynamique des méthodes de façon détectable par pywebview
  (fonctions/méthodes vues par ``dir()``) ;
- ``charger_jeu`` déléguant à ``ApiJeu.charger_partie``.

La remise à zéro complète de ``ApiJeu.charger_partie`` est testée dans
``test_jeu.py`` (proche de la classe testée).
"""

import inspect

import pytest

from scrabble.ui.accueil import ApiAccueil
from scrabble.ui.application import (
    VUE_ACCUEIL,
    VUE_JEU,
    ApiRouteur,
)
from scrabble.ui.jeu import ApiJeu


class _SousApiFactice:
    """Sous-API minimale traçant ses appels, pour un routage sans dépendances."""

    def __init__(self, marque: str) -> None:
        self.marque = marque
        self.appels: list[tuple] = []

    def obtenir_etat(self) -> dict:
        # Méthode en collision (présente des deux côtés) : renvoie sa marque pour
        # prouver quelle sous-API a réellement répondu.
        self.appels.append(("obtenir_etat",))
        return {"vue": self.marque}

    def set_window(self, window) -> None:
        self.appels.append(("set_window", window))
        self.window = window


class TestRoutageVueActive:
    """Le routeur dirige chaque appel vers la sous-API de la vue active."""

    def test_obtenir_etat_route_vers_accueil_puis_jeu(self):
        """La collision ``obtenir_etat`` est tranchée par la vue active."""
        acc = _SousApiFactice("accueil")
        jeu = _SousApiFactice("jeu")
        routeur = ApiRouteur(api_accueil=acc, api_jeu=jeu)

        # Vue accueil par défaut : l'appel tombe sur la sous-API accueil.
        assert routeur.obtenir_etat() == {"vue": "accueil"}
        assert acc.appels == [("obtenir_etat",)]
        assert jeu.appels == []

        # Bascule en vue jeu : le MÊME appel tombe désormais sur la sous-API jeu.
        routeur.activer_vue(VUE_JEU)
        assert routeur.obtenir_etat() == {"vue": "jeu"}
        assert jeu.appels == [("obtenir_etat",)]
        # L'accueil n'a pas été rappelé.
        assert acc.appels == [("obtenir_etat",)]

    def test_obtenir_etat_collision_avec_vraies_sous_api(self):
        """Collision ``obtenir_etat`` résolue avec de vraies ApiAccueil/ApiJeu."""
        routeur = ApiRouteur()

        # Accueil actif : état de configuration (dict avec ``joueurs``).
        routeur.activer_vue(VUE_ACCUEIL)
        etat_accueil = routeur.obtenir_etat()
        assert "joueurs" in etat_accueil
        assert "peut_lancer" in etat_accueil

        # Jeu actif sans partie chargée : garde de ``ApiJeu`` (charge d'erreur),
        # pas l'état d'accueil — preuve que le routage a bien changé de cible.
        routeur.activer_vue(VUE_JEU)
        etat_jeu = routeur.obtenir_etat()
        assert etat_jeu.get("succes") is False
        assert "joueurs" not in etat_jeu

    def test_methode_propre_au_jeu_hors_vue_leve_attribute_error(self):
        """Une méthode absente de la vue active lève une ``AttributeError`` claire."""
        routeur = ApiRouteur()

        # ``obtenir_theme_plateau`` n'existe que côté jeu.
        routeur.activer_vue(VUE_JEU)
        assert routeur.obtenir_theme_plateau() == "classique"

        routeur.activer_vue(VUE_ACCUEIL)
        with pytest.raises(AttributeError):
            routeur.obtenir_theme_plateau()

    def test_methode_propre_a_l_accueil_hors_vue_leve_attribute_error(self):
        """Symétrique : une méthode accueil-only en vue jeu lève ``AttributeError``."""
        routeur = ApiRouteur()

        routeur.activer_vue(VUE_ACCUEIL)
        assert isinstance(routeur.obtenir_niveaux(), list)

        routeur.activer_vue(VUE_JEU)
        with pytest.raises(AttributeError):
            routeur.obtenir_niveaux()

    def test_activer_vue_inconnue_refusee(self):
        """``activer_vue`` refuse une vue inconnue sans changer l'état."""
        routeur = ApiRouteur()
        resultat = routeur.activer_vue("inexistante")
        assert resultat["succes"] is False
        # La vue active reste l'accueil (valeur par défaut).
        assert routeur._vue_active == VUE_ACCUEIL

    def test_constructeur_refuse_vue_initiale_inconnue(self):
        """Le constructeur refuse une ``vue_active`` initiale invalide."""
        with pytest.raises(ValueError):
            ApiRouteur(vue_active="bidon")


class TestFenetreUnique:
    """Le routeur porte et propage la fenêtre physique unique."""

    def test_set_window_propage_aux_deux_sous_api(self):
        """``set_window`` renseigne le routeur ET les deux sous-API."""
        acc = _SousApiFactice("accueil")
        jeu = _SousApiFactice("jeu")
        routeur = ApiRouteur(api_accueil=acc, api_jeu=jeu)

        sentinelle = object()
        routeur.set_window(sentinelle)

        assert routeur._window is sentinelle
        assert acc.window is sentinelle
        assert jeu.window is sentinelle

    def test_set_window_reelle_renseigne_plateau_du_jeu(self):
        """Avec de vraies sous-API, ``ApiJeu`` reçoit la fenêtre comme plateau."""
        routeur = ApiRouteur()
        sentinelle = object()
        routeur.set_window(sentinelle)
        assert routeur._api_accueil._window is sentinelle
        assert routeur._api_jeu._window_plateau is sentinelle


class TestExpositionPywebview:
    """Les routes sont détectables par l'énumération de pywebview."""

    def test_methodes_publiques_exposees_comme_fonctions(self):
        """pywebview énumère ``dir()`` hors ``_`` et ne garde que fonctions/méthodes.

        On reproduit son critère (``inspect.ismethod or inspect.isfunction``) et on
        vérifie que les routes dynamiques (dont ``obtenir_etat``) sont bien vues,
        de même que les méthodes de contrôle propres au routeur.
        """
        routeur = ApiRouteur()
        exposees = {
            nom
            for nom in dir(routeur)
            if not nom.startswith("_")
            and (
                inspect.ismethod(getattr(routeur, nom))
                or inspect.isfunction(getattr(routeur, nom))
            )
        }
        # Route en collision + routes propres à chaque vue.
        assert "obtenir_etat" in exposees
        assert "obtenir_theme_plateau" in exposees  # jeu
        assert "obtenir_niveaux" in exposees  # accueil
        # Méthodes de contrôle du routeur.
        assert "set_window" in exposees
        assert "activer_vue" in exposees
        assert "charger_jeu" in exposees

    def test_set_window_est_la_methode_de_controle_du_routeur(self):
        """``set_window`` est la méthode de classe du routeur, pas une route."""
        routeur = ApiRouteur()
        # Une méthode de classe (liée), pas une fonction posée en attribut.
        assert inspect.ismethod(routeur.set_window)
        # Le nom qualifié atteste qu'il s'agit bien de ``ApiRouteur.set_window``.
        assert routeur.set_window.__func__ is ApiRouteur.set_window


class TestChargerJeu:
    """``charger_jeu`` prépare la sous-API Jeu en différé."""

    def test_charger_jeu_delegue_a_charger_partie(self):
        """``charger_jeu`` installe la partie dans la sous-API Jeu (vide au départ)."""
        routeur = ApiRouteur()
        assert routeur._api_jeu._partie is None

        partie, id_partie = _partie_deux_joueurs()
        resultat = routeur.charger_jeu(partie, id_partie)

        assert resultat["succes"] is True
        assert routeur._api_jeu._partie is partie
        assert routeur._api_jeu._id_partie == id_partie
        # ``charger_jeu`` ne bascule PAS la vue (transitions non câblées, issue #179).
        assert routeur._vue_active == VUE_ACCUEIL


class _FenetreFactice:
    """Fenêtre pywebview minimale traçant ``load_url`` (transition issue #180)."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def load_url(self, url: str) -> None:
        self.urls.append(url)


class TestDemarrerJeu:
    """``demarrer_jeu`` câble la transition Accueil→Jeu dans la fenêtre unique."""

    def _routeur_avec_partie(self, monkeypatch, infos_tirage=None):
        """Routeur prêt : partie déposée sur l'accueil, finalisation neutralisée."""
        routeur = ApiRouteur()
        fenetre = _FenetreFactice()
        routeur.set_window(fenetre)
        # Simule ce que ``ApiAccueil.lancer_partie``/``reprendre`` a déjà déposé.
        partie, id_partie = _partie_deux_joueurs()
        routeur._api_accueil._partie = partie
        routeur._api_accueil._id_partie = id_partie
        routeur._api_accueil._infos_tirage = infos_tirage
        # Neutralise la finalisation (fils + fenêtres réelles) : on trace l'appel.
        appels = []
        monkeypatch.setattr(
            routeur._api_jeu,
            "finaliser_entree_vue_jeu",
            lambda: appels.append("finaliser"),
        )
        return routeur, fenetre, partie, id_partie, appels

    def test_sequence_dans_le_bon_ordre(self, monkeypatch):
        """Charge la partie, bascule la vue AVANT ``load_url``, puis finalise."""
        routeur, fenetre, partie, id_partie, appels = self._routeur_avec_partie(
            monkeypatch
        )

        resultat = routeur.demarrer_jeu()

        assert resultat["succes"] is True
        # 1. partie chargée dans la sous-API Jeu (reprise : pas de tirage).
        assert routeur._api_jeu._partie is partie
        assert routeur._api_jeu._id_partie == id_partie
        assert routeur._api_jeu._tirage_termine is True
        # 2. la vue Jeu est active (basculée avant la navigation).
        assert routeur._vue_active == VUE_JEU
        # 3. navigation load_url vers jeu.html dans la MÊME fenêtre.
        assert len(fenetre.urls) == 1
        assert fenetre.urls[0].endswith("jeu.html")
        # 4. finalisation rejouée.
        assert appels == ["finaliser"]

    def test_transmet_infos_tirage_nouvelle_partie(self, monkeypatch):
        """Une nouvelle partie (infos_tirage) laisse le tirage à mener côté Jeu."""
        infos = {"noms_creation": ["Alice", "Robot"], "graine": 42,
                 "noms_humains": ["Alice"]}
        routeur, _fenetre, _partie, _id, _appels = self._routeur_avec_partie(
            monkeypatch, infos_tirage=infos
        )

        routeur.demarrer_jeu()

        assert routeur._api_jeu._infos_tirage == infos
        # Tirage encore à mener : terminer_tirage révélera le chevalet au « Continuer ».
        assert routeur._api_jeu._tirage_termine is False

    def test_sans_partie_prete_echoue_sans_naviguer(self, monkeypatch):
        """Sans partie déposée, la transition échoue proprement (bouton réactivé)."""
        routeur = ApiRouteur()
        fenetre = _FenetreFactice()
        routeur.set_window(fenetre)
        appels = []
        monkeypatch.setattr(
            routeur._api_jeu,
            "finaliser_entree_vue_jeu",
            lambda: appels.append("finaliser"),
        )

        resultat = routeur.demarrer_jeu()

        assert resultat["succes"] is False
        assert "erreur" in resultat
        # Aucune navigation, aucune bascule de vue, aucune finalisation.
        assert fenetre.urls == []
        assert routeur._vue_active == VUE_ACCUEIL
        assert appels == []

    def test_demarrer_jeu_est_methode_de_controle(self):
        """``demarrer_jeu`` est une vraie méthode du routeur (jamais une route)."""
        import inspect

        routeur = ApiRouteur()
        assert inspect.ismethod(routeur.demarrer_jeu)
        assert routeur.demarrer_jeu.__func__ is ApiRouteur.demarrer_jeu
        assert "demarrer_jeu" in ApiRouteur._CONTROLE


class _DicoFactice:
    """Dictionnaire minimal (accepte tout)."""

    def contient(self, mot: str) -> bool:
        return True


def _partie_deux_joueurs():
    """Petite partie déterministe (humain + ordinateur) et un id factice."""
    from scrabble.moteur.ia import Niveau
    from scrabble.moteur.partie import Joueur, Partie

    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
    ]
    return Partie(joueurs, _DicoFactice(), graine=42), 99
