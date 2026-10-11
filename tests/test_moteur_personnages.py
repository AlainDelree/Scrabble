"""Tests du registre de personnages IA (issue #439, lot B).

Couvre le personnage Opportuniste (bonus premium renforcé, poids du leave à
zéro — voir ``scrabble.moteur.personnages``) : il doit choisir, en moyenne,
des coups utilisant davantage de cases à multiplicateur que Classique sur un
même plateau et un même chevalet. Vérifie aussi que Classique (profil vide)
reproduit exactement le comportement sans profil, pour garantir que
l'introduction du registre ne régresse pas le comportement par défaut.

Couvre aussi Chasseur de scrabbles (issue #448, lot H) : bonus de pose de 7
lettres et poids du leave renforcé — il doit choisir, en moyenne, davantage
de coups posant les 7 lettres du chevalet (« scrabbles ») que Classique, sur
un plateau et un chevalet fabriqués où un scrabble est possible.

Couvre aussi Titeuf (issue #452, lot J) : liste de mots favoris et tirage
pondéré en sa faveur — il doit choisir, en moyenne, bien plus souvent un mot
favori que Classique au même niveau, sur un plateau et un chevalet fabriqués
où un mot favori est jouable.

Couvre aussi Lettré (issue #454, lot K) : même mécanisme que Titeuf, liste de
mots favoris indépendante, et un bonus de score (``bonus_favori``) qui, lui,
agit aussi à AVANCE/EXPERT/CHAMPION_DU_MONDE (meilleur coup, le tirage pondéré
de Titeuf y est sans effet) — il doit choisir un mot favori nettement plus
souvent que Classique, y compris à AVANCE.
"""

from __future__ import annotations

import random

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.generateur import generer_coups
from scrabble.moteur.ia import Niveau, choisir_coup
from scrabble.moteur.personnages import (
    CLE_ALEATOIRE,
    BONUS_FAVORI_LETTRE,
    CHEMIN_MOTS_FAVORIS_LETTRE,
    CHEMIN_MOTS_FAVORIS_TITEUF,
    DESCRIPTION_ALEATOIRE,
    MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT,
    MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS,
    MOTS_FAVORIS_LETTRE,
    MOTS_FAVORIS_TITEUF,
    NB_JOUEURS_LETTRE,
    NB_JOUEURS_TITEUF,
    NIVEAUX_LETTRE,
    NIVEAUX_TITEUF,
    PART_VOCABULAIRE_COURT_CHASSEUR,
    PART_VOCABULAIRE_LONG_CHASSEUR,
    PERSONNAGES,
    POIDS_TIRAGE_FAVORI_TITEUF,
    POIDS_TIRAGE_SCRABBLE_CHASSEUR,
    Personnage,
    TOUS_NIVEAUX,
    TOUTES_TAILLES,
    aleatoire_disponible_a_nb_joueurs,
    aleatoire_disponible_a_niveau,
    charger_mots_favoris,
    explication_disponibilite_niveaux,
    explication_disponibilite_tailles,
    libelle_choix_accueil,
    libelle_niveaux,
    libelle_niveaux_aleatoire,
    libelle_personnage_partie,
    libelle_tailles,
    libelle_tailles_aleatoire,
    lister_personnages,
    personnage_disponible_a_nb_joueurs,
    personnage_disponible_a_niveau,
    personnages_disponibles_a_nb_joueurs,
    personnages_disponibles_a_niveau,
    profil_pour_niveau,
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
        ne doit jamais le renvoyer, même sur de nombreuses graines.

        Depuis l'introduction de Titeuf (issue #452, lot J, seul personnage
        disponible à Débutant en plus de Classique), le tirage peut renvoyer
        l'un ou l'autre — jamais Opportuniste ni Chasseur de scrabbles."""
        for graine in range(50):
            tire = tirer_personnage(random.Random(graine), Niveau.DEBUTANT)
            assert tire.cle in {"classique", "titeuf"}

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

    def test_tirage_restreint_au_nb_joueurs_ne_tire_jamais_opportuniste_a_trois(self):
        """``nb_joueurs`` restreint pareillement le tirage (issue #449, lot
        I) : Opportuniste et Chasseur de scrabbles n'étant disponibles qu'à
        deux joueurs, un tirage pour une table de trois ne doit jamais les
        renvoyer, même sur de nombreuses graines."""
        for graine in range(50):
            tire = tirer_personnage(random.Random(graine), None, 3)
            assert tire.cle == "classique"

    def test_tirage_restreint_au_nb_joueurs_peut_tirer_opportuniste_a_deux(self):
        cles = {
            tirer_personnage(random.Random(g), None, 2).cle for g in range(50)
        }
        assert cles == set(PERSONNAGES)

    def test_tirage_sans_nb_joueurs_ignore_la_restriction(self):
        """``nb_joueurs=None`` (défaut) reprend le comportement historique :
        tout le registre, sans restriction de taille de table."""
        cles = {tirer_personnage(random.Random(g)).cle for g in range(50)}
        assert cles == set(PERSONNAGES)

    def test_tirage_combine_niveau_et_nb_joueurs(self):
        """Les deux restrictions se combinent (issue #449, lot I) : à
        Débutant (seul Classique disponible par niveau) ET à trois joueurs
        (seul Classique disponible par taille), le tirage combiné ne doit
        jamais renvoyer autre chose que Classique."""
        for graine in range(30):
            tire = tirer_personnage(random.Random(graine), Niveau.DEBUTANT, 3)
            assert tire.cle == "classique"


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

    def test_aleatoire_disponible_a_debutant_grace_a_titeuf(self):
        """Depuis l'introduction de Titeuf (issue #452, lot J), Débutant
        compte deux personnages réels (Classique + Titeuf) : Aléatoire, qui
        demande au moins deux personnages, y est donc de nouveau disponible —
        remplace ``test_aleatoire_indisponible_a_debutant_un_seul_personnage``
        (issue #447, lot G), devenu faux par construction."""
        assert personnages_disponibles_a_niveau(Niveau.DEBUTANT) == [
            PERSONNAGES["classique"],
            PERSONNAGES["titeuf"],
        ]
        assert aleatoire_disponible_a_niveau(Niveau.DEBUTANT) is True
        assert personnage_disponible_a_niveau(CLE_ALEATOIRE, Niveau.DEBUTANT) is True

    def test_aleatoire_disponible_des_que_deux_personnages_le_sont(self):
        """Ajouter un personnage fictif disponible à un niveau qui n'en a
        qu'un rend Aléatoire disponible à ce niveau sans aucune autre
        modification (point 4).

        Débutant compte désormais déjà deux personnages réels (Classique +
        Titeuf, issue #452, lot J) : ce test retire temporairement Titeuf du
        registre pour retrouver la situation à un seul personnage et
        vérifier proprement le mécanisme, puis le restaure."""
        titeuf = PERSONNAGES.pop("titeuf")
        try:
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
        finally:
            PERSONNAGES["titeuf"] = titeuf

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

    def test_libelle_aleatoire_tous_les_niveaux_grace_a_titeuf(self):
        """Depuis l'introduction de Titeuf (issue #452, lot J), Débutant a
        aussi deux personnages disponibles : Aléatoire couvre maintenant
        TOUS les niveaux — remplace
        ``test_libelle_aleatoire_aujourdhui_comme_opportuniste`` (issue #447,
        lot G), devenu faux par construction."""
        assert libelle_niveaux_aleatoire() == "Tous les niveaux"

    def test_explication_classique_vide(self):
        assert explication_disponibilite_niveaux("classique") == ""

    def test_explication_opportuniste(self):
        assert (
            explication_disponibilite_niveaux("opportuniste")
            == "Disponible à partir de Facile"
        )

    def test_explication_aleatoire_vide_grace_a_titeuf(self):
        """Depuis l'introduction de Titeuf (issue #452, lot J), Aléatoire est
        disponible à tous les niveaux : rien à expliquer — remplace
        ``test_explication_aleatoire`` (issue #447, lot G), devenu faux par
        construction."""
        assert explication_disponibilite_niveaux(CLE_ALEATOIRE) == ""


# --------------------------------------------------------------------------- #
# Disponibilité selon le nombre de joueurs à table (issue #449, lot I)
# --------------------------------------------------------------------------- #


class TestDisponibiliteNbJoueursPersonnages:
    """Disponibilité des personnages selon la taille de table (issue #449, lot I)."""

    def test_classique_disponible_a_toutes_les_tailles(self):
        for nb_joueurs in (2, 3, 4):
            assert personnage_disponible_a_nb_joueurs("classique", nb_joueurs) is True

    def test_personnage_sans_declaration_disponible_a_toutes_les_tailles(self):
        """Point 1 : le champ est facultatif et vaut « toutes les tailles »
        par défaut — un futur personnage sans déclaration explicite reste
        disponible partout."""
        assert PERSONNAGES["classique"].nb_joueurs_disponibles == TOUTES_TAILLES

    def test_opportuniste_refuse_a_trois_et_quatre_joueurs(self):
        for nb_joueurs in (3, 4):
            assert (
                personnage_disponible_a_nb_joueurs("opportuniste", nb_joueurs)
                is False
            )

    def test_opportuniste_accepte_a_deux_joueurs(self):
        assert personnage_disponible_a_nb_joueurs("opportuniste", 2) is True

    def test_chasseur_refuse_a_trois_et_quatre_joueurs(self):
        for nb_joueurs in (3, 4):
            assert (
                personnage_disponible_a_nb_joueurs("chasseur_de_scrabbles", nb_joueurs)
                is False
            )

    def test_chasseur_accepte_a_deux_joueurs(self):
        assert personnage_disponible_a_nb_joueurs("chasseur_de_scrabbles", 2) is True

    def test_personnage_inconnu_indisponible_partout(self):
        assert personnage_disponible_a_nb_joueurs("ninja", 2) is False

    def test_aleatoire_disponible_a_deux_joueurs(self):
        """Classique + Opportuniste + Chasseur de scrabbles : trois
        personnages disponibles à deux joueurs."""
        assert aleatoire_disponible_a_nb_joueurs(2) is True
        assert personnage_disponible_a_nb_joueurs(CLE_ALEATOIRE, 2) is True

    def test_aleatoire_indisponible_a_trois_ou_quatre_joueurs_un_seul_personnage(self):
        """Aujourd'hui, seul Classique est disponible à trois ou quatre
        joueurs : Aléatoire, qui demande au moins deux personnages, y est
        donc indisponible (conséquence explicite de l'intention de l'issue)."""
        for nb_joueurs in (3, 4):
            assert personnages_disponibles_a_nb_joueurs(nb_joueurs) == [
                PERSONNAGES["classique"]
            ]
            assert aleatoire_disponible_a_nb_joueurs(nb_joueurs) is False
            assert personnage_disponible_a_nb_joueurs(CLE_ALEATOIRE, nb_joueurs) is False

    def test_aleatoire_redevient_disponible_si_un_personnage_fictif_declare_trois_joueurs(self):
        """Un personnage fictif ajouté au registre et déclaré pour trois
        joueurs rend Aléatoire à nouveau disponible à cette taille, sans
        aucune autre modification (même mécanisme que pour les niveaux)."""
        fictif = Personnage(
            cle="fictif_trois_joueurs",
            prenom="Fictif",
            description="Personnage de test.",
            profil=PERSONNAGES["classique"].profil,
            nb_joueurs_disponibles=frozenset({3}),
        )
        assert aleatoire_disponible_a_nb_joueurs(3) is False
        PERSONNAGES["fictif_trois_joueurs"] = fictif
        try:
            assert aleatoire_disponible_a_nb_joueurs(3) is True
            assert personnage_disponible_a_nb_joueurs(CLE_ALEATOIRE, 3) is True
        finally:
            del PERSONNAGES["fictif_trois_joueurs"]
        assert aleatoire_disponible_a_nb_joueurs(3) is False


class TestLibelleEtExplicationTailles:
    """Textes affichés pour les tailles de table de disponibilité (issue
    #449, lot I, points 2 et 5)."""

    def test_libelle_classique_toutes_les_parties(self):
        assert libelle_tailles(PERSONNAGES["classique"]) == "Toutes les parties"

    def test_libelle_opportuniste(self):
        assert libelle_tailles(PERSONNAGES["opportuniste"]) == "Parties à deux joueurs"

    def test_libelle_chasseur(self):
        assert (
            libelle_tailles(PERSONNAGES["chasseur_de_scrabbles"])
            == "Parties à deux joueurs"
        )

    def test_libelle_aleatoire_aujourdhui_comme_opportuniste(self):
        assert libelle_tailles_aleatoire() == "Parties à deux joueurs"

    def test_explication_classique_vide(self):
        assert explication_disponibilite_tailles("classique") == ""

    def test_explication_opportuniste(self):
        assert (
            explication_disponibilite_tailles("opportuniste")
            == MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS
        )

    def test_explication_chasseur(self):
        assert (
            explication_disponibilite_tailles("chasseur_de_scrabbles")
            == MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS
        )

    def test_explication_aleatoire(self):
        assert (
            explication_disponibilite_tailles(CLE_ALEATOIRE)
            == MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT
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
            # texte des niveaux où le personnage est disponible. "tailles_label"
            # ajouté par l'issue #449 (lot I, point 5) : texte des tailles de
            # table où le personnage est disponible.
            assert set(p.keys()) == {
                "cle", "prenom", "description", "dans_la_partie", "niveaux_label",
                "tailles_label",
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


# --------------------------------------------------------------------------- #
# Chasseur de scrabbles (issue #448, lot H)
# --------------------------------------------------------------------------- #


def _plateau_chasseur() -> PlateauPartie:
    """Plateau fabriqué pour qu'un scrabble (coup posant les 7 lettres du
    chevalet) soit possible, en concurrence avec un coup plus court mais
    mieux payé en score brut (voir le rapport de l'issue #448, lot H, pour le
    détail du calcul des deux scores) :

    * ``A`` posée en (7, 8) permet le mot vertical ``AOKWUXLN`` (7 lettres
      nouvelles, colonne 8, lignes 8 à 14) : score brut modeste (les cases à
      multiplicateur de lettre rencontrées reçoivent les lettres les moins
      chères du chevalet), mais avec le bonus « scrabble » intrinsèque
      (+50, :data:`scrabble.moteur.score.BONUS_SCRABBLE`).
    * ``Z`` posée en (0, 10) permet le mot ``ZOKWX`` (4 lettres nouvelles,
      ligne 0, colonnes 11 à 14) qui s'achève sur la case mot triple (0, 14) :
      score brut plus élevé malgré 3 lettres de moins, sans bonus scrabble.

    Sans personnage, le second coup (score brut plus haut) l'emporte pour
    AVANCE/EXPERT/CHAMPION_DU_MONDE ; avec Chasseur de scrabbles
    (``bonus_scrabble=150``), l'écart est renversé et le premier (le
    scrabble) l'emporte.
    """
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(7, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("DA")))
    plateau.poser_coup(Coup(0, 10, Direction.HORIZONTALE, tuiles_depuis_chaine("Z")))
    return plateau


#: Chevalet du scénario ci-dessus : K/W/X (lettres chères) et quatre lettres
#: à 1 point (O/U/L/N), de quoi fabriquer les deux coups concurrents.
_CHEVALET_CHASSEUR = list("KWXOULN")

#: Vocabulaire minimal couvrant exactement les deux coups du scénario
#: (``_plateau_chasseur``) et les mots déjà posés.
_MOTS_CHASSEUR = ("DA", "Z", "AOKWUXLN", "ZOKWX")


def _proportion_scrabbles(niveau: Niveau, profil, n: int = 200) -> float:
    """Proportion des coups choisis (sur ``n`` graines) qui posent les 7
    lettres du chevalet, sur le scénario :func:`_plateau_chasseur`."""
    plateau = _plateau_chasseur()
    dico = Trie.depuis_iterable(_MOTS_CHASSEUR)
    coups_ref = {
        cn.coup: cn for cn in generer_coups(plateau, _CHEVALET_CHASSEUR, dico)
    }

    nb_scrabbles = 0
    nb_joues = 0
    for graine in range(n):
        coup = choisir_coup(
            plateau,
            _CHEVALET_CHASSEUR,
            dico,
            niveau,
            random.Random(graine),
            profil=profil,
        )
        if coup is None:
            continue
        nb_joues += 1
        if coups_ref[coup].nb_nouvelles == 7:
            nb_scrabbles += 1
    assert nb_joues > 0
    return nb_scrabbles / nb_joues


class TestPersonnageChasseurDeScrabbles:
    """Chasseur de scrabbles doit choisir le scrabble plus souvent que
    Classique, sur un plateau et un chevalet où un scrabble est possible
    (issue #448, lot H, point « choix du coup »)."""

    def test_chasseur_choisit_plus_souvent_le_scrabble_que_classique_avance(self):
        profil_classique = PERSONNAGES["classique"].profil
        profil_chasseur = PERSONNAGES["chasseur_de_scrabbles"].profil

        proportion_classique = _proportion_scrabbles(Niveau.AVANCE, profil_classique)
        proportion_chasseur = _proportion_scrabbles(Niveau.AVANCE, profil_chasseur)
        assert proportion_chasseur > proportion_classique

    def test_chasseur_choisit_plus_souvent_le_scrabble_que_classique_expert(self):
        profil_classique = PERSONNAGES["classique"].profil
        profil_chasseur = PERSONNAGES["chasseur_de_scrabbles"].profil

        proportion_classique = _proportion_scrabbles(Niveau.EXPERT, profil_classique)
        proportion_chasseur = _proportion_scrabbles(Niveau.EXPERT, profil_chasseur)
        assert proportion_chasseur > proportion_classique

    def test_chasseur_choisit_plus_souvent_le_scrabble_que_classique_champion(self):
        profil_classique = PERSONNAGES["classique"].profil
        profil_chasseur = PERSONNAGES["chasseur_de_scrabbles"].profil

        proportion_classique = _proportion_scrabbles(
            Niveau.CHAMPION_DU_MONDE, profil_classique
        )
        proportion_chasseur = _proportion_scrabbles(
            Niveau.CHAMPION_DU_MONDE, profil_chasseur
        )
        assert proportion_chasseur > proportion_classique

    def test_chasseur_dans_le_registre(self):
        assert "chasseur_de_scrabbles" in PERSONNAGES
        chasseur = PERSONNAGES["chasseur_de_scrabbles"]
        assert chasseur.prenom == "Chasseur de scrabbles"
        assert chasseur.description != ""

    def test_chasseur_profil_vocabulaire_long_actif_sans_surcharge_de_leave(self):
        """Issue #450 (lot H bis) : le caractère du personnage vient
        maintenant du vocabulaire (``vocabulaire_long``), pas d'un poids de
        leave renforcé — ``poids_leave`` n'est plus surchargé (``None``, le
        niveau du joueur s'applique tel quel), contrairement au lot H
        (2.0)."""
        chasseur = PERSONNAGES["chasseur_de_scrabbles"].profil
        assert chasseur.vocabulaire_long is True
        assert chasseur.poids_leave is None
        assert chasseur.bonus_scrabble == 150

    def test_autres_personnages_vocabulaire_long_neutre(self):
        """``vocabulaire_long`` reste ``None`` pour tout personnage qui ne le
        demande pas explicitement (Classique, Opportuniste) — champ
        strictement additif, sans effet de bord sur les personnages
        existants."""
        assert PERSONNAGES["classique"].profil.vocabulaire_long is None
        assert PERSONNAGES["opportuniste"].profil.vocabulaire_long is None

    def test_chasseur_apparait_dans_la_liste(self):
        cles = [p["cle"] for p in lister_personnages()]
        assert "chasseur_de_scrabbles" in cles

    def test_chasseur_indisponible_a_debutant_facile_expert_champion(self):
        """Issue #450 (lot H bis) : plage resserrée à Intermédiaire/Avancé —
        le caractère du personnage vient du vocabulaire, qui n'est restreint
        par rapport au lexique complet qu'à ces deux niveaux (voir
        :data:`scrabble.moteur.personnages.NIVEAUX_CHASSEUR_SCRABBLES`)."""
        for niveau in (
            Niveau.DEBUTANT,
            Niveau.FACILE,
            Niveau.EXPERT,
            Niveau.CHAMPION_DU_MONDE,
        ):
            assert (
                personnage_disponible_a_niveau("chasseur_de_scrabbles", niveau)
                is False
            )

    def test_chasseur_disponible_intermediaire_avance(self):
        for niveau in (Niveau.INTERMEDIAIRE, Niveau.AVANCE):
            assert (
                personnage_disponible_a_niveau("chasseur_de_scrabbles", niveau)
                is True
            )

    def test_libelle_niveaux_chasseur(self):
        assert (
            libelle_niveaux(PERSONNAGES["chasseur_de_scrabbles"])
            == "Intermédiaire à Avancé"
        )

    def test_explication_disponibilite_chasseur(self):
        assert (
            explication_disponibilite_niveaux("chasseur_de_scrabbles")
            == "Disponible : Intermédiaire à Avancé"
        )


# --------------------------------------------------------------------------- #
# Poids de tirage des scrabbles (issue #451, lot H ter, point 4)
# --------------------------------------------------------------------------- #


class TestPoidsTirageScrabbleChasseur:
    """``poids_tirage_scrabble`` de Chasseur de scrabbles : champ plat (une
    constante, pas une table par niveau), neutre pour les autres
    personnages."""

    def test_chasseur_poids_tirage_scrabble(self):
        chasseur = PERSONNAGES["chasseur_de_scrabbles"].profil
        assert chasseur.poids_tirage_scrabble == POIDS_TIRAGE_SCRABBLE_CHASSEUR
        assert POIDS_TIRAGE_SCRABBLE_CHASSEUR == 5.0

    def test_autres_personnages_poids_tirage_scrabble_neutre(self):
        assert PERSONNAGES["classique"].profil.poids_tirage_scrabble is None
        assert PERSONNAGES["opportuniste"].profil.poids_tirage_scrabble is None

    def test_chasseur_choisit_plus_souvent_le_scrabble_que_classique_intermediaire(
        self,
    ):
        """Constat de départ de l'issue #451 : à Intermédiaire, le tirage
        uniforme dans la tranche des 15 % meilleurs coups diluait l'effet du
        vocabulaire long (lot H bis) — le poids de tirage doit rendre le
        style de nouveau visible à ce niveau précis."""
        profil_classique = PERSONNAGES["classique"].profil
        profil_chasseur = PERSONNAGES["chasseur_de_scrabbles"].profil

        proportion_classique = _proportion_scrabbles(
            Niveau.INTERMEDIAIRE, profil_classique
        )
        proportion_chasseur = _proportion_scrabbles(
            Niveau.INTERMEDIAIRE, profil_chasseur
        )
        assert proportion_chasseur > proportion_classique


# --------------------------------------------------------------------------- #
# Part de mots longs connus par niveau (issue #451, lot H ter, points 8 et 9)
# --------------------------------------------------------------------------- #


class TestPartVocabulaireLongChasseur:
    """Table :data:`PART_VOCABULAIRE_LONG_CHASSEUR` et sa résolution par
    :func:`profil_pour_niveau` — jamais directement visible sur
    ``PERSONNAGES["chasseur_de_scrabbles"].profil`` (qui reste la valeur
    plate, sans résolution de niveau)."""

    def test_valeurs_de_depart(self):
        """Remis à 100 % aux deux niveaux par le lot H quater (issue #453) :
        AVANCE valait 0.5 au lot H ter — voir :data:`PART_VOCABULAIRE_COURT_CHASSEUR`
        pour le nouveau levier qui reprend ce rôle."""
        assert PART_VOCABULAIRE_LONG_CHASSEUR == {
            Niveau.INTERMEDIAIRE: 1.0,
            Niveau.AVANCE: 1.0,
        }

    def test_profil_plat_ne_porte_pas_la_surcharge_par_niveau(self):
        """``.profil`` (accès direct) ne résout rien par niveau : c'est
        :func:`profil_pour_niveau` qui porte cette résolution — condition
        nécessaire pour que les tests existants qui accèdent à ``.profil``
        directement (AVANCE/EXPERT/CHAMPION_DU_MONDE, lot H bis) restent
        valides sans modification."""
        assert PERSONNAGES["chasseur_de_scrabbles"].profil.part_vocabulaire_long is None

    def test_profil_pour_niveau_intermediaire(self):
        profil = profil_pour_niveau("chasseur_de_scrabbles", Niveau.INTERMEDIAIRE)
        assert profil.part_vocabulaire_long == 1.0
        # Les autres champs restent ceux du profil de base, inchangés.
        assert profil.bonus_scrabble == PERSONNAGES["chasseur_de_scrabbles"].profil.bonus_scrabble
        assert profil.vocabulaire_long is True

    def test_profil_pour_niveau_avance(self):
        profil = profil_pour_niveau("chasseur_de_scrabbles", Niveau.AVANCE)
        assert profil.part_vocabulaire_long == 1.0
        assert profil.vocabulaire_long is True

    def test_profil_pour_niveau_sans_entree_dans_la_table(self):
        """Un niveau absent de la table (ici DEBUTANT, où Chasseur n'est de
        toute façon pas disponible) laisse le profil inchangé — même
        résultat que l'accès direct à ``.profil``."""
        profil = profil_pour_niveau("chasseur_de_scrabbles", Niveau.DEBUTANT)
        assert profil == PERSONNAGES["chasseur_de_scrabbles"].profil

    def test_profil_pour_niveau_none_laisse_le_profil_inchange(self):
        """``niveau=None`` (joueur humain, ou appelant qui ne connaît encore
        aucun niveau) ne trouve jamais d'entrée dans la table."""
        profil = profil_pour_niveau("chasseur_de_scrabbles", None)
        assert profil == PERSONNAGES["chasseur_de_scrabbles"].profil

    def test_profil_pour_niveau_personnage_sans_table_inchange(self):
        """Classique et Opportuniste n'ont pas de table de surcharge : même
        résultat que l'accès direct à ``.profil``, quel que soit le niveau."""
        for cle in ("classique", "opportuniste"):
            for niveau in Niveau:
                assert profil_pour_niveau(cle, niveau) == PERSONNAGES[cle].profil

    def test_profil_pour_niveau_cle_inconnue_leve_keyerror(self):
        with pytest.raises(KeyError):
            profil_pour_niveau("ne_existe_pas", Niveau.AVANCE)

    def test_resolution_ne_mute_pas_le_profil_de_base(self):
        """La résolution par niveau ne doit jamais muter le ``ProfilPersonnage``
        de base du registre — seulement en dériver une copie."""
        avant = PERSONNAGES["chasseur_de_scrabbles"].profil
        profil_pour_niveau("chasseur_de_scrabbles", Niveau.AVANCE)
        assert PERSONNAGES["chasseur_de_scrabbles"].profil is avant
        assert avant.part_vocabulaire_long is None


# --------------------------------------------------------------------------- #
# Part de mots courts connus par niveau (issue #453, lot H quater)
# --------------------------------------------------------------------------- #


class TestPartVocabulaireCourtChasseur:
    """Table :data:`PART_VOCABULAIRE_COURT_CHASSEUR` et sa résolution par
    :func:`profil_pour_niveau` — même principe que
    :data:`PART_VOCABULAIRE_LONG_CHASSEUR` (lot H ter), table indépendante."""

    def test_valeurs_de_depart(self):
        assert PART_VOCABULAIRE_COURT_CHASSEUR == {
            Niveau.INTERMEDIAIRE: 0.7,
            Niveau.AVANCE: 0.7,
        }

    def test_profil_plat_ne_porte_pas_la_surcharge_par_niveau(self):
        assert PERSONNAGES["chasseur_de_scrabbles"].profil.part_vocabulaire_court is None

    def test_profil_pour_niveau_intermediaire(self):
        profil = profil_pour_niveau("chasseur_de_scrabbles", Niveau.INTERMEDIAIRE)
        assert profil.part_vocabulaire_court == 0.7
        # La surcharge des mots longs, indépendante, reste appliquée aussi.
        assert profil.part_vocabulaire_long == 1.0
        assert profil.vocabulaire_long is True

    def test_profil_pour_niveau_avance(self):
        profil = profil_pour_niveau("chasseur_de_scrabbles", Niveau.AVANCE)
        assert profil.part_vocabulaire_court == 0.7
        assert profil.part_vocabulaire_long == 1.0

    def test_profil_pour_niveau_sans_entree_dans_la_table(self):
        profil = profil_pour_niveau("chasseur_de_scrabbles", Niveau.DEBUTANT)
        assert profil == PERSONNAGES["chasseur_de_scrabbles"].profil

    def test_profil_pour_niveau_personnage_sans_table_inchange(self):
        """Classique, Opportuniste et Titeuf n'ont pas de table de surcharge
        pour ce champ : même résultat que l'accès direct à ``.profil``, quel
        que soit le niveau — aucun effet sur les autres personnages."""
        for cle in ("classique", "opportuniste", "titeuf"):
            for niveau in Niveau:
                assert profil_pour_niveau(cle, niveau) == PERSONNAGES[cle].profil
                assert profil_pour_niveau(cle, niveau).part_vocabulaire_court is None

    def test_resolution_ne_mute_pas_le_profil_de_base(self):
        avant = PERSONNAGES["chasseur_de_scrabbles"].profil
        profil_pour_niveau("chasseur_de_scrabbles", Niveau.AVANCE)
        assert PERSONNAGES["chasseur_de_scrabbles"].profil is avant
        assert avant.part_vocabulaire_court is None


# --------------------------------------------------------------------------- #
# Titeuf (issue #452, lot J)
# --------------------------------------------------------------------------- #


def _plateau_titeuf() -> PlateauPartie:
    """Plateau fabriqué pour qu'un mot favori COURT (``CACA``, 4 lettres) ne
    soit jouable qu'avec le lexique complet, en concurrence avec des coups
    courts jouables avec le seul vocabulaire du niveau — même scénario que
    :func:`scrabble.moteur.ia._plateau_mot_favori` dans ``test_moteur_ia.py``.

    Un ``Z`` isolé est posé en (7, 6). Le chevalet ``CACAXYW`` permet :

    * des coups COURTS (``ZX``, ``ZY``, ``ZW``) présents dans le vocabulaire
      du niveau ;
    * le mot favori ``CACA``, vertical à partir de (7, 7) — mot croisé
      ``ZC`` compris —, absent du vocabulaire du niveau, présent seulement
      dans le lexique complet.
    """
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(7, 6, Direction.HORIZONTALE, tuiles_depuis_chaine("Z")))
    return plateau


#: Chevalet du scénario ci-dessus.
_CHEVALET_TITEUF = list("CACAXYW")

#: Vocabulaire du niveau (restreint) pour le scénario ci-dessus : ne connaît
#: que des coups courts sans rapport avec ``CACA``.
_DICO_NIVEAU_TITEUF = ("ZX", "ZY", "ZW")

#: Lexique complet pour le scénario ci-dessus : coups courts ET mot favori
#: (mot principal et mot croisé).
_DICO_COMPLET_TITEUF = ("ZX", "ZY", "ZW", "CACA", "ZC")


def _proportion_mot_favori(niveau: Niveau, profil, n: int = 300) -> float:
    """Proportion des coups choisis (sur ``n`` graines) dont le mot principal
    est ``CACA``, sur le scénario :func:`_plateau_titeuf`."""
    plateau = _plateau_titeuf()
    dico_niveau = Trie.depuis_iterable(_DICO_NIVEAU_TITEUF)
    dico_complet = Trie.depuis_iterable(_DICO_COMPLET_TITEUF)

    nb_favori = 0
    nb_joues = 0
    for graine in range(n):
        coup = choisir_coup(
            plateau,
            _CHEVALET_TITEUF,
            dico_niveau,
            niveau,
            random.Random(graine),
            profil=profil,
            dictionnaire_complet=dico_complet,
        )
        if coup is None:
            continue
        nb_joues += 1
        mot = "".join(t.lettre for t in coup.tuiles)
        if mot == "CACA":
            nb_favori += 1
    assert nb_joues > 0
    return nb_favori / nb_joues


class TestPersonnageTiteuf:
    """Titeuf doit choisir un mot favori plus souvent que Classique, sur un
    plateau et un chevalet où un mot favori est jouable (issue #452, lot
    J)."""

    def test_titeuf_choisit_plus_souvent_un_mot_favori_que_classique(self):
        profil_classique = PERSONNAGES["classique"].profil
        profil_titeuf = PERSONNAGES["titeuf"].profil

        proportion_classique = _proportion_mot_favori(Niveau.DEBUTANT, profil_classique)
        proportion_titeuf = _proportion_mot_favori(Niveau.DEBUTANT, profil_titeuf)
        assert proportion_titeuf > proportion_classique

    def test_titeuf_joue_le_mot_favori_environ_la_moitie_des_cas_ou_plus(self):
        """Objectif de comportement de l'issue #452 : quand au moins un mot
        favori est jouable, Titeuf le joue dans environ la moitié des cas ou
        plus — vérifié avec une marge (40 %) pour ne pas être trop fragile à
        la variance d'un scénario de test miniature (le dictionnaire réel
        n'est pas disponible dans ce worktree isolé, voir le rapport de
        l'issue)."""
        profil_titeuf = PERSONNAGES["titeuf"].profil
        proportion = _proportion_mot_favori(Niveau.DEBUTANT, profil_titeuf, n=500)
        assert proportion >= 0.40

    def test_titeuf_dans_le_registre(self):
        assert "titeuf" in PERSONNAGES
        titeuf = PERSONNAGES["titeuf"]
        assert titeuf.prenom == "Titeuf"
        assert titeuf.description != ""

    def test_titeuf_apparait_dans_la_liste(self):
        cles = [p["cle"] for p in lister_personnages()]
        assert "titeuf" in cles

    def test_titeuf_profil_mots_favoris_et_poids_tirage(self):
        titeuf = PERSONNAGES["titeuf"].profil
        assert titeuf.mots_favoris == MOTS_FAVORIS_TITEUF
        assert titeuf.poids_tirage_favori == POIDS_TIRAGE_FAVORI_TITEUF
        assert POIDS_TIRAGE_FAVORI_TITEUF == 50.0

    def test_autres_personnages_mots_favoris_neutre(self):
        """``mots_favoris``/``poids_tirage_favori`` restent ``None`` pour
        tout personnage qui ne les demande pas explicitement — champs
        strictement additifs, sans effet de bord sur les personnages
        existants."""
        for cle in ("classique", "opportuniste", "chasseur_de_scrabbles"):
            assert PERSONNAGES[cle].profil.mots_favoris is None
            assert PERSONNAGES[cle].profil.poids_tirage_favori is None

    def test_titeuf_disponible_uniquement_a_debutant(self):
        assert NIVEAUX_TITEUF == frozenset({Niveau.DEBUTANT})
        for niveau in Niveau:
            attendu = niveau is Niveau.DEBUTANT
            assert personnage_disponible_a_niveau("titeuf", niveau) is attendu

    def test_titeuf_disponible_a_deux_joueurs_seulement(self):
        assert NB_JOUEURS_TITEUF == frozenset({2})
        assert personnage_disponible_a_nb_joueurs("titeuf", 2) is True
        for nb_joueurs in (3, 4):
            assert personnage_disponible_a_nb_joueurs("titeuf", nb_joueurs) is False

    def test_libelle_niveaux_titeuf(self):
        assert libelle_niveaux(PERSONNAGES["titeuf"]) == "Débutant"

    def test_libelle_tailles_titeuf(self):
        assert libelle_tailles(PERSONNAGES["titeuf"]) == "Parties à deux joueurs"

    def test_explication_disponibilite_titeuf(self):
        assert (
            explication_disponibilite_niveaux("titeuf")
            == "Disponible : Débutant"
        )
        assert (
            explication_disponibilite_tailles("titeuf")
            == MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS
        )

    def test_aleatoire_redevient_disponible_a_debutant_grace_a_titeuf(self):
        """Point central de l'issue #452 : la règle déjà en place (lot G,
        issue #447) rend Aléatoire de nouveau disponible à Débutant dès que
        Titeuf y figure, sans aucune autre modification."""
        assert aleatoire_disponible_a_niveau(Niveau.DEBUTANT) is True
        assert personnages_disponibles_a_niveau(Niveau.DEBUTANT) == [
            PERSONNAGES["classique"],
            PERSONNAGES["titeuf"],
        ]

    def test_tirage_aleatoire_a_debutant_inclut_titeuf(self):
        """Le tirage « Aléatoire » à Débutant doit, sur de nombreuses
        graines, couvrir les deux personnages désormais disponibles."""
        cles = {
            tirer_personnage(random.Random(g), Niveau.DEBUTANT).cle
            for g in range(50)
        }
        assert cles == {"classique", "titeuf"}


class TestMotsFavorisTiteuf:
    """Chargement de la liste de mots favoris (issue #452, lot J, points 1
    et 9) : fichier texte simple, modifiable sans toucher au code."""

    def test_liste_de_depart_chargee_depuis_le_fichier_du_depot(self):
        """La liste effectivement utilisée par Titeuf vient bien du fichier
        du dépôt (pas d'une valeur codée en dur ailleurs)."""
        assert CHEMIN_MOTS_FAVORIS_TITEUF.exists()
        assert MOTS_FAVORIS_TITEUF == charger_mots_favoris(CHEMIN_MOTS_FAVORIS_TITEUF)
        assert "CACA" in MOTS_FAVORIS_TITEUF
        assert "PROUT" in MOTS_FAVORIS_TITEUF

    def test_fichier_absent_renvoie_un_ensemble_vide_sans_erreur(self, tmp_path):
        assert charger_mots_favoris(tmp_path / "n_existe_pas.txt") == frozenset()

    def test_mots_normalises_majuscules_et_desaccentues(self, tmp_path):
        chemin = tmp_path / "favoris.txt"
        chemin.write_text("café\n  Pâté  \nCACA\n\n", encoding="utf-8")
        assert charger_mots_favoris(chemin) == frozenset({"CAFE", "PATE", "CACA"})

    def test_modification_du_fichier_prise_en_compte_sans_toucher_au_code(self, tmp_path):
        """La fonction de chargement relit le fichier à chaque appel : une
        liste modifiée est prise en compte sans toucher à une seule ligne de
        code — seul le fichier change."""
        chemin = tmp_path / "favoris.txt"
        chemin.write_text("caca\n", encoding="utf-8")
        assert charger_mots_favoris(chemin) == frozenset({"CACA"})

        chemin.write_text("caca\nprout\n", encoding="utf-8")
        assert charger_mots_favoris(chemin) == frozenset({"CACA", "PROUT"})

    def test_mot_absent_du_lexique_ignore_sans_filtrage_dedie(self):
        """Un mot de la liste absent du lexique complet installé n'est PAS
        filtré au chargement — la liste de mots favoris et le lexique
        complet sont deux préoccupations indépendantes (voir
        ``scrabble.moteur.ia._generer_coups_candidats`` pour l'endroit où ce
        mot est, lui, naturellement ignoré faute de coup validable)."""
        plateau = _plateau_titeuf()
        dico_niveau = Trie.depuis_iterable(_DICO_NIVEAU_TITEUF)
        # Lexique complet sans "CACA" : un mot de la liste absent du lexique.
        dico_complet_sans_caca = Trie.depuis_iterable(("ZX", "ZY", "ZW"))
        from scrabble.moteur.ia import ProfilPersonnage, _generer_coups_candidats

        profil = ProfilPersonnage(mots_favoris=frozenset({"CACA", "UNMOTABSENT"}))
        coups = _generer_coups_candidats(
            plateau, _CHEVALET_TITEUF, dico_niveau, profil, dico_complet_sans_caca
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "CACA" not in mots
        assert "UNMOTABSENT" not in mots
        # Les coups courts du vocabulaire du niveau restent, eux, inchangés.
        assert "ZX" in mots


# --------------------------------------------------------------------------- #
# Lettré (issue #454, lot K)
# --------------------------------------------------------------------------- #


def _plateau_lettre() -> PlateauPartie:
    """Plateau fabriqué pour que le mot favori ``AZOTURE`` (mot réel de la
    liste du Lettré, 7 lettres) soit en concurrence avec un coup mieux payé
    en score brut (``ZOTA``, synthétique, touchant la case mot triple
    (7, 14)) — même principe que :func:`_plateau_chasseur` (issue #448, lot
    H, deux ancres séparées), mais utilisé ici à AVANCE/EXPERT/CHAMPION_DU_MONDE
    (toujours le meilleur coup), pour démontrer que c'est bien
    ``bonus_favori`` qui renverse l'écart : le tirage pondéré de Titeuf n'a
    par construction aucun effet à ces niveaux.

    Deux ancres isolées :

    * ``Z`` en (7, 11) : permet ``ZOTA`` horizontal (``Z`` réutilisé, 3
      lettres nouvelles O/T/A) jusqu'en (7, 14), la case mot triple — score
      brut 39, stratégique 61 à AVANCE (bonus premium + leave value de
      production, sans aucun profil).
    * ``A`` en (0, 0) : permet ``AZOTURE`` horizontal ou vertical (``A``
      réutilisé, 6 lettres nouvelles Z/O/T/U/R/E), absent du vocabulaire du
      niveau, présent seulement dans le lexique complet — score brut 17,
      stratégique 17 à AVANCE SANS ``bonus_favori`` (perd nettement face à
      ``ZOTA``), 57 AVEC (l'emporte).
    """
    plateau = PlateauPartie()
    plateau.poser_coup(Coup(7, 11, Direction.HORIZONTALE, tuiles_depuis_chaine("Z")))
    plateau.poser_coup(Coup(0, 0, Direction.HORIZONTALE, tuiles_depuis_chaine("A")))
    return plateau


#: Chevalet du scénario ci-dessus : O/T/A pour ``ZOTA`` (``Z`` déjà sur le
#: plateau), Z/O/T/U/R/E pour ``AZOTURE`` (``A`` déjà sur le plateau) — sept
#: lettres distinctes, aucune ne manque à l'un ou l'autre coup.
_CHEVALET_LETTRE = list("OTAZURE")

#: Vocabulaire du niveau (restreint) pour le scénario ci-dessus : ne connaît
#: que le coup concurrent, sans rapport avec ``AZOTURE``.
_DICO_NIVEAU_LETTRE = ("ZOTA",)

#: Lexique complet pour le scénario ci-dessus : coup concurrent ET mot
#: favori.
_DICO_COMPLET_LETTRE = ("ZOTA", "AZOTURE")


def _proportion_mot_favori_lettre(niveau: Niveau, profil, n: int = 30) -> float:
    """Proportion des coups choisis (sur ``n`` graines) dont le mot principal
    est ``AZOTURE``, sur le scénario :func:`_plateau_lettre`."""
    plateau = _plateau_lettre()
    dico_niveau = Trie.depuis_iterable(_DICO_NIVEAU_LETTRE)
    dico_complet = Trie.depuis_iterable(_DICO_COMPLET_LETTRE)

    nb_favori = 0
    nb_joues = 0
    for graine in range(n):
        coup = choisir_coup(
            plateau,
            _CHEVALET_LETTRE,
            dico_niveau,
            niveau,
            random.Random(graine),
            profil=profil,
            dictionnaire_complet=dico_complet,
        )
        if coup is None:
            continue
        nb_joues += 1
        mot = "".join(t.lettre for t in coup.tuiles)
        if mot == "AZOTURE":
            nb_favori += 1
    assert nb_joues > 0
    return nb_favori / nb_joues


class TestPersonnageLettre:
    """Lettré doit choisir un mot favori nettement plus souvent que
    Classique, y compris à AVANCE — niveau qui joue toujours son meilleur
    coup, où le tirage pondéré de Titeuf n'aurait aucun effet (issue #454,
    lot K)."""

    def test_lettre_choisit_le_mot_favori_a_avance_bien_plus_souvent_que_classique(
        self,
    ):
        profil_classique = PERSONNAGES["classique"].profil
        profil_lettre = PERSONNAGES["lettre"].profil

        proportion_classique = _proportion_mot_favori_lettre(
            Niveau.AVANCE, profil_classique
        )
        proportion_lettre = _proportion_mot_favori_lettre(Niveau.AVANCE, profil_lettre)
        assert proportion_lettre > proportion_classique

    @pytest.mark.parametrize(
        "niveau", [Niveau.AVANCE, Niveau.EXPERT, Niveau.CHAMPION_DU_MONDE]
    )
    def test_lettre_joue_toujours_le_mot_favori_sur_ce_scenario(self, niveau):
        """Démonstration précise (issue #454, lot K, point « choix du coup
        même à un niveau qui joue toujours son meilleur coup ») : sur ce
        scénario fabriqué, Classique ne connaît même pas ``AZOTURE`` (absent
        de son vocabulaire) et Lettré le joue sur CHAQUE graine, aux trois
        niveaux où il est disponible, puisque son score stratégique dépasse
        celui du concurrent une fois le bonus de mot favori ajouté."""
        profil_lettre = PERSONNAGES["lettre"].profil
        assert _proportion_mot_favori_lettre(niveau, profil_lettre) == 1.0
        assert (
            _proportion_mot_favori_lettre(niveau, PERSONNAGES["classique"].profil)
            == 0.0
        )

    def test_bonus_favori_necessaire_sur_ce_scenario(self):
        """Sans ``bonus_favori`` (mais avec ``mots_favoris``, donc le mot
        favori est bien candidat), le coup concurrent mieux payé en score
        brut l'emporte quand même à AVANCE — preuve que c'est le bonus, pas
        le seul élargissement des coups candidats, qui fait gagner le mot
        favori sur ce scénario."""
        from scrabble.moteur.ia import ProfilPersonnage

        profil_sans_bonus = ProfilPersonnage(mots_favoris=frozenset({"AZOTURE"}))
        assert _proportion_mot_favori_lettre(Niveau.AVANCE, profil_sans_bonus) == 0.0

    def test_lettre_dans_le_registre(self):
        assert "lettre" in PERSONNAGES
        lettre = PERSONNAGES["lettre"]
        assert lettre.prenom == "Lettré"
        assert lettre.description != ""

    def test_lettre_apparait_dans_la_liste(self):
        cles = [p["cle"] for p in lister_personnages()]
        assert "lettre" in cles

    def test_lettre_profil_mots_favoris_et_bonus_favori(self):
        lettre = PERSONNAGES["lettre"].profil
        assert lettre.mots_favoris == MOTS_FAVORIS_LETTRE
        assert lettre.bonus_favori == BONUS_FAVORI_LETTRE
        assert BONUS_FAVORI_LETTRE == 40
        # Lettré ne renseigne volontairement pas le tirage pondéré (voir la
        # docstring du module) : le bonus de score suffit sur ses niveaux.
        assert lettre.poids_tirage_favori is None

    def test_autres_personnages_bonus_favori_neutre(self):
        """``bonus_favori`` reste ``None`` pour tout personnage qui ne le
        demande pas explicitement — champ strictement additif, sans effet de
        bord sur les personnages existants, Titeuf compris (qui renseigne
        ``mots_favoris``/``poids_tirage_favori`` mais pas ``bonus_favori``)."""
        for cle in ("classique", "opportuniste", "chasseur_de_scrabbles", "titeuf"):
            assert PERSONNAGES[cle].profil.bonus_favori is None

    def test_mots_favoris_lettre_independants_de_titeuf(self):
        """La liste du Lettré est indépendante de celle de Titeuf (issue
        #454, lot K, point « liste indépendante ») : fichiers distincts,
        contenus disjoints sur les mots emblématiques de chacun."""
        assert CHEMIN_MOTS_FAVORIS_LETTRE != CHEMIN_MOTS_FAVORIS_TITEUF
        assert MOTS_FAVORIS_LETTRE != MOTS_FAVORIS_TITEUF
        assert "CACA" not in MOTS_FAVORIS_LETTRE
        assert "PROUT" not in MOTS_FAVORIS_LETTRE
        assert "AZOTURE" not in MOTS_FAVORIS_TITEUF

    def test_lettre_disponible_a_avance_expert_champion_uniquement(self):
        assert NIVEAUX_LETTRE == frozenset(
            {Niveau.AVANCE, Niveau.EXPERT, Niveau.CHAMPION_DU_MONDE}
        )
        for niveau in Niveau:
            attendu = niveau in NIVEAUX_LETTRE
            assert personnage_disponible_a_niveau("lettre", niveau) is attendu

    def test_lettre_disponible_a_deux_joueurs_seulement(self):
        assert NB_JOUEURS_LETTRE == frozenset({2})
        assert personnage_disponible_a_nb_joueurs("lettre", 2) is True
        for nb_joueurs in (3, 4):
            assert personnage_disponible_a_nb_joueurs("lettre", nb_joueurs) is False

    def test_libelle_niveaux_lettre(self):
        assert libelle_niveaux(PERSONNAGES["lettre"]) == "Avancé à Champion du monde"

    def test_libelle_tailles_lettre(self):
        assert libelle_tailles(PERSONNAGES["lettre"]) == "Parties à deux joueurs"

    def test_explication_disponibilite_tailles_lettre(self):
        assert (
            explication_disponibilite_tailles("lettre")
            == MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS
        )

    def test_tirage_aleatoire_a_avance_peut_inclure_lettre(self):
        """Le tirage « Aléatoire » à AVANCE doit, sur de nombreuses graines,
        pouvoir renvoyer Lettré (en plus des personnages déjà disponibles à
        ce niveau)."""
        cles = {
            tirer_personnage(random.Random(g), Niveau.AVANCE).cle for g in range(50)
        }
        assert "lettre" in cles


class TestMotsFavorisLettre:
    """Chargement de la liste de mots favoris du Lettré (issue #454, lot K,
    points 1 et 9) : même fonction de chargement que Titeuf, fichier
    distinct, fourni par Alain."""

    def test_liste_de_depart_chargee_depuis_le_fichier_du_depot(self):
        """La liste effectivement utilisée par Lettré vient bien du fichier
        du dépôt (pas d'une valeur codée en dur ailleurs)."""
        assert CHEMIN_MOTS_FAVORIS_LETTRE.exists()
        assert MOTS_FAVORIS_LETTRE == charger_mots_favoris(CHEMIN_MOTS_FAVORIS_LETTRE)
        assert len(MOTS_FAVORIS_LETTRE) > 0
        assert "AZOTURE" in MOTS_FAVORIS_LETTRE

    def test_mot_absent_du_lexique_ignore_sans_filtrage_dedie(self):
        """Un mot de la liste absent du lexique complet installé n'est PAS
        filtré au chargement — même garantie que pour Titeuf (voir
        ``scrabble.moteur.ia._generer_coups_candidats``)."""
        plateau = _plateau_lettre()
        dico_niveau = Trie.depuis_iterable(_DICO_NIVEAU_LETTRE)
        # Lexique complet sans "AZOTURE" : un mot de la liste absent du lexique.
        dico_complet_sans_azoture = Trie.depuis_iterable(("ZOTA",))
        from scrabble.moteur.ia import ProfilPersonnage, _generer_coups_candidats

        profil = ProfilPersonnage(mots_favoris=frozenset({"AZOTURE", "UNMOTABSENT"}))
        coups = _generer_coups_candidats(
            plateau, _CHEVALET_LETTRE, dico_niveau, profil, dico_complet_sans_azoture
        )
        mots = {"".join(t.lettre for t in cn.coup.tuiles) for cn in coups}
        assert "AZOTURE" not in mots
        assert "UNMOTABSENT" not in mots
        # Le coup concurrent du vocabulaire du niveau reste, lui, inchangé.
        assert "ZOTA" in mots
