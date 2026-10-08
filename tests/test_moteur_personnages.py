"""Tests du registre de personnages IA (issue #439, lot B).

Couvre le personnage Opportuniste (bonus premium renforcé, poids du leave à
zéro — voir ``scrabble.moteur.personnages``) : il doit choisir, en moyenne,
des coups utilisant davantage de cases à multiplicateur que Classique sur un
même plateau et un même chevalet. Vérifie aussi que Classique (profil vide)
reproduit exactement le comportement sans profil, pour garantir que
l'introduction du registre ne régresse pas le comportement par défaut.
"""

from __future__ import annotations

import random

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.generateur import generer_coups
from scrabble.moteur.ia import Niveau, choisir_coup
from scrabble.moteur.personnages import PERSONNAGES, tirer_personnage
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)

#: Vocabulaire couvrant les coups accessibles depuis CADRE posé au centre
#: (voir _plateau_avec_cadre) pour le chevalet "SOIRIT" : un mélange
#: délibéré de coups touchant une case à multiplicateur (SO/RO/SA/IA/RA/AS/AI/AR,
#: via les cases lettre double adjacentes à la case centrale) et de coups qui
#: n'en touchent aucune (OS, RESO, OD, DO, SER/SET/RES/TES, ERS/ETS, OR/IR, SE/ES).
_MOTS = (
    "CADRE", "AS", "SA", "AI", "IA", "AR", "RA", "DO", "OD", "RI", "IR",
    "RO", "OR", "ES", "SE", "ERS", "RES", "SER", "RESO", "ETS", "SET",
    "TES", "SO", "OS",
)


def _plateau_avec_cadre() -> PlateauPartie:
    """Plateau avec CADRE déjà posé horizontalement sur la case centrale.

    Contrairement à un plateau vide (où *tout* premier coup touche
    obligatoirement la case centrale, donc une case à multiplicateur), ce
    plateau laisse les coups suivants libres de toucher, ou non, une case à
    multiplicateur ailleurs sur la grille — condition nécessaire pour mesurer
    une préférence d'Opportuniste pour ces cases.
    """
    plateau = PlateauPartie()
    ligne, colonne = CENTRE
    coup = Coup(ligne, colonne, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))
    plateau.poser_coup(coup)
    return plateau


def _proportion_coups_premium(
    niveau: Niveau, profil, n: int = 300
) -> float:
    """Proportion des coups choisis (sur ``n`` graines) qui touchent une case bonus."""
    plateau = _plateau_avec_cadre()
    chevalet = list("SOIRIT")
    dico = Trie.depuis_iterable(_MOTS)
    coups_ref = {cn.coup: cn for cn in generer_coups(plateau, chevalet, dico)}

    nb_premium = 0
    nb_joues = 0
    for graine in range(n):
        coup = choisir_coup(
            plateau, chevalet, dico, niveau, random.Random(graine), profil=profil
        )
        if coup is None:
            continue
        nb_joues += 1
        cn = coups_ref[coup]
        if any(mot.cases_bonus for mot in cn.detail.mots):
            nb_premium += 1
    assert nb_joues > 0
    return nb_premium / nb_joues


class TestPersonnageOpportuniste:
    """Opportuniste doit viser les cases bonus plus souvent que Classique."""

    def test_opportuniste_utilise_plus_de_cases_premium_que_classique_intermediaire(self):
        profil_classique = PERSONNAGES["classique"].profil
        profil_opportuniste = PERSONNAGES["opportuniste"].profil

        proportion_classique = _proportion_coups_premium(
            Niveau.INTERMEDIAIRE, profil_classique
        )
        proportion_opportuniste = _proportion_coups_premium(
            Niveau.INTERMEDIAIRE, profil_opportuniste
        )
        assert proportion_opportuniste > proportion_classique

    def test_opportuniste_utilise_plus_de_cases_premium_que_classique_facile(self):
        profil_classique = PERSONNAGES["classique"].profil
        profil_opportuniste = PERSONNAGES["opportuniste"].profil

        proportion_classique = _proportion_coups_premium(Niveau.FACILE, profil_classique)
        proportion_opportuniste = _proportion_coups_premium(
            Niveau.FACILE, profil_opportuniste
        )
        assert proportion_opportuniste > proportion_classique


class TestPersonnageClassiqueInchange:
    """Classique (profil vide du registre) ne doit rien changer au comportement par défaut."""

    def test_profil_classique_est_vide(self):
        """Le profil enregistré pour Classique n'a aucun champ renseigné."""
        profil = PERSONNAGES["classique"].profil
        assert profil.malus_longueur is None
        assert profil.bonus_premium is None
        assert profil.poids_leave is None

    def test_choisir_coup_avec_profil_classique_egale_sans_profil(self):
        """``choisir_coup`` avec le profil Classique == sans profil, graine à graine.

        Reproduit le scénario du test Opportuniste (mêmes plateau/chevalet/
        dictionnaire) pour les six niveaux, afin de garantir que le passage
        par le registre de personnages n'introduit aucune différence, même
        indirecte, par rapport à l'absence totale de profil.
        """
        plateau = _plateau_avec_cadre()
        chevalet = list("SOIRIT")
        dico = Trie.depuis_iterable(_MOTS)
        profil_classique = PERSONNAGES["classique"].profil

        for niveau in Niveau:
            for graine in range(50):
                coup_sans_profil = choisir_coup(
                    plateau, chevalet, dico, niveau, random.Random(graine)
                )
                coup_avec_classique = choisir_coup(
                    plateau,
                    chevalet,
                    dico,
                    niveau,
                    random.Random(graine),
                    profil=profil_classique,
                )
                assert coup_avec_classique == coup_sans_profil


class TestTirerPersonnage:
    """Tirage « Aléatoire » parmi le registre (issue #440, lot D, point 3)."""

    def test_tirage_deterministe_avec_generateur_injecte(self):
        a = tirer_personnage(random.Random(7))
        b = tirer_personnage(random.Random(7))
        assert a.cle == b.cle

    def test_tirage_renvoie_toujours_une_entree_du_registre(self):
        for graine in range(50):
            tire = tirer_personnage(random.Random(graine))
            assert tire.cle in PERSONNAGES
            assert tire is PERSONNAGES[tire.cle]

    def test_tirage_peut_renvoyer_classique(self):
        """Classique n'est pas exclu du tirage (point 3 : « Classique compris »)."""
        cles = {tirer_personnage(random.Random(g)).cle for g in range(50)}
        assert "classique" in cles

    def test_tirage_sans_generateur_ne_leve_pas(self):
        """Sans générateur injecté, retombe sur le module ``random`` global."""
        tire = tirer_personnage()
        assert tire.cle in PERSONNAGES
