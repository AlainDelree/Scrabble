"""Détermination de l'ordre de jeu par tirage alphabétique (règle « maison »).

Rôle : implémenter la mécanique par laquelle l'ordre de jeu d'une partie est
décidé, non pas par l'ordre de création des joueurs, mais par un **tirage d'une
lettre par joueur**, l'ordre suivant l'ordre alphabétique des lettres tirées
(``A`` avant ``G`` avant ``H``…). En cas d'égalité, seuls les joueurs concernés
retirent une nouvelle lettre entre eux pour se départager, le procédé se
répétant tant qu'une égalité subsiste.

Périmètre volontairement restreint
----------------------------------
Ce module ne construit **pas** de partie et ne distribue **aucun** chevalet :
c'est de la pure logique de détermination d'ordre. Il est consommé par
:func:`scrabble.moteur.partie.creer_partie` (paramètre ``tirage_ordre``) qui
réordonne sa liste de joueurs avant de construire la :class:`~scrabble.moteur.
partie.Partie`. L'ordre de jeu de la partie reste porté par l'ordre de la liste
``joueurs`` — aucun nouveau concept d'ordre séparé n'est introduit.

Choix du module dédié
---------------------
Cette règle est une brique autonome (elle ne dépend ni de ``Joueur`` ni de
``Partie`` : elle raisonne sur une simple liste d'éléments) et sera consommée
plus tard par un écran d'accueil. Un module séparé la garde testable isolément
et évite d'alourdir :mod:`scrabble.moteur.partie`.

Sac de détermination
--------------------
Le tirage réutilise la répartition officielle via
:func:`scrabble.regles.lettres.constituer_sac`, dont on **retire les 2 jokers**
(:data:`scrabble.regles.lettres.JOKER`) : un joker ne représente aucune lettre,
il n'a pas de rang alphabétique. Ce sac filtré est propre à la détermination
d'ordre ; il ne consomme rien du sac réel de la partie, dont la distribution
normale des 7 lettres de chevalet (jokers compris) a lieu ensuite.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from scrabble.regles.lettres import JOKER, constituer_sac


class TirageOrdreImpossible(RuntimeError):
    """Levée si le sac filtré s'épuise avant d'avoir départagé tous les joueurs.

    Cas extrême (beaucoup de joueurs et de rejouages d'égalité successifs) :
    plutôt que de planter obscurément sur un sac vide, on signale explicitement
    que la détermination d'ordre n'a pas pu aboutir.
    """


@dataclass(frozen=True)
class ResultatTirageOrdre:
    """Résultat d'un tirage d'ordre.

    ``ordre`` est la liste des **indices** des joueurs (dans la liste passée à
    :func:`determiner_ordre_jeu`) rangés dans l'ordre de jeu déterminé.
    ``lettres`` donne, pour chaque joueur et **dans l'ordre d'origine** de la
    liste (``lettres[i]`` correspond au joueur ``i``), la lettre qu'il a tirée
    au premier tour de tirage — utile pour un affichage futur du type
    « Alice a tiré B, Marc a tiré K… ». Les lettres des éventuels retirages de
    départage restent internes et ne sont pas exposées.
    """

    ordre: list[int]
    lettres: list[str]


def determiner_ordre_jeu(
    joueurs: Sequence[object],
    alea: random.Random | None = None,
) -> ResultatTirageOrdre:
    """Détermine l'ordre de jeu par tirage alphabétique d'une lettre par joueur.

    Chaque joueur tire une lettre d'un sac filtré (sac officiel **sans les 2
    jokers**, mélangé) ; l'ordre de jeu suit l'ordre alphabétique des lettres
    tirées. Les joueurs à égalité retirent une lettre entre eux, à partir des
    lettres restantes du **même** sac filtré, jusqu'à départage complet.

    ``joueurs`` n'est utilisé que pour son cardinal : la fonction raisonne sur
    des indices et n'inspecte pas les éléments (elle s'applique donc aussi bien
    à des :class:`~scrabble.moteur.partie.Joueur` qu'à de simples marqueurs de
    test). ``alea`` (un :class:`random.Random`) rend le tirage reproductible ;
    à défaut, un générateur non graine est créé.

    :raises TirageOrdreImpossible: si le sac filtré s'épuise avant d'avoir
        départagé tous les joueurs.
    """
    if alea is None:
        alea = random.Random()
    nombre = len(joueurs)
    if nombre == 0:
        return ResultatTirageOrdre(ordre=[], lettres=[])

    sac = [jeton for jeton in constituer_sac() if jeton != JOKER]
    alea.shuffle(sac)

    # Premier tirage : une lettre par joueur, conservée pour l'exposition.
    lettres = [_tirer_une(sac) for _ in range(nombre)]
    lettres_du_tour = {indice: lettres[indice] for indice in range(nombre)}
    ordre = _departager(list(range(nombre)), lettres_du_tour, sac)
    return ResultatTirageOrdre(ordre=ordre, lettres=lettres)


def _departager(
    indices: list[int],
    lettres_du_tour: dict[int, str],
    sac: list[str],
) -> list[int]:
    """Ordonne ``indices`` selon ``lettres_du_tour``, égalités résolues par retirage.

    Les indices sont groupés par lettre tirée ; les groupes sont parcourus dans
    l'ordre alphabétique. Un groupe d'un seul joueur est placé directement ; un
    groupe à égalité fait retirer **une nouvelle lettre à ses seuls membres**
    (depuis ``sac``, partagé) puis est ordonné récursivement — ce qui répète le
    départage tant qu'une égalité subsiste.
    """
    groupes: dict[str, list[int]] = {}
    for indice in indices:
        groupes.setdefault(lettres_du_tour[indice], []).append(indice)

    ordre: list[int] = []
    for lettre in sorted(groupes):
        groupe = groupes[lettre]
        if len(groupe) == 1:
            ordre.append(groupe[0])
        else:
            nouvelles = {indice: _tirer_une(sac) for indice in groupe}
            ordre.extend(_departager(groupe, nouvelles, sac))
    return ordre


def _tirer_une(sac: list[str]) -> str:
    """Retire et renvoie une lettre du sac filtré.

    :raises TirageOrdreImpossible: si le sac est vide.
    """
    if not sac:
        raise TirageOrdreImpossible(
            "Le sac de détermination d'ordre (sans jokers) est épuisé : "
            "impossible de départager tous les joueurs."
        )
    return sac.pop()
