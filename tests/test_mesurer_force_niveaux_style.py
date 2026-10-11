"""Tests des indicateurs de style de ``scripts/mesurer_force_niveaux.py`` (issue #446).

Comme ``test_generer_mots_courants.py``, le script vit hors du paquet
``scrabble`` (hors ``pythonpath``) : on le charge par son chemin, comme le
ferait un lancement en ligne de commande, plutôt que de l'importer comme un
module normal.

Trois axes, repris du point 4 de l'issue :

* :func:`test_calculer_indicateurs_sur_partie_fabriquee_a_la_main` — une
  petite partie à 4 actions, montée coup par coup à la main (pas via l'IA, ni
  via ``jouer_une_partie``), dont on connaît par avance les cases bonus
  touchées, la longueur des mots, le joker posé et son tour, et les passes ;
  elle vérifie que :func:`_calculer_indicateurs_joueur` produit exactement les
  valeurs attendues.
* :func:`test_ecrire_csv_exporte_les_indicateurs_de_style` — l'export CSV
  complet (point 2) sur des résultats synthétiques, jokers compris (cas où la
  moyenne doit rester vide plutôt que ``0``).
* :func:`test_jouer_une_partie_integre_les_indicateurs_sans_changer_la_force`
  — ``jouer_une_partie`` de bout en bout (dictionnaire vide à dessein, pour ne
  dépendre d'aucun vrai dictionnaire ni d'un déroulement long) : les
  indicateurs sont bien renseignés, et le résultat de force (graine, scores,
  qui commence, nombre de tours) est strictement déterministe — reproduit à
  l'identique sur un second appel aux mêmes paramètres, donc non perturbé par
  le calcul des indicateurs (point 3 : ce calcul n'est qu'une relecture de
  l'historique une fois la partie terminée, sans second appel à l'IA ni
  consommation additionnelle d'aléa).
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import CENTRE, Coup, Direction, tuiles_depuis_chaine
from scrabble.regles.lettres import valeur_lettre

_CHEMIN_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "mesurer_force_niveaux.py"
)
_spec = importlib.util.spec_from_file_location("mesurer_force_niveaux", _CHEMIN_SCRIPT)
mfn = importlib.util.module_from_spec(_spec)
# Les dataclasses du module (``ResultatPartie``, etc., avec annotations
# différées via ``from __future__ import annotations``) résolvent leurs types
# via ``sys.modules[cls.__module__]`` : le module doit donc déjà y être
# enregistré avant son exécution, sinon ``dataclass`` lève à l'import.
sys.modules[_spec.name] = mfn
_spec.loader.exec_module(mfn)


# --------------------------------------------------------------------------- #
# Partie fabriquée à la main (point 4) : CHAT (A, centre) / CH (B, LD) /
# AS-joker (A, LD) / passe (B).
# --------------------------------------------------------------------------- #

def _construire_partie_fabriquee() -> Partie:
    """Monte à la main la petite partie décrite dans le docstring du module.

    Tour 1 (A) : ``CHAT`` horizontal couvrant le centre (ligne 7, colonnes
    6-9) — premier coup, 4 lettres neuves, une seule case bonus touchée (le
    centre).
    Tour 2 (B) : ``CH`` vertical sous le ``C`` existant (ligne 7→8, colonne 6)
    — 1 lettre neuve sur une case lettre-double (6, pas mot double/triple).
    Tour 3 (A) : ``AS`` vertical sous le ``A`` existant (ligne 7→8, colonne 8)
    avec un joker représentant le ``S`` — 1 lettre neuve (le joker) sur une
    autre case lettre-double.
    Tour 4 (B) : passe.
    """
    dictionnaire = Trie.depuis_iterable(["CHAT", "CH", "AS"])
    joueur_a = Joueur(nom="A:TEST", humain=True, chevalet=["C", "H", "A", "T", "*", "Q", "Q"])
    joueur_b = Joueur(nom="B:TEST", humain=True, chevalet=["H", "A", "Z", "Z", "Z", "Z", "Z"])
    partie = Partie([joueur_a, joueur_b], dictionnaire, graine=1)
    # Rejoue les chevalets sur les valeurs voulues (la distribution initiale du
    # sac, aléatoire, ne nous intéresse pas ici : seule la suite d'actions
    # compte pour les indicateurs).
    partie.joueurs[0].chevalet = ["C", "H", "A", "T", "*", "Q", "Q"]
    partie.joueurs[1].chevalet = ["H", "A", "Z", "Z", "Z", "Z", "Z"]
    # Sac déjà entamé par la distribution initiale : on le vide pour que les
    # piochés de complément après chaque coup ne perturbent pas les chevalets
    # construits à la main ci-dessus (seules les lettres qu'on y a mises sont
    # jouées).
    partie.sac.tirer(partie.sac.jetons_restants())

    ligne, colonne = CENTRE
    partie.jouer_coup(Coup(ligne, colonne - 1, Direction.HORIZONTALE, tuiles_depuis_chaine("CHAT")))
    partie.jouer_coup(Coup(ligne, colonne - 1, Direction.VERTICALE, tuiles_depuis_chaine("CH")))
    partie.jouer_coup(
        Coup(
            ligne,
            colonne + 1,
            Direction.VERTICALE,
            tuiles_depuis_chaine("AS", jokers=frozenset({1})),
        )
    )
    partie.passer()
    return partie


def test_calculer_indicateurs_sur_partie_fabriquee_a_la_main():
    partie = _construire_partie_fabriquee()

    ind_a = mfn._calculer_indicateurs_joueur(partie.historique, "A:", penalite_fin=18)
    ind_b = mfn._calculer_indicateurs_joueur(partie.historique, "B:", penalite_fin=1)

    # Camp A : CHAT (centre) puis AS au joker (lettre double).
    assert ind_a.coups_poses == 2
    assert ind_a.coups_touchant_multiplicateur == 2  # centre + lettre double
    assert ind_a.coups_touchant_mot_double_triple == 1  # seul le centre compte
    assert ind_a.lettres_posees == [4, 1]
    assert ind_a.longueur_mot_principal == [4, 2]  # "CHAT" puis "AS"
    valeur_chat = 2 * (valeur_lettre("C") + valeur_lettre("H") + valeur_lettre("A") + valeur_lettre("T"))
    valeur_as = valeur_lettre("A")  # le joker ne rapporte rien, la case LD ne multiplie que 0
    assert ind_a.points_par_coup == [valeur_chat, valeur_as]
    assert ind_a.scrabbles == 0
    assert ind_a.nb_jokers == 1
    assert ind_a.points_coups_joker == [valeur_as]
    assert ind_a.tours_coups_joker == [3]  # 3e action de l'historique complet
    assert ind_a.passes == 0
    assert ind_a.penalite_fin == 18

    # Camp B : CH (lettre double) puis passe.
    assert ind_b.coups_poses == 1
    assert ind_b.coups_touchant_multiplicateur == 1
    assert ind_b.coups_touchant_mot_double_triple == 0
    assert ind_b.lettres_posees == [1]
    assert ind_b.longueur_mot_principal == [2]  # "CH"
    valeur_ch = valeur_lettre("C") + 2 * valeur_lettre("H")
    assert ind_b.points_par_coup == [valeur_ch]
    assert ind_b.nb_jokers == 0
    assert ind_b.points_coups_joker == []
    assert ind_b.tours_coups_joker == []
    assert ind_b.passes == 1
    assert ind_b.penalite_fin == 1


# --------------------------------------------------------------------------- #
# Part des coups à mot favori (issue #452, lot J)
# --------------------------------------------------------------------------- #

def test_calculer_indicateurs_mot_favori():
    """``mots_favoris`` (issue #452, lot J) alimente ``coups_mot_favori``, et
    vaut 0 quand il n'est pas fourni (cas d'un personnage sans liste)."""
    partie = _construire_partie_fabriquee()

    # Camp A a joué CHAT puis AS : seul CHAT est un mot favori ici.
    ind_a_avec_favori = mfn._calculer_indicateurs_joueur(
        partie.historique, "A:", penalite_fin=0, mots_favoris=frozenset({"CHAT"})
    )
    assert ind_a_avec_favori.coups_mot_favori == 1

    # Sans mots_favoris (défaut), toujours 0 — même historique.
    ind_a_sans_favori = mfn._calculer_indicateurs_joueur(
        partie.historique, "A:", penalite_fin=0
    )
    assert ind_a_sans_favori.coups_mot_favori == 0

    # Une liste qui ne contient aucun des mots joués reste à 0.
    ind_a_favori_absent = mfn._calculer_indicateurs_joueur(
        partie.historique, "A:", penalite_fin=0, mots_favoris=frozenset({"PROUT"})
    )
    assert ind_a_favori_absent.coups_mot_favori == 0


def test_jouer_une_partie_titeuf_sans_coup_jouable_mot_favori_reste_a_zero():
    """Pas de régression du déterminisme de force avec un personnage à liste
    de mots favoris (Titeuf) : même scénario sans aucun coup jouable que
    :func:`test_jouer_une_partie_integre_les_indicateurs_sans_changer_la_force`
    ci-dessous — la résolution de ``mots_favoris`` ne perturbe rien."""
    dictionnaire_vide = Trie.depuis_iterable([])
    config_a = mfn.ConfigJoueur(niveau=mfn.Niveau.DEBUTANT, personnage="titeuf")
    config_b = mfn.ConfigJoueur(niveau=mfn.Niveau.DEBUTANT, personnage="classique")

    resultat = mfn.jouer_une_partie(
        config_a, config_b, graine_partie=7,
        dictionnaire=dictionnaire_vide,
        trie_a=dictionnaire_vide, trie_b=dictionnaire_vide,
    )
    assert resultat.indicateurs_a.coups_mot_favori == 0
    assert resultat.indicateurs_b.coups_mot_favori == 0


def test_jouer_une_partie_lettre_sans_coup_jouable_mot_favori_reste_a_zero():
    """Même non-régression que ci-dessus pour Lettré (issue #454, lot K) : la
    colonne « coups dont le mot principal est un mot favori » lit bien la
    liste PROPRE à ce personnage (pas celle de Titeuf), résolue depuis son
    profil comme n'importe quel autre personnage à liste — voir
    ``_calculer_indicateurs_joueur``."""
    dictionnaire_vide = Trie.depuis_iterable([])
    config_a = mfn.ConfigJoueur(niveau=mfn.Niveau.AVANCE, personnage="lettre")
    config_b = mfn.ConfigJoueur(niveau=mfn.Niveau.AVANCE, personnage="classique")

    resultat = mfn.jouer_une_partie(
        config_a, config_b, graine_partie=7,
        dictionnaire=dictionnaire_vide,
        trie_a=dictionnaire_vide, trie_b=dictionnaire_vide,
    )
    assert resultat.indicateurs_a.coups_mot_favori == 0
    assert resultat.indicateurs_b.coups_mot_favori == 0


# --------------------------------------------------------------------------- #
# Export CSV complet (point 2 et point 4)
# --------------------------------------------------------------------------- #

def test_ecrire_csv_exporte_les_indicateurs_de_style(tmp_path):
    ind_a = mfn.IndicateursPartieJoueur(
        coups_poses=2,
        coups_touchant_multiplicateur=2,
        coups_touchant_mot_double_triple=1,
        lettres_posees=[4, 1],
        points_par_coup=[18, 1],
        longueur_mot_principal=[4, 2],
        scrabbles=0,
        nb_jokers=1,
        points_coups_joker=[1],
        tours_coups_joker=[3],
        passes=0,
        penalite_fin=18,
    )
    ind_b = mfn.IndicateursPartieJoueur(
        coups_poses=1,
        coups_touchant_multiplicateur=1,
        coups_touchant_mot_double_triple=0,
        lettres_posees=[1],
        points_par_coup=[11],
        longueur_mot_principal=[2],
        scrabbles=0,
        nb_jokers=0,
        points_coups_joker=[],
        tours_coups_joker=[],
        passes=1,
        penalite_fin=1,
    )
    resultat = mfn.ResultatPartie(
        graine=1, score_a=19, score_b=10, commence="a", tours=4,
        indicateurs_a=ind_a, indicateurs_b=ind_b,
    )

    chemin = tmp_path / "mesure.csv"
    mfn._ecrire_csv(chemin, "CAMP_A", "CAMP_B", [resultat])

    with open(chemin, newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    assert len(lignes) == 1
    ligne = lignes[0]

    # Colonnes historiques inchangées.
    assert ligne["graine"] == "1"
    assert ligne["score_CAMP_A"] == "19"
    assert ligne["score_CAMP_B"] == "10"
    assert ligne["vainqueur"] == "CAMP_A"
    assert ligne["a_commence"] == "CAMP_A"
    assert ligne["tours"] == "4"

    # Nouvelles colonnes de style, camp A.
    assert ligne["a_coups"] == "2"
    assert float(ligne["a_part_bonus"]) == 1.0
    assert float(ligne["a_part_mot_double_triple"]) == 0.5
    assert float(ligne["a_lettres_moy"]) == 2.5
    assert ligne["a_jokers"] == "1"
    assert float(ligne["a_points_coup_joker_moy"]) == 1.0
    assert float(ligne["a_tour_joker_moy"]) == 3.0

    # Camp B : aucun joker joué cette partie → moyenne vide, pas 0.
    assert ligne["b_jokers"] == "0"
    assert ligne["b_points_coup_joker_moy"] == ""
    assert ligne["b_tour_joker_moy"] == ""
    assert ligne["b_passes"] == "1"
    assert ligne["b_penalite_fin"] == "1"

    # Colonne "part_mot_favori" (issue #452, lot J) : absente des deux
    # ``IndicateursPartieJoueur`` fabriqués ci-dessus (``coups_mot_favori``
    # par défaut à 0) — la part doit donc être 0, pas vide (contrairement à
    # une moyenne jamais observée, un coup posé est toujours soit un mot
    # favori, soit non).
    assert float(ligne["a_part_mot_favori"]) == 0.0
    assert float(ligne["b_part_mot_favori"]) == 0.0


# --------------------------------------------------------------------------- #
# Intégration : jouer_une_partie, déterminisme de la force inchangé
# --------------------------------------------------------------------------- #

def test_jouer_une_partie_integre_les_indicateurs_sans_changer_la_force():
    # Dictionnaire vide à dessein : aucun coup n'est jamais valide, les deux
    # IA passent donc immédiatement (confirmé indépendamment : avec un Trie
    # vide, ``ia.choisir_coup`` renvoie toujours ``None``) et la partie se
    # termine par blocage dès le 2e tour — rapide et sans dépendre d'un vrai
    # dictionnaire (absent de ce worktree, comme au lot B).
    dictionnaire_vide = Trie.depuis_iterable([])
    config_a = mfn.ConfigJoueur(niveau=mfn.Niveau.DEBUTANT)
    config_b = mfn.ConfigJoueur(niveau=mfn.Niveau.DEBUTANT)

    def jouer():
        return mfn.jouer_une_partie(
            config_a, config_b, graine_partie=7,
            dictionnaire=dictionnaire_vide,
            trie_a=dictionnaire_vide, trie_b=dictionnaire_vide,
        )

    resultat_1 = jouer()
    resultat_2 = jouer()

    # Déterminisme de la force : identique d'un appel à l'autre, donc non
    # perturbé par le calcul des indicateurs de style.
    assert (resultat_1.graine, resultat_1.score_a, resultat_1.score_b,
            resultat_1.commence, resultat_1.tours) == (
        resultat_2.graine, resultat_2.score_a, resultat_2.score_b,
        resultat_2.commence, resultat_2.tours,
    )

    # Aucun coup possible : uniquement des passes, des deux côtés — le score
    # final n'est donc que la pénalité des lettres jamais posées (chevalet
    # initial complet, jamais réduit).
    assert resultat_1.tours == 2
    assert resultat_1.indicateurs_a.coups_poses == 0
    assert resultat_1.indicateurs_b.coups_poses == 0
    assert resultat_1.indicateurs_a.passes == 1
    assert resultat_1.indicateurs_b.passes == 1
    assert resultat_1.indicateurs_a.penalite_fin > 0
    assert resultat_1.indicateurs_b.penalite_fin > 0
    assert resultat_1.score_a == -resultat_1.indicateurs_a.penalite_fin
    assert resultat_1.score_b == -resultat_1.indicateurs_b.penalite_fin
