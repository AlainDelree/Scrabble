"""Tests de la logique non-UI de l'écran de jeu (issue #28).

Couvre :
- la règle de confidentialité : ``etat_public`` n'expose aucune lettre de
  chevalet, et ``ApiJeu.obtenir_chevalet`` n'expose qu'**un seul** chevalet
  à la fois (jamais tous en une fois).

Note : les tests de sérialisation ont été déplacés dans
``test_jeu_serialisation.py`` (issue #255).
"""

from collections import Counter

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie, creer_partie
from tests._aides_test_jeu import (
    _DicoFactice,
    _DicoMots,
    _partie_simple,
    _placement,
)
from scrabble.persistance import (
    STATUT_TERMINEE,
    demarrer_suivi,
    lister_parties,
    reprendre_partie,
)
from scrabble.regles.plateau import CENTRE, TAILLE
from scrabble.ui.jeu import ApiJeu, construire_partie_demo, etat_public


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


class TestFermetureMutuellePopovers:
    """Fermeture mutuelle des popovers dans la fenêtre plateau (issue #151).

    Ouvrir un popover (« Derniers coups », « Vérification dictionnaire ») doit
    refermer tout autre popover déjà ouvert dans la même fenêtre. Le mécanisme
    commun (``configurerPopover`` dans ``commun.js``) tient un registre des
    popovers câblés et ferme les autres avant d'afficher le nouveau. Un signal
    ``fermerTousPopovers`` permet en outre de refermer les popovers du plateau
    quand une action de tour survient (y compris déclenchée depuis le chevalet),
    détectée à l'apparition d'un nouveau coup en tête d'historique.
    """

    def _lire(self, nom: str) -> str:
        from scrabble.ui.jeu import DOSSIER_WEB

        return (DOSSIER_WEB / nom).read_text(encoding="utf-8")

    def test_configurer_popover_ferme_les_autres_avant_ouverture(self):
        """L'ouverture d'un popover ferme les autres popovers câblés."""
        js = self._lire("commun.js")
        # Registre des popovers de la fenêtre + fermeture des autres à l'ouverture.
        assert "popoversCables" in js
        assert "fermerAutresPopovers(fermer)" in js

    def test_commun_expose_fermer_tous_popovers(self):
        """``fermerTousPopovers`` est exposé sur le namespace Commun."""
        js = self._lire("commun.js")
        assert "function fermerTousPopovers" in js
        assert "fermerTousPopovers," in js  # présent dans l'export window.Commun

    def test_plateau_ferme_les_popovers_a_un_nouveau_coup(self):
        """Le plateau referme ses popovers quand un nouveau coup apparaît."""
        js = self._lire("jeu.js")
        assert "C.fermerTousPopovers()" in js


class TestApiJeuHelpersCoquilleUnifiee:
    """Méthodes ApiJeu extraites/ajoutées pour la coquille unifiée (issue #181).

    ``preparer_partie_recommencee`` et ``supprimer_partie_annulee`` sont
    réutilisées par le routeur unifié (``ApiRouteur``) sans détruire de fenêtre
    ni positionner de drapeau inter-boucles. Elles sont aussi le cœur partagé du
    chemin de production.
    """

    _INFOS = {
        "noms_creation": ["Alice", "Robot"],
        "graine": 1,
        "noms_humains": ["Alice"],
    }

    def _partie_mixte(self, graine: int = 3) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Ordi", humain=False, niveau=Niveau.EXPERT),
        ]
        return Partie(joueurs, _DicoFactice(), graine=graine)

    def test_preparer_partie_recommencee_persiste_sans_toucher_les_drapeaux(
        self, tmp_path
    ):
        chemin = tmp_path / "parties.db"
        origine = self._partie_mixte()
        id_origine = demarrer_suivi(origine, chemin)
        api = ApiJeu(origine, id_partie=id_origine, chemin_persistance=chemin)

        nouvelle, nouvel_id, infos = api.preparer_partie_recommencee()

        # Nouvelle partie distincte, mêmes joueurs, suivie sous un nouvel id.
        assert nouvelle is not origine
        cle = lambda p: {(j.nom, j.humain, j.niveau) for j in p.joueurs}
        assert cle(nouvelle) == cle(origine)
        assert nouvel_id is not None and nouvel_id != id_origine
        ids = {p.id for p in lister_parties(chemin)}
        assert ids == {id_origine, nouvel_id}
        # Infos de tirage d'ordre transmises pour rejouer l'écran de tirage.
        assert set(infos.keys()) == {"noms_creation", "graine", "noms_humains"}
        # Aucun drapeau inter-boucles positionné (chemin unifié : pas de pont).
        assert api._recommencer is False
        assert api._nouvelle_partie is None
        assert api._nouvel_id_partie is None

    def test_preparer_partie_recommencee_mode_demo_ne_persiste_pas(self):
        api = ApiJeu(self._partie_mixte(), id_partie=None)
        nouvelle, nouvel_id, infos = api.preparer_partie_recommencee()
        assert nouvelle is not None
        assert nouvel_id is None
        assert infos is not None

    def test_supprimer_partie_annulee_supprime_via_persistance(self, monkeypatch):
        from scrabble.ui import api_tirage_ordre as mod

        supprimees: list = []
        monkeypatch.setattr(
            mod, "supprimer_partie",
            lambda id_p, chemin: supprimees.append(id_p) or True,
        )
        api = ApiJeu(_partie_simple(), id_partie=42, infos_tirage=dict(self._INFOS))

        api.supprimer_partie_annulee()

        assert supprimees == [42]

    def test_supprimer_partie_annulee_mode_demo_ne_supprime_rien(self, monkeypatch):
        from scrabble.ui import api_tirage_ordre as mod

        supprimees: list = []
        monkeypatch.setattr(
            mod, "supprimer_partie",
            lambda id_p, chemin: supprimees.append(id_p) or True,
        )
        # id_partie None (démonstration) : rien à supprimer.
        api = ApiJeu(_partie_simple(), id_partie=None, infos_tirage=dict(self._INFOS))

        api.supprimer_partie_annulee()

        assert supprimees == []






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
    """Maximisation du plateau à la finalisation (issue #95 / #193)."""

    def test_finalise_maximise_le_plateau(self, monkeypatch):
        from scrabble.ui import jeu as mod

        appels: list = []
        monkeypatch.setattr(
            mod, "_maximiser_plateau", lambda w: appels.append(("plateau", w))
        )
        mod._finaliser_fenetres("PLAT")
        assert appels == [("plateau", "PLAT")]


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
