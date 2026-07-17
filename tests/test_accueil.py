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
        """Les compteurs distinguent humains et ordinateurs."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_humain("Bob")
        config.ajouter_ordinateur("Camille", Niveau.INTERMEDIAIRE)

        assert config.nb_humains == 2
        assert config.nb_ordinateurs == 1
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

    def test_limite_4_humains(self):
        """On ne peut pas dépasser 4 joueurs humains."""
        config = ConfigPartie()
        for i in range(MAX_HUMAINS):
            assert config.peut_ajouter_humain() is True
            config.ajouter_humain(f"Joueur{i}")

        assert config.nb_humains == 4
        assert config.peut_ajouter_humain() is False

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
        """Le total ne peut pas dépasser 4 joueurs."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_humain("Bob")
        config.ajouter_ordinateur("Camille", Niveau.FACILE)
        config.ajouter_ordinateur("Daniel", Niveau.EXPERT)

        assert config.nb_total == 4
        assert config.peut_ajouter_humain() is False
        assert config.peut_ajouter_ordinateur() is False

    def test_mix_humains_ordinateurs_limite(self):
        """3 humains + 1 ordinateur = 4, plus aucun ajout possible."""
        config = ConfigPartie()
        config.ajouter_humain("A")
        config.ajouter_humain("B")
        config.ajouter_humain("C")
        config.ajouter_ordinateur("X", Niveau.DEBUTANT)

        assert config.nb_total == 4
        assert config.peut_ajouter_humain() is False
        assert config.peut_ajouter_ordinateur() is False


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


class TestConfigPartieNoms:
    """Tests de la gestion des noms utilisés."""

    def test_noms_utilises_vide(self):
        """Une config vide n'a aucun nom utilisé."""
        config = ConfigPartie()
        assert config.noms_utilises() == set()

    def test_noms_utilises_humains(self):
        """Les noms des humains sont dans les noms utilisés."""
        config = ConfigPartie()
        config.ajouter_humain("Alice")
        config.ajouter_humain("Bob")
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
        config.ajouter_humain("Bob")

        assert config.retirer(0) is True
        assert config.nb_humains == 1
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
        """Retirer un joueur réactive les possibilités d'ajout."""
        config = ConfigPartie()
        for i in range(4):
            config.ajouter_humain(f"J{i}")

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
        """Ajouter un humain quand impossible retourne False."""
        config = ConfigPartie()
        for i in range(4):
            config.ajouter_humain(f"J{i}")
        assert config.ajouter_humain("Trop") is False

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
            lambda id_partie, trie: partie_reprise,
        )

        api = ApiAccueil()
        result = api.reprendre(99)

        assert result["succes"] is True
        assert result["pret"] is True
        assert result["id_partie"] == 99
        assert api._partie is partie_reprise
        assert api._id_partie == 99

    def test_lancer_partie_echec_sans_humain(self):
        """lancer_partie() échoue sans joueur humain (pas de pret)."""
        from scrabble.ui.accueil import ApiAccueil

        api = ApiAccueil()
        # Pas de joueur ajouté
        result = api.lancer_partie()

        assert result["succes"] is False
        assert "pret" not in result
        assert "erreur" in result


class TestApiAccueilTirageOrdre:
    """Tests du tirage d'ordre exposé par lancer_partie (issue #54).

    Vérifie que le tirage d'ordre est activé (``creer_partie(tirage_ordre=True)``)
    et que le détail du tirage renvoyé au JS est cohérent avec l'ordre de jeu
    réel de la partie créée.
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

    def test_lancer_partie_expose_tirage_ordre(self, monkeypatch):
        """lancer_partie() renvoie le détail du tirage d'ordre."""
        api = self._api_prete(monkeypatch)
        api.ajouter_humain("Alice")
        api.ajouter_humain("Bob")
        api.ajouter_ordinateur("Intermédiaire")  # nom tiré automatiquement

        result = api.lancer_partie()

        assert result["succes"] is True
        tirage = result["tirage_ordre"]
        # Une lettre par joueur, avec le nom associé et un drapeau humain
        # (issue #61 : le JS distingue les tours humains des ordinateurs).
        assert len(tirage["tirages"]) == 3
        for entree in tirage["tirages"]:
            assert set(entree.keys()) == {"nom", "lettre", "humain"}
            assert isinstance(entree["lettre"], str) and len(entree["lettre"]) == 1
            assert isinstance(entree["humain"], bool)
        # Les deux humains sont marqués humain=True, l'ordinateur humain=False.
        humain_par_nom = {t["nom"]: t["humain"] for t in tirage["tirages"]}
        assert humain_par_nom["Alice"] is True
        assert humain_par_nom["Bob"] is True
        assert sum(1 for v in humain_par_nom.values() if v) == 2
        # L'ordre annoncé contient tous les joueurs, une seule fois chacun.
        noms_config = {j.nom for j in api.config_partie.joueurs}
        assert set(tirage["ordre"]) == noms_config
        assert len(tirage["ordre"]) == 3

    def test_ordre_annonce_correspond_a_la_partie(self, monkeypatch):
        """L'ordre du tirage annoncé reflète l'ordre réel de partie.joueurs."""
        api = self._api_prete(monkeypatch)
        api.ajouter_humain("Alice")
        api.ajouter_humain("Bob")
        api.ajouter_ordinateur("Expert")

        result = api.lancer_partie()

        ordre_partie = [j.nom for j in api._partie.joueurs]
        assert result["tirage_ordre"]["ordre"] == ordre_partie

    def test_lettres_dans_ordre_alphabetique(self, monkeypatch):
        """Les lettres des joueurs départagés suivent l'ordre alphabétique."""
        api = self._api_prete(monkeypatch)
        api.ajouter_humain("Alice")
        api.ajouter_humain("Bob")
        api.ajouter_ordinateur("Facile")

        result = api.lancer_partie()

        tirage = result["tirage_ordre"]
        lettre_par_nom = {t["nom"]: t["lettre"] for t in tirage["tirages"]}
        lettres_dans_ordre = [lettre_par_nom[nom] for nom in tirage["ordre"]]
        # L'ordre de jeu suit l'ordre alphabétique des lettres tirées (les
        # égalités éventuelles sont départagées par retirage, non exposé, mais
        # la séquence des premières lettres reste croissante ou égale).
        assert lettres_dans_ordre == sorted(lettres_dans_ordre)


class TestApiAccueilPartieUnique:
    """Tests de lister_parties_en_cours : une seule partie proposée (issue #54)."""

    def _resume(self, id_partie, statut="en_cours"):
        from scrabble.persistance.stockage import ResumePartie

        return ResumePartie(
            id=id_partie,
            statut=statut,
            graine=id_partie,
            date_creation="2026-07-01T10:00:00",
            date_maj=f"2026-07-{id_partie:02d}T10:00:00",
            joueurs=[{"nom": "Alice", "humain": True, "niveau": None}],
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

    def test_ignore_les_parties_terminees(self, monkeypatch):
        """Une partie terminée n'est pas proposée, même si listée en tête."""
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

        assert len(parties) == 1
        assert parties[0]["id"] == 4

    def test_aucune_partie_en_cours(self, monkeypatch):
        """Aucune partie en cours -> liste vide."""
        from scrabble.ui.accueil import ApiAccueil

        monkeypatch.setattr(
            "scrabble.ui.accueil.lister_parties",
            lambda: [self._resume(9, statut="terminee")],
        )

        api = ApiAccueil()
        assert api.lister_parties_en_cours() == []


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
