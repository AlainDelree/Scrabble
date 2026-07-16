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
