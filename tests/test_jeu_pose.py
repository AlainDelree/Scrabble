"""Tests de l'état de pose centralisé et des actions de coup (issue #259).

Couvre :
- ``ApiJeu.poser_mot`` et ``ApiJeu.verifier_coup`` (succès, erreur, confidentialité)
- la sélection de lettres (``_selection``)
- les placements en attente (``_en_attente``)
- la pose de joker (modale de choix)
- le remplacement d'une lettre en attente (issue #129)
- la garde de tour (mutations refusées hors tour, issue #99)
- la pose via l'état interne (issue #90)
- la source dictionnaire appliquée à la validation (issue #211)

Note : ce module regroupe les tests extraits de ``test_jeu.py`` pour la lisibilité.
"""

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import Tuile
from scrabble.regles.lettres import JOKER
from scrabble.ui.jeu import ApiJeu
from tests._aides_test_jeu import (
    _DicoMots,
    _FenetreEspionne,
    _placement,
)


def _api_pose(lettres: str = "CHATSER") -> tuple[ApiJeu, _FenetreEspionne]:
    """API prête pour la pose, avec une fenêtre espionne unique (plateau).

    Le joueur 0 (humain, courant) porte le chevalet ``lettres``. Renvoie
    ``(api, fenetre_plateau)``.
    """
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(nom="Robot", humain=False, niveau=Niveau.FACILE),
    ]
    partie = Partie(joueurs, _DicoMots("CHAT", "CHATS"), graine=1)
    partie.index_courant = 0
    partie.joueurs[0].chevalet = list(lettres)
    api = ApiJeu(partie, None)
    plateau = _FenetreEspionne()
    api.set_window(plateau)
    return api, plateau


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

    def test_verifier_coup_valide_ne_joue_pas(self):
        # ApiJeu.verifier_coup (issue #69) : calcule les points sans jouer.
        api = self._api_avec_chevalet("CHATSER", mots=("CHAT",))
        placements = [
            _placement(7, 7, "C"),
            _placement(7, 8, "H"),
            _placement(7, 9, "A"),
            _placement(7, 10, "T"),
        ]
        res = api.verifier_coup(placements)
        assert res["succes"] is True
        assert res["points"] > 0
        assert res["detail"]["mots"][0]["texte"] == "CHAT"
        # Le coup n'a pas été joué : plateau vide, tour et chevalet inchangés.
        partie = api._partie
        assert partie.plateau.case_vide(7, 7)
        assert partie.index_courant == 0
        assert partie.joueurs[0].chevalet == list("CHATSER")

    def test_verifier_coup_invalide_renvoie_erreur(self):
        api = self._api_avec_chevalet("XYZWKQJ", mots=("CHAT",))
        placements = [
            _placement(7, 7, "X"),
            _placement(7, 8, "Y"),
            _placement(7, 9, "Z"),
        ]
        res = api.verifier_coup(placements)
        assert res["succes"] is False
        assert res.get("erreur")
        assert "points" not in res


class TestApiJeuSelection:
    """``ApiJeu.selectionner_lettre`` : centralisation de ``_selection`` (issue #90)."""

    def test_selectionne_met_a_jour_et_diffuse(self):
        api, plateau = _api_pose()
        res = api.selectionner_lettre(2)
        assert res["succes"] is True
        assert api._selection == 2
        # Depuis l'issue #187 (chevalet migré en zone C de jeu.html), les DEUX
        # charges sont poussées à la MÊME fenêtre Jeu unique.
        assert len(plateau.scripts) == 2
        assert any("appliquerEtatPlateau" in s for s in plateau.scripts)
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)

    def test_reclic_meme_index_deselectionne(self):
        api, _plateau = _api_pose()
        api.selectionner_lettre(2)
        api.selectionner_lettre(2)
        assert api._selection is None

    def test_index_none_annule_la_selection(self):
        api, _plateau = _api_pose()
        api.selectionner_lettre(1)
        api.selectionner_lettre(None)
        assert api._selection is None


class TestApiJeuPoseEnAttente:
    """Pose/retrait d'une lettre en attente pilotés par l'état interne (issue #90)."""

    def test_pose_resout_la_lettre_depuis_la_selection(self):
        api, plateau = _api_pose("CHATSER")
        api.selectionner_lettre(0)  # « C »
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert (place["ligne"], place["colonne"]) == (7, 7)
        assert place["lettre"] == "C"
        assert place["joker"] is False
        assert place["index"] == 0
        # La sélection est consommée et l'état rediffusé (les deux charges vers la
        # fenêtre Jeu unique depuis l'issue #187).
        assert api._selection is None
        assert any("appliquerEtatPlateau" in s for s in plateau.scripts)
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)

    def test_pose_sans_selection_refusee(self):
        api, _plateau = _api_pose()
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert api._en_attente == []

    def test_pose_sur_case_occupee_refusee(self):
        api, _plateau = _api_pose()
        api._partie.plateau.poser_tuile(7, 7, Tuile("Z"))
        api.selectionner_lettre(0)
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert api._en_attente == []

    def test_pose_hors_plateau_refusee(self):
        api, _plateau = _api_pose()
        api.selectionner_lettre(0)
        res = api.poser_lettre_en_attente(-1, 7)
        assert res["succes"] is False

    def test_deux_lettres_sur_la_meme_case_refusee(self):
        api, _plateau = _api_pose()
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert len(api._en_attente) == 1

    def test_retrait_supprime_le_placement_et_diffuse(self):
        api, plateau = _api_pose()
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        avant_plateau = len(plateau.scripts)
        res = api.retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert api._en_attente == []
        # Le retrait effectif rediffuse l'état : depuis l'issue #187, un _diffuser
        # pousse les DEUX charges (plateau + chevalet) à la fenêtre Jeu unique,
        # d'où +2 scripts sur la fenêtre plateau.
        assert len(plateau.scripts) == avant_plateau + 2

    def test_retrait_sans_placement_ne_diffuse_pas(self):
        api, plateau = _api_pose()
        avant = len(plateau.scripts)
        res = api.retirer_lettre_en_attente(0, 0)
        assert res["succes"] is True
        assert len(plateau.scripts) == avant  # aucune mutation, aucune diffusion

    def test_annuler_pose_vide_tout_et_diffuse(self):
        api, plateau = _api_pose()
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        res = api.annuler_pose()
        assert res["succes"] is True
        assert api._en_attente == []
        assert api._selection is None
        # Les deux charges vers la fenêtre Jeu unique depuis l'issue #187.
        assert any("appliquerEtatPlateau" in s for s in plateau.scripts)
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)


class TestApiJeuPoseJoker:
    """Pose d'un joker : la modale de choix s'ouvre côté chevalet (issue #90)."""

    def test_clic_plateau_sur_joker_differe_la_pose(self):
        api, _plateau = _api_pose(JOKER + "CHATSE")
        api.selectionner_lettre(0)  # le joker
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert res["joker_requis"] is True
        # Rien n'est encore posé ; la case visée est mémorisée pour le chevalet.
        assert api._en_attente == []
        assert api._joker_demande == {"ligne": 7, "colonne": 7, "index": 0}

    def test_finalisation_joker_depuis_le_chevalet(self):
        api, _plateau = _api_pose(JOKER + "CHATSE")
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # Le chevalet renvoie la lettre choisie pour le joker.
        res = api.poser_lettre_en_attente(7, 7, lettre="E", joker=True, valeur=0, index=0)
        assert res["succes"] is True
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert place["lettre"] == "E"
        assert place["joker"] is True
        assert place["valeur"] == 0
        assert api._joker_demande is None


class TestApiJeuRemplacementEnAttente:
    """Remplacement d'une lettre en attente au clic, avec sélection (issue #129).

    Un clic sur une case portant une lettre en attente du tour courant passe
    désormais par ``remplacer_ou_retirer_lettre_en_attente`` : avec une lettre
    sélectionnée, la sélection prend la place et l'ancienne revient au chevalet ;
    sans sélection, le comportement de retrait simple est préservé.
    """

    def test_remplacement_avec_selection(self):
        api, plateau = _api_pose("CHATSER")
        # « C » (index 0) posée en 7,7.
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # On sélectionne « H » (index 1) et on reclique la case : remplacement.
        api.selectionner_lettre(1)
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        # Une seule lettre en attente : la nouvelle, à la même place.
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert (place["ligne"], place["colonne"]) == (7, 7)
        assert place["lettre"] == "H"
        assert place["index"] == 1
        assert place["joker"] is False
        # L'ancienne lettre (index 0) n'est plus consommée : de nouveau disponible.
        assert all(p["index"] != 0 for p in api._en_attente)
        # La sélection est consommée et l'état rediffusé (les deux charges vers la
        # fenêtre Jeu unique depuis l'issue #187).
        assert api._selection is None
        assert any("appliquerEtatPlateau" in s for s in plateau.scripts)
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)

    def test_remplacement_ne_casse_pas_le_compteur(self):
        api, _plateau = _api_pose("CHATSER")
        # Deux lettres posées : « C » (0) en 7,7 et « H » (1) en 7,8.
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        api.poser_lettre_en_attente(7, 8)
        # On remplace « C » par « A » (index 2) : le compteur reste à 2.
        api.selectionner_lettre(2)
        api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert len(api._en_attente) == 2
        indices = sorted(p["index"] for p in api._en_attente)
        assert indices == [1, 2]  # « C » (0) libérée, « A » (2) posée, « H » (1) intacte

    def test_sans_selection_retrait_simple(self):
        api, plateau = _api_pose("CHATSER")
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # Aucune sélection active au moment du clic : retrait simple (cas limite 1).
        assert api._selection is None
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert api._en_attente == []
        assert res.get("joker_requis") is None

    def test_remplacement_par_joker_ouvre_la_modale(self):
        api, _plateau = _api_pose("C" + JOKER + "ATSER")
        # « C » (index 0) posée en 7,7, puis on sélectionne le joker (index 1).
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        api.selectionner_lettre(1)
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is True
        assert res["joker_requis"] is True
        # La pose du joker est différée : l'ancienne lettre reste en place tant que
        # la modale n'est pas validée, et la case est mémorisée pour le chevalet.
        assert api._joker_demande == {"ligne": 7, "colonne": 7, "index": 1}
        assert len(api._en_attente) == 1
        assert api._en_attente[0]["lettre"] == "C"
        # Finalisation depuis le chevalet : le joker remplace l'ancienne lettre.
        api.poser_lettre_en_attente(7, 7, lettre="E", joker=True, valeur=0, index=1)
        assert len(api._en_attente) == 1
        place = api._en_attente[0]
        assert place["lettre"] == "E"
        assert place["joker"] is True
        assert place["index"] == 1
        assert api._joker_demande is None

    def test_case_sans_lettre_en_attente_sans_effet(self):
        api, plateau = _api_pose("CHATSER")
        api.selectionner_lettre(0)
        avant = len(plateau.scripts)
        res = api.remplacer_ou_retirer_lettre_en_attente(0, 0)
        assert res["succes"] is True
        assert api._en_attente == []
        # Aucune mutation : la sélection reste intacte, rien n'est rediffusé.
        assert api._selection == 0
        assert len(plateau.scripts) == avant

    def test_remplacement_hors_tour_refuse(self):
        api, _plateau = _api_pose("CHATSER")
        api.selectionner_lettre(0)
        api.poser_lettre_en_attente(7, 7)
        # On passe hors tour : la mutation doit être refusée sans toucher l'état.
        api._partie.index_courant = 1
        res = api.remplacer_ou_retirer_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert len(api._en_attente) == 1


class TestApiJeuGardeDeTour:
    """Mutations de pose refusées hors du tour du joueur de référence (issue #99).

    Le chevalet est désormais toujours visible et sélectionnable, mais toute
    mutation de l'état de pose reste réservée au tour réel : la garde
    :meth:`ApiJeu._refuser_hors_tour` doit refuser proprement sans toucher à
    ``_selection`` / ``_en_attente``.
    """

    def _api_hors_tour(self):
        """API où le joueur de référence (index 0) n'est PAS courant (tour IA)."""
        api, plateau = _api_pose("CHATSER")
        api._partie.index_courant = 1  # au tour de l'ordinateur
        return api, plateau

    def test_selectionner_lettre_hors_tour_refusee(self):
        api, plateau = self._api_hors_tour()
        avant_plateau = len(plateau.scripts)
        res = api.selectionner_lettre(0)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._selection is None  # état de pose intact
        # Aucune diffusion : l'état n'a pas bougé.
        assert len(plateau.scripts) == avant_plateau

    def test_poser_lettre_en_attente_hors_tour_refusee(self):
        api, _plateau = self._api_hors_tour()
        res = api.poser_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._en_attente == []

    def test_retirer_lettre_en_attente_hors_tour_refusee(self):
        api, _plateau = self._api_hors_tour()
        # On injecte un placement pour vérifier qu'il n'est PAS retiré hors tour.
        api._en_attente = [
            {"ligne": 7, "colonne": 7, "lettre": "C", "joker": False,
             "valeur": 3, "index": 0}
        ]
        res = api.retirer_lettre_en_attente(7, 7)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert len(api._en_attente) == 1  # placement intact

    def test_annuler_pose_hors_tour_refusee(self):
        api, _plateau = self._api_hors_tour()
        api._selection = 2
        api._en_attente = [
            {"ligne": 7, "colonne": 7, "lettre": "C", "joker": False,
             "valeur": 3, "index": 0}
        ]
        res = api.annuler_pose()
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._selection == 2  # état de pose intact
        assert len(api._en_attente) == 1

    def test_mutation_refusee_partie_terminee(self):
        api, _plateau = _api_pose("CHATSER")
        api._partie.index_courant = 0  # c'est bien le tour du joueur de référence
        api._partie.terminee = True
        res = api.selectionner_lettre(0)
        assert res["succes"] is False
        assert res["erreur"] == "Ce n'est pas votre tour."
        assert api._selection is None

    def test_mutation_autorisee_au_tour_du_joueur_reference(self):
        api, _plateau = _api_pose("CHATSER")
        api._partie.index_courant = 0  # tour du joueur de référence
        res = api.selectionner_lettre(0)
        assert res["succes"] is True
        assert api._selection == 0


class TestApiJeuPoseViaEtatInterne:
    """``poser_mot``/``verifier_coup`` lisent ``_en_attente`` (issue #90)."""

    def test_poser_mot_sans_argument_lit_l_etat_interne(self):
        api, _plateau = _api_pose("CHATSER")
        for i, (lig, col, let) in enumerate(
            [(7, 7, "C"), (7, 8, "H"), (7, 9, "A"), (7, 10, "T")]
        ):
            api.selectionner_lettre(i)
            api.poser_lettre_en_attente(lig, col)
        res = api.poser_mot()  # aucun placement passé : lecture de _en_attente
        assert res["succes"] is True
        assert "etat" in res
        # Après un coup joué, l'état de pose est remis à zéro.
        assert api._en_attente == []
        assert api._selection is None

    def test_verifier_coup_sans_argument_lit_l_etat_interne(self):
        api, _plateau = _api_pose("CHATSER")
        for i, (lig, col, _let) in enumerate(
            [(7, 7, "C"), (7, 8, "H"), (7, 9, "A"), (7, 10, "T")]
        ):
            api.selectionner_lettre(i)
            api.poser_lettre_en_attente(lig, col)
        res = api.verifier_coup()  # non destructif : ne consomme pas l'attente
        assert res["succes"] is True
        assert res["detail"]["mots"][0]["texte"] == "CHAT"
        assert len(api._en_attente) == 4  # rien n'est consommé
        assert api._partie.plateau.case_vide(7, 7)

    def test_poser_mot_reussi_diffuse_le_nouvel_etat(self):
        api, plateau = _api_pose("CHATSER")
        for i, (lig, col) in enumerate([(7, 7), (7, 8), (7, 9), (7, 10)]):
            api.selectionner_lettre(i)
            api.poser_lettre_en_attente(lig, col)  # « CHAT »
        avant = len(plateau.scripts)
        res = api.poser_mot()
        assert res["succes"] is True
        # Le coup joué rediffuse les deux charges vers la fenêtre Jeu unique
        # (issue #187) : la fenêtre plateau reçoit et l'état public et l'état privé.
        assert len(plateau.scripts) > avant
        assert any("appliquerEtatChevalet" in s for s in plateau.scripts)


class TestApiJeuDiffusionConfidentialite:
    """``_diffuser`` : payload public + payload privé, tous deux à la fenêtre Jeu.

    Depuis l'issue #187 (chevalet migré en zone C de ``jeu.html``), les deux
    charges sont poussées à la MÊME fenêtre (``_window_plateau``) : la charge
    publique (``appliquerEtatPlateau``, sans lettre de chevalet) et la charge
    privée (``appliquerEtatChevalet``, lettres du seul joueur de référence). La
    garantie de confidentialité (#99) est inchangée — voir les tests de
    ``_etat_chevalet`` ci-dessus.
    """

    def test_payload_plateau_public_sans_lettres_de_chevalet(self):
        api, _plateau = _api_pose("CHATSER")
        etat = api._etat_plateau()
        # Aucune identité de lettre de chevalet : ni au niveau racine, ni par joueur.
        assert "lettres" not in etat
        for joueur_pub in etat["joueurs"]:
            assert "lettres" not in joueur_pub
        # En revanche l'état de pose neutre (sélection, placements) y figure.
        assert "en_attente" in etat
        assert "selection" in etat

    def test_payload_chevalet_contient_les_lettres_privees(self):
        api, _plateau = _api_pose("CHATSER")
        etat = api._etat_chevalet()
        lettres = [c["lettre"] for c in etat["lettres"]]
        assert lettres == list("CHATSER")
        assert etat["selection"] is None
        assert etat["en_attente"] == []
        # Au tour du joueur de référence : mon_tour est vrai (issue #99).
        assert etat["mon_tour"] is True
        assert etat["index_reference"] == 0
        # Champs supprimés (issue #99) : plus de tour_humain ni nb_humains.
        assert "tour_humain" not in etat
        assert "nb_humains" not in etat

    def test_chevalet_reference_toujours_expose_au_tour_ia(self):
        """Au tour de l'IA, le chevalet du joueur de référence reste exposé.

        Le panneau est toujours visible (issue #99) : ``lettres`` porte bien le
        chevalet du joueur humain de référence (jamais celui de l'IA) et
        ``mon_tour`` vaut ``False`` puisque ce n'est pas son tour.
        """
        api, _plateau = _api_pose("CHATSER")
        api._partie.index_courant = 1  # au tour de l'ordinateur
        etat = api._etat_chevalet()
        lettres = [c["lettre"] for c in etat["lettres"]]
        assert lettres == list("CHATSER")  # chevalet du joueur de référence
        assert etat["index_reference"] == 0  # jamais l'index de l'IA
        assert etat["mon_tour"] is False

    def test_chevalet_ordinateur_jamais_expose(self):
        """Le chevalet d'un ordinateur n'est jamais sérialisé (issue #35/#99).

        Même au tour de l'IA, ``lettres`` reste le chevalet du joueur de
        référence (index 0), jamais celui de l'ordinateur (index 1).
        """
        api, _plateau = _api_pose("CHATSER")
        api._partie.joueurs[1].chevalet = list("ZZZZZZZ")  # chevalet IA distinct
        api._partie.index_courant = 1  # au tour de l'ordinateur
        etat = api._etat_chevalet()
        lettres = [c["lettre"] for c in etat["lettres"]]
        assert lettres == list("CHATSER")  # celui du joueur de référence
        assert "Z" not in lettres  # jamais le chevalet de l'IA
        assert etat["mon_tour"] is False

    def test_diffusion_route_les_deux_charges_vers_la_fenetre_jeu(self):
        api, plateau = _api_pose("CHATSER")
        api._diffuser()
        # Les deux charges partent à la fenêtre Jeu unique (issue #187).
        assert len(plateau.scripts) == 2
        script_public = next(
            s for s in plateau.scripts if "appliquerEtatPlateau" in s)
        script_prive = next(
            s for s in plateau.scripts if "appliquerEtatChevalet" in s)
        # La charge publique ne transporte AUCUNE liste de lettres de chevalet ;
        # la charge privée, si (clé JSON "lettres") — confidentialité inchangée.
        assert '"lettres"' not in script_public
        assert '"lettres"' in script_prive

    def test_fenetre_absente_ne_bloque_pas_la_diffusion(self):
        api, _plateau = _api_pose()
        api.set_window(None)  # plus aucune fenêtre
        # Ne doit pas lever, même sans fenêtre à qui pousser l'état.
        api._diffuser()


class TestSourceDictionnaireValidationCoup:
    """La source du dictionnaire s'applique jusqu'à la validation d'un coup réel (issue #211).

    Suite de l'issue #210 : celui-ci ne corrigeait que la CRÉATION de la partie
    (``ApiAccueil.lancer_partie``/``reprendre`` transmettant enfin
    ``source_dictionnaire`` à ``obtenir_trie``). Le rapport #211 soupçonnait un
    SECOND point — côté ``ui/jeu.py`` (``ApiJeu.verifier_coup``/``poser_mot``) ou
    ``ui/application.py`` — qui reconstruirait un Trie sur l'ODS par défaut au
    lieu de réutiliser ``partie.dictionnaire`` déjà corrigé.

    Vérification exhaustive : aucun tel point n'existe. ``verifier_coup`` délègue
    à :func:`simuler_coup` (→ ``valider_coup(..., partie.dictionnaire)``),
    ``poser_mot`` à :func:`jouer_placements` (→ ``partie.jouer_coup`` →
    ``self.dictionnaire``). Ces tests l'ancrent de bout en bout : on crée la
    partie via l'accueil avec une source donnée (Trie **spécifique à la source**,
    monkeypatché), puis on valide/joue un coup via la vraie ``ApiJeu`` et on
    exige que le verdict suive la source choisie.

    Note factuelle (données réelles vérifiées) : « COVID » est présent dans la
    source Hunspell et **absent** de l'ODS8 ; « AERA » est présent dans l'ODS8 et
    **absent** de Hunspell. Le rapport #211 avait inversé ces appartenances : le
    « COVID accepté sous Hunspell » qu'il décrivait est en réalité le
    comportement CORRECT. Ces mots servent ici de témoins croisés.
    """

    _TRIES = {
        # COVID : Hunspell uniquement ; AERA : ODS uniquement (données réelles).
        "hunspell": _DicoMots("COVID"),
        "ods": _DicoMots("AERA"),
    }

    def _creer_partie_via_accueil(self, monkeypatch, source):
        """Crée une partie via ``ApiAccueil.lancer_partie`` avec la source donnée.

        On monkeypatch ``obtenir_trie`` pour renvoyer un Trie **propre à la
        source** (sans dépendre des fichiers de dictionnaire réels, gitignorés),
        exactement comme le fait le chemin de production après #210.
        """
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.charger_config",
            lambda: {
                "source_dictionnaire": source,
                "vocabulaire_humain": False,
                "bonus_fin_partie": False,
            },
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda s="ods": self._TRIES[s],
        )
        # Pas de persistance en base pendant le test : id_partie reste None,
        # ce qui neutralise aussi ``_persister_entrees`` côté ApiJeu.
        monkeypatch.setattr("scrabble.ui.accueil.demarrer_suivi", lambda partie: None)

        api = ApiAccueil()
        api.ajouter_humain("Alice")
        api.ajouter_ordinateur("Facile")
        resultat = api.lancer_partie()
        assert resultat["succes"] is True
        return api._partie, api._id_partie

    @staticmethod
    def _preparer_api_jeu(partie, id_partie, lettres):
        """Installe la partie dans une ``ApiJeu`` et arme le chevalet du joueur courant."""
        # Le tirage d'ordre a pu réordonner les joueurs : on place la main sur le
        # joueur humain et on lui donne les tuiles nécessaires au coup.
        partie.index_courant = next(
            i for i, j in enumerate(partie.joueurs) if j.humain
        )
        partie.joueurs[partie.index_courant].chevalet = list(lettres)
        # Chemin historique accueil → jeu : ``ApiJeu(partie, id_partie)`` (voir
        # ``lancer_jeu``). id_partie None → aucune écriture en base.
        return ApiJeu(partie, id_partie)

    @staticmethod
    def _placements(mot):
        """Placements « clic-clic » d'un mot horizontal couvrant le centre (7,7)."""
        return [_placement(7, 7 + i, lettre) for i, lettre in enumerate(mot)]

    def test_verifier_coup_refuse_mot_absent_de_la_source_active(self, monkeypatch):
        """Sous Hunspell, un mot ODS-only (« AERA ») est refusé par « Vérifier et calculer »."""
        partie, id_partie = self._creer_partie_via_accueil(monkeypatch, "hunspell")
        api = self._preparer_api_jeu(partie, id_partie, "AERASXY")

        resultat = api.verifier_coup(self._placements("AERA"))

        assert resultat["succes"] is False
        assert resultat.get("erreur")
        # Aucun score annoncé pour un coup refusé (pas de « +N points » trompeur).
        assert "points" not in resultat

    def test_poser_mot_refuse_mot_absent_de_la_source_active(self, monkeypatch):
        """Sous Hunspell, « Jouer » refuse aussi le mot ODS-only et n'avance pas la partie."""
        partie, id_partie = self._creer_partie_via_accueil(monkeypatch, "hunspell")
        api = self._preparer_api_jeu(partie, id_partie, "AERASXY")
        index_avant = partie.index_courant
        historique_avant = len(partie.historique)

        resultat = api.poser_mot(self._placements("AERA"))

        assert resultat["succes"] is False
        assert resultat.get("erreur")
        # La partie n'a pas avancé : correction possible sans rien perdre.
        assert partie.index_courant == index_avant
        assert len(partie.historique) == historique_avant
        assert partie.plateau.case_vide(7, 7)

    def test_verifier_coup_accepte_mot_propre_a_la_source_active(self, monkeypatch):
        """Sous Hunspell, un mot Hunspell-only (« COVID ») est bien accepté et scoré.

        Témoin positif : prouve que le Trie effectivement consulté est celui de
        Hunspell (et non un ODS reconstruit, qui refuserait COVID).
        """
        partie, id_partie = self._creer_partie_via_accueil(monkeypatch, "hunspell")
        api = self._preparer_api_jeu(partie, id_partie, "COVIDSX")

        resultat = api.verifier_coup(self._placements("COVID"))

        assert resultat["succes"] is True
        assert resultat["points"] > 0
        assert resultat["detail"]["mots"][0]["texte"] == "COVID"

    def test_source_ods_par_defaut_aucune_regression(self, monkeypatch):
        """Sous ODS (défaut), le verdict s'inverse : AERA accepté, COVID refusé.

        Garde-fou anti-régression sur le comportement par défaut demandé par #211.
        """
        partie, id_partie = self._creer_partie_via_accueil(monkeypatch, "ods")
        api = self._preparer_api_jeu(partie, id_partie, "AERACOV")

        accepte = api.verifier_coup(self._placements("AERA"))
        assert accepte["succes"] is True
        assert accepte["detail"]["mots"][0]["texte"] == "AERA"

        refuse = api.verifier_coup(self._placements("COVID"))
        assert refuse["succes"] is False
        assert refuse.get("erreur")

    def test_routeur_unifie_conserve_le_dictionnaire_de_la_partie(self, monkeypatch):
        """La coquille unifiée (``ApiRouteur.charger_jeu``) ne reconstruit aucun Trie.

        Point 3 du rapport #211 : ``application.py`` transmet la partie créée par
        l'accueil à la sous-API Jeu SANS toucher au dictionnaire. On vérifie
        l'identité de l'objet ``dictionnaire`` de bout en bout, ce qui exclut
        toute reconstruction silencieuse sur la source par défaut.
        """
        from scrabble.ui.application import ApiRouteur

        partie, id_partie = self._creer_partie_via_accueil(monkeypatch, "hunspell")
        dico_attendu = partie.dictionnaire

        routeur = ApiRouteur()
        routeur.charger_jeu(partie, id_partie)

        # La sous-API Jeu tient exactement la même partie, avec le même Trie.
        assert routeur._api_jeu._partie is partie
        assert routeur._api_jeu._partie.dictionnaire is dico_attendu
