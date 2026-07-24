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
    _FenetreEspionne,
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
from scrabble.ui.jeu import (
    ApiJeu,
    construire_partie_demo,
    echanger_chevalet_complet,
    echanger_jetons,
    etat_public,
    jouer_tours_ia_ui,
    passer_tour,
)


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


# --------------------------------------------------------------------------- #
# Suite #29 (issue #31) : comptage des humains, échange complet du chevalet.
# Note : les tests de vérification dictionnaire du brouillon ont été déplacés
# dans ``test_jeu_brouillon.py`` (issue #257).
# --------------------------------------------------------------------------- #


class TestEchangerChevaletComplet:
    """Échange de la totalité du chevalet (remet tout et passe le tour)."""

    def _partie(self) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        return partie

    def test_succes_change_tout_et_passe_tour(self):
        partie = self._partie()
        chevalet_avant = list(partie.joueurs[0].chevalet)
        sac_avant = partie.sac.jetons_restants()

        res = echanger_chevalet_complet(partie, None)

        assert res["succes"] is True
        assert "etat" in res
        # Le tour a bien avancé (échange = consommation du tour).
        assert partie.index_courant == 1
        # Le chevalet reste plein mais son contenu a été renouvelé depuis le sac.
        assert len(partie.joueurs[0].chevalet) == len(chevalet_avant)
        # Le sac garde le même total (autant tiré que remis).
        assert partie.sac.jetons_restants() == sac_avant
        # L'état renvoyé reste public (aucune lettre de chevalet).
        for joueur_pub in res["etat"]["joueurs"]:
            assert "lettres" not in joueur_pub

    def test_echec_sac_trop_pauvre(self):
        partie = self._partie()
        # On vide le sac : plus assez de jetons pour échanger tout le chevalet.
        partie.sac.tirer(partie.sac.jetons_restants())
        chevalet_avant = list(partie.joueurs[0].chevalet)

        res = echanger_chevalet_complet(partie, None)

        assert res["succes"] is False
        assert res.get("erreur")
        assert "etat" not in res
        # Aucun effet de bord : ni le tour ni le chevalet ne bougent.
        assert partie.index_courant == 0
        assert list(partie.joueurs[0].chevalet) == chevalet_avant

    def test_api_echanger_tout_delegue(self):
        partie = self._partie()
        api = ApiJeu(partie, 42)
        res = api.echanger_tout()
        assert res["succes"] is True
        assert res["etat"]["id_partie"] == 42
        assert partie.index_courant == 1


class TestEchangerSelection:
    """Échange PARTIEL d'une sélection de lettres du chevalet (issue #138)."""

    def _partie(self) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        return partie

    def _api(self, partie: Partie, *, partiel: bool = False) -> ApiJeu:
        # id_partie=None : aucune écriture en base pendant les tests.
        api = ApiJeu(partie, None)
        api._type_echange = "partiel" if partiel else "complet"
        return api

    def test_echanger_jetons_cas_general(self):
        """Le cœur commun échange une liste précise et passe le tour."""
        partie = self._partie()
        sac_avant = partie.sac.jetons_restants()
        cible = partie.joueurs[0].chevalet[0]

        res = echanger_jetons(partie, None, [cible])

        assert res["succes"] is True
        assert "etat" in res
        assert partie.index_courant == 1
        assert len(partie.joueurs[0].chevalet) == 7
        assert partie.sac.jetons_restants() == sac_avant

    def test_echange_une_lettre(self):
        partie = self._partie()
        sac_avant = partie.sac.jetons_restants()
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([0])

        assert res["succes"] is True
        assert "etat" in res
        # Le tour a avancé, le chevalet reste plein, le sac garde son total.
        assert partie.index_courant == 1
        assert len(partie.joueurs[0].chevalet) == 7
        assert partie.sac.jetons_restants() == sac_avant
        # L'historique consigne un échange d'exactement une lettre.
        assert partie.historique[-1].lettres_echangees == 1

    def test_echange_plusieurs_lettres(self):
        partie = self._partie()
        sac_avant = partie.sac.jetons_restants()
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([0, 2, 4])

        assert res["succes"] is True
        assert partie.index_courant == 1
        assert len(partie.joueurs[0].chevalet) == 7
        assert partie.sac.jetons_restants() == sac_avant
        assert partie.historique[-1].lettres_echangees == 3

    def test_echec_sac_insuffisant(self):
        partie = self._partie()
        # On vide le sac : plus assez de jetons pour échanger la sélection.
        partie.sac.tirer(partie.sac.jetons_restants())
        chevalet_avant = list(partie.joueurs[0].chevalet)
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([0, 1])

        assert res["succes"] is False
        assert res.get("erreur")
        assert "etat" not in res
        # Aucun effet de bord : ni le tour ni le chevalet ne bougent.
        assert partie.index_courant == 0
        assert list(partie.joueurs[0].chevalet) == chevalet_avant

    def test_echec_hors_tour(self):
        """La garde de tour (#99/#130) refuse un échange hors du tour de référence."""
        partie = self._partie()
        # Ce n'est plus le tour du joueur de référence (Alice, index 0).
        partie.index_courant = 1
        chevalet_ref = list(partie.joueurs[0].chevalet)
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([0])

        assert res["succes"] is False
        assert "tour" in res["erreur"].lower()
        # Rien n'a bougé : ni le tour, ni le chevalet du joueur de référence.
        assert partie.index_courant == 1
        assert list(partie.joueurs[0].chevalet) == chevalet_ref

    def test_echec_selection_vide(self):
        """Une sélection vide (0 lettre) est refusée (1 à 7, jamais 0)."""
        partie = self._partie()
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([])

        assert res["succes"] is False
        assert partie.index_courant == 0

    def test_echec_selection_none_sans_marquage(self):
        """Sans indices explicites ni marquage, la sélection courante est vide → refus."""
        partie = self._partie()
        api = self._api(partie, partiel=True)

        res = api.echanger_selection()

        assert res["succes"] is False
        assert partie.index_courant == 0

    def test_echec_index_invalide(self):
        """Un index hors du chevalet invalide toute la sélection."""
        partie = self._partie()
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([0, 99])

        assert res["succes"] is False
        assert partie.index_courant == 0

    def test_echec_index_duplique(self):
        """Un même index répété est refusé (sélection incohérente)."""
        partie = self._partie()
        api = self._api(partie, partiel=True)

        res = api.echanger_selection([1, 1])

        assert res["succes"] is False
        assert partie.index_courant == 0

    def test_flux_mode_marquage_puis_validation(self):
        """commencer → basculer (marquage multiple) → echanger_selection (sans indices)."""
        partie = self._partie()
        sac_avant = partie.sac.jetons_restants()
        api = self._api(partie, partiel=True)

        assert api.commencer_echange()["succes"] is True
        assert api._mode_echange is True

        api.basculer_echange(0)
        api.basculer_echange(3)
        assert api._selection_echange == [0, 3]
        # Reclic : on démarque la lettre 0.
        api.basculer_echange(0)
        assert api._selection_echange == [3]

        res = api.echanger_selection()

        assert res["succes"] is True
        assert partie.index_courant == 1
        assert partie.sac.jetons_restants() == sac_avant
        # Le mode et la sélection sont remis à zéro après un échange réussi.
        assert api._mode_echange is False
        assert api._selection_echange == []

    def test_commencer_echange_refuse_en_mode_complet(self):
        """En mode « complet », le flux d'échange partiel n'est pas ouvrable."""
        partie = self._partie()
        api = self._api(partie, partiel=False)

        res = api.commencer_echange()

        assert res["succes"] is False
        assert api._mode_echange is False

    def test_basculer_refuse_hors_mode(self):
        """Marquer une lettre sans avoir ouvert le mode échange est refusé."""
        partie = self._partie()
        api = self._api(partie, partiel=True)

        res = api.basculer_echange(0)

        assert res["succes"] is False
        assert api._selection_echange == []

    def test_annuler_echange_vide_la_selection(self):
        """Annuler quitte le mode et vide la sélection sans rien échanger."""
        partie = self._partie()
        chevalet_avant = list(partie.joueurs[0].chevalet)
        api = self._api(partie, partiel=True)
        api.commencer_echange()
        api.basculer_echange(0)
        api.basculer_echange(1)

        res = api.annuler_echange()

        assert res["succes"] is True
        assert api._mode_echange is False
        assert api._selection_echange == []
        # Aucun échange : le chevalet et le tour sont intacts.
        assert list(partie.joueurs[0].chevalet) == chevalet_avant
        assert partie.index_courant == 0

    def test_type_echange_complet_par_defaut_dans_api(self):
        """Sans réglage « partiel », l'API démarre en mode complet (non-régression)."""
        partie = self._partie()
        # Construit sans forcer le mode : lit la config réelle (défaut « complet »).
        api = ApiJeu(partie, None)
        assert api._type_echange == "complet"
        # L'échange complet historique reste opérant et inchangé.
        res = api.echanger_tout()
        assert res["succes"] is True
        assert partie.index_courant == 1


class TestApparenceBoutonsEchange:
    """Cohérence visuelle des boutons d'échange dans le markup (issue #147).

    Vérification headless : « Échanger des lettres… » (mode partiel) doit avoir
    l'apparence d'un vrai bouton **dès son état initial**, avant tout clic — la
    même famille visuelle (« btn btn-secondaire ») que « Remettre toutes ses
    lettres et passer » (mode complet, issue #139). Une fois le mode de sélection
    engagé (« après clic »), les boutons révélés (« Échanger la sélection… » /
    « Annuler la sélection ») doivent eux aussi porter le style « btn ».
    """

    @staticmethod
    def _classes(html: str, id_bouton: str) -> list[str]:
        """Renvoie la liste des classes CSS du ``<button id=...>`` demandé."""
        import re

        motif = re.compile(
            r'<button\b[^>]*\bid="' + re.escape(id_bouton) + r'"[^>]*>',
            re.DOTALL,
        )
        balise = motif.search(html)
        assert balise is not None, f"bouton #{id_bouton} introuvable dans jeu.html"
        classe = re.search(r'\bclass="([^"]*)"', balise.group(0))
        assert classe is not None, f"bouton #{id_bouton} sans attribut class"
        return classe.group(1).split()

    def _html(self) -> str:
        from scrabble.ui.jeu import DOSSIER_WEB

        return (DOSSIER_WEB / "jeu.html").read_text(encoding="utf-8")

    def test_bouton_commencer_echange_a_apparence_de_bouton(self):
        """État initial (avant clic) : « Échanger des lettres… » est un vrai bouton."""
        classes = self._classes(self._html(), "btn-commencer-echange")
        assert "btn" in classes
        assert "btn-secondaire" in classes
        # Plus de style « lien discret » : plus de changement d'apparence au clic.
        assert "lien-discret" not in classes

    def test_coherence_entre_modes_complet_et_partiel(self):
        """Les deux déclencheurs d'échange partagent la même famille visuelle."""
        html = self._html()
        complet = self._classes(html, "btn-echanger-tout")
        partiel = self._classes(html, "btn-commencer-echange")
        assert "btn" in complet and "btn-secondaire" in complet
        assert set(complet) == set(partiel)

    def test_boutons_selection_restent_des_boutons(self):
        """Après clic : les boutons de sélection révélés gardent le style « btn »."""
        html = self._html()
        assert "btn" in self._classes(html, "btn-echanger-selection")
        assert "btn" in self._classes(html, "btn-annuler-echange")


class TestBoutonJouerDansFicheJoueur:
    """Bouton « ▶ Jouer » dans la fiche d'un ordinateur courant (issue #149).

    Vérification headless du markup : pendant le tour d'un ordinateur, sa fiche
    joueur expose un bouton « ▶ Jouer » (classe ``panneau-btn-jouer``) à la place
    de l'ancien label « ● son tour », qui déclenche ``api.faire_jouer_ia`` ; l'humain
    courant garde sa pastille « ● à vous ». L'ancien bouton séparé de la zone
    d'attente IA (``#btn-jouer-ia``, « Faire jouer l'ordinateur ») est retiré ; et
    depuis l'issue #160 le cadre d'attente lui-même (« En attente du coup de… ») est
    entièrement supprimé.
    """

    def _lire(self, nom: str) -> str:
        from scrabble.ui.jeu import DOSSIER_WEB

        return (DOSSIER_WEB / nom).read_text(encoding="utf-8")

    def test_fiche_ordinateur_courant_a_un_bouton_jouer(self):
        """La branche « ordinateur courant » produit un bouton « Jouer »."""
        js = self._lire("jeu.js")
        # Le bouton porte la classe dédiée, le style primaire et le texte « Jouer ».
        assert "panneau-btn-jouer" in js
        assert "▶ Jouer" in js
        assert "btn btn-primaire panneau-btn-jouer" in js

    def test_humain_courant_garde_la_pastille_a_vous(self):
        """L'humain courant conserve « ● à vous » (pas de bouton Jouer)."""
        js = self._lire("jeu.js")
        assert "● à vous" in js

    def test_ancien_label_son_tour_retire(self):
        """Le label « son tour » a disparu (remplacé par le bouton Jouer).

        On cible la chaîne LITTÉRALE ``'son tour'`` de l'ancien ternaire de badge ;
        « Passer son tour » (autre fonctionnalité) reste évidemment présent ailleurs.
        """
        js = self._lire("jeu.js")
        assert "'son tour'" not in js

    def test_bouton_declenche_faire_jouer_ia(self):
        """Le bouton de la fiche est câblé au flux api.faire_jouer_ia."""
        js = self._lire("jeu.js")
        # Le bouton du panneau est relié à lancerTourIA, qui appelle l'API.
        assert "querySelector('.panneau-btn-jouer')" in js
        assert "lancerTourIA" in js
        assert "api.faire_jouer_ia()" in js

    def test_ancien_bouton_separe_retire(self):
        """Plus de bouton « Faire jouer l'ordinateur » dans la zone d'attente."""
        html = self._lire("jeu.html")
        js = self._lire("jeu.js")
        assert 'id="btn-jouer-ia"' not in html
        assert "btn-jouer-ia" not in js
        assert "btnJouerIA" not in js

    def test_cadre_attente_supprime(self):
        """Le cadre « En attente du coup de… » est supprimé (issue #160).

        La réorganisation des actions de tour autour de la fiche du joueur humain
        (issue #160) supprime complètement ce bandeau : pendant le tour d'un
        ordinateur, son coup se déclenche déjà via le bouton « ▶ Jouer » de sa
        propre fiche (issue #149), ce cadre n'apportait plus rien. On vérifie que
        ni le conteneur, ni le message, ni le texte ne subsistent.
        """
        html = self._lire("jeu.html")
        js = self._lire("jeu.js")
        assert 'id="zone-attente-ia"' not in html
        assert 'id="attente-ia-message"' not in html
        assert "En attente du coup de" not in js


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


class TestPasserTour:
    """Passage « sec » du tour (sans échange) — débloque un humain sac vide (#132)."""

    def _partie(self) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        return partie

    def test_passe_incremente_le_compteur_et_avance(self):
        partie = self._partie()
        assert partie.passes_consecutives == 0

        res = passer_tour(partie, None)

        assert res["succes"] is True
        assert "etat" in res
        # La passe a bien été comptée et le tour a avancé, sans terminer (2 joueurs).
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1
        assert partie.terminee is False
        # L'état renvoyé reste public (aucune lettre de chevalet).
        for joueur_pub in res["etat"]["joueurs"]:
            assert "lettres" not in joueur_pub

    def test_humain_sac_vide_peut_passer(self):
        # Cas moteur du rapport #130 : sac vide, l'humain ne peut ni poser ni
        # échanger, mais DOIT pouvoir passer.
        partie = self._partie()
        partie.sac.tirer(partie.sac.jetons_restants())
        assert partie.sac.jetons_restants() == 0

        res = passer_tour(partie, None)

        assert res["succes"] is True
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1

    def test_api_passer_delegue_et_incremente(self):
        partie = self._partie()
        api = ApiJeu(partie, 42)
        res = api.passer()
        assert res["succes"] is True
        assert res["etat"]["id_partie"] == 42
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1

    def test_passe_refusee_partie_terminee(self):
        partie = self._partie()
        partie.terminee = True

        res = passer_tour(partie, None)

        assert res["succes"] is False
        assert res.get("erreur")
        assert "etat" not in res

    def test_tous_passent_atteint_la_fin_par_blocage(self):
        # De bout en bout : une partie où TOUS les joueurs (ici deux humains)
        # passent consécutivement atteint la fin par blocage — le critère
        # ``passes_consecutives >= len(joueurs)`` est désormais atteignable même
        # avec des humains (via l'API), ce qui était impossible avant #132.
        partie = self._partie()
        api = ApiJeu(partie, id_partie=None)

        res1 = api.passer()
        assert res1["succes"] is True
        assert partie.terminee is False
        assert partie.passes_consecutives == 1

        res2 = api.passer()
        assert res2["succes"] is True
        # Deux joueurs, deux passes consécutives : partie bloquée → terminée.
        assert partie.passes_consecutives >= len(partie.joueurs)
        assert partie.terminee is True
        assert res2["etat"]["terminee"] is True


# --------------------------------------------------------------------------- #
# Correction du défaut d'exposition du tour IA (issue #35)
# --------------------------------------------------------------------------- #


class TestJouerToursIaUi:
    """Enchaînement des tours IA côté API (jouer_tours_ia_ui / faire_jouer_ia)."""

    def _partie_ia(self) -> Partie:
        """Humain (index 0) puis deux ordinateurs, sur un dictionnaire réel."""
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot1", humain=False, niveau=Niveau.EXPERT),
            Joueur(nom="Robot2", humain=False, niveau=Niveau.EXPERT),
        ]
        return Partie(joueurs, Trie.depuis_iterable(["CADRE"]), graine=1)

    def test_joueur_humain_courant_aucun_tour(self):
        partie = self._partie_ia()
        partie.index_courant = 0
        res = jouer_tours_ia_ui(partie, None)
        assert res["succes"] is True
        assert res["nb_tours"] == 0
        assert partie.index_courant == 0  # rien n'a bougé
        assert res["etat"]["index_courant"] == 0

    def test_un_seul_tour_ia_par_appel(self):
        partie = self._partie_ia()
        partie.index_courant = 1  # tour du premier ordinateur
        # Chevalets sans voyelle jouable : les IA passent leur tour (2 de 3 passes
        # consécutives ne terminent pas une partie à 3 joueurs).
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        # Un seul clic = un seul tour d'ordinateur (issue #55) : après cet appel,
        # c'est au tour du DEUXIÈME ordinateur, pas encore à l'humain.
        res = jouer_tours_ia_ui(partie, None)
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert partie.index_courant == 2
        assert partie.joueur_courant().humain is False
        assert res["etat"]["index_courant"] == 2
        assert res["etat"]["tour_humain"] is False
        # Deuxième clic : le second ordinateur joue, puis la main revient à
        # l'humain.
        res2 = jouer_tours_ia_ui(partie, None)
        assert res2["nb_tours"] == 1
        assert partie.index_courant == 0
        assert partie.joueur_courant().humain is True
        assert res2["etat"]["tour_humain"] is True

    def test_api_faire_jouer_ia_delegue(self):
        partie = self._partie_ia()
        partie.index_courant = 1
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        api = ApiJeu(partie, 99)
        # Un seul tour joué par appel (issue #55) : reste au tour du 2e ordinateur.
        res = api.faire_jouer_ia()
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert res["etat"]["id_partie"] == 99
        assert partie.index_courant == 2
        assert partie.joueur_courant().humain is False

    def test_api_faire_jouer_ia_sans_effet_si_humain(self):
        partie = self._partie_ia()
        partie.index_courant = 0
        api = ApiJeu(partie, None)
        res = api.faire_jouer_ia()
        assert res["nb_tours"] == 0
        assert partie.index_courant == 0


class TestApiJeuRetourMenu:
    """Tests de ``ApiJeu.retour_menu`` (issue #74).

    Vérifie que la fenêtre de jeu est fermée depuis Python via
    ``window.destroy()`` (fiable sous GTK/WebKit, issues #53/#57) et que le
    drapeau ``_retour_menu`` est positionné pour que ``lancer_jeu`` rouvre
    l'accueil. Testé sans vraie fenêtre grâce à un objet factice.
    """

    def test_retour_menu_appelle_destroy_et_marque_le_drapeau(self):
        class FakeWindow:
            def __init__(self):
                self.detruite = False

            def destroy(self):
                self.detruite = True

        api = ApiJeu(_partie_simple(), id_partie=7)
        fake = FakeWindow()
        api.set_window(fake)

        resultat = api.retour_menu()

        assert resultat["succes"] is True
        assert fake.detruite is True
        assert api._retour_menu is True

    def test_retour_menu_sans_fenetre(self):
        api = ApiJeu(_partie_simple(), id_partie=None)
        resultat = api.retour_menu()

        assert resultat["succes"] is False
        assert "erreur" in resultat
        # Aucune fenêtre : pas de retour au menu déclenché.
        assert api._retour_menu is False

    def test_retour_menu_exception_destroy_naboutit_pas(self):
        class FakeWindow:
            def destroy(self):
                raise RuntimeError("backend HS")

        api = ApiJeu(_partie_simple(), id_partie=1)
        api.set_window(FakeWindow())

        resultat = api.retour_menu()

        assert resultat["succes"] is False
        assert "backend HS" in resultat["erreur"]
        # La fermeture a échoué : on ne rouvrira PAS l'accueil.
        assert api._retour_menu is False


class TestApiJeuRecommencer:
    """Tests de ``ApiJeu.recommencer`` / ``creer_partie_recommencee`` (issue #142).

    Vérifie que « Recommencer » fabrique une nouvelle partie avec les mêmes
    joueurs (nom, humain/IA, niveau), qu'elle est suivie en base sans supprimer
    l'ancienne partie, et que les deux fenêtres sont fermées (drapeau
    ``_recommencer``). Testé sans vraie fenêtre grâce à un objet factice.
    """

    class _FakeWindow:
        def __init__(self):
            self.detruite = False

        def destroy(self):
            self.detruite = True

    def _partie_mixte(self, graine: int = 3) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
            Joueur(nom="Ordi", humain=False, niveau=Niveau.EXPERT),
        ]
        return Partie(joueurs, _DicoFactice(), graine=graine)

    def test_creer_partie_recommencee_memes_joueurs(self):
        origine = self._partie_mixte()
        api = ApiJeu(origine, id_partie=None)

        nouvelle = api.creer_partie_recommencee()

        assert nouvelle is not origine
        cle = lambda p: {(j.nom, j.humain, j.niveau) for j in p.joueurs}
        assert cle(nouvelle) == cle(origine)
        # Partie neuve : graine explicite (pour le suivi), historique vierge.
        assert nouvelle.graine is not None
        assert nouvelle.historique == []
        assert not nouvelle.terminee

    def test_recommencer_persiste_la_nouvelle_sans_supprimer_l_ancienne(self, tmp_path):
        chemin = tmp_path / "parties.db"
        origine = self._partie_mixte()
        id_origine = demarrer_suivi(origine, chemin)

        api = ApiJeu(origine, id_partie=id_origine, chemin_persistance=chemin)
        fake = self._FakeWindow()
        api.set_window(fake)

        resultat = api.recommencer()

        assert resultat["succes"] is True
        assert fake.detruite is True
        assert api._recommencer is True
        assert api._nouvelle_partie is not None
        # Un nouvel identifiant, distinct de l'ancien, a été attribué.
        assert api._nouvel_id_partie is not None
        assert api._nouvel_id_partie != id_origine
        # L'ancienne partie n'a PAS été supprimée : les deux coexistent en base.
        ids = {p.id for p in lister_parties(chemin)}
        assert ids == {id_origine, api._nouvel_id_partie}

    def test_recommencer_mode_demo_ne_persiste_pas(self):
        # id_partie None (démonstration) : la nouvelle partie n'est pas suivie,
        # mais la mécanique de fermeture/relance fonctionne quand même.
        api = ApiJeu(self._partie_mixte(), id_partie=None)
        fake = self._FakeWindow()
        api.set_window(fake)

        resultat = api.recommencer()

        assert resultat["succes"] is True
        assert api._recommencer is True
        assert api._nouvelle_partie is not None
        assert api._nouvel_id_partie is None

    def test_recommencer_sans_fenetre(self):
        api = ApiJeu(self._partie_mixte(), id_partie=None)
        resultat = api.recommencer()

        assert resultat["succes"] is False
        assert "erreur" in resultat
        assert api._recommencer is False
        assert api._nouvelle_partie is None

    def test_recommencer_exception_destroy_naboutit_pas(self):
        class FakeWindowKO:
            def destroy(self):
                raise RuntimeError("backend HS")

        api = ApiJeu(self._partie_mixte(), id_partie=None)
        api.set_window(FakeWindowKO())

        resultat = api.recommencer()

        assert resultat["succes"] is False
        assert "backend HS" in resultat["erreur"]
        # Échec de fermeture : on n'enchaîne PAS de nouvelle partie.
        assert api._recommencer is False
        assert api._nouvelle_partie is None


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






class TestApiJeuRetourMenuFenetreUnique:
    """``retour_menu`` détruit la fenêtre unique (issue #193)."""

    def test_retour_menu_avec_seule_fenetre_plateau(self):
        # Compat mono-fenêtre : set_window ne renseigne que le plateau.
        api = ApiJeu(_partie_simple(), id_partie=1)
        fake = _FenetreEspionne()
        api.set_window(fake)
        res = api.retour_menu()
        assert res["succes"] is True
        assert fake.detruite is True
        # « Retour au menu » repositionne le drapeau qui rouvre l'accueil.
        assert api._retour_menu is True


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
