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
import threading

import pytest

from scrabble.moteur.ia import Niveau
from scrabble.ui import application as _mod_application
from scrabble.ui.accueil import ApiAccueil
from scrabble.ui.application import (
    VUE_ACCUEIL,
    VUE_JEU,
    ApiRouteur,
    lancer_application_unifiee,
)
from scrabble.ui.jeu import ApiJeu

# Référence vers le VRAI ``_differer`` (fil démon + délai), capturée avant tout
# ``monkeypatch`` : la fixture autouse ci-dessous le remplace par une exécution
# synchrone pour tous les tests, mais son comportement réel reste testable via
# cette référence (cf. ``TestNavigationDifferee``).
_DIFFERER_REEL = _mod_application._differer


@pytest.fixture(autouse=True)
def _navigation_synchrone(monkeypatch):
    """Rend la navigation différée (issue #183) synchrone pendant les tests.

    En production, ``_differer`` repousse le ``load_url`` dans un fil démon (après
    un court délai) pour éviter le « callback de retour orphelin ». En test, on
    l'exécute immédiatement : les assertions sur ``load_url``/finalisation restent
    déterministes, sans fil ni délai. Les tests qui veulent observer le différé
    lui-même re-patchent ``_differer`` localement.
    """
    monkeypatch.setattr(
        "scrabble.ui.application._differer", lambda action: action()
    )


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
    """Fenêtre pywebview minimale traçant ``load_url``/``hide``/``show`` (issues #180/#181)."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.masquee = False
        self.montree = False

    def load_url(self, url: str) -> None:
        self.urls.append(url)

    def hide(self) -> None:
        self.masquee = True

    def show(self) -> None:
        self.montree = True


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


class TestTransitionsJeuAccueil:
    """Transitions Jeu→Accueil dans la fenêtre unique (issue #181).

    « Retour au menu », « Recommencer » et « Annuler le tirage » naviguent par
    ``load_url`` dans la MÊME fenêtre (aucune destruction/recréation), masquent le
    chevalet persistant, réinitialisent l'état Accueil au retour et n'ouvrent/ne
    ferment aucune session de journalisation supplémentaire.
    """

    def _routeur_en_jeu(self, monkeypatch, id_partie=None):
        """Routeur en vue Jeu, partie chargée, chevalet monté, finalisation neutralisée."""
        routeur = ApiRouteur()
        fenetre = _FenetreFactice()
        routeur.set_window(fenetre)
        chevalet = _FenetreFactice()
        # Chevalet compagnon persistant (créé une fois au démarrage, issue #180).
        routeur._api_jeu._window_chevalet = chevalet
        partie, _id = _partie_deux_joueurs()
        routeur.charger_jeu(partie, id_partie)
        routeur.activer_vue(VUE_JEU)
        appels: list[str] = []
        monkeypatch.setattr(
            routeur._api_jeu,
            "finaliser_entree_vue_jeu",
            lambda: appels.append("finaliser"),
        )
        return routeur, fenetre, chevalet, partie, appels

    def test_retourner_accueil_masque_reinitialise_et_navigue(self, monkeypatch):
        routeur, fenetre, chevalet, _partie, _appels = self._routeur_en_jeu(
            monkeypatch
        )
        # Prénom principal configuré : le retour doit re-seeder l'humain.
        monkeypatch.setattr(
            routeur._api_accueil, "obtenir_prenom_principal", lambda: "Alice"
        )
        # Résidu de configuration/partie sur l'accueil persistant.
        routeur._api_accueil.config_partie.ajouter_ordinateur("Robot", Niveau.FACILE)
        routeur._api_accueil._partie = object()
        routeur._api_accueil._id_partie = 5

        resultat = routeur.retourner_accueil()

        assert resultat["succes"] is True
        # 1. chevalet compagnon masqué (jamais détruit).
        assert chevalet.masquee is True
        # 2. accueil réinitialisé : config vierge, humain re-seedé, partie purgée.
        assert routeur._api_accueil.config_partie.nb_ordinateurs == 0
        assert routeur._api_accueil.config_partie.nb_humains == 1
        assert routeur._api_accueil.config_partie.joueurs[0].nom == "Alice"
        assert routeur._api_accueil._partie is None
        assert routeur._api_accueil._id_partie is None
        # 3. vue Accueil active AVANT la navigation (course #178).
        assert routeur._vue_active == VUE_ACCUEIL
        # 4. navigation load_url vers accueil.html dans la MÊME fenêtre.
        assert len(fenetre.urls) == 1
        assert fenetre.urls[0].endswith("accueil.html")

    def test_recommencer_jeu_recharge_et_remasque_le_chevalet(self, monkeypatch):
        routeur, fenetre, chevalet, partie, appels = self._routeur_en_jeu(
            monkeypatch
        )

        resultat = routeur.recommencer_jeu()

        assert resultat["succes"] is True
        # Nouvelle partie chargée (distincte), tirage d'ordre à mener.
        assert routeur._api_jeu._partie is not partie
        assert routeur._api_jeu._infos_tirage is not None
        assert routeur._api_jeu._tirage_termine is False
        # Reste en vue Jeu et recharge jeu.html (DOM neuf).
        assert routeur._vue_active == VUE_JEU
        assert fenetre.urls[-1].endswith("jeu.html")
        # Chevalet remis masqué (nouveau tirage) + finalisation rejouée.
        assert chevalet.masquee is True
        assert appels == ["finaliser"]
        # Aucun drapeau inter-boucles positionné dans le chemin unifié.
        assert routeur._api_jeu._recommencer is False

    def test_annuler_tirage_accueil_supprime_puis_retourne(self, monkeypatch):
        from scrabble.ui import jeu as mod

        supprimees: list = []
        monkeypatch.setattr(
            mod, "supprimer_partie",
            lambda id_p, chemin: supprimees.append(id_p) or True,
        )
        routeur, fenetre, chevalet, _partie, _appels = self._routeur_en_jeu(
            monkeypatch, id_partie=99
        )

        resultat = routeur.annuler_tirage_accueil()

        assert resultat["succes"] is True
        # Partie créée puis annulée : supprimée de la persistance.
        assert supprimees == [99]
        # Puis même chemin que « Retour au menu » : chevalet masqué + nav accueil.
        assert chevalet.masquee is True
        assert routeur._vue_active == VUE_ACCUEIL
        assert fenetre.urls[-1].endswith("accueil.html")

    def test_transitions_nouvrent_ni_ne_ferment_de_session(self, monkeypatch):
        """Les trois transitions ne touchent JAMAIS à la session (issue #179)."""
        from scrabble import journal

        demarrees: list = []
        cloturees: list = []
        monkeypatch.setattr(
            journal, "demarrer_session", lambda *a, **k: demarrees.append(1)
        )
        monkeypatch.setattr(
            journal, "cloturer_session", lambda *a, **k: cloturees.append(1)
        )
        monkeypatch.setattr(
            "scrabble.ui.jeu.supprimer_partie", lambda id_p, chemin: True
        )

        routeur, _fenetre, _chevalet, partie, _appels = self._routeur_en_jeu(
            monkeypatch
        )
        routeur.retourner_accueil()
        routeur.charger_jeu(partie, None)
        routeur.activer_vue(VUE_JEU)
        routeur.recommencer_jeu()
        routeur.annuler_tirage_accueil()

        assert demarrees == []
        assert cloturees == []

    def test_nouvelles_methodes_sont_de_controle(self):
        """Les trois transitions sont des méthodes de contrôle (jamais routées)."""
        routeur = ApiRouteur()
        for nom in ("retourner_accueil", "recommencer_jeu", "annuler_tirage_accueil"):
            assert nom in ApiRouteur._CONTROLE
            assert inspect.ismethod(getattr(routeur, nom))
            assert getattr(routeur, nom).__func__ is getattr(ApiRouteur, nom)


class _FenetreUnifiee:
    """Fenêtre pywebview factice **complète** pour un parcours de bout en bout (issue #182).

    Combine le suivi ``load_url``/``show``/``hide`` de :class:`_FenetreFactice`
    avec un vrai ``events.closing`` (``webview.event.Event``, comme
    ``_FenetreFermable`` dans ``test_jeu.py``). Son ``destroy`` **re-émet**
    ``closing`` comme le backend GTK (où ``destroy()`` repasse par
    ``close_window``) : c'est exactement le scénario que le garde-fou anti-boucle
    de la fermeture croisée doit neutraliser.
    """

    def __init__(self, nom: str) -> None:
        from webview.event import Event

        self.nom = nom
        self.urls: list[str] = []
        self.masquee = False
        self.montree = False
        self.detruite = False
        self.events = type("_Ev", (), {})()
        self.events.closing = Event(self, True)

    def load_url(self, url: str) -> None:
        self.urls.append(url)

    def show(self) -> None:
        self.montree = True
        self.masquee = False

    def hide(self) -> None:
        self.masquee = True
        self.montree = False

    def destroy(self) -> None:
        self.detruite = True
        # Comme GTK : la destruction programmatique repasse par ``closing``.
        self.events.closing.set()


def _routeur_avec_fenetres_fermables():
    """Routeur unifié câblé à deux fenêtres factices fermables (plateau + chevalet).

    Reproduit le câblage posé par :func:`lancer_application_unifiee` sans ouvrir
    de vraie fenêtre : ``set_windows`` + ``installer_fermeture_croisee`` sur la
    sous-API Jeu, la fenêtre plateau étant AUSSI la fenêtre unique du routeur.
    """
    routeur = ApiRouteur()
    plateau = _FenetreUnifiee("plateau")
    chevalet = _FenetreUnifiee("chevalet")
    routeur.set_window(plateau)
    routeur._api_jeu.set_windows(plateau, chevalet)
    routeur._api_jeu.installer_fermeture_croisee()
    return routeur, plateau, chevalet


class TestFermetureCroiseeUnifiee:
    """Fermeture par la croix ✕ dans la coquille mono-fenêtre unifiée (issue #182).

    Risque n°1 des rapports #177/#178 : une fenêtre masquée maintient
    ``webview.start()`` vivant. Le chevalet compagnon (issue #180) est persistant
    et masqué la plupart du temps (vue Accueil, tirage). Un ✕ natif doit détruire
    **les deux** fenêtres physiques, quelle que soit la vue active, pour que la
    boucle rende la main et que le processus se termine.
    """

    def test_croix_principale_en_vue_accueil_detruit_le_chevalet_masque(self):
        """✕ sur la fenêtre principale en vue Accueil : le chevalet masqué est détruit."""
        routeur, plateau, chevalet = _routeur_avec_fenetres_fermables()
        # Vue Accueil active + chevalet masqué (état le plus fréquent du chevalet).
        routeur.activer_vue(VUE_ACCUEIL)
        routeur._api_jeu.masquer_chevalet()
        assert chevalet.masquee is True

        # Croix native sur la fenêtre principale (GTK émet ``closing``).
        plateau.events.closing.set()

        # Le chevalet — pourtant masqué — est bien détruit : plus aucune fenêtre
        # ne peut maintenir ``webview.start()`` vivant.
        assert chevalet.detruite is True
        assert routeur._api_jeu._fermeture_en_cours is True

    def test_croix_principale_en_vue_jeu_detruit_le_chevalet(self):
        """✕ sur la fenêtre principale en vue Jeu : le chevalet est détruit."""
        routeur, plateau, chevalet = _routeur_avec_fenetres_fermables()
        routeur.activer_vue(VUE_JEU)

        plateau.events.closing.set()

        assert chevalet.detruite is True

    def test_croix_du_chevalet_detruit_la_fenetre_principale(self):
        """✕ sur le chevalet lui-même : la fenêtre principale est détruite."""
        routeur, plateau, chevalet = _routeur_avec_fenetres_fermables()

        chevalet.events.closing.set()

        # Le chevalet se ferme de lui-même (backend) ; le handler détruit l'AUTRE
        # fenêtre (la principale), donc aucune orpheline ne subsiste.
        assert plateau.detruite is True

    def test_aucune_confirmation_implicite_ne_bloque_la_croix(self):
        """Le handler ne renvoie jamais ``False`` (aucune confirmation ne bloque la ✕).

        pywebview n'annule une fermeture que si un abonné à ``closing`` renvoie
        ``False``. La confirmation d'un coup en attente est portée côté JS par le
        bouton « Retour au menu », jamais par la croix : le handler natif doit
        laisser la fermeture se poursuivre.
        """
        routeur, plateau, chevalet = _routeur_avec_fenetres_fermables()
        # Appel direct du handler : il retourne None (poursuite de la fermeture).
        assert routeur._api_jeu._sur_fermeture_native(plateau) is None

    def test_croix_ne_declenche_pas_de_retour_menu(self):
        """La croix quitte l'application (elle ne repositionne pas ``_retour_menu``)."""
        routeur, plateau, chevalet = _routeur_avec_fenetres_fermables()
        plateau.events.closing.set()
        # Contrairement à « Retour au menu », une croix ne rouvre pas l'accueil.
        assert routeur._api_jeu._retour_menu is False


class TestParcoursCompletUnifie:
    """Parcours de bout en bout dans la coquille unifiée (issue #182).

    Un seul ``webview.start()``, une seule session de journalisation, aucune
    ``AttributeError`` de routage, et une fermeture par la croix qui détruit tout.
    Les vraies fenêtres et la vraie boucle pywebview sont neutralisées (headless).
    """

    def test_parcours_complet_une_seule_session_et_fermeture(self, monkeypatch):
        """lancement→accueil→partie→tirage→jeu→menu→reprise→recommencer→✕.

        Le parcours entier est joué **à l'intérieur** de l'unique
        ``webview.start()`` (stubé) ouvert par :func:`lancer_application_unifiee`,
        prouvant qu'une seule session couvre tout et qu'aucun appel ne tombe sur
        la mauvaise sous-API.
        """
        from scrabble import journal
        from scrabble.ui import jeu as mod_jeu

        # --- Neutralisation de tout ce qui exige un vrai backend graphique ---
        monkeypatch.setattr(
            "scrabble.ui.backend_graphique.configurer_backend_graphique",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "scrabble.ui.backend_graphique.deployer_fenetre_maximisee",
            lambda *a, **k: None,
        )
        # Positionnement/liaison réels du chevalet (WebKitGTK) → no-op.
        monkeypatch.setattr(mod_jeu, "_repositionner_chevalet", lambda *a, **k: None)
        monkeypatch.setattr(mod_jeu, "_lier_chevalet_au_plateau", lambda *a, **k: None)
        # Persistance de « Recommencer » (nouvelle partie suivie en base) → id factice.
        monkeypatch.setattr(mod_jeu, "demarrer_suivi", lambda *a, **k: 123)

        # --- Comptage strict des sessions de journalisation ---
        demarrees: list = []
        cloturees: list = []
        monkeypatch.setattr(journal, "session_courante", lambda: None)
        monkeypatch.setattr(
            journal, "demarrer_session", lambda *a, **k: demarrees.append(1)
        )
        monkeypatch.setattr(
            journal, "cloturer_session", lambda *a, **k: cloturees.append(1)
        )

        # --- Fenêtres factices injectées à la place des vraies ---
        plateau = _FenetreUnifiee("plateau")
        chevalet = _FenetreUnifiee("chevalet")
        monkeypatch.setattr(
            "scrabble.ui.application.webview.create_window",
            lambda *a, **k: plateau,
        )
        monkeypatch.setattr(mod_jeu, "_creer_fenetre_chevalet", lambda *a, **k: chevalet)

        # Routeur injecté : finalisation (fil + fenêtres réelles) neutralisée mais tracée.
        routeur = ApiRouteur()
        finaliser: list = []
        monkeypatch.setattr(
            routeur._api_jeu, "finaliser_entree_vue_jeu", lambda: finaliser.append(1)
        )

        # Le driver JOUE tout le parcours à l'intérieur de l'unique webview.start.
        def _parcours(*_a, **_k):
            # 0. Au lancement : vue Accueil, fenêtres câblées, session ouverte.
            assert routeur._vue_active == VUE_ACCUEIL
            assert demarrees == [1] and cloturees == []
            # Routage Accueil : collision ``obtenir_etat`` + méthode accueil-only.
            assert "joueurs" in routeur.obtenir_etat()
            assert isinstance(routeur.obtenir_niveaux(), list)
            # Une méthode jeu-only en vue Accueil DOIT lever (routage correct).
            with pytest.raises(AttributeError):
                routeur.obtenir_theme_plateau()

            # 1. Nouvelle partie (infos_tirage) déposée par l'accueil, puis démarrage.
            partie1, id1 = _partie_deux_joueurs()
            routeur._api_accueil._partie = partie1
            routeur._api_accueil._id_partie = id1
            routeur._api_accueil._infos_tirage = {
                "noms_creation": ["Alice", "Robot"],
                "graine": 1,
                "noms_humains": ["Alice"],
            }
            assert routeur.demarrer_jeu()["succes"] is True
            assert routeur._vue_active == VUE_JEU
            assert plateau.urls[-1].endswith("jeu.html")
            # Nouvelle partie : tirage d'ordre à mener (chevalet encore masqué).
            assert routeur._api_jeu._tirage_termine is False

            # 2. Routage Jeu : collision ``obtenir_etat`` (→ etat_public) + jeu-only.
            assert "joueurs" in routeur.obtenir_etat()
            assert routeur.obtenir_theme_plateau() == "classique"
            # Une méthode accueil-only en vue Jeu DOIT lever (routage correct).
            with pytest.raises(AttributeError):
                routeur.obtenir_niveaux()

            # 3. Fin du tirage : le chevalet compagnon est révélé (jamais recréé).
            assert routeur.terminer_tirage()["succes"] is True
            assert routeur._api_jeu._tirage_termine is True
            assert chevalet.montree is True

            # 4. Retour au menu : chevalet masqué, navigation vers l'accueil.
            assert routeur.retourner_accueil()["succes"] is True
            assert routeur._vue_active == VUE_ACCUEIL
            assert chevalet.masquee is True
            assert plateau.urls[-1].endswith("accueil.html")
            # Re-routage Accueil effectif après la navigation.
            assert "joueurs" in routeur.obtenir_etat()

            # 5. Reprise d'une AUTRE partie (pas de tirage → jouable directement).
            partie2, _id2 = _partie_deux_joueurs()
            routeur._api_accueil._partie = partie2
            routeur._api_accueil._id_partie = 77
            routeur._api_accueil._infos_tirage = None
            assert routeur.demarrer_jeu()["succes"] is True
            assert routeur._vue_active == VUE_JEU
            assert routeur._api_jeu._tirage_termine is True

            # 6. Recommencer : nouvelle partie (mêmes joueurs), DOM rechargé.
            assert routeur.recommencer_jeu()["succes"] is True
            assert routeur._vue_active == VUE_JEU
            assert plateau.urls[-1].endswith("jeu.html")
            assert routeur._api_jeu._tirage_termine is False  # nouveau tirage
            # Aucun drapeau inter-boucles positionné dans le chemin unifié.
            assert routeur._api_jeu._recommencer is False

            # 7. Fermeture par la croix ✕ sur la fenêtre principale.
            plateau.events.closing.set()
            # Le chevalet compagnon est détruit (plus de fenêtre masquée orpheline
            # qui maintiendrait la boucle vivante). La fenêtre principale, elle, est
            # fermée par le backend lui-même (l'émettrice de ``closing``).
            assert chevalet.detruite is True

            # Toujours une seule session, jamais ré-ouverte/re-fermée en cours de route.
            assert demarrees == [1] and cloturees == []

        monkeypatch.setattr("scrabble.ui.application.webview.start", _parcours)

        # Lance la coquille : ouvre la session, câble les fenêtres, joue le parcours.
        resultat = lancer_application_unifiee(routeur=routeur)

        assert resultat is routeur
        # La finalisation a été rejouée à chaque entrée en vue Jeu (3 fois :
        # nouvelle partie, reprise, recommencer).
        assert finaliser == [1, 1, 1]
        # Exactement UNE session ouverte et UNE fermée pour tout le parcours.
        assert demarrees == [1]
        assert cloturees == [1]


class TestNavigationDifferee:
    """La navigation ``load_url`` est différée après le retour de l'appel JS (issue #183).

    pywebview livre la valeur de retour de l'appel JS courant (résolution du
    ``Promise``) sur le document ENCORE affiché, juste après le retour de la
    méthode Python. Si ``load_url`` remplace ce document trop tôt, le callback de
    retour devient orphelin et le JS lève (exception non bloquante au terminal).
    Le routeur diffère donc toute navigation déclenchée par un appel JS.
    """

    def _routeur_pret(self, monkeypatch, capture):
        """Routeur en vue Jeu, partie chargée, chevalet monté ; ``_differer`` capturé."""
        monkeypatch.setattr(
            "scrabble.ui.application._differer",
            lambda action: capture.append(action),
        )
        routeur = ApiRouteur()
        fenetre = _FenetreFactice()
        routeur.set_window(fenetre)
        routeur._api_jeu._window_chevalet = _FenetreFactice()
        monkeypatch.setattr(
            routeur._api_jeu, "finaliser_entree_vue_jeu", lambda: None
        )
        return routeur, fenetre

    def test_demarrer_jeu_ne_navigue_pas_avant_le_retour(self, monkeypatch):
        """``demarrer_jeu`` rend la main (succès) SANS avoir encore navigué."""
        capture: list = []
        routeur, fenetre = self._routeur_pret(monkeypatch, capture)
        partie, id_partie = _partie_deux_joueurs()
        routeur._api_accueil._partie = partie
        routeur._api_accueil._id_partie = id_partie

        resultat = routeur.demarrer_jeu()

        # Succès rendu, mais navigation encore EN ATTENTE (différée) : la valeur de
        # retour peut être livrée sur accueil.html sans callback orphelin.
        assert resultat["succes"] is True
        assert fenetre.urls == []
        assert len(capture) == 1
        # La vue est déjà basculée AVANT la navigation (course #178, point 3).
        assert routeur._vue_active == VUE_JEU

        # L'action différée, une fois jouée, navigue effectivement vers jeu.html.
        capture[0]()
        assert fenetre.urls[-1].endswith("jeu.html")

    def test_retourner_accueil_ne_navigue_pas_avant_le_retour(self, monkeypatch):
        """``retourner_accueil`` diffère aussi sa navigation vers accueil.html."""
        capture: list = []
        routeur, fenetre = self._routeur_pret(monkeypatch, capture)
        routeur.activer_vue(VUE_JEU)

        resultat = routeur.retourner_accueil()

        assert resultat["succes"] is True
        assert fenetre.urls == []
        assert len(capture) == 1
        assert routeur._vue_active == VUE_ACCUEIL

        capture[0]()
        assert fenetre.urls[-1].endswith("accueil.html")

    def test_recommencer_jeu_ne_navigue_pas_avant_le_retour(self, monkeypatch):
        """``recommencer_jeu`` diffère le rechargement de jeu.html."""
        capture: list = []
        routeur, fenetre = self._routeur_pret(monkeypatch, capture)
        partie, _id = _partie_deux_joueurs()
        routeur.charger_jeu(partie, None)
        routeur.activer_vue(VUE_JEU)

        resultat = routeur.recommencer_jeu()

        assert resultat["succes"] is True
        assert fenetre.urls == []
        assert len(capture) == 1

        capture[0]()
        assert fenetre.urls[-1].endswith("jeu.html")

    def test_differer_execute_bien_l_action_dans_un_fil(self):
        """Le vrai ``_differer`` finit par exécuter l'action (fil démon + délai)."""
        fait = threading.Event()
        _DIFFERER_REEL(fait.set)
        assert fait.wait(timeout=2.0) is True


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
