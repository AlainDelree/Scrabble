"""Détermination de l'ordre de jeu par tirage alphabétique (règle « maison »).

Rôle : implémenter la mécanique par laquelle l'ordre de jeu d'une partie est
décidé, non pas par l'ordre de création des joueurs, mais par un **tirage d'une
lettre par joueur**, l'ordre suivant l'ordre alphabétique des lettres tirées
(``A`` avant ``G`` avant ``H``…).

Lettres nécessairement distinctes
---------------------------------
Chaque joueur tire une lettre **différente de toutes celles déjà tirées** par
les autres joueurs pendant ce tirage d'ordre (issue #118). L'exclusion en amont
des lettres déjà sorties garantit par construction que deux joueurs ne peuvent
jamais obtenir la même lettre : l'ordre alphabétique est donc toujours univoque,
sans jamais avoir à gérer de cas d'égalité ni de nouveau tirage de départage.

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
il n'a pas de rang alphabétique. Ce sac filtré est un **objet jetable** propre à
la détermination d'ordre ; il ne consomme rien du sac réel de la partie, qui est
reconstitué complet et indépendamment par :func:`scrabble.moteur.partie.creer_
partie` — la distribution normale des 7 lettres de chevalet (jokers compris) a
donc lieu sur un sac intact, ce tirage d'ordre n'y prélevant aucune lettre.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from scrabble.regles.lettres import JOKER, constituer_sac


class TirageOrdreImpossible(RuntimeError):
    """Levée s'il est impossible de donner une lettre distincte à chaque joueur.

    Chaque joueur devant tirer une lettre différente des autres, il faut au moins
    autant de lettres distinctes que de joueurs. Le sac filtré ne compte que 26
    lettres distinctes ; au-delà, plutôt que de planter obscurément, on signale
    explicitement que la détermination d'ordre n'a pas pu aboutir.
    """


@dataclass(frozen=True)
class ResultatTirageOrdre:
    """Résultat d'un tirage d'ordre.

    ``ordre`` est la liste des **indices** des joueurs (dans la liste passée à
    :func:`determiner_ordre_jeu`) rangés dans l'ordre de jeu déterminé.
    ``lettres`` donne, pour chaque joueur et **dans l'ordre d'origine** de la
    liste (``lettres[i]`` correspond au joueur ``i``), la lettre qu'il a tirée —
    utile pour un affichage du type « Alice a tiré B, Marc a tiré K… ». Ces
    lettres sont toutes **distinctes** deux à deux (issue #118).
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
    tirées. Chaque lettre déjà tirée est **exclue** des tirages suivants, de
    sorte que tous les joueurs obtiennent des lettres deux à deux distinctes :
    aucune égalité n'est alors possible et l'ordre est toujours univoque
    (issue #118). Le sac filtré est un objet local et jetable ; le sac réel de
    la partie n'est pas touché par ce tirage.

    ``joueurs`` n'est utilisé que pour son cardinal : la fonction raisonne sur
    des indices et n'inspecte pas les éléments (elle s'applique donc aussi bien
    à des :class:`~scrabble.moteur.partie.Joueur` qu'à de simples marqueurs de
    test). ``alea`` (un :class:`random.Random`) rend le tirage reproductible ;
    à défaut, un générateur non graine est créé.

    :raises TirageOrdreImpossible: s'il n'y a pas assez de lettres distinctes
        pour donner une lettre différente à chaque joueur (plus de 26 joueurs).
    """
    if alea is None:
        alea = random.Random()
    nombre = len(joueurs)
    if nombre == 0:
        return ResultatTirageOrdre(ordre=[], lettres=[])

    sac = [jeton for jeton in constituer_sac() if jeton != JOKER]
    alea.shuffle(sac)

    # Une lettre par joueur, chacune distincte de celles déjà tirées : deux
    # joueurs ne peuvent donc jamais obtenir la même lettre.
    deja_tirees: set[str] = set()
    lettres: list[str] = []
    for _ in range(nombre):
        lettre = _tirer_une_distincte(sac, deja_tirees)
        deja_tirees.add(lettre)
        lettres.append(lettre)

    # Toutes les lettres étant distinctes, l'ordre est le simple tri
    # alphabétique — aucun départage d'égalité n'est nécessaire.
    ordre = sorted(range(nombre), key=lambda indice: lettres[indice])
    return ResultatTirageOrdre(ordre=ordre, lettres=lettres)


def _tirer_une_distincte(sac: list[str], deja_tirees: set[str]) -> str:
    """Retire et renvoie une lettre du sac absente de ``deja_tirees``.

    Les jetons dont la lettre est déjà sortie sont défaussés au passage : ils ne
    servent plus au tirage d'ordre (le sac est jetable). On s'arrête à la
    première lettre nouvelle.

    :raises TirageOrdreImpossible: si le sac ne contient plus aucune lettre non
        encore tirée (moins de lettres distinctes que de joueurs).
    """
    while sac:
        lettre = sac.pop()
        if lettre not in deja_tirees:
            return lettre
    raise TirageOrdreImpossible(
        "Le sac de détermination d'ordre (sans jokers) ne contient plus de "
        "lettre distincte : impossible de donner une lettre différente à "
        "chaque joueur."
    )
