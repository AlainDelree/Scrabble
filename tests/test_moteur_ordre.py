"""Tests de ``scrabble.moteur.ordre`` (détermination de l'ordre de jeu).

Couvre le tirage simple (ordre alphabétique appliqué, lettre de chaque joueur
exposée), la garantie que toutes les lettres tirées sont distinctes deux à deux
(issue #118 : plus aucune égalité possible), l'exclusion structurelle des jokers
du sac de détermination, la reproductibilité par graine, et l'épuisement du sac
filtré au-delà de 26 joueurs.
"""

from __future__ import annotations

import random

import pytest

from scrabble.moteur.ordre import (
    ResultatTirageOrdre,
    TirageOrdreImpossible,
    determiner_ordre_jeu,
)
from scrabble.regles.lettres import JOKER


def _cherche_graine(nombre_joueurs, predicat, *, maxi=2000):
    """Renvoie la première graine (0..maxi) dont le tirage vérifie ``predicat``.

    ``predicat`` reçoit la liste des lettres tirées (premier tour) et renvoie un
    booléen. Sert à fabriquer, de façon déterministe et reproductible, des cas
    de tirage aux propriétés voulues (égalité ou non) sans coder « en dur » un
    résultat de ``random``.
    """
    joueurs = list(range(nombre_joueurs))
    for graine in range(maxi):
        resultat = determiner_ordre_jeu(joueurs, random.Random(graine))
        if predicat(resultat.lettres):
            return graine
    raise AssertionError("Aucune graine trouvée pour le prédicat demandé.")


# --------------------------------------------------------------------------- #
# Tirage simple, sans égalité
# --------------------------------------------------------------------------- #

def test_tirage_simple_sans_egalite_ordre_alphabetique():
    graine = _cherche_graine(4, lambda ls: len(set(ls)) == 4)
    resultat = determiner_ordre_jeu(list(range(4)), random.Random(graine))

    assert isinstance(resultat, ResultatTirageOrdre)
    # Chaque joueur a une lettre exposée, parallèle à la liste d'origine.
    assert len(resultat.lettres) == 4
    # L'ordre suit l'ordre alphabétique des lettres tirées.
    lettres_dans_l_ordre = [resultat.lettres[i] for i in resultat.ordre]
    assert lettres_dans_l_ordre == sorted(resultat.lettres)
    # L'ordre est une permutation de tous les indices.
    assert sorted(resultat.ordre) == [0, 1, 2, 3]


def test_lettre_de_chaque_joueur_exposee():
    resultat = determiner_ordre_jeu(list(range(3)), random.Random(7))
    assert len(resultat.lettres) == 3
    assert all(lettre.isalpha() for lettre in resultat.lettres)


# --------------------------------------------------------------------------- #
# Lettres distinctes — plus aucune égalité possible (issue #118)
# --------------------------------------------------------------------------- #

def test_lettres_toujours_distinctes_sur_de_nombreuses_graines():
    # Sur de nombreux tirages et pour des effectifs variés (jusqu'au maximum de
    # 26 joueurs = 26 lettres distinctes), aucune lettre n'est jamais tirée deux
    # fois au cours d'un même tirage d'ordre : l'égalité est impossible.
    for nombre in (2, 3, 4, 8, 20, 26):
        for graine in range(300):
            resultat = determiner_ordre_jeu(
                list(range(nombre)), random.Random(graine)
            )
            assert len(set(resultat.lettres)) == nombre, (
                f"Lettres non distinctes pour {nombre} joueurs, "
                f"graine {graine} : {resultat.lettres}"
            )


def test_ordre_est_le_tri_alphabetique_des_lettres_distinctes():
    # Les lettres étant distinctes, l'ordre est simplement leur tri alphabétique
    # et une permutation complète des indices, sans doublon.
    for graine in range(50):
        resultat = determiner_ordre_jeu(list(range(5)), random.Random(graine))
        assert sorted(resultat.ordre) == [0, 1, 2, 3, 4]
        lettres_dans_l_ordre = [resultat.lettres[i] for i in resultat.ordre]
        assert lettres_dans_l_ordre == sorted(resultat.lettres)


# --------------------------------------------------------------------------- #
# Exclusion des jokers
# --------------------------------------------------------------------------- #

def test_aucun_joker_tire_sur_de_nombreuses_graines():
    for graine in range(500):
        resultat = determiner_ordre_jeu(list(range(4)), random.Random(graine))
        assert JOKER not in resultat.lettres


# --------------------------------------------------------------------------- #
# Reproductibilité
# --------------------------------------------------------------------------- #

def test_reproductibilite_meme_graine_meme_ordre():
    r1 = determiner_ordre_jeu(list(range(4)), random.Random(123))
    r2 = determiner_ordre_jeu(list(range(4)), random.Random(123))
    assert r1 == r2


def test_graines_differentes_donnent_des_tirages_differents():
    r1 = determiner_ordre_jeu(list(range(4)), random.Random(1))
    r2 = determiner_ordre_jeu(list(range(4)), random.Random(2))
    # Extrêmement probable d'être différent ; sinon l'un des deux au moins l'est.
    assert (r1.lettres, r1.ordre) != (r2.lettres, r2.ordre)


# --------------------------------------------------------------------------- #
# Cas limites
# --------------------------------------------------------------------------- #

def test_liste_vide():
    resultat = determiner_ordre_jeu([], random.Random(0))
    assert resultat.ordre == []
    assert resultat.lettres == []


def test_un_seul_joueur():
    resultat = determiner_ordre_jeu([object()], random.Random(0))
    assert resultat.ordre == [0]
    assert len(resultat.lettres) == 1


def test_sac_epuise_leve_une_erreur_explicite():
    # Chaque joueur exigeant une lettre distincte, il n'y a que 26 lettres
    # disponibles : au-delà de 26 joueurs, on ne peut plus toutes les départager.
    with pytest.raises(TirageOrdreImpossible):
        determiner_ordre_jeu(list(range(27)), random.Random(0))


def test_vingt_six_joueurs_epuisent_toutes_les_lettres_sans_erreur():
    # 26 joueurs = les 26 lettres distinctes exactement : cas limite valide.
    resultat = determiner_ordre_jeu(list(range(26)), random.Random(0))
    assert sorted(resultat.ordre) == list(range(26))
    assert len(set(resultat.lettres)) == 26
