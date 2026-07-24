"""Tests d'échange de lettres du chevalet (issue #260).

Couvre :
- l'échange complet du chevalet (remettre tout et passer le tour)
- l'échange partiel d'une sélection de lettres (issue #138)
"""

import pytest

from scrabble.moteur.partie import Joueur, Partie
from scrabble.ui.jeu import (
    ApiJeu,
    echanger_chevalet_complet,
    echanger_jetons,
)
from tests._aides_test_jeu import _DicoFactice, _partie_simple


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
