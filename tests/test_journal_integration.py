"""Tests d'intégration du journal dans l'accueil et l'écran de jeu (issue #66).

Vérifient, sans dépendre d'un vrai fichier de log sur disque (le module
``scrabble.journal`` est remplacé par un espion en mémoire) :

- que ``ApiAccueil`` et ``ApiJeu`` appellent ``journal.info`` / ``journal.erreur``
  aux points d'intégration clés (ajout/retrait de joueur, lancement/reprise de
  partie, coup posé, échange, tour d'ordinateur, fin de partie, erreurs) ;
- que ``lancer_accueil`` ouvre une session au démarrage et la clôture même en
  cas d'exception ;
- que ``lancer_jeu`` **réutilise** une session déjà ouverte (enchaînement
  normal depuis l'accueil) et en démarre une propre en lancement autonome, la
  clôturant dans tous les cas à la fermeture de la fenêtre.

Le comportement fonctionnel (ce qui est renvoyé au JS) n'est pas modifié par la
journalisation : les tests ci-dessous s'ajoutent aux suites existantes qui le
vérifient déjà (``test_accueil.py``, ``test_jeu.py``).
"""

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.ui import accueil as mod_accueil
from scrabble.ui import jeu as mod_jeu
from scrabble.ui.accueil import ApiAccueil
from scrabble.ui.jeu import ApiJeu


class _EspionJournal:
    """Remplaçant en mémoire du module ``journal`` : enregistre tout, aucun disque.

    Reproduit le contrat de la session courante (``session_courante`` /
    ``demarrer_session`` / ``cloturer_session``) et l'**idempotence** de la
    clôture (un second appel sans session ouverte est sans effet), fidèlement au
    module réel, pour tester la réutilisation et la clôture des sessions.
    """

    def __init__(self, session_existante=None):
        self._session = session_existante
        self.demarrages = 0
        self.clotures = 0
        self.infos: list[str] = []
        self.erreurs: list[tuple[str, BaseException | None]] = []

    # -- Session courante -------------------------------------------------
    def session_courante(self):
        return self._session

    def demarrer_session(self, *args, **kwargs):
        self.demarrages += 1
        self._session = object()
        return self._session

    def cloturer_session(self):
        if self._session is not None:
            self.clotures += 1
            self._session = None

    # -- Entrées ----------------------------------------------------------
    def info(self, message: str) -> None:
        self.infos.append(message)

    def erreur(self, message: str, exc: BaseException | None = None) -> None:
        self.erreurs.append((message, exc))

    # -- Confort de test --------------------------------------------------
    def a_info_contenant(self, fragment: str) -> bool:
        return any(fragment in m for m in self.infos)

    def a_erreur_contenant(self, fragment: str) -> bool:
        return any(fragment in m for (m, _exc) in self.erreurs)


class _DicoFactice:
    """Dictionnaire minimal (accepte tout)."""

    def contient(self, mot: str) -> bool:
        return True


# --------------------------------------------------------------------------- #
# Journalisation des actions et erreurs côté accueil
# --------------------------------------------------------------------------- #


class TestJournalAccueil:
    """``ApiAccueil`` journalise les actions normales et les erreurs (issue #66)."""

    @pytest.fixture
    def espion(self, monkeypatch):
        esp = _EspionJournal(session_existante=object())
        monkeypatch.setattr(mod_accueil, "journal", esp)
        return esp

    def test_ajout_humain_journalise(self, espion):
        api = ApiAccueil()
        api.ajouter_humain("Alice")
        assert espion.a_info_contenant("Alice")

    def test_ajout_ordinateur_journalise(self, espion):
        api = ApiAccueil()
        api.ajouter_ordinateur("Facile")
        assert any("ordinateur" in m.lower() for m in espion.infos)

    def test_retrait_joueur_journalise(self, espion):
        api = ApiAccueil()
        api.ajouter_humain("Alice")
        avant = len(espion.infos)
        api.retirer_joueur(0)
        assert len(espion.infos) > avant
        assert espion.a_info_contenant("retiré")

    def test_lancer_partie_journalise_avec_nb_joueurs(self, espion, monkeypatch):
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda source="ods": Trie.depuis_iterable(["MAISON", "TEST"]),
        )
        monkeypatch.setattr("scrabble.ui.accueil.demarrer_suivi", lambda partie: 42)

        api = ApiAccueil()
        api.ajouter_humain("Alice")
        api.ajouter_ordinateur("Intermédiaire")
        res = api.lancer_partie()

        assert res["succes"] is True
        # Une ligne « partie #42 lancée (2 joueurs) » doit apparaître.
        assert espion.a_info_contenant("#42")
        assert espion.a_info_contenant("2 joueurs")

    def test_lancer_partie_erreur_journalisee(self, espion, monkeypatch):
        boum = RuntimeError("dictionnaire cassé")
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda source="ods": (_ for _ in ()).throw(boum),
        )
        api = ApiAccueil()
        api.ajouter_humain("Alice")
        res = api.lancer_partie()

        # Comportement fonctionnel inchangé : un message d'erreur est renvoyé au JS.
        assert res["succes"] is False
        assert res.get("erreur")
        # La journalisation s'ajoute : l'exception capturée est bien transmise.
        assert espion.erreurs
        assert espion.erreurs[-1][1] is boum

    def test_reprendre_journalise_id(self, espion, monkeypatch):
        partie = Partie(
            [Joueur(nom="Bob", humain=True)],
            Trie.depuis_iterable(["TEST"]),
            graine=1,
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda source="ods": Trie.depuis_iterable(["TEST"]),
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.reprendre_partie",
            lambda id_partie, trie, dictionnaire_ia=None: partie,
        )
        api = ApiAccueil()
        res = api.reprendre(99)

        assert res["succes"] is True
        assert espion.a_info_contenant("#99")

    def test_reprendre_introuvable_journalise_erreur(self, espion, monkeypatch):
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda source="ods": Trie.depuis_iterable(["TEST"]),
        )

        def _absente(id_partie, trie, dictionnaire_ia=None):
            raise KeyError(id_partie)

        monkeypatch.setattr("scrabble.ui.accueil.reprendre_partie", _absente)
        api = ApiAccueil()
        res = api.reprendre(7)

        # Message inchangé côté JS + erreur journalisée en plus.
        assert res["succes"] is False
        assert "introuvable" in res["erreur"]
        assert espion.erreurs


# --------------------------------------------------------------------------- #
# Journalisation des actions et erreurs côté jeu
# --------------------------------------------------------------------------- #


class _DicoMots:
    def __init__(self, *mots: str) -> None:
        self._mots = {m.upper() for m in mots}

    def contient(self, mot: str) -> bool:
        return mot.upper() in self._mots


def _placement(ligne: int, colonne: int, lettre: str, joker: bool = False) -> dict:
    return {"ligne": ligne, "colonne": colonne, "lettre": lettre, "joker": joker}


class TestJournalJeu:
    """``ApiJeu`` journalise coups, échanges, tours d'ordinateur et fin (issue #66)."""

    @pytest.fixture
    def espion(self, monkeypatch):
        esp = _EspionJournal(session_existante=object())
        monkeypatch.setattr(mod_jeu, "journal", esp)
        return esp

    def _api_avec_chevalet(self, lettres: str, mots: tuple[str, ...]) -> ApiJeu:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoMots(*mots), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list(lettres)
        return ApiJeu(partie, None)

    def test_coup_pose_journalise(self, espion):
        api = self._api_avec_chevalet("CHATSER", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        res = api.poser_mot(placements)
        assert res["succes"] is True
        # Joueur, mot et score reconstituables depuis la ligne de journal.
        assert espion.a_info_contenant("Alice")
        assert espion.a_info_contenant("CHAT")

    def test_coup_refuse_journalise_en_info(self, espion):
        api = self._api_avec_chevalet("XYZWKQJ", mots=("CHAT",))
        placements = [
            _placement(7, 7, "X"),
            _placement(7, 8, "Y"),
            _placement(7, 9, "Z"),
        ]
        res = api.poser_mot(placements)
        assert res["succes"] is False
        # Un coup refusé est un déroulé normal : tracé en INFO, pas en ERREUR,
        # pour ne pas déclencher la rétention du fichier de log.
        assert espion.a_info_contenant("refusé")
        assert espion.erreurs == []

    def test_echange_journalise(self, espion):
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        api = ApiJeu(partie, None)

        res = api.echanger_tout()
        assert res["succes"] is True
        assert espion.a_info_contenant("échange")
        assert espion.a_info_contenant("Alice")

    def test_tour_ordinateur_journalise(self, espion):
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.EXPERT),
        ]
        partie = Partie(joueurs, Trie.depuis_iterable(["CADRE"]), graine=1)
        partie.index_courant = 1  # tour de l'ordinateur
        api = ApiJeu(partie, None)

        res = api.faire_jouer_ia()
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert espion.a_info_contenant("ordinateur")
        assert espion.a_info_contenant("Robot")

    def test_fin_de_partie_journalisee_une_seule_fois(self, espion):
        api = self._api_avec_chevalet("CHATSER", mots=("CHAT",))
        # Simule une partie terminée avec un gagnant désigné.
        api._partie.terminee = True
        api._partie.gagnants = [api._partie.joueurs[0]]

        api._journaliser_fin_partie()
        fins = [m for m in espion.infos if "fin de partie" in m.lower()]
        assert len(fins) == 1
        assert espion.a_info_contenant("Alice")
        # Un second déclenchement (ré-appel API sans effet) ne re-journalise pas.
        api._journaliser_fin_partie()
        fins = [m for m in espion.infos if "fin de partie" in m.lower()]
        assert len(fins) == 1

    def test_fin_de_partie_non_journalisee_si_partie_en_cours(self, espion):
        api = self._api_avec_chevalet("CHATSER", mots=("CHAT",))
        assert api._partie.terminee is False
        api._journaliser_fin_partie()
        assert not espion.a_info_contenant("fin de partie")


# --------------------------------------------------------------------------- #
# Cycle de vie des sessions (démarrage / réutilisation / clôture)
# --------------------------------------------------------------------------- #


def _partie_simple() -> Partie:
    return Partie([Joueur(nom="Alice", humain=True)], _DicoFactice(), graine=1)


class TestCycleSession:
    """Ouverture, réutilisation et clôture garantie des sessions (issue #66)."""

    def _neutraliser_webview(self, monkeypatch, on_start=None):
        """Empêche l'ouverture d'une vraie fenêtre pywebview pendant les tests."""
        capture: dict = {}

        def fake_create_window(*args, js_api=None, **kwargs):
            capture["api"] = js_api
            return object()

        def fake_start(func=None, args=None, **kwargs):
            # Depuis l'issue #91, lancer_jeu appelle webview.start(func, args) pour
            # repositionner la fenêtre chevalet après démarrage de la boucle. On ne
            # rejoue pas ce callback ici (fenêtre factice) : on simule seulement
            # l'effet « la boucle a tourné » via le hook on_start.
            if on_start is not None:
                on_start(capture.get("api"))

        import webview

        monkeypatch.setattr(webview, "create_window", fake_create_window)
        monkeypatch.setattr(webview, "start", fake_start)
        return capture

    def test_lancer_jeu_autonome_ouvre_et_cloture_sa_session(self, monkeypatch):
        esp = _EspionJournal(session_existante=None)
        monkeypatch.setattr(mod_jeu, "journal", esp)
        self._neutraliser_webview(monkeypatch)

        mod_jeu.lancer_jeu(_partie_simple(), None)

        # Aucune session préalable : le jeu démarre la sienne, puis la clôture.
        assert esp.demarrages == 1
        assert esp.clotures == 1
        assert esp.session_courante() is None

    def test_lancer_jeu_reutilise_session_existante(self, monkeypatch):
        esp = _EspionJournal(session_existante=object())
        session_initiale = esp.session_courante()
        vue_pendant = {}

        monkeypatch.setattr(mod_jeu, "journal", esp)
        self._neutraliser_webview(
            monkeypatch,
            on_start=lambda api: vue_pendant.setdefault(
                "session", esp.session_courante()
            ),
        )

        mod_jeu.lancer_jeu(_partie_simple(), 7)

        # Session déjà ouverte : réutilisée (aucun nouveau démarrage)...
        assert esp.demarrages == 0
        assert vue_pendant["session"] is session_initiale
        # ...puis clôturée à la fermeture de la fenêtre de jeu.
        assert esp.clotures == 1
        assert esp.session_courante() is None

    def test_lancer_jeu_cloture_meme_si_exception(self, monkeypatch):
        esp = _EspionJournal(session_existante=None)
        monkeypatch.setattr(mod_jeu, "journal", esp)

        import webview

        monkeypatch.setattr(
            webview, "create_window", lambda *a, **k: object()
        )

        def start_qui_plante(func=None, args=None, **kwargs):
            raise RuntimeError("backend HS")

        monkeypatch.setattr(webview, "start", start_qui_plante)

        with pytest.raises(RuntimeError):
            mod_jeu.lancer_jeu(_partie_simple(), None)

        # Le try/finally garantit la clôture malgré l'exception.
        assert esp.clotures == 1
        assert esp.session_courante() is None

    def test_lancer_accueil_sans_enchainement_cloture_session(self, monkeypatch):
        esp = _EspionJournal(session_existante=None)
        monkeypatch.setattr(mod_accueil, "journal", esp)
        self._neutraliser_webview(monkeypatch)

        # Aucune partie créée (webview.start ne fait rien) : pas d'enchaînement
        # vers le jeu, donc l'accueil clôture lui-même sa session.
        partie, id_partie = mod_accueil.lancer_accueil(ouvrir_jeu=True)

        assert partie is None and id_partie is None
        assert esp.demarrages == 1
        assert esp.clotures == 1
        assert esp.session_courante() is None

    def test_enchainement_accueil_vers_jeu_reutilise_session(self, monkeypatch):
        """La session ouverte par l'accueil est réutilisée par l'écran de jeu."""
        esp = _EspionJournal(session_existante=None)
        # Même espion partagé par les deux écrans (une seule session logique).
        monkeypatch.setattr(mod_accueil, "journal", esp)
        monkeypatch.setattr(mod_jeu, "journal", esp)

        partie = _partie_simple()
        sessions_vues: list = []

        def on_start(api):
            # Côté accueil : simule le JS ayant créé une partie avant fermeture.
            if isinstance(api, ApiAccueil):
                api._partie = partie
                api._id_partie = 7
            sessions_vues.append(esp.session_courante())

        self._neutraliser_webview(monkeypatch, on_start=on_start)

        resultat, id_partie = mod_accueil.lancer_accueil(ouvrir_jeu=True)

        assert resultat is partie
        assert id_partie == 7
        # Une seule session démarrée (par l'accueil), jamais redémarrée par le jeu.
        assert esp.demarrages == 1
        # Les deux écrans ont vu la MÊME session pendant leur boucle.
        assert len(sessions_vues) == 2
        assert sessions_vues[0] is sessions_vues[1]
        # Clôturée une seule fois (par le jeu ; le finally de l'accueil est neutre).
        assert esp.clotures == 1
        assert esp.session_courante() is None

    def test_retour_menu_rouvre_accueil_et_reutilise_la_session(self, monkeypatch):
        """« Retour au menu » (issue #74) : le jeu rouvre l'accueil sans nouvelle session.

        Le jeu ne clôture PAS sa session quand ``_retour_menu`` est vrai ; il
        rouvre l'accueil, qui réutilise la même session et la clôture à sa propre
        fermeture. Une seule session vit sur tout le cycle jeu → accueil.
        """
        esp = _EspionJournal(session_existante=object())
        session_initiale = esp.session_courante()
        monkeypatch.setattr(mod_accueil, "journal", esp)
        monkeypatch.setattr(mod_jeu, "journal", esp)

        sessions_vues: list = []

        def on_start(api):
            sessions_vues.append(esp.session_courante())
            # Côté jeu : simule le clic « Retour au menu » avant fermeture.
            # Côté accueil rouvert : rien à faire (fermé sans lancer de partie).
            if isinstance(api, ApiJeu):
                api._retour_menu = True

        self._neutraliser_webview(monkeypatch, on_start=on_start)

        mod_jeu.lancer_jeu(_partie_simple(), 7)

        # Session préexistante réutilisée par le jeu ET par l'accueil rouvert.
        assert esp.demarrages == 0
        # Jeu puis accueil ont tourné sur la MÊME session (jamais redémarrée).
        assert len(sessions_vues) == 2
        assert sessions_vues[0] is session_initiale
        assert sessions_vues[1] is session_initiale
        # Clôturée une seule fois, par l'accueil rouvert (le jeu ne l'a pas fait).
        assert esp.clotures == 1
        assert esp.session_courante() is None
        assert esp.a_info_contenant("retour au menu")

    def test_retour_menu_demarre_session_si_absente(self, monkeypatch):
        """Filet de sécurité : réutilisation demandée mais aucune session ouverte.

        En lancement autonome du jeu (``python -m scrabble.ui.jeu``) suivi d'un
        « Retour au menu », le jeu a démarré la session ; il la garde ouverte pour
        l'accueil rouvert, qui la clôture. Une seule session sur tout le cycle.
        """
        esp = _EspionJournal(session_existante=None)
        monkeypatch.setattr(mod_accueil, "journal", esp)
        monkeypatch.setattr(mod_jeu, "journal", esp)

        def on_start(api):
            if isinstance(api, ApiJeu):
                api._retour_menu = True

        self._neutraliser_webview(monkeypatch, on_start=on_start)

        mod_jeu.lancer_jeu(_partie_simple(), None)

        # Le jeu démarre la session (aucune préalable), l'accueil rouvert la
        # réutilise sans en redémarrer une (une seule au total).
        assert esp.demarrages == 1
        assert esp.clotures == 1
        assert esp.session_courante() is None

    def test_ouverture_accueil_place_le_joueur_humain_par_defaut(self, monkeypatch):
        """Vérification headless (issue #141) : à l'ouverture de l'accueil, le

        joueur humain de référence est déjà présent dans la configuration, sans
        ajout manuel. On neutralise pywebview et on inspecte, pendant la boucle
        simulée, l'état exposé par l'API au JS (``obtenir_etat``).
        """
        esp = _EspionJournal(session_existante=None)
        monkeypatch.setattr(mod_accueil, "journal", esp)
        # Prénom principal de référence, indépendamment du config.json réel.
        monkeypatch.setattr(mod_accueil, "lire_reglage", lambda cle: "Alain")

        etats_vus: list = []

        def on_start(api):
            if isinstance(api, ApiAccueil):
                etats_vus.append(api.obtenir_etat())

        self._neutraliser_webview(monkeypatch, on_start=on_start)

        mod_accueil.lancer_accueil(ouvrir_jeu=False)

        assert len(etats_vus) == 1
        etat = etats_vus[0]
        assert etat["nb_humains"] == 1
        assert etat["joueurs"] == [
            {"nom": "Alain", "humain": True, "niveau": None, "avatar": None}
        ]
        # Présent d'office => la partie est immédiatement lançable.
        assert etat["peut_lancer"] is True
