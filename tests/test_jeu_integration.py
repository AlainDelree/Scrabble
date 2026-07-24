"""Tests d'intégration de l'écran de jeu (issue #264).

Ces tests couvrent volontairement plusieurs mixins à la fois : ils vérifient
des scénarios de bout en bout traversant pose, persistance, reprise et fin
de partie. Ce regroupement est intentionnel — il ne s'agit pas d'un défaut
de tri mais d'une couverture transversale délibérée.
"""

from collections import Counter

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie, creer_partie
from scrabble.persistance import (
    STATUT_TERMINEE,
    demarrer_suivi,
    lister_parties,
    reprendre_partie,
)
from scrabble.ui.jeu import ApiJeu

from tests._aides_test_jeu import _DicoFactice, _DicoMots, _partie_simple, _placement


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
