"""Tests des points d'entrée et de l'interface plateau (issue #263).

Couvre :
- le mode démonstration (``construire_partie_demo``)
- le déploiement plein écran du plateau (``_maximiser_plateau``)
- la finalisation des fenêtres (``_finaliser_fenetres``)
- la détection de la zone de travail (``_zone_travail_ecran``)
- la fermeture mutuelle des popovers
"""

from scrabble.regles.plateau import CENTRE, TAILLE
from scrabble.ui.jeu import construire_partie_demo, etat_public


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
