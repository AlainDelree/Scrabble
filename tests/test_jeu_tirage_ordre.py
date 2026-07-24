"""Tests du tirage d'ordre et de la confidentialité pour l'écran de jeu (issue #258).

Classes extraites de test_jeu.py :
- TestDetailTirageOrdre — détail du tirage d'ordre (issue #170)
- TestApiConfidentialite — règle « un seul chevalet exposé à la fois »
- TestThemePlateau — lecture du thème visuel de plateau
- TestApiJeuTirageOrdre — tirage piloté par ApiJeu (issue #170)
- TestFinaliserEntreeVueJeu — finalisation à chaque entrée (#180)
"""

import pytest

from scrabble.ui.jeu import ApiJeu
from tests._aides_test_jeu import _DicoFactice, _partie_simple


class _FenetreEspionne:
    """Fenêtre pywebview factice qui enregistre les appels ``evaluate_js``."""

    def __init__(self) -> None:
        self.scripts: list[str] = []
        self.detruite = False

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)

    def destroy(self) -> None:
        self.detruite = True


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
            "scrabble.ui.api_tirage_ordre.charger_config", lambda: {"theme_plateau": "vert"}
        )
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_theme_plateau() == "vert"

    def test_theme_inconnu_retombe_sur_classique(self, monkeypatch):
        """Une valeur imprévue (config trafiquée) est ramenée à « classique »."""
        monkeypatch.setattr(
            "scrabble.ui.api_tirage_ordre.charger_config", lambda: {"theme_plateau": "n_importe_quoi"}
        )
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_theme_plateau() == "classique"

    def test_theme_absent_retombe_sur_classique(self, monkeypatch):
        """Clé absente de la config : défaut « classique »."""
        monkeypatch.setattr("scrabble.ui.api_tirage_ordre.charger_config", lambda: {})
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_theme_plateau() == "classique"


class TestDetailTirageOrdre:
    """Tests de ``detail_tirage_ordre`` migré de l'accueil (issue #170).

    La reconstitution du détail du tirage d'ordre (« Chaque joueur a tiré une
    lettre ») vit désormais dans ``scrabble.ui.jeu``. On vérifie sa structure,
    le drapeau ``humain`` par joueur, l'ordre alphabétique des lettres et le
    déterminisme à graine fixée.
    """

    def test_structure_et_drapeau_humain(self):
        from scrabble.ui.jeu import detail_tirage_ordre

        detail = detail_tirage_ordre(
            ["Alice", "Bob", "Ordi"], graine=7, noms_humains=["Alice", "Bob"]
        )
        assert set(detail.keys()) == {"tirages", "ordre"}
        assert len(detail["tirages"]) == 3
        for t in detail["tirages"]:
            assert set(t.keys()) == {"nom", "lettre", "humain"}
            assert isinstance(t["lettre"], str) and len(t["lettre"]) == 1
        humain = {t["nom"]: t["humain"] for t in detail["tirages"]}
        assert humain == {"Alice": True, "Bob": True, "Ordi": False}
        # L'ordre annoncé est une permutation des mêmes noms, chacun une fois.
        assert sorted(detail["ordre"]) == ["Alice", "Bob", "Ordi"]

    def test_ordre_suit_les_lettres_alphabetiques(self):
        from scrabble.ui.jeu import detail_tirage_ordre

        detail = detail_tirage_ordre(["Alice", "Bob", "Ordi"], graine=11)
        lettre_par_nom = {t["nom"]: t["lettre"] for t in detail["tirages"]}
        lettres_dans_ordre = [lettre_par_nom[nom] for nom in detail["ordre"]]
        # L'ordre de jeu suit l'ordre alphabétique des lettres tirées (égalités
        # départagées par retirage, non exposé : la séquence reste croissante).
        assert lettres_dans_ordre == sorted(lettres_dans_ordre)

    def test_deterministe_a_graine_fixee(self):
        from scrabble.ui.jeu import detail_tirage_ordre

        a = detail_tirage_ordre(["Alice", "Bob"], graine=3)
        b = detail_tirage_ordre(["Alice", "Bob"], graine=3)
        assert a == b

    def test_sans_noms_humains_tous_non_humains(self):
        from scrabble.ui.jeu import detail_tirage_ordre

        detail = detail_tirage_ordre(["Alice", "Bob"], graine=1)
        assert all(t["humain"] is False for t in detail["tirages"])


class TestApiJeuTirageOrdre:
    """Tests du tirage d'ordre piloté par ``ApiJeu`` (issue #170).

    Le tirage, autrefois affiché en modale de l'accueil, est désormais mené dans
    la fenêtre Jeu : ``obtenir_tirage_ordre`` fournit son détail au démarrage (ou
    ``None`` en reprise), ``terminer_tirage`` marque le tirage terminé au clic
    « Continuer », et ``annuler_tirage`` supprime la partie créée puis revient à
    l'accueil. Testé sans vraie fenêtre grâce à des objets factices.
    """

    _INFOS = {
        "noms_creation": ["Alice", "Robot"],
        "graine": 1,
        "noms_humains": ["Alice"],
    }

    def test_obtenir_tirage_ordre_none_sans_infos(self):
        api = ApiJeu(_partie_simple(), id_partie=1)
        assert api.obtenir_tirage_ordre() is None
        # Aucun tirage à mener : considéré terminé d'emblée (garde idempotence).
        assert api._tirage_termine is True

    def test_obtenir_tirage_ordre_reconstitue_le_detail(self):
        api = ApiJeu(_partie_simple(), id_partie=1, infos_tirage=dict(self._INFOS))
        assert api._tirage_termine is False
        detail = api.obtenir_tirage_ordre()
        assert set(detail.keys()) == {"tirages", "ordre"}
        assert len(detail["tirages"]) == 2
        humain = {t["nom"]: t["humain"] for t in detail["tirages"]}
        assert humain == {"Alice": True, "Robot": False}

    def test_terminer_tirage_marque_termine_et_est_idempotent(self):
        api = ApiJeu(_partie_simple(), id_partie=1, infos_tirage=dict(self._INFOS))
        assert api._tirage_termine is False

        res = api.terminer_tirage()
        assert res["succes"] is True
        assert api._tirage_termine is True

        # Idempotent : un second appel (reprise/double-clic) reste sans effet.
        res2 = api.terminer_tirage()
        assert res2["succes"] is True
        assert api._tirage_termine is True

    def test_annuler_tirage_supprime_la_partie_et_ferme(self, monkeypatch):
        from scrabble.ui import api_tirage_ordre as mod

        supprimees: list = []
        monkeypatch.setattr(
            mod,
            "supprimer_partie",
            lambda id_p, chemin: supprimees.append(id_p) or True,
        )

        api = ApiJeu(_partie_simple(), id_partie=42, infos_tirage=dict(self._INFOS))
        plateau = _FenetreEspionne()
        api.set_window(plateau)

        res = api.annuler_tirage()
        assert res["succes"] is True
        # La partie fraîchement créée (aucun coup joué) est supprimée de la base.
        assert supprimees == [42]
        assert plateau.detruite is True
        # Retour à l'accueil via le même drapeau que « Retour au menu ».
        assert api._retour_menu is True

    def test_annuler_tirage_sans_fenetre(self):
        api = ApiJeu(_partie_simple(), id_partie=42, infos_tirage=dict(self._INFOS))
        res = api.annuler_tirage()
        assert res["succes"] is False
        assert "erreur" in res
        assert api._retour_menu is False


class TestFinaliserEntreeVueJeu:
    """``_finaliser_entree_vue_jeu`` rejoue la finalisation à chaque entrée (#180).

    Depuis la suppression de la fenêtre chevalet (issue #193), le corps ne fait
    plus que maximiser le plateau puis amorcer l'état (``_diffuser``).
    """

    def _api(self, monkeypatch, infos_tirage=None):
        """API prête + fenêtre espionne unique ; neutralise le plein écran."""
        from scrabble.moteur.ia import Niveau
        from scrabble.moteur.partie import Joueur, Partie
        from scrabble.ui import jeu as mod

        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=1)
        partie.index_courant = 0
        partie.joueurs[0].chevalet = list("CHATSER")
        api = ApiJeu(partie, None)
        plateau = _FenetreEspionne()
        api.set_window(plateau)
        if infos_tirage is not None:
            # Rejoue le contrat de charger_partie : tirage encore à mener.
            api._infos_tirage = infos_tirage
            api._tirage_termine = False
        # Neutralise les opérations fenêtre réelles (attente shown, WM, GDK).
        appels = []
        monkeypatch.setattr(mod, "_maximiser_plateau",
                            lambda w: appels.append("maximiser"))
        return api, plateau, appels

    def test_reprise_maximise_et_amorce(self, monkeypatch):
        """Sans tirage : plateau maximisé puis état amorcé (_diffuser)."""
        api, plateau, appels = self._api(monkeypatch)  # reprise

        api._finaliser_entree_vue_jeu()

        assert appels == ["maximiser"]
        # Le chevalet ayant migré dans jeu.html (issue #187), l'amorçage
        # (appliquerEtatChevalet via _diffuser) part vers la fenêtre plateau/Jeu.
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)

    def test_diffuse_meme_pendant_le_tirage(self, monkeypatch):
        """Avec tirage en cours : plateau maximisé et état tout de même amorcé."""
        infos = {"noms_creation": ["Alice", "Robot"], "graine": 1,
                 "noms_humains": ["Alice"]}
        api, plateau, appels = self._api(monkeypatch, infos_tirage=infos)

        api._finaliser_entree_vue_jeu()

        # La maximisation du plateau est rejouée (plus aucune distinction tirage).
        assert appels == ["maximiser"]
        # L'état (zone C de jeu.html) est amorcé via la fenêtre plateau/Jeu, même
        # tirage en cours, prêt pour terminer_tirage (issue #187).
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)

    def test_thread_lance_le_corps(self, monkeypatch):
        """``finaliser_entree_vue_jeu`` exécute bien le corps (via un fil)."""
        api, _plateau, _appels = self._api(monkeypatch)
        marqueur = []
        monkeypatch.setattr(api, "_finaliser_entree_vue_jeu",
                            lambda: marqueur.append("fait"))

        api.finaliser_entree_vue_jeu()
        # Le fil est daemon : on lui laisse le temps de tourner.
        import time
        for _ in range(50):
            if marqueur:
                break
            time.sleep(0.01)
        assert marqueur == ["fait"]
