"""Tests de la logique non-UI de l'écran d'accueil.

Couvre :
- ConfigPartie : validation des contraintes de nombre de joueurs
- Construction de la configuration avant appel à creer_partie
- Logique d'exclusion des prénoms déjà pris à la table
"""

import pytest

from scrabble.moteur.ia import Niveau
from scrabble.ui.accueil import (
    MAX_HUMAINS,
    MAX_ORDINATEURS,
    ConfigPartie,
    JoueurConfig,
    NIVEAUX_LABELS,
)
from scrabble.ui.noms_ordinateur import PRENOMS_ORDINATEUR


class TestJoueurConfig:
    """Tests de la dataclass JoueurConfig."""

    def test_joueur_humain_par_defaut(self):
        """Un joueur est humain par défaut, sans niveau."""
        joueur = JoueurConfig(nom="Marie")
        assert joueur.nom == "Marie"
        assert joueur.humain is True
        assert joueur.niveau is None

    def test_joueur_ordinateur(self):
        """Un ordinateur a humain=False et un niveau défini."""
        joueur = JoueurConfig(nom="Antoine", humain=False, niveau=Niveau.FACILE)
        assert joueur.nom == "Antoine"
        assert joueur.humain is False
        assert joueur.niveau == Niveau.FACILE


class TestConfigPartieCompteurs:
    """Tests des compteurs de ConfigPartie."""

    def test_config_vide(self):
        """Une configuration vide n'a aucun joueur."""
        config = ConfigPartie()
        assert config.nb_humains == 0
        assert config.nb_ordinateurs == 0
        assert config.nb_total == 0

    def test_compteurs_mixtes(self):
        """Les compteurs distinguent humains et ordinateurs.

        Un seul humain est désormais autorisé (issue #175) : on complète donc
        avec des ordinateurs pour exercer le mélange des compteurs.
        """
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_ordinateur("Bob", Niveau.FACILE)
        config.ajouter_ordinateur("Camille", Niveau.INTERMEDIAIRE)

        assert config.nb_humains == 1
        assert config.nb_ordinateurs == 2
        assert config.nb_total == 3


class TestConfigPartieContraintes:
    """Tests des contraintes de nombre de joueurs."""

    def test_peut_ajouter_humain_config_vide(self):
        """On peut ajouter un humain dans une configuration vide."""
        config = ConfigPartie()
        assert config.peut_ajouter_humain() is True

    def test_peut_ajouter_ordinateur_config_vide(self):
        """On peut ajouter un ordinateur dans une configuration vide."""
        config = ConfigPartie()
        assert config.peut_ajouter_ordinateur() is True

    def test_limite_un_seul_humain(self):
        """On ne peut pas dépasser UN joueur humain (issue #175).

        ``MAX_HUMAINS`` vaut désormais 1 : dès le premier humain ajouté,
        ``peut_ajouter_humain`` repasse à ``False`` et un second ajout est
        refusé (le bouton « Ajouter un joueur » disparaît côté UI).
        """
        assert MAX_HUMAINS == 1
        config = ConfigPartie()
        assert config.peut_ajouter_humain() is True

        assert config.ajouter_humain("Alice") is True
        assert config.nb_humains == 1
        assert config.peut_ajouter_humain() is False

        # Le second ajout est refusé sans modifier la configuration.
        assert config.ajouter_humain("Bob") is False
        assert config.nb_humains == 1

    def test_limite_3_ordinateurs(self):
        """On ne peut pas dépasser 3 ordinateurs."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")  # Il faut au moins un humain
        for i in range(MAX_ORDINATEURS):
            assert config.peut_ajouter_ordinateur() is True
            config.ajouter_ordinateur(f"Ordi{i}", Niveau.FACILE)

        assert config.nb_ordinateurs == 3
        assert config.peut_ajouter_ordinateur() is False

    def test_limite_4_joueurs_total(self):
        """Le total ne peut pas dépasser 4 joueurs (1 humain + 3 ordinateurs)."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_ordinateur("Bob", Niveau.FACILE)
        config.ajouter_ordinateur("Camille", Niveau.FACILE)
        config.ajouter_ordinateur("Daniel", Niveau.EXPERT)

        assert config.nb_total == 4
        assert config.peut_ajouter_humain() is False
        assert config.peut_ajouter_ordinateur() is False

    def test_second_humain_refuse_meme_table_non_pleine(self):
        """Un second humain est refusé même quand la table n'est pas pleine.

        La contrainte « un seul humain » (issue #175) est indépendante de la
        limite de 4 joueurs : avec un seul humain configuré, ``peut_ajouter_
        humain`` est déjà ``False`` alors que ``peut_ajouter_ordinateur`` reste
        ``True``.
        """
        config = ConfigPartie()
        config.ajouter_humain("Alice")

        assert config.nb_total == 1
        assert config.peut_ajouter_humain() is False
        assert config.peut_ajouter_ordinateur() is True


class TestConfigPartieLancement:
    """Tests des conditions de lancement."""

    def test_ne_peut_pas_lancer_sans_humain(self):
        """Une partie sans humain ne peut pas être lancée."""
        config = ConfigPartie()
        assert config.peut_lancer() is False

        config.ajouter_ordinateur("Ordi", Niveau.FACILE)
        assert config.peut_lancer() is False

    def test_peut_lancer_avec_un_humain(self):
        """Un seul humain suffit pour lancer."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        assert config.peut_lancer() is True

    def test_peut_lancer_avec_humain_et_ordinateurs(self):
        """On peut lancer avec un mix humains/ordinateurs."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_ordinateur("Bob", Niveau.EXPERT)
        config.ajouter_ordinateur("Charlie", Niveau.DEBUTANT)
        assert config.peut_lancer() is True

    def test_ne_peut_pas_lancer_avec_deux_humains(self):
        """Exactement un humain est requis (issue #175).

        ``ajouter_humain`` refusant déjà un second humain, on force ici une
        configuration invalide en insérant directement les ``JoueurConfig`` pour
        vérifier que ``peut_lancer`` (garde-fou backend non contournable) rejette
        bien le multi-humains.
        """
        config = ConfigPartie(
            joueurs=[
                JoueurConfig(nom="Alice", humain=True),
                JoueurConfig(nom="Bob", humain=True),
            ]
        )
        assert config.nb_humains == 2
        assert config.peut_lancer() is False


class TestConfigPartieNoms:
    """Tests de la gestion des noms utilisés."""

    def test_noms_utilises_vide(self):
        """Une config vide n'a aucun nom utilisé."""
        config = ConfigPartie()
        assert config.noms_utilises() == set()

    def test_noms_utilises_humains(self):
        """Le nom de l'humain (unique désormais) est dans les noms utilisés."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_ordinateur("Bob", Niveau.FACILE)
        assert config.noms_utilises() == {"Alice", "Bob"}

    def test_noms_utilises_mixtes(self):
        """Tous les noms (humains et ordinateurs) sont dans les noms utilisés."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_ordinateur("Camille", Niveau.FACILE)
        assert config.noms_utilises() == {"Alice", "Camille"}


class TestConfigPartieRetrait:
    """Tests du retrait de joueurs."""

    def test_retrait_joueur_valide(self):
        """Retirer un joueur à un index valide fonctionne."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_ordinateur("Bob", Niveau.FACILE)

        assert config.retirer(0) is True
        assert config.nb_humains == 0
        assert config.joueurs[0].nom == "Bob"

    def test_retrait_index_invalide(self):
        """Retirer à un index invalide retourne False."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")

        assert config.retirer(-1) is False
        assert config.retirer(1) is False
        assert config.retirer(100) is False
        assert config.nb_humains == 1

    def test_retrait_reactive_boutons(self):
        """Retirer l'humain réactive la possibilité d'en ajouter un (issue #175).

        Le bouton « Ajouter un joueur » (masqué tant qu'un humain est présent)
        doit réapparaître dès que cet humain est retiré.
        """
        config = ConfigPartie()
        config.ajouter_humain("Alice")

        assert config.peut_ajouter_humain() is False
        config.retirer(0)
        assert config.peut_ajouter_humain() is True


class TestConfigPartieAjoutAvecRetour:
    """Tests des retours des méthodes d'ajout."""

    def test_ajouter_humain_succes(self):
        """Ajouter un humain retourne True."""
        config = ConfigPartie()
        assert config.ajouter_humain("Alice") is True

    def test_ajouter_humain_echec(self):
        """Ajouter un second humain retourne False (issue #175)."""
        config = ConfigPartie()
        assert config.ajouter_humain("Alice") is True
        assert config.ajouter_humain("Trop") is False
        assert config.nb_humains == 1

    def test_ajouter_ordinateur_succes(self):
        """Ajouter un ordinateur retourne True."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        assert config.ajouter_ordinateur("Bot", Niveau.FACILE) is True

    def test_ajouter_ordinateur_echec(self):
        """Ajouter un ordinateur quand impossible retourne False."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        for i in range(3):
            config.ajouter_ordinateur(f"Bot{i}", Niveau.FACILE)
        assert config.ajouter_ordinateur("Trop", Niveau.EXPERT) is False


class TestNiveauxLabels:
    """Tests du mapping des labels de niveau."""

    def test_tous_les_niveaux_ont_un_label(self):
        """Chaque niveau de l'enum a un label français."""
        for niveau in Niveau:
            label_trouve = any(
                NIVEAUX_LABELS[label] == niveau for label in NIVEAUX_LABELS
            )
            assert label_trouve, f"Niveau {niveau} sans label"

    def test_labels_attendus(self):
        """Les labels français correspondent aux bons niveaux."""
        assert NIVEAUX_LABELS["Débutant"] == Niveau.DEBUTANT
        assert NIVEAUX_LABELS["Facile"] == Niveau.FACILE
        assert NIVEAUX_LABELS["Intermédiaire"] == Niveau.INTERMEDIAIRE
        assert NIVEAUX_LABELS["Expert"] == Niveau.EXPERT


class TestExclusionPrenoms:
    """Tests de l'exclusion des prénoms déjà utilisés."""

    def test_noms_utilises_pour_exclusion(self):
        """Les noms utilisés servent à exclure les tirages."""
        config = ConfigPartie()
        config.ajouter_humain("Antoine")  # Prénom de la liste PRENOMS_ORDINATEUR

        noms_pris = config.noms_utilises()
        assert "Antoine" in noms_pris

    def test_tous_prenoms_ordinateur_excluables(self):
        """On peut exclure n'importe quel prénom de la liste ordinateur."""
        from scrabble.ui.noms_ordinateur import prenoms_disponibles

        config = ConfigPartie()
        config.ajouter_humain("Camille")

        disponibles = prenoms_disponibles(config.noms_utilises())
        assert "Camille" not in [p.casefold() for p in disponibles]
        # Mais les autres sont disponibles
        assert len(disponibles) == len(PRENOMS_ORDINATEUR) - 1


class TestApiAccueilLancement:
    """Tests de ApiAccueil.lancer_partie et .reprendre (issue #52).

    Vérifie que les méthodes renvoient ``pret: True`` pour signaler au JS
    qu'il doit fermer la fenêtre et laisser l'écran de jeu s'ouvrir.
    """

    def test_lancer_partie_renvoie_pret(self, tmp_path, monkeypatch):
        """lancer_partie() renvoie pret=True en cas de succès."""
        from scrabble.ui.accueil import ApiAccueil
        from scrabble.dictionnaire.dictionnaire import Trie

        # Stub du dictionnaire pour éviter le chargement complet
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda: Trie.depuis_iterable(["MAISON", "TEST"]),
        )
        # Stub de la persistance pour éviter d'écrire sur disque
        monkeypatch.setattr(
            "scrabble.ui.accueil.demarrer_suivi",
            lambda partie: 42,
        )

        api = ApiAccueil()
        api.ajouter_humain("Alice")
        api.ajouter_ordinateur("Intermédiaire")

        result = api.lancer_partie()
        assert result["succes"] is True
        assert result["pret"] is True
        assert result["id_partie"] == 42
        assert api._partie is not None
        assert api._id_partie == 42

    def test_reprendre_renvoie_pret(self, tmp_path, monkeypatch):
        """reprendre() renvoie pret=True en cas de succès."""
        from scrabble.ui.accueil import ApiAccueil
        from scrabble.dictionnaire.dictionnaire import Trie
        from scrabble.moteur.partie import Partie, Joueur

        # Créer une partie factice à "reprendre"
        partie_reprise = Partie(
            joueurs=[Joueur(nom="Bob", humain=True)],
            dictionnaire=Trie.depuis_iterable(["TEST"]),
            graine=123,
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda: Trie.depuis_iterable(["TEST"]),
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.reprendre_partie",
            lambda id_partie, trie, dictionnaire_ia=None: partie_reprise,
        )

        api = ApiAccueil()
        result = api.reprendre(99)

        assert result["succes"] is True
        assert result["pret"] is True
        assert result["id_partie"] == 99
        assert api._partie is partie_reprise
        assert api._id_partie == 99

    def test_reprendre_efface_infos_tirage_residuel(self, tmp_path, monkeypatch):
        """reprendre() remet ``_infos_tirage`` à None (coquille unifiée, issue #180).

        Dans la coquille mono-fenêtre unifiée, l'``ApiAccueil`` persiste toute la
        session : un « Lancer la partie » antérieur a pu renseigner
        ``_infos_tirage``. Une reprise ne doit PAS afficher de tirage : le champ
        doit être effacé, sinon l'écran de jeu s'ouvrirait à tort sur le tirage.
        """
        from scrabble.ui.accueil import ApiAccueil
        from scrabble.dictionnaire.dictionnaire import Trie
        from scrabble.moteur.partie import Partie, Joueur

        partie_reprise = Partie(
            joueurs=[Joueur(nom="Bob", humain=True)],
            dictionnaire=Trie.depuis_iterable(["TEST"]),
            graine=123,
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda: Trie.depuis_iterable(["TEST"]),
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.reprendre_partie",
            lambda id_partie, trie, dictionnaire_ia=None: partie_reprise,
        )

        api = ApiAccueil()
        # Résidu d'un « Lancer la partie » précédent dans la même session.
        api._infos_tirage = {"noms_creation": ["X"], "graine": 1, "noms_humains": ["X"]}
        api.reprendre(99)

        assert api._infos_tirage is None

    def test_lancer_partie_echec_sans_humain(self):
        """lancer_partie() échoue sans joueur humain (pas de pret)."""
        from scrabble.ui.accueil import ApiAccueil

        api = ApiAccueil()
        # Pas de joueur ajouté
        result = api.lancer_partie()

        assert result["succes"] is False
        assert "pret" not in result
        assert "erreur" in result

    def test_lancer_partie_refuse_plusieurs_humains(self):
        """lancer_partie() refuse plus d'un humain avec un message dédié (issue #175).

        Garde-fou backend non contournable : on force une configuration à deux
        humains en insérant directement les ``JoueurConfig`` (l'UI n'y arrive
        plus), et on vérifie que la création est refusée avant tout appel au
        moteur, avec un message explicite.
        """
        from scrabble.ui.accueil import ApiAccueil, JoueurConfig

        api = ApiAccueil()
        api.config_partie.joueurs = [
            JoueurConfig(nom="Alice", humain=True),
            JoueurConfig(nom="Bob", humain=True),
        ]

        result = api.lancer_partie()

        assert result["succes"] is False
        assert "pret" not in result
        assert "un seul joueur humain" in result["erreur"].lower()
        assert api._partie is None

    def test_ajouter_humain_api_refuse_le_second(self):
        """ApiAccueil.ajouter_humain refuse le second humain avec un message clair."""
        from scrabble.ui.accueil import ApiAccueil

        api = ApiAccueil()
        assert api.ajouter_humain("Alice")["succes"] is True

        result = api.ajouter_humain("Bob")
        assert result["succes"] is False
        assert "un seul joueur humain" in result["erreur"].lower()
        assert api.config_partie.nb_humains == 1


class TestApiAccueilJoueurHumainParDefaut:
    """Tests de la présence d'office du joueur humain de référence (issue #141).

    Le support multi-humains étant abandonné, le joueur humain de référence
    (prénom ``prenom_principal``) doit figurer d'office dès l'ouverture de
    l'accueil, sans ajout manuel, tout en restant retirable.
    """

    def test_ajoute_le_prenom_principal(self, monkeypatch):
        """initialiser_joueur_humain() ajoute le joueur repris des réglages."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lire_reglage", lambda cle: "Alain"
        )
        api = ApiAccueil()
        ajoute = api.initialiser_joueur_humain()

        assert ajoute is True
        etat = api.obtenir_etat()
        assert etat["nb_humains"] == 1
        assert etat["joueurs"] == [
            {"nom": "Alain", "humain": True, "niveau": None, "avatar": None}
        ]
        # La configuration est directement lançable, sans action manuelle.
        assert etat["peut_lancer"] is True

    def test_sans_prenom_principal_aucun_joueur(self, monkeypatch):
        """Sans prénom principal configuré, aucun joueur n'est ajouté."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr("scrabble.ui.accueil.lire_reglage", lambda cle: "")
        api = ApiAccueil()
        ajoute = api.initialiser_joueur_humain()

        assert ajoute is False
        assert api.obtenir_etat()["nb_humains"] == 0

    def test_prenom_principal_espaces_ignore(self, monkeypatch):
        """Un prénom principal fait uniquement d'espaces n'ajoute personne."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lire_reglage", lambda cle: "   "
        )
        api = ApiAccueil()

        assert api.initialiser_joueur_humain() is False
        assert api.obtenir_etat()["nb_humains"] == 0

    def test_idempotent_si_humain_deja_present(self, monkeypatch):
        """La méthode ne double pas le joueur déjà présent."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lire_reglage", lambda cle: "Alain"
        )
        api = ApiAccueil()
        api.config_partie.ajouter_humain("Marie")

        assert api.initialiser_joueur_humain() is False
        assert api.obtenir_etat()["nb_humains"] == 1
        assert api.config_partie.joueurs[0].nom == "Marie"

    def test_joueur_par_defaut_reste_retirable(self, monkeypatch):
        """Le joueur ajouté d'office peut être retiré (pas de présence forcée)."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lire_reglage", lambda cle: "Alain"
        )
        api = ApiAccueil()
        api.initialiser_joueur_humain()

        result = api.retirer_joueur(0)

        assert result["succes"] is True
        assert result["etat"]["nb_humains"] == 0
        # Le retrait n'est pas re-annulé : ``initialiser_joueur_humain`` n'est
        # appelée qu'une fois, à l'ouverture (jamais après un retrait), donc le
        # joueur reste bien parti pour cette configuration.

    def test_lecture_reglage_defaillante_nignore_pas_l_ouverture(
        self, monkeypatch
    ):
        """Une erreur de lecture des réglages n'empêche pas l'ouverture."""
        from scrabble.ui.accueil import ApiAccueil

        def _boum(cle):
            raise RuntimeError("config illisible")

        monkeypatch.setattr("scrabble.ui.accueil.lire_reglage", _boum)
        api = ApiAccueil()

        # obtenir_prenom_principal absorbe l'erreur -> aucun joueur, pas d'exception.
        assert api.initialiser_joueur_humain() is False
        assert api.obtenir_etat()["nb_humains"] == 0


class TestApiAccueilAvatarPrincipal:
    """L'avatar du joueur humain à l'accueil reflète les réglages (issue #148).

    Le joueur humain de référence ajouté d'office doit porter l'avatar choisi
    dans les réglages (``avatar_principal``, issue #139) — le même que celui
    utilisé tout au long de la partie (:func:`~scrabble.ui.jeu.calculer_avatars`)
    — au lieu de l'icône générique codée en dur.
    """

    @staticmethod
    def _patch_reglages(monkeypatch, prenom, avatar):
        """Monkeypatch ``lire_reglage`` avec un prénom et un avatar donnés."""
        reglages = {"prenom_principal": prenom, "avatar_principal": avatar}
        monkeypatch.setattr(
            "scrabble.ui.accueil.lire_reglage",
            lambda cle: reglages.get(cle, ""),
        )

    def test_avatar_configure_expose_pour_l_humain(self, monkeypatch):
        """L'avatar valide des réglages est renvoyé dans l'état du joueur humain."""
        from scrabble.ui.accueil import ApiAccueil

        self._patch_reglages(monkeypatch, "Alain", "avatar-07")
        api = ApiAccueil()
        api.initialiser_joueur_humain()

        assert api.obtenir_etat()["joueurs"] == [
            {"nom": "Alain", "humain": True, "niveau": None, "avatar": "avatar-07"}
        ]

    def test_sans_avatar_configure_aucun_avatar(self, monkeypatch):
        """Sans avatar choisi, ``avatar`` reste None (icône générique côté JS)."""
        from scrabble.ui.accueil import ApiAccueil

        self._patch_reglages(monkeypatch, "Alain", "")
        api = ApiAccueil()
        api.initialiser_joueur_humain()

        assert api.obtenir_etat()["joueurs"][0]["avatar"] is None

    def test_avatar_inconnu_ignore(self, monkeypatch):
        """Un avatar inconnu (config trafiquée) est ignoré plutôt qu'exposé."""
        from scrabble.ui.accueil import ApiAccueil

        self._patch_reglages(monkeypatch, "Alain", "avatar-999")
        api = ApiAccueil()
        api.initialiser_joueur_humain()

        assert api.obtenir_etat()["joueurs"][0]["avatar"] is None

    def test_ordinateur_n_herite_pas_de_l_avatar(self, monkeypatch):
        """Seul le joueur humain de référence porte l'avatar configuré."""
        from scrabble.moteur.ia import Niveau
        from scrabble.ui.accueil import ApiAccueil

        self._patch_reglages(monkeypatch, "Alain", "avatar-07")
        api = ApiAccueil()
        api.initialiser_joueur_humain()
        api.config_partie.ajouter_ordinateur("Robot", Niveau.FACILE)

        joueurs = api.obtenir_etat()["joueurs"]
        assert joueurs[0]["avatar"] == "avatar-07"
        assert joueurs[1]["avatar"] is None

    def test_coherent_avec_calculer_avatars(self, monkeypatch):
        """L'avatar exposé à l'accueil est celui attribué à l'humain en partie."""
        from scrabble.moteur.partie import Joueur
        from scrabble.ui.accueil import ApiAccueil
        from scrabble.ui.jeu import calculer_avatars

        self._patch_reglages(monkeypatch, "Alain", "avatar-07")
        api = ApiAccueil()
        api.initialiser_joueur_humain()
        avatar_accueil = api.obtenir_etat()["joueurs"][0]["avatar"]

        joueurs = [Joueur(nom="Alain", humain=True)]
        assert avatar_accueil == calculer_avatars(joueurs, "avatar-07")[0]


class TestApiAccueilInfosTirage:
    """Tests des infos de tirage préparées par lancer_partie (issues #54, #170).

    Depuis l'issue #170, le tirage d'ordre n'est plus affiché ni renvoyé au JS
    par l'accueil : il l'est dans la fenêtre Jeu. ``lancer_partie`` ne fait donc
    que mémoriser, dans ``_infos_tirage``, ce qu'il faut pour le rejouer côté Jeu
    (``noms_creation`` dans l'ordre de création, ``graine``, ``noms_humains``).
    On vérifie que ces infos, rejouées par ``jeu.detail_tirage_ordre``, sont
    cohérentes avec l'ordre de jeu réel de la partie créée.
    """

    def _api_prete(self, monkeypatch):
        from scrabble.ui.accueil import ApiAccueil
        from scrabble.dictionnaire.dictionnaire import Trie

        monkeypatch.setattr(
            "scrabble.ui.accueil.obtenir_trie",
            lambda: Trie.depuis_iterable(["MAISON", "TEST"]),
        )
        monkeypatch.setattr(
            "scrabble.ui.accueil.demarrer_suivi",
            lambda partie: 7,
        )
        return ApiAccueil()

    def test_lancer_partie_ne_renvoie_plus_le_tirage(self, monkeypatch):
        """lancer_partie() n'expose plus le détail du tirage au JS (issue #170)."""
        api = self._api_prete(monkeypatch)
        api.ajouter_humain("Alice")
        api.ajouter_ordinateur("Intermédiaire")

        result = api.lancer_partie()

        assert result["succes"] is True
        assert "tirage_ordre" not in result

    def test_infos_tirage_memorisees(self, monkeypatch):
        """Les infos de tirage sont mémorisées dans l'ordre de création.

        Un seul humain est désormais autorisé (issue #175) : l'ordre de création
        reste « humain d'abord, ordinateurs ensuite ».
        """
        api = self._api_prete(monkeypatch)
        api.ajouter_humain("Alice")
        api.ajouter_ordinateur("Intermédiaire")  # nom tiré automatiquement
        api.ajouter_ordinateur("Expert")  # nom tiré automatiquement

        api.lancer_partie()

        infos = api._infos_tirage
        assert infos is not None
        assert set(infos.keys()) == {"noms_creation", "graine", "noms_humains"}
        # Ordre de création : l'humain d'abord, ordinateurs ensuite.
        assert infos["noms_creation"][0] == "Alice"
        assert infos["noms_humains"] == ["Alice"]
        assert len(infos["noms_creation"]) == 3
        assert isinstance(infos["graine"], int)

    def test_infos_tirage_reconstituent_l_ordre_de_la_partie(self, monkeypatch):
        """detail_tirage_ordre(_infos_tirage) reproduit l'ordre réel de la partie."""
        from scrabble.ui.jeu import detail_tirage_ordre

        api = self._api_prete(monkeypatch)
        api.ajouter_humain("Alice")
        api.ajouter_ordinateur("Expert")

        api.lancer_partie()

        detail = detail_tirage_ordre(**api._infos_tirage)
        ordre_partie = [j.nom for j in api._partie.joueurs]
        assert detail["ordre"] == ordre_partie
        # Une lettre par joueur, drapeau humain cohérent avec la config :
        # Alice est l'unique humain, l'ordinateur porte ``humain=False``.
        humain_par_nom = {t["nom"]: t["humain"] for t in detail["tirages"]}
        assert humain_par_nom["Alice"] is True
        assert sum(1 for h in humain_par_nom.values() if h) == 1
        assert any(h is False for h in humain_par_nom.values())


class TestApiAccueilPartieUnique:
    """Tests de lister_parties_en_cours (issues #54, #150).

    On propose au plus deux encarts : la partie en cours la plus récente (à
    reprendre) et la partie terminée la plus récente (à consulter)."""

    def _resume(self, id_partie, statut="en_cours", joueurs=None, scores_actuels=None):
        from scrabble.persistance.stockage import ResumePartie

        return ResumePartie(
            id=id_partie,
            statut=statut,
            graine=id_partie,
            date_creation="2026-07-01T10:00:00",
            date_maj=f"2026-07-{id_partie:02d}T10:00:00",
            joueurs=joueurs or [{"nom": "Alice", "humain": True, "niveau": None}],
            scores_actuels=scores_actuels,
        )

    def test_ne_renvoie_que_la_plus_recente(self, monkeypatch):
        """Seule la première partie en cours (la plus récente) est renvoyée."""
        from scrabble.ui.accueil import ApiAccueil

        # lister_parties() renvoie déjà les parties triées date décroissante :
        # la plus récente en tête.
        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [self._resume(9), self._resume(5), self._resume(3)],
        )

        api = ApiAccueil()
        parties = api.lister_parties_en_cours()

        assert len(parties) == 1
        assert parties[0]["id"] == 9

    def test_inclut_partie_terminee_et_en_cours(self, monkeypatch):
        """La partie terminée la plus récente ET la partie en cours la plus
        récente sont proposées, du plus récent au plus ancien (issue #150)."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [
                self._resume(9, statut="terminee"),
                self._resume(4),
                self._resume(2),
            ],
        )

        api = ApiAccueil()
        parties = api.lister_parties_en_cours()

        # Deux encarts : la terminée (9, la plus récente) puis l'en cours (4).
        assert [p["id"] for p in parties] == [9, 4]
        assert parties[0]["terminee"] is True
        assert parties[1]["terminee"] is False

    def test_une_seule_partie_terminee_est_proposee(self, monkeypatch):
        """Sans partie en cours, la partie terminée la plus récente est
        proposée à la consultation (issue #150)."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [self._resume(9, statut="terminee")],
        )

        api = ApiAccueil()
        parties = api.lister_parties_en_cours()

        assert len(parties) == 1
        assert parties[0]["id"] == 9
        assert parties[0]["terminee"] is True

    def test_une_seule_terminee_par_categorie(self, monkeypatch):
        """Seule la plus récente de chaque catégorie est retenue (issues #54,
        #150) : les parties terminées plus anciennes ne sont pas proposées."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [
                self._resume(9, statut="terminee"),
                self._resume(7, statut="terminee"),
                self._resume(4),
                self._resume(2),
            ],
        )

        api = ApiAccueil()
        parties = api.lister_parties_en_cours()

        assert [p["id"] for p in parties] == [9, 4]

    def test_expose_le_score_de_chaque_joueur(self, monkeypatch):
        """Chaque joueur est renvoyé avec son score courant (issue #76)."""
        from scrabble.ui.accueil import ApiAccueil

        joueurs = [
            {"nom": "Alice", "humain": True, "niveau": None},
            {"nom": "Léon", "humain": False, "niveau": "FACILE"},
        ]
        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [self._resume(9, joueurs=joueurs, scores_actuels=[14, 9])],
        )

        api = ApiAccueil()
        parties = api.lister_parties_en_cours()

        assert parties[0]["joueurs"] == [
            {"nom": "Alice", "score": 14},
            {"nom": "Léon", "score": 9},
        ]

    def test_score_defaut_zero_si_absent(self, monkeypatch):
        """Sans ``scores_actuels``, chaque joueur reçoit un score de 0."""
        from scrabble.ui.accueil import ApiAccueil

        joueurs = [
            {"nom": "Alice", "humain": True, "niveau": None},
            {"nom": "Bob", "humain": True, "niveau": None},
        ]
        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [self._resume(9, joueurs=joueurs, scores_actuels=None)],
        )

        api = ApiAccueil()
        parties = api.lister_parties_en_cours()

        assert parties[0]["joueurs"] == [
            {"nom": "Alice", "score": 0},
            {"nom": "Bob", "score": 0},
        ]


class TestApiAccueilFermeture:
    """Tests de ApiAccueil.fermer_fenetre (issue #53).

    Vérifie que la fenêtre est fermée depuis Python via ``window.destroy()``
    plutôt que via ``window.close()`` côté JS (non fiable sous GTK/WebKit).
    Testé sans vraie fenêtre grâce à un objet factice exposant ``destroy()``.
    """

    def test_fermer_fenetre_appelle_destroy(self):
        """fermer_fenetre() appelle window.destroy() et renvoie succes."""
        from scrabble.ui.accueil import ApiAccueil

        class FakeWindow:
            def __init__(self):
                self.detruite = False

            def destroy(self):
                self.detruite = True

        api = ApiAccueil()
        fake = FakeWindow()
        api.set_window(fake)

        result = api.fermer_fenetre()

        assert result["succes"] is True
        assert fake.detruite is True

    def test_fermer_fenetre_sans_fenetre(self):
        """fermer_fenetre() échoue proprement si aucune fenêtre n'est associée."""
        from scrabble.ui.accueil import ApiAccueil

        api = ApiAccueil()
        result = api.fermer_fenetre()

        assert result["succes"] is False
        assert "erreur" in result

    def test_fermer_fenetre_exception_destroy(self):
        """fermer_fenetre() capture l'exception de destroy() (filet JS)."""
        from scrabble.ui.accueil import ApiAccueil

        class FakeWindow:
            def destroy(self):
                raise RuntimeError("backend HS")

        api = ApiAccueil()
        api.set_window(FakeWindow())

        result = api.fermer_fenetre()

        assert result["succes"] is False
        assert "erreur" in result
        assert "backend HS" in result["erreur"]


class TestReinitialiserPourRetourAccueil:
    """Réinitialisation de l'``ApiAccueil`` persistante au retour Jeu→Accueil (issue #181).

    Dans la coquille unifiée, la même instance d'``ApiAccueil`` sert plusieurs
    visites de l'accueil : elle doit repartir d'un état vierge (config remise à
    zéro, humain re-seedé, partie préparée purgée) à chaque retour.
    """

    def test_reinitialise_config_et_partie(self):
        from scrabble.ui.accueil import ApiAccueil

        api = ApiAccueil()
        # Résidu d'une partie précédente : joueurs configurés + partie préparée.
        api.config_partie.ajouter_ordinateur("Robot", Niveau.FACILE)
        api._partie = object()
        api._id_partie = 7
        api._infos_tirage = {"graine": 1}

        api.reinitialiser_pour_retour_accueil()

        # Configuration remise à neuf (aucun ordinateur résiduel).
        assert api.config_partie.nb_ordinateurs == 0
        # Partie préparée purgée : rien ne doit fuiter dans un futur démarrage.
        assert api._partie is None
        assert api._id_partie is None
        assert api._infos_tirage is None

    def test_reseed_du_joueur_humain(self, monkeypatch):
        from scrabble.ui.accueil import ApiAccueil

        api = ApiAccueil()
        # Simule un prénom principal configuré : le seeding doit rajouter l'humain.
        monkeypatch.setattr(api, "obtenir_prenom_principal", lambda: "Alice")

        api.reinitialiser_pour_retour_accueil()

        assert api.config_partie.nb_humains == 1
        assert api.config_partie.joueurs[0].nom == "Alice"
        assert api.config_partie.joueurs[0].humain is True

    def test_ne_touche_ni_fenetre_ni_session(self, monkeypatch):
        from scrabble import journal
        from scrabble.ui.accueil import ApiAccueil

        appels_session = []
        monkeypatch.setattr(
            journal, "demarrer_session", lambda *a, **k: appels_session.append("d")
        )
        monkeypatch.setattr(
            journal, "cloturer_session", lambda *a, **k: appels_session.append("c")
        )
        api = ApiAccueil()
        sentinelle = object()
        api.set_window(sentinelle)

        api.reinitialiser_pour_retour_accueil()

        # La fenêtre partagée n'est pas touchée ; aucune session ouverte/fermée.
        assert api._window is sentinelle
        assert appels_session == []
