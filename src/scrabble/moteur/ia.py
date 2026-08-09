"""Stratégies de sélection de coup IA pour la boucle de partie.

Rôle : choisir, au tour d'un joueur IA, un coup parmi ceux générés
exhaustivement par :func:`scrabble.moteur.generateur.generer_coups`.
La génération est identique quel que soit le niveau ; seule la stratégie
de sélection dans la liste triée par score varie.

Niveaux de difficulté (refonte issue #401, sur la base de l'issue #400)
-------------------------------------------------------------------------
:class:`Niveau` garde ses six membres, dans le même ordre — seule la
logique associée à chaque nom change. Chaque niveau reprend la stratégie
de sélection d'un ancien niveau plus fort, ce qui resserre l'échelle vers
le haut ; EXPERT devient un niveau à part entière, intercalé entre l'ancien
AVANCE (désormais niveau AVANCE, meilleur coup) et CHAMPION_DU_MONDE :

* **CHAMPION_DU_MONDE** : inchangé. Même stratégie de sélection qu'AVANCE
  (meilleur coup) et même tranche de malus/bonus stratégiques. Ne se
  distingue d'AVANCE que par le vocabulaire — câblé par l'appelant (issue
  #369, lot C) via :func:`resoudre_palier` : AVANCE reçoit le Trie restreint
  du palier ``"avance"``, CHAMPION_DU_MONDE le Trie complet (ODS8 sans
  filtre, ``obtenir_trie()``). Ce module lui-même reste agnostique du
  dictionnaire reçu (voir « Ordre réel de force » ci-dessous).
* **EXPERT** : nouveau niveau (issue #401). Choix aléatoire uniforme parmi
  les 5 % meilleurs coups (top 5 %, :func:`_choisir_top5`), sur le Trie
  complet ODS8 — comme CHAMPION_DU_MONDE, EXPERT n'a pas de palier de
  vocabulaire restreint (voir :func:`resoudre_palier`). Intercalaire entre
  AVANCE (meilleur coup, vocabulaire restreint) et CHAMPION_DU_MONDE
  (meilleur coup, vocabulaire complet).
* **AVANCE** : choisit le meilleur coup (premier de la liste triée), sur le
  palier de vocabulaire ``"avance"``. En cas d'égalité de score entre
  plusieurs coups de tête, choix aléatoire parmi eux. Reprend la stratégie
  de sélection de l'ancien EXPERT (issue #401).
* **INTERMEDIAIRE** : choix aléatoire uniforme parmi les 15 % meilleurs
  coups (top 15 %). Reprend la stratégie de sélection de l'ancien AVANCE
  (issue #401).
* **FACILE** : choix aléatoire uniforme parmi le meilleur tiers des coups
  (top 33 %). Reprend la stratégie de sélection de l'ancien INTERMEDIAIRE
  (issue #401).
* **DEBUTANT** : choix aléatoire uniforme parmi les 70 % meilleurs coups
  (top 70 %). Fusionne les anciens DEBUTANT (top 85 %) et FACILE (top 60 %)
  en un seul niveau d'entrée de gamme (issue #401).

Ordre réel de force (score moyen)
---------------------------------
Les stratégies ci-dessus produisent, en moyenne, l'ordre croissant
``DEBUTANT < FACILE < INTERMEDIAIRE < AVANCE < EXPERT < CHAMPION_DU_MONDE``
— cohérent avec l'ordre de la classe :class:`Niveau` et avec ce que
suggèrent les noms des niveaux.

Cette monotonie est STRUCTURELLE pour les quatre premiers niveaux : tous
passent par le même mécanisme (tri par score stratégique puis tirage
uniforme dans une tranche haute), et les tranches sont strictement
emboîtées — top 70 % (DEBUTANT) ⊃ top 33 % (FACILE) ⊃ top 15 %
(INTERMEDIAIRE) ⊃ meilleur coup (AVANCE). Chaque tranche étant un
sous-ensemble strictement meilleur de la précédente, les scores moyens
croissent mécaniquement avec le niveau, indépendamment du dictionnaire
employé. Aucun niveau n'a de filtre dur spécifique : l'issue #359 avait doté
l'ancien DEBUTANT d'un filtre sur la longueur (``nb_nouvelles >= 3``) qui le
rendait plus sélectif que l'ancien FACILE et cassait la monotonie ; l'issue
#361 l'a remplacé par une tranche haute, principe conservé ici.

Les deux derniers maillons, AVANCE < EXPERT < CHAMPION_DU_MONDE, sont de
nature DIFFÉRENTE : AVANCE et CHAMPION_DU_MONDE partagent la même stratégie
de sélection (:func:`_choisir_avance`, meilleur coup) et ne se distinguent
que par le vocabulaire — câblé par l'appelant (issue #369, lot C, voir
:func:`resoudre_palier`). EXPERT, lui, change à la fois de stratégie (top
5 % plutôt que meilleur coup) et de vocabulaire par rapport à AVANCE (Trie
complet ODS8, comme CHAMPION_DU_MONDE) : ces deux facteurs jouent dans le
même sens (top 5 % sur vocabulaire plus large ouvre en moyenne de meilleurs
coups qu'un coup unique sur vocabulaire restreint), d'où l'inégalité
attendue en moyenne. Contrairement aux quatre premiers niveaux, ce n'est
donc PAS une propriété purement structurelle de ce module — voir la fixture
de test dédiée pour la vérification empirique.

Comportement de repli (listes courtes)
--------------------------------------
Si la tranche calculée (top 5 %, top 15 %, tiers, top 70 %) est vide, on
retombe sur la liste complète via ``max(1, ...)``. Cela évite tout crash sur
des positions avec peu de coups jouables.
Exemple : 2 coups disponibles, tiers = 0 → on choisit parmi les 2.

Reproductibilité
----------------
Le paramètre ``alea`` (:class:`random.Random` optionnel) permet d'injecter
un générateur aléatoire à graine fixée pour des tests reproductibles.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING

from scrabble.moteur.generateur import CoupNote, generer_coups
from scrabble.moteur.plateau_partie import Coup, PlateauPartie
from scrabble.regles.lettres import JOKER
from scrabble.regles.plateau import TypeCase

if TYPE_CHECKING:
    from scrabble.moteur.generateur import TrieProtocol


class Niveau(Enum):
    """Niveaux de difficulté IA, du plus faible au plus fort.

    :attr:`CHAMPION_DU_MONDE` est ajouté en fin de liste (issue #368, lot D) :
    la position en fin garantit la rétro-compatibilité des parties existantes
    sérialisées par ``.name`` (voir ``stockage.py``), la position des
    ``auto()`` précédents n'ayant aucun impact sur les données stockées.
    """

    DEBUTANT = auto()
    FACILE = auto()
    INTERMEDIAIRE = auto()
    AVANCE = auto()
    EXPERT = auto()
    CHAMPION_DU_MONDE = auto()


# Résolution Niveau → clé de palier de vocabulaire IA (issue #369, lot C).
#
# Emplacement volontaire : ce module (``moteur.ia``) connaît :class:`Niveau`,
# et les clés ci-dessous ne sont que des chaînes — aucune dépendance vers
# ``scrabble.dictionnaire`` n'est introduite ici. C'est le sens inverse qui est
# strictement interdit (choix du lot A, issue #366) : ``dictionnaire.py`` ne
# doit jamais importer le moteur, pour rester utilisable sans lui. Le moteur,
# lui, peut décrire une correspondance vers des clés de palier sans en
# importer la définition : ces mêmes clés sont utilisées, côté appelant
# (``scrabble.ui.accueil``, qui importe déjà les deux modules), pour indexer
# :data:`scrabble.dictionnaire.dictionnaire.FICHIERS_VOCABULAIRE_PALIER` et
# :data:`~scrabble.dictionnaire.dictionnaire.FICHIERS_CACHE_IA_PALIER` — une
# correspondance de test (``test_moteur_ia.py``) vérifie qu'elles restent en
# phase.
#
# :data:`Niveau.EXPERT` et :data:`Niveau.CHAMPION_DU_MONDE` n'ont
# volontairement aucune entrée (issue #401) : ils ne se résolvent vers aucun
# palier restreint mais vers le Trie complet
# (:func:`~scrabble.dictionnaire.dictionnaire.obtenir_trie`, ODS8 sans
# filtre) — voir :func:`resoudre_palier`.
_PALIERS_PAR_NIVEAU: dict[Niveau, str] = {
    Niveau.DEBUTANT: "debutant",
    Niveau.FACILE: "facile",
    Niveau.INTERMEDIAIRE: "intermediaire",
    Niveau.AVANCE: "avance",
}


def resoudre_palier(niveau: Niveau) -> str | None:
    """Résout un :class:`Niveau` vers sa clé de palier de vocabulaire IA.

    Renvoie la clé de palier (``"debutant"``, ``"facile"``… voir
    :data:`_PALIERS_PAR_NIVEAU`) pour les quatre niveaux filtrés, et ``None``
    pour :data:`Niveau.EXPERT` et :data:`Niveau.CHAMPION_DU_MONDE` (issue
    #401) : ces deux niveaux ne sont câblés sur aucun fichier de vocabulaire
    restreint, l'appelant doit se rabattre sur le Trie complet
    (``obtenir_trie()``) plutôt que sur ``obtenir_trie_ia(palier=...)``.
    """
    return _PALIERS_PAR_NIVEAU.get(niveau)


#: Malus (négatif) appliqué au score de tri d'un coup posant peu de lettres
#: (``nb_nouvelles <= 2``), doublé si une seule lettre est posée (« hook
#: pur »). Croissant en valeur absolue avec le niveau : un niveau fort doit
#: éviter les hooks encore plus nettement qu'un niveau faible (issue #359).
#: Valeurs inchangées par la refonte de l'échelle (issue #401) : indexées
#: par membre de :class:`Niveau` (ordre inchangé), elles restent monotones
#: avec la force de chaque niveau indépendamment de la stratégie de
#: sélection qui lui est associée. EXPERT (nouveau niveau) hérite donc des
#: valeurs de l'ancien EXPERT (-25).
_MALUS_LONGUEUR: dict[Niveau, int] = {
    Niveau.DEBUTANT: -5,
    Niveau.FACILE: -8,
    Niveau.INTERMEDIAIRE: -12,
    Niveau.AVANCE: -18,
    Niveau.EXPERT: -25,
    Niveau.CHAMPION_DU_MONDE: -25,
}

#: Bonus (positif) appliqué au score de tri d'un coup exploitant au moins
#: une case premium (mot ou lettre compte double/triple). Croissant avec le
#: niveau (issue #359). Valeurs inchangées par la refonte de l'échelle
#: (issue #401), pour la même raison que :data:`_MALUS_LONGUEUR` : EXPERT
#: (nouveau niveau) hérite des valeurs de l'ancien EXPERT (20).
_BONUS_PREMIUM: dict[Niveau, int] = {
    Niveau.DEBUTANT: 3,
    Niveau.FACILE: 5,
    Niveau.INTERMEDIAIRE: 8,
    Niveau.AVANCE: 12,
    Niveau.EXPERT: 20,
    Niveau.CHAMPION_DU_MONDE: 20,
}

#: Cases dont le bonus porte sur le mot entier (plus précieuses que les
#: cases à bonus de lettre seule) : reçoivent le plein bonus premium, contre
#: la moitié pour LETTRE_DOUBLE/LETTRE_TRIPLE.
_CASES_BONUS_MOT = frozenset({TypeCase.MOT_DOUBLE, TypeCase.MOT_TRIPLE, TypeCase.CENTRE})

#: Seuil (en nombre de lettres nouvellement posées) en-deçà duquel la
#: pénalité longueur s'applique.
_SEUIL_PENALITE_LONGUEUR = 2

#: Valeur heuristique de chaque lettre pour le calcul du reliquat (leave
#: value, issue #395). Reflète la difficulté de placement future : le
#: joker et le S (formation de pluriels/hooks) valent le plus cher, les
#: lettres rares (Q/K/W/X/Z) le moins. Une lettre absente vaut 0.0
#: (utilisé via ``.get()``, jamais levé en KeyError).
_VALEURS_LEAVE: dict[str, float] = {
    JOKER: 24.0,
    # Voyelles
    "E": 5.0,
    "A": 4.0,
    "I": 3.5,
    "O": 3.0,
    "U": 2.0,
    # Consonnes fortes
    "S": 9.0,
    "R": 5.5,
    "N": 4.5,
    "T": 4.0,
    "L": 3.5,
    # Consonnes moyennes
    "D": 3.0,
    "M": 3.0,
    "P": 2.5,
    "C": 2.5,
    "B": 2.0,
    "F": 2.0,
    "G": 2.0,
    "H": 2.0,
    "V": 2.0,
    # Consonnes faibles
    "J": 1.0,
    "Y": 1.5,
    "Q": 0.5,
    "K": 0.5,
    "W": 0.5,
    "X": 0.5,
    "Z": 0.5,
}

#: Voyelles comptées pour l'ajustement d'équilibre de :func:`leave_value`.
_VOYELLES_LEAVE = frozenset("AEIOU")

#: Poids d'intégration de la leave value dans :func:`_score_strategique`,
#: par niveau (issue #395). Nul pour DEBUTANT/FACILE : ces niveaux
#: n'anticipent pas la qualité du reliquat, cohérent avec leur tirage très
#: large. Croissant avec le niveau, plafonné à 1.0 (poids plein) à partir
#: d'EXPERT. Valeurs inchangées par la refonte de l'échelle (issue #401),
#: pour la même raison que :data:`_MALUS_LONGUEUR` : indexées par membre de
#: :class:`Niveau` (ordre inchangé), elles restent monotones avec la force
#: de chaque niveau.
_POIDS_LEAVE: dict[Niveau, float] = {
    Niveau.DEBUTANT: 0.0,
    Niveau.FACILE: 0.0,
    Niveau.INTERMEDIAIRE: 0.3,
    Niveau.AVANCE: 0.6,
    Niveau.EXPERT: 1.0,
    Niveau.CHAMPION_DU_MONDE: 1.0,
}


def leave_value(lettres: Sequence[str]) -> float:
    """Valeur heuristique du reliquat (lettres restant au chevalet après un coup).

    Combine la somme des valeurs individuelles (:data:`_VALEURS_LEAVE`) avec
    un ajustement d'équilibre voyelles/consonnes : bonus (+4.0) si le
    reliquat compte 2 à 4 voyelles (mélange jouable), malus (-4.0) s'il en
    compte 0-1 (pas de quoi combiner) ou 5 et plus (engorgement). Renvoie
    0.0 pour un reliquat vide (aucun ajustement d'équilibre appliqué).
    """
    if not lettres:
        return 0.0

    total = sum(_VALEURS_LEAVE.get(lettre, 0.0) for lettre in lettres)
    nb_voyelles = sum(1 for lettre in lettres if lettre in _VOYELLES_LEAVE)
    if nb_voyelles in (2, 3, 4):
        total += 4.0
    else:
        total -= 4.0
    return total


def _score_strategique(
    cn: CoupNote, niveau: Niveau, lettres_restantes: Sequence[str] = ()
) -> int:
    """Score ajusté servant UNIQUEMENT au tri des coups par niveau IA.

    N'affecte pas :attr:`CoupNote.score` (score réel affiché/marqué) : c'est
    une clé de tri parallèle qui corrige deux biais du tri glouton sur score
    brut (issue #359) :

    * pénalise les coups posant peu de lettres (``nb_nouvelles <= 2``), en
      particulier les « hooks » purs (une seule lettre posée, malus doublé) ;
    * valorise les coups exploitant une case premium, même à score brut
      légèrement inférieur à un hook.

    Les deux ajustements sont proportionnels au niveau : un niveau fort doit
    éviter les hooks et viser les cases premium plus nettement qu'un niveau
    faible, cohérent avec l'idée qu'un débutant humain *essaie* de faire de
    vrais mots — c'est la qualité de sa recherche qui est faible, pas son
    style de jeu.

    Un troisième ajustement, optionnel, prend en compte ``lettres_restantes``
    (le reliquat au chevalet après ce coup) : sa valeur heuristique
    (:func:`leave_value`) est ajoutée au score, pondérée par
    :data:`_POIDS_LEAVE` selon le niveau (nulle pour DEBUTANT/FACILE — ces
    niveaux restent inchangés) et arrondie à l'entier pour rester cohérente
    avec le type de retour ``int`` (issue #395).
    """
    ajustement = 0

    if cn.nb_nouvelles <= _SEUIL_PENALITE_LONGUEUR:
        malus = _MALUS_LONGUEUR[niveau]
        if cn.nb_nouvelles == 1:
            malus *= 2
        ajustement += malus

    if any(mot.cases_bonus for mot in cn.detail.mots):
        bonus = _BONUS_PREMIUM[niveau]
        types_case = {
            type_case
            for mot in cn.detail.mots
            for (_, _, type_case) in mot.cases_bonus
        }
        if not types_case & _CASES_BONUS_MOT:
            bonus //= 2
        ajustement += bonus

    if _POIDS_LEAVE[niveau] > 0.0:
        ajustement += round(_POIDS_LEAVE[niveau] * leave_value(lettres_restantes))

    return cn.score + ajustement


def choisir_coup(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: "TrieProtocol",
    niveau: Niveau,
    alea: random.Random | None = None,
) -> Coup | None:
    """Choisit un coup selon le niveau IA, ou None pour passer.

    Le tri par score stratégique (:func:`_score_strategique`) est fait en
    deux passes : une première passe sans reliquat, puis une seconde qui
    calcule, pour chaque coup, les lettres restant au chevalet une fois ce
    coup joué (chevalet moins :attr:`~scrabble.moteur.generateur.CoupNote.lettres_du_chevalet`)
    et relance le tri avec ce score enrichi de la leave value (issue #395).
    Le reliquat dépendant de chaque coup individuellement, il ne peut pas
    être calculé une fois pour toute la liste — d'où la lambda qui le
    recalcule à la volée pour chaque comparaison.

    Args:
        plateau: État courant du plateau de jeu.
        chevalet: Jetons disponibles pour le joueur IA.
        dictionnaire: Trie du dictionnaire.
        niveau: Stratégie de sélection à appliquer.
        alea: Générateur aléatoire optionnel pour reproductibilité.

    Returns:
        Le coup choisi, ou None si aucun coup n'est jouable (le joueur passe).
    """
    coups = generer_coups(plateau, chevalet, dictionnaire)
    if not coups:
        return None

    rng = alea if alea is not None else random.Random()

    coups = sorted(coups, key=lambda cn: _score_strategique(cn, niveau), reverse=True)

    def _lettres_restantes(cn: CoupNote) -> list[str]:
        restantes = list(chevalet)
        for lettre in cn.lettres_du_chevalet:
            restantes.remove(lettre)
        return restantes

    coups = sorted(
        coups,
        key=lambda cn: _score_strategique(cn, niveau, _lettres_restantes(cn)),
        reverse=True,
    )

    if niveau in (Niveau.AVANCE, Niveau.CHAMPION_DU_MONDE):
        return _choisir_avance(coups, rng)
    if niveau == Niveau.EXPERT:
        return _choisir_top5(coups, rng)
    if niveau == Niveau.INTERMEDIAIRE:
        return _choisir_intermediaire(coups, rng)
    if niveau == Niveau.FACILE:
        return _choisir_facile(coups, rng)
    return _choisir_debutant(coups, rng)


def _choisir_avance(coups: list[CoupNote], rng: random.Random) -> Coup:
    """AVANCE et CHAMPION_DU_MONDE : meilleur coup, aléatoire en cas d'égalité.

    Les deux niveaux partagent exactement la même stratégie de sélection et
    les mêmes tranches de malus/bonus (:data:`_MALUS_LONGUEUR`,
    :data:`_BONUS_PREMIUM`) : seul le vocabulaire reçu en paramètre les
    distingue, câblé par l'appelant (issue #369, lot C, voir
    :func:`resoudre_palier`) — AVANCE sur le palier ``"avance"``,
    CHAMPION_DU_MONDE sur le Trie complet ODS8. Reprend la stratégie de
    l'ancien EXPERT (issue #401).
    """
    meilleur_score = coups[0].score
    meilleurs = [cn for cn in coups if cn.score == meilleur_score]
    return rng.choice(meilleurs).coup


def _choisir_top5(coups: list[CoupNote], rng: random.Random) -> Coup:
    """EXPERT : aléatoire parmi les 5 % meilleurs coups (top 5 %).

    Nouveau niveau (issue #401), intercalaire entre AVANCE (meilleur coup,
    vocabulaire restreint) et CHAMPION_DU_MONDE (meilleur coup, vocabulaire
    complet). Généré et joué sur le Trie complet ODS8 (pas de palier de
    vocabulaire restreint, voir :func:`resoudre_palier`). ``max(1, ...)``
    garantit un sous-ensemble non vide (repli sur le seul meilleur coup pour
    les listes très courtes), comme les autres niveaux.
    """
    taille_haut = max(1, len(coups) * 5 // 100)
    return rng.choice(coups[:taille_haut]).coup


def _choisir_intermediaire(coups: list[CoupNote], rng: random.Random) -> Coup:
    """INTERMEDIAIRE : aléatoire parmi les 15 % meilleurs coups (top 15 %).

    Reprend la stratégie de sélection de l'ancien AVANCE (issue #401).
    ``max(1, ...)`` garantit un sous-ensemble non vide (repli sur le seul
    meilleur coup pour les listes très courtes), comme les autres niveaux.
    """
    taille_haut = max(1, len(coups) * 15 // 100)
    return rng.choice(coups[:taille_haut]).coup


def _choisir_facile(coups: list[CoupNote], rng: random.Random) -> Coup:
    """FACILE : aléatoire parmi le meilleur tiers des coups (top 33 %).

    Reprend la stratégie de sélection de l'ancien INTERMEDIAIRE (issue #401).
    ``max(1, ...)`` garantit un sous-ensemble non vide (repli sur le seul
    meilleur coup pour les listes très courtes), comme les autres niveaux.
    """
    taille_tiers = max(1, len(coups) // 3)
    return rng.choice(coups[:taille_tiers]).coup


def _choisir_debutant(coups: list[CoupNote], rng: random.Random) -> Coup:
    """DEBUTANT : aléatoire parmi les 70 % meilleurs coups (top 70 %).

    Fusionne les anciens DEBUTANT (top 85 %) et FACILE (top 60 %) en un seul
    niveau d'entrée de gamme (issue #401) : seuls les 30 % de coups les plus
    faibles au sens du score stratégique sont écartés (le malus longueur y
    relègue les hooks les plus pauvres), ce qui laisse ce niveau très proche
    d'un tirage au hasard tout en garantissant qu'il reste le niveau le plus
    faible et strictement sous FACILE (top 33 %, sous-ensemble strictement
    meilleur). ``max(1, ...)`` garantit un sous-ensemble non vide, comme les
    autres niveaux.
    """
    taille_haut = max(1, len(coups) * 70 // 100)
    return rng.choice(coups[:taille_haut]).coup
