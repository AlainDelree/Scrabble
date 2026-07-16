"""Tests de ``scrabble.moteur.ordre`` (détermination de l'ordre de jeu).

Couvre le tirage simple sans égalité (ordre alphabétique appliqué, lettre de
chaque joueur exposée), la résolution d'égalité par retirage des seuls joueurs
concernés, l'exclusion structurelle des jokers du sac de détermination, la
reproductibilité par graine, et l'épuisement du sac filtré.
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
# Égalités
# --------------------------------------------------------------------------- #

def test_egalite_departagee_par_retirage_sans_retirer_les_autres():
    # Deux joueurs à égalité, un troisième distinct : on cherche un tirage où
    # exactement deux des trois lettres coïncident.
    def deux_ex_aequo(lettres):
        return len(set(lettres)) == 2 and any(
            lettres.count(l) == 2 for l in lettres
        )

    graine = _cherche_graine(3, deux_ex_aequo)
    resultat = determiner_ordre_jeu(list(range(3)), random.Random(graine))

    # Malgré l'égalité, l'ordre départage bien les trois joueurs.
    assert sorted(resultat.ordre) == [0, 1, 2]
    # Le joueur à lettre unique garde son rang alphabétique par rapport aux
    # deux ex æquo (son placement ne dépend pas du retirage interne).
    lettres = resultat.lettres
    (lettre_unique,) = [l for l in set(lettres) if lettres.count(l) == 1]
    idx_unique = lettres.index(lettre_unique)
    lettre_partagee = next(l for l in lettres if lettres.count(l) == 2)
    rang_unique = resultat.ordre.index(idx_unique)
    rangs_partages = [
        resultat.ordre.index(i)
        for i, l in enumerate(lettres)
        if l == lettre_partagee
    ]
    if lettre_unique < lettre_partagee:
        assert rang_unique < min(rangs_partages)
    else:
        assert rang_unique > max(rangs_partages)


def test_egalite_persistante_finit_par_se_departager():
    # Tous les joueurs à la même lettre au premier tour : le retirage doit
    # néanmoins produire un ordre total (aucun doublon d'indice).
    graine = _cherche_graine(3, lambda ls: len(set(ls)) == 1)
    resultat = determiner_ordre_jeu(list(range(3)), random.Random(graine))
    assert sorted(resultat.ordre) == [0, 1, 2]


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
    # 101 « joueurs » : le sac filtré ne compte que 100 lettres.
    with pytest.raises(TirageOrdreImpossible):
        determiner_ordre_jeu(list(range(101)), random.Random(0))
