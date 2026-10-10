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
from scrabble.moteur.personnages import (
    CLE_ALEATOIRE,
    DESCRIPTION_ALEATOIRE,
    MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT,
    PERSONNAGES,
    Personnage,
    TOUS_NIVEAUX,
    aleatoire_disponible_a_niveau,
    explication_disponibilite_niveaux,
    libelle_choix_accueil,
    libelle_niveaux,
    libelle_niveaux_aleatoire,
    libelle_personnage_partie,
    lister_personnages,
    personnage_disponible_a_niveau,
    personnages_disponibles_a_niveau,
    tirer_personnage,
)
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

    def test_description_classique(self):
        """Texte reformulé (issue #443, lot F bis) : plus clair que l'ancien
        « Joue sans biais de personnalité... »."""
        assert PERSONNAGES["classique"].description == "Joue normalement selon son niveau."

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

    def test_tirage_restreint_au_niveau_ne_tire_jamais_opportuniste_a_debutant(self):
        """``niveau`` restreint le tirage (issue #447, lot G, point 4) :
        Opportuniste n'étant pas disponible à Débutant, un tirage à ce niveau
        ne doit jamais le renvoyer, même sur de nombreuses graines."""
        for graine in range(50):
            tire = tirer_personnage(random.Random(graine), Niveau.DEBUTANT)
            assert tire.cle == "classique"

    def test_tirage_restreint_au_niveau_peut_tirer_opportuniste_a_facile(self):
        cles = {
            tirer_personnage(random.Random(g), Niveau.FACILE).cle
            for g in range(50)
        }
        assert cles == {"classique", "opportuniste"}

    def test_tirage_sans_niveau_ignore_la_restriction(self):
        """``niveau=None`` (défaut) reprend le comportement historique : tout
        le registre, sans restriction — non-régression explicite."""
        cles = {tirer_personnage(random.Random(g)).cle for g in range(50)}
        assert cles == set(PERSONNAGES)


class TestDisponibiliteNiveauxPersonnages:
    """Disponibilité des personnages selon le niveau (issue #447, lot G)."""

    def test_classique_disponible_a_tous_les_niveaux(self):
        for niveau in Niveau:
            assert personnage_disponible_a_niveau("classique", niveau) is True

    def test_personnage_sans_declaration_disponible_a_tous_les_niveaux(self):
        """Point 1 : le champ est facultatif et vaut « tous les niveaux » par
        défaut — un futur personnage sans déclaration explicite reste
        disponible partout."""
        assert PERSONNAGES["classique"].niveaux_disponibles == TOUS_NIVEAUX

    def test_opportuniste_refuse_a_debutant(self):
        assert personnage_disponible_a_niveau("opportuniste", Niveau.DEBUTANT) is False

    def test_opportuniste_accepte_de_facile_a_champion(self):
        for niveau in Niveau:
            if niveau is Niveau.DEBUTANT:
                continue
            assert personnage_disponible_a_niveau("opportuniste", niveau) is True

    def test_personnage_inconnu_indisponible_partout(self):
        assert personnage_disponible_a_niveau("ninja", Niveau.EXPERT) is False

    def test_aleatoire_indisponible_a_debutant_un_seul_personnage(self):
        """Aujourd'hui, seul Classique est disponible à Débutant : Aléatoire,
        qui demande au moins deux personnages, y est donc indisponible."""
        assert personnages_disponibles_a_niveau(Niveau.DEBUTANT) == [PERSONNAGES["classique"]]
        assert aleatoire_disponible_a_niveau(Niveau.DEBUTANT) is False
        assert personnage_disponible_a_niveau(CLE_ALEATOIRE, Niveau.DEBUTANT) is False

    def test_aleatoire_disponible_des_que_deux_personnages_le_sont(self):
        """Ajouter un personnage fictif disponible à Débutant rend Aléatoire
        disponible à Débutant sans aucune autre modification (point 4)."""
        fictif = Personnage(
            cle="fictif_debutant",
            prenom="Fictif",
            description="Personnage de test.",
            profil=PERSONNAGES["classique"].profil,
            niveaux_disponibles=frozenset({Niveau.DEBUTANT}),
        )
        assert aleatoire_disponible_a_niveau(Niveau.DEBUTANT) is False
        PERSONNAGES["fictif_debutant"] = fictif
        try:
            assert aleatoire_disponible_a_niveau(Niveau.DEBUTANT) is True
            assert personnage_disponible_a_niveau(CLE_ALEATOIRE, Niveau.DEBUTANT) is True
        finally:
            del PERSONNAGES["fictif_debutant"]
        assert aleatoire_disponible_a_niveau(Niveau.DEBUTANT) is False

    def test_aleatoire_disponible_a_facile(self):
        """Classique + Opportuniste : deux personnages disponibles à Facile."""
        assert aleatoire_disponible_a_niveau(Niveau.FACILE) is True


class TestLibelleEtExplicationNiveaux:
    """Textes affichés pour les niveaux de disponibilité (issue #447, lot G,
    points 2 et 5)."""

    def test_libelle_classique_tous_les_niveaux(self):
        assert libelle_niveaux(PERSONNAGES["classique"]) == "Tous les niveaux"

    def test_libelle_opportuniste(self):
        assert libelle_niveaux(PERSONNAGES["opportuniste"]) == "Facile à Champion du monde"

    def test_libelle_aleatoire_aujourdhui_comme_opportuniste(self):
        assert libelle_niveaux_aleatoire() == "Facile à Champion du monde"

    def test_explication_classique_vide(self):
        assert explication_disponibilite_niveaux("classique") == ""

    def test_explication_opportuniste(self):
        assert (
            explication_disponibilite_niveaux("opportuniste")
            == "Disponible à partir de Facile"
        )

    def test_explication_aleatoire(self):
        assert (
            explication_disponibilite_niveaux(CLE_ALEATOIRE)
            == MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT
        )


class TestLibelleChoixAccueil:
    """Libellé entre parenthèses pour le sélecteur de l'accueil (issue #441).

    Porte sur la clé encore non résolue mémorisée par ``JoueurConfig`` —
    jamais sur une identité réelle tirée (pas de révélation possible avant le
    lancement de la partie).
    """

    def test_classique_pas_de_parenthese(self):
        assert libelle_choix_accueil("classique") == ""

    def test_absence_de_personnage_pas_de_parenthese(self):
        """Un humain (``JoueurConfig.personnage`` jamais exploité) ou une
        ancienne configuration sans personnage renvoient aussi une chaîne vide."""
        assert libelle_choix_accueil("") == ""

    def test_personnage_explicite_porte_son_prenom(self):
        assert libelle_choix_accueil("opportuniste") == "Opportuniste"

    def test_aleatoire_porte_le_libelle_mystere(self):
        """Avant résolution, « Aléatoire » lui-même, jamais une identité réelle."""
        assert libelle_choix_accueil(CLE_ALEATOIRE) == "Aléatoire"


class TestLibellePersonnagePartie:
    """Libellé entre parenthèses pour un ``Joueur`` déjà en partie (issue #441).

    Porte sur l'identité réelle (``Joueur.personnage``) et le drapeau
    ``Joueur.personnage_aleatoire`` — jamais sur le libellé « Aléatoire » de
    l'accueil.
    """

    def test_classique_choisi_explicitement_pas_de_parenthese(self):
        assert libelle_personnage_partie("classique", personnage_aleatoire=False) == ""

    def test_absence_de_personnage_pas_de_parenthese(self):
        """Sauvegarde antérieure à l'issue #438, sans personnage du tout."""
        assert libelle_personnage_partie("", personnage_aleatoire=False) == ""

    def test_personnage_explicite_porte_son_prenom(self):
        assert (
            libelle_personnage_partie("opportuniste", personnage_aleatoire=False)
            == "Opportuniste"
        )

    def test_aleatoire_non_revele_affiche_aleatoire_seul(self):
        """Pendant toute la partie (``reveler=False``), quel que soit le
        personnage réellement tiré — y compris Classique — rien ne doit fuiter."""
        for cle in PERSONNAGES:
            assert (
                libelle_personnage_partie(cle, personnage_aleatoire=True, reveler=False)
                == "Aléatoire"
            )

    def test_aleatoire_revele_affiche_le_personnage_tire_pour_chaque_entree(self):
        """En fin de partie (``reveler=True``), le personnage réel apparaît,
        Classique compris — jamais le prénom seul (point 3 de l'issue #441)."""
        for cle, personnage in PERSONNAGES.items():
            assert (
                libelle_personnage_partie(cle, personnage_aleatoire=True, reveler=True)
                == f"Aléatoire : {personnage.prenom}"
            )

    def test_aleatoire_revele_classique_nest_jamais_le_prenom_seul(self):
        """Cas explicite rappelé par l'issue : « Aléatoire : Classique », pas
        « Classique » tout court, pour ne pas ressembler à un défaut d'affichage."""
        libelle = libelle_personnage_partie(
            "classique", personnage_aleatoire=True, reveler=True
        )
        assert libelle == "Aléatoire : Classique"
        assert libelle != "Classique"


class TestListerPersonnages:
    """Fenêtre « Les personnages » (issue #442, lot F) : liste construite depuis le registre."""

    def test_contient_le_registre_puis_aleatoire_en_dernier(self):
        personnages = lister_personnages()
        cles = [p["cle"] for p in personnages]
        assert cles == [*PERSONNAGES.keys(), CLE_ALEATOIRE]
        for p in personnages:
            # "niveaux_label" ajouté par l'issue #447 (lot G, point 5) :
            # texte des niveaux où le personnage est disponible.
            assert set(p.keys()) == {
                "cle", "prenom", "description", "dans_la_partie", "niveaux_label",
            }

    def test_un_personnage_ajoute_au_registre_apparait_dans_la_liste(self, monkeypatch):
        """Un personnage ajouté au registre pendant le test doit apparaître,
        sans aucune autre modification — garantit que la liste n'est pas codée
        en dur ailleurs qu'au travers du registre."""
        from dataclasses import replace

        nouveau = replace(
            PERSONNAGES["classique"], cle="test_lot_f", prenom="TestLotF"
        )
        monkeypatch.setitem(PERSONNAGES, "test_lot_f", nouveau)

        cles = [p["cle"] for p in lister_personnages()]
        assert "test_lot_f" in cles
        # Aléatoire doit rester en dernier malgré l'ajout.
        assert cles[-1] == CLE_ALEATOIRE

    def test_aleatoire_en_dernier_meme_avec_des_entrees_dans_la_partie(self):
        cles_dans_partie = frozenset(PERSONNAGES.keys())
        personnages = lister_personnages(cles_dans_partie)
        assert personnages[-1]["cle"] == CLE_ALEATOIRE

    def test_aleatoire_nest_jamais_marque_dans_la_partie(self):
        """Même si toutes les clés réelles du registre sont « dans la partie »,
        l'entrée Aléatoire ne doit jamais être marquée — elle ne représente
        aucune identité, et ne doit donc jamais laisser deviner un tirage."""
        cles_dans_partie = frozenset(PERSONNAGES.keys())
        personnages = lister_personnages(cles_dans_partie)
        aleatoire = next(p for p in personnages if p["cle"] == CLE_ALEATOIRE)
        assert aleatoire["dans_la_partie"] is False
        assert aleatoire["description"] == DESCRIPTION_ALEATOIRE

    def test_marquage_dans_la_partie_ne_concerne_que_les_cles_fournies(self):
        personnages = lister_personnages(frozenset({"opportuniste"}))
        marques = {p["cle"] for p in personnages if p["dans_la_partie"]}
        assert marques == {"opportuniste"}

    def test_sans_cles_dans_partie_rien_nest_marque(self):
        personnages = lister_personnages()
        assert all(not p["dans_la_partie"] for p in personnages)

    def test_aleatoire_dans_partie_marque_uniquement_lentree_aleatoire(self):
        """``aleatoire_dans_partie`` (issue #443, lot F bis) ne marque QUE
        l'entrée Aléatoire, jamais une entrée réelle du registre."""
        personnages = lister_personnages(aleatoire_dans_partie=True)
        marques = {p["cle"] for p in personnages if p["dans_la_partie"]}
        assert marques == {CLE_ALEATOIRE}

    def test_aleatoire_dans_partie_faux_par_defaut(self):
        personnages = lister_personnages(frozenset({"opportuniste"}))
        aleatoire = next(p for p in personnages if p["cle"] == CLE_ALEATOIRE)
        assert aleatoire["dans_la_partie"] is False
