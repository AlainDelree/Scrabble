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

Tirage pondéré dans la tranche (issue #451, lot H ter ; généralisé issue
#452, lot J)
--------------------------------------------------------------------------
Pour DEBUTANT, FACILE, INTERMEDIAIRE et EXPERT (les niveaux qui tirent au
hasard dans une tranche de meilleurs coups), :attr:`ProfilPersonnage.poids_tirage_scrabble`
permet à un personnage de donner plus de poids, dans ce tirage, aux coups
de la tranche qui posent les 7 lettres du chevalet — voir
:func:`_tirer_dans_tranche`. Sans effet sur AVANCE et CHAMPION_DU_MONDE
(meilleur coup, jamais un tirage dans une tranche). Neutre par défaut : la
COMPOSITION de la tranche ne change jamais, et un profil qui ne renseigne
pas ce champ consomme le générateur aléatoire de façon rigoureusement
identique à avant son introduction.

:attr:`ProfilPersonnage.poids_tirage_favori` (issue #452, lot J) reprend ce
même mécanisme pour les coups dont le mot principal est un mot favori du
personnage (:attr:`ProfilPersonnage.mots_favoris`), avec une différence : ces
coups sont ajoutés au pool de tirage même s'ils sont absents de la tranche
elle-même (voir :func:`_tirer_dans_tranche`) — un mot favori peu rémunérateur
pourrait sinon en être exclu d'office, en particulier à DEBUTANT.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from scrabble.dictionnaire.dictionnaire import Trie
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

#: Nombre de lettres nouvellement posées à partir duquel un coup pose les 7
#: lettres du chevalet (« scrabble ») — déclenche le bonus optionnel
#: :attr:`ProfilPersonnage.bonus_scrabble` (issue #448, lot H). Un chevalet
#: compte toujours 7 lettres en jeu normal (fin de sac exceptée).
_SEUIL_BONUS_SCRABBLE = 7

#: Longueur minimale du **mot principal** (toutes les lettres du mot formé
#: dans la direction du coup, déjà posées comprises — ``len(coup.tuiles)``,
#: PAS :attr:`~scrabble.moteur.generateur.CoupNote.nb_nouvelles`, qui ne
#: compte que les lettres nouvellement posées) à partir de laquelle le style
#: « vocabulaire long » (:attr:`ProfilPersonnage.vocabulaire_long`, issue
#: #450, lot H bis) élargit les coups candidats au lexique complet — voir
#: :func:`_generer_coups_candidats`. Distincte de :data:`_SEUIL_BONUS_SCRABBLE`
#: (même valeur, mais un critère différent : celui-ci porte sur la longueur
#: du mot posé, pas sur le nombre de lettres prises au chevalet) : les deux
#: constantes pourront diverger si la mesure le justifie.
_SEUIL_VOCABULAIRE_LONG = 7


def _mot_connu_vocabulaire_long(mot: str, part_vocabulaire_long: float) -> bool:
    """Le mot ``mot`` fait-il partie de la fraction ``part_vocabulaire_long``
    des mots longs connus (:attr:`ProfilPersonnage.part_vocabulaire_long`,
    issue #451, lot H ter) ?

    Déterministe et propre à ``mot`` : repose sur un hachage stable
    (SHA-256) de son texte, PAS sur le ``hash()`` intégré de Python
    (randomisé d'un processus à l'autre via ``PYTHONHASHSEED``, sauf à le
    désactiver explicitement — un piège à éviter plutôt qu'à contourner). Un
    même mot est donc toujours connu ou toujours inconnu, quelle que soit la
    graine de la partie ou l'ordre dans lequel les coups sont générés.
    """
    empreinte = hashlib.sha256(mot.encode("utf-8")).digest()
    valeur = int.from_bytes(empreinte[:8], "big") / 2**64
    return valeur < part_vocabulaire_long


def _mot_connu_vocabulaire_court(mot: str, part_vocabulaire_court: float) -> bool:
    """Le mot ``mot`` fait-il partie de la fraction ``part_vocabulaire_court``
    des mots courts connus (:attr:`ProfilPersonnage.part_vocabulaire_court`,
    issue #453, lot H quater) ?

    Même procédé que :func:`_mot_connu_vocabulaire_long` (hachage SHA-256
    stable du texte du mot, déterministe et indépendant de la graine de la
    partie), avec un **décalage distinct** (préfixe ``b"court:"`` ajouté avant
    hachage) : pour un même mot, le résultat de cette fonction et celui de
    :func:`_mot_connu_vocabulaire_long` sont statistiquement indépendants —
    condition explicite de l'issue #453, nécessaire puisqu'un personnage
    pourrait un jour vouloir combiner les deux critères sans qu'ils ne se
    corrèlent artificiellement.
    """
    empreinte = hashlib.sha256(b"court:" + mot.encode("utf-8")).digest()
    valeur = int.from_bytes(empreinte[:8], "big") / 2**64
    return valeur < part_vocabulaire_court

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


@dataclass(frozen=True)
class ProfilPersonnage:
    """Surcharges optionnelles de réglages stratégiques (issue #438, lot A).

    Pure couche additive par-dessus les réglages indexés par :class:`Niveau`
    (:data:`_MALUS_LONGUEUR`, :data:`_BONUS_PREMIUM`, :data:`_POIDS_LEAVE`),
    jamais une redéfinition de ces dicts : un profil absent (``None``) ou dont
    tous les champs valent ``None`` (valeur par défaut) donne un comportement
    identique bit à bit à l'absence de profil — c'est le personnage
    « Classique ». Chaque champ non ``None`` remplace, pour ce coup, la valeur
    indexée par niveau qu'il surcharge. Lots suivants : nouveaux champs pour
    les personnages dont le style demande un calcul inédit (bonus bingo,
    rareté, risque premium…).

    ``bonus_scrabble`` (issue #448, lot H) diffère des trois champs
    précédents : il n'existe aucun réglage de production indexé par niveau à
    surcharger — neutre par défaut (``None``, traité comme 0 quel que soit le
    niveau), il n'a d'effet que si un personnage le renseigne explicitement.
    Ajouté au score stratégique uniquement pour les coups posant les 7
    lettres du chevalet (:data:`_SEUIL_BONUS_SCRABBLE`).

    ``vocabulaire_long`` (issue #450, lot H bis) diffère des quatre champs
    précédents : il n'agit pas sur le score stratégique mais sur l'ENSEMBLE
    des coups candidats proposés au tri (voir :func:`_generer_coups_candidats`).
    Neutre par défaut (``None``/``False`` : ensemble de coups inchangé, celui
    du vocabulaire du niveau). Quand il vaut ``True`` **et** qu'un
    ``dictionnaire_complet`` est fourni à :func:`choisir_coup`/
    :func:`evaluer_coups`, l'ensemble de coups candidats est élargi aux coups
    dont le mot principal compte au moins :data:`_SEUIL_VOCABULAIRE_LONG`
    lettres, générés et validés avec ce dictionnaire complet plutôt qu'avec
    le vocabulaire du niveau.

    ``poids_tirage_scrabble`` (issue #451, lot H ter) n'agit ni sur le score
    stratégique ni sur l'ensemble des coups candidats, mais sur le TIRAGE
    final fait par les niveaux qui choisissent au hasard dans une tranche de
    meilleurs coups (DEBUTANT, FACILE, INTERMEDIAIRE, EXPERT — voir
    :func:`_tirer_dans_tranche`). Neutre par défaut (``None`` : tirage
    uniforme dans la tranche, comportement identique à avant l'introduction
    de ce champ, y compris la consommation du générateur aléatoire). Quand il
    est renseigné (valeur > 1), les coups de la tranche qui posent les 7
    lettres du chevalet (:data:`_SEUIL_BONUS_SCRABBLE`) reçoivent ce poids
    dans le tirage pondéré, les autres coups de la tranche gardant le poids
    1 — la COMPOSITION de la tranche (laquelle est calculée en amont par
    :func:`_trier_par_score_strategique`) ne change pas, seules les
    probabilités de tirage à l'intérieur changent. Sans effet sur AVANCE et
    CHAMPION_DU_MONDE (meilleur coup, jamais un tirage dans une tranche).

    ``part_vocabulaire_long`` (issue #451, lot H ter) affine
    ``vocabulaire_long`` : parmi les mots de 7 lettres et plus du lexique
    complet qui élargissent les coups candidats (ceux-là seuls — jamais les
    mots courts, ni les mots déjà dans le vocabulaire du niveau), seule cette
    fraction reste accessible (voir :func:`_mot_connu_vocabulaire_long` et
    :func:`_generer_coups_candidats`). Neutre par défaut (``None``, traité
    comme 1.0 : tous les mots longs du lexique complet restent accessibles,
    comportement identique à celui du lot H bis). La sélection des mots
    connus est déterministe et propre à chaque mot (hachage stable de son
    texte, PAS le ``hash()`` intégré de Python, aléatoire d'un processus à
    l'autre) : indépendante de la graine de la partie et de l'ordre de
    génération des coups.

    ``mots_favoris`` (issue #452, lot J) généralise ``vocabulaire_long`` à un
    critère de LISTE plutôt que de longueur : l'ensemble des coups candidats
    est élargi aux coups dont le **mot principal** figure dans cette liste
    (mots déjà normalisés — majuscules, désaccentués —, voir
    :func:`scrabble.moteur.personnages.charger_mots_favoris`), générés avec un
    petit Trie construit depuis la liste (:func:`_generer_coups_candidats`)
    et VALIDÉS (mot principal et mots croisés) avec ``dictionnaire_complet``,
    exactement comme ``vocabulaire_long``. Un mot de la liste absent du
    lexique complet ne produit simplement aucun coup validé — ignoré sans
    erreur, sans filtrage dédié. Neutre par défaut (``None`` : ensemble de
    coups inchangé).

    ``poids_tirage_favori`` (issue #452, lot J) généralise
    ``poids_tirage_scrabble`` à ce même critère de liste : dans le tirage
    pondéré des niveaux qui tirent au hasard dans une tranche de meilleurs
    coups (voir :func:`_tirer_dans_tranche`), les coups dont le mot principal
    est un mot favori reçoivent ce poids — ajoutés au tirage même s'ils ne
    font pas partie de la tranche (différence avec ``poids_tirage_scrabble``,
    qui ne pondère qu'À L'INTÉRIEUR de la tranche déjà calculée) : un mot
    favori peu rémunérateur, plausible pour ce style de personnage, pourrait
    sinon en être exclu d'office. Neutre par défaut (``None`` : tirage
    inchangé, y compris la consommation du générateur aléatoire).

    ``part_vocabulaire_court`` (issue #453, lot H quater) va dans le sens
    inverse de ``part_vocabulaire_long`` : au lieu d'ÉLARGIR les coups
    candidats, elle RESTREINT l'ensemble déjà constitué (vocabulaire du
    niveau, plus l'éventuel élargissement ``vocabulaire_long``/``mots_favoris``
    ci-dessus) aux coups dont le mot principal compte MOINS de
    :data:`_SEUIL_VOCABULAIRE_LONG` lettres : ceux-là ne restent candidats
    que si ce mot est « connu » selon :func:`_mot_connu_vocabulaire_court` —
    même procédé déterministe que ``part_vocabulaire_long``, avec un décalage
    de hachage distinct pour que les deux sélections soient indépendantes.
    Les mots de :data:`_SEUIL_VOCABULAIRE_LONG` lettres ou plus ne sont
    JAMAIS filtrés par ce champ, qu'ils viennent du vocabulaire du niveau ou
    d'un élargissement ``vocabulaire_long``. Neutre par défaut (``None``,
    traité comme 1.0 : aucun mot court filtré, comportement identique à avant
    l'introduction de ce champ). Garde-fou (voir :func:`_generer_coups_candidats`) :
    si le filtre ne laisse plus aucun coup candidat, il est ignoré pour ce
    tour plutôt que de forcer une passe.
    """

    malus_longueur: int | None = None
    bonus_premium: int | None = None
    poids_leave: float | None = None
    bonus_scrabble: int | None = None
    vocabulaire_long: bool | None = None
    poids_tirage_scrabble: float | None = None
    part_vocabulaire_long: float | None = None
    mots_favoris: frozenset[str] | None = None
    poids_tirage_favori: float | None = None
    part_vocabulaire_court: float | None = None


def _score_strategique(
    cn: CoupNote,
    niveau: Niveau,
    lettres_restantes: Sequence[str] = (),
    profil: ProfilPersonnage | None = None,
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

    ``profil`` (issue #438, lot A) permet de surcharger, pour ce coup, les
    trois réglages ci-dessus — chaque champ non ``None`` remplace la valeur
    indexée par ``niveau`` qu'il surcharge, les dicts ``_MALUS_LONGUEUR``/
    ``_BONUS_PREMIUM``/``_POIDS_LEAVE`` restant par ailleurs la seule source
    de vérité du calibrage. ``profil=None`` (ou tous ses champs ``None``,
    défaut) reproduit exactement le calcul d'avant son introduction.

    Un quatrième ajustement, lui aussi optionnel et porté uniquement par
    ``profil`` (:attr:`ProfilPersonnage.bonus_scrabble`, issue #448, lot H) :
    ajoute une constante au score des coups posant les 7 lettres du chevalet
    (:data:`_SEUIL_BONUS_SCRABBLE`). Sans réglage de production à surcharger
    (contrairement aux trois précédents), il vaut 0 par défaut — neutre pour
    tous les niveaux tant qu'aucun personnage ne le renseigne.
    """
    malus_longueur = _MALUS_LONGUEUR[niveau]
    bonus_premium = _BONUS_PREMIUM[niveau]
    poids_leave = _POIDS_LEAVE[niveau]
    bonus_scrabble = 0
    if profil is not None:
        if profil.malus_longueur is not None:
            malus_longueur = profil.malus_longueur
        if profil.bonus_premium is not None:
            bonus_premium = profil.bonus_premium
        if profil.poids_leave is not None:
            poids_leave = profil.poids_leave
        if profil.bonus_scrabble is not None:
            bonus_scrabble = profil.bonus_scrabble

    ajustement = 0

    if cn.nb_nouvelles <= _SEUIL_PENALITE_LONGUEUR:
        malus = malus_longueur
        if cn.nb_nouvelles == 1:
            malus *= 2
        ajustement += malus

    if any(mot.cases_bonus for mot in cn.detail.mots):
        bonus = bonus_premium
        types_case = {
            type_case
            for mot in cn.detail.mots
            for (_, _, type_case) in mot.cases_bonus
        }
        if not types_case & _CASES_BONUS_MOT:
            bonus //= 2
        ajustement += bonus

    if poids_leave > 0.0:
        ajustement += round(poids_leave * leave_value(lettres_restantes))

    if cn.nb_nouvelles == _SEUIL_BONUS_SCRABBLE:
        ajustement += bonus_scrabble

    return cn.score + ajustement


def _trier_par_score_strategique(
    coups: list[CoupNote],
    niveau: Niveau,
    chevalet: Sequence[str],
    profil: ProfilPersonnage | None,
) -> list[tuple[CoupNote, int]]:
    """Trie ``coups`` par score stratégique décroissant (leave value incluse).

    Fonction pure, sans aléa : factorise le tri en deux passes (sans puis avec
    reliquat, issue #395) utilisé à la fois par la sélection réelle
    (:func:`choisir_coup`) et par l'évaluation a posteriori du journal de
    décision (:func:`evaluer_coups`, issue #445) — les deux appels restent
    ainsi trivialement en phase, sans dupliquer la logique de tri.

    Renvoie la liste triée de paires ``(coup, score_stratégique)``.
    """
    coups = sorted(
        coups,
        key=lambda cn: _score_strategique(cn, niveau, profil=profil),
        reverse=True,
    )

    def _lettres_restantes(cn: CoupNote) -> list[str]:
        restantes = list(chevalet)
        for lettre in cn.lettres_du_chevalet:
            restantes.remove(lettre)
        return restantes

    coups = sorted(
        coups,
        key=lambda cn: _score_strategique(
            cn, niveau, _lettres_restantes(cn), profil=profil
        ),
        reverse=True,
    )
    return [
        (cn, _score_strategique(cn, niveau, _lettres_restantes(cn), profil=profil))
        for cn in coups
    ]


def _mot_principal(coup: Coup) -> str:
    """Le mot principal d'un coup : toutes ses tuiles, lettres déjà posées comprises."""
    return "".join(tuile.lettre for tuile in coup.tuiles)


def _generer_coups_candidats(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: "TrieProtocol",
    profil: ProfilPersonnage | None,
    dictionnaire_complet: "TrieProtocol | None",
) -> list[CoupNote]:
    """Génère les coups candidats, élargis ou restreints selon le profil.

    Sans ``profil`` (ou tous ses champs concernés à ``None``/``False``, cas
    par défaut) ou sans ``dictionnaire_complet`` (pour les champs qui en ont
    besoin), renvoie exactement ``generer_coups(plateau, chevalet, dictionnaire)``
    — comportement identique, bit à bit, à avant l'introduction du champ
    ``vocabulaire_long`` (issue #450, lot H bis) : condition de neutralité du
    profil vide.

    Avec ``vocabulaire_long`` actif et un ``dictionnaire_complet`` fourni,
    l'ensemble renvoyé est l'UNION, sans doublon, de ces coups habituels
    (vocabulaire du niveau, via ``dictionnaire``) et des coups dont le **mot
    principal** (:func:`_mot_principal`, ``len(coup.tuiles)``, PAS
    ``nb_nouvelles``) compte au moins :data:`_SEUIL_VOCABULAIRE_LONG` lettres,
    générés avec ``dictionnaire_complet``. Cette seconde génération élague ET
    valide (mot principal et mots croisés) avec ``dictionnaire_complet`` —
    :func:`~scrabble.moteur.generateur.generer_coups` appelle
    :func:`~scrabble.moteur.validation.coup_valide` avec le même Trie que
    celui reçu pour l'exploration, donc tous les mots formés par ces coups
    longs (principal et transversaux) sont bien validés avec le lexique
    complet, sans logique de validation supplémentaire à écrire. Le doublon
    (même case de départ, direction et mot) entre les deux générations n'est
    conservé qu'une fois.

    ``profil.part_vocabulaire_long`` (issue #451, lot H ter) restreint cet
    élargissement : quand il est renseigné et inférieur à 1.0, seule cette
    fraction des mots longs **hors vocabulaire du niveau** (ceux qui ne
    figurent pas déjà dans ``coups``, donc exactement ceux que cette seconde
    génération ajoute réellement) reste accessible — voir
    :func:`_mot_connu_vocabulaire_long`. ``None`` (défaut) ou 1.0 laisse tous
    ces mots accessibles, comportement identique à celui du lot H bis.

    ``profil.mots_favoris`` (issue #452, lot J) élargit pareillement les
    coups candidats, selon un critère de LISTE plutôt que de longueur : un
    petit Trie est construit depuis cette liste (:func:`Trie.depuis_iterable`)
    et utilisé pour EXPLORER (seuls les mots de la liste peuvent être
    trouvés), tandis que ``dictionnaire_complet`` sert à VALIDER (mot
    principal ET mots croisés) — voir le second paramètre de
    :func:`generer_coups`. Un mot de la liste absent du lexique complet ne
    produit ainsi simplement aucun coup validé (ignoré sans erreur, sans
    filtrage dédié). Les deux élargissements (``vocabulaire_long`` et
    ``mots_favoris``) sont indépendants et se combinent sans doublon (même
    ensemble ``vus`` que l'élargissement par longueur).

    ``profil.part_vocabulaire_court`` (issue #453, lot H quater) agit en
    dernier, APRÈS les deux élargissements ci-dessus, et dans le sens
    inverse : elle RESTREINT l'ensemble des coups déjà réunis à une fraction
    des mots dont le mot principal compte MOINS de
    :data:`_SEUIL_VOCABULAIRE_LONG` lettres, selon
    :func:`_mot_connu_vocabulaire_court` — les mots de
    :data:`_SEUIL_VOCABULAIRE_LONG` lettres ou plus (vocabulaire du niveau ou
    ajoutés par ``vocabulaire_long``) ne sont jamais concernés. N'a besoin ni
    de ``vocabulaire_long``/``mots_favoris`` actifs ni de
    ``dictionnaire_complet`` fourni : un profil qui ne renseigne QUE ce champ
    filtre déjà l'ensemble issu du seul ``dictionnaire`` (vocabulaire du
    niveau). Garde-fou : si le filtre ne laisse plus aucun coup candidat
    (début de partie, chevalet difficile), il est ignoré pour ce tour — mieux
    vaut un tour sans filtre qu'une passe forcée qui fausserait la mesure de
    force du personnage. ``None`` (défaut) ou 1.0 ne filtre rien, comportement
    identique à avant l'introduction de ce champ, y compris sans aucune
    consommation du générateur aléatoire (calcul purement déterministe).
    """
    coups = generer_coups(plateau, chevalet, dictionnaire)
    if profil is None:
        return coups

    if dictionnaire_complet is not None and (profil.vocabulaire_long or profil.mots_favoris):

        def _cle(cn: CoupNote) -> tuple[int, int, str, str]:
            return (
                cn.coup.ligne,
                cn.coup.colonne,
                cn.coup.direction.value,
                _mot_principal(cn.coup),
            )

        vus = {_cle(cn) for cn in coups}

        if profil.vocabulaire_long:
            part_vocabulaire_long = profil.part_vocabulaire_long
            for cn in generer_coups(plateau, chevalet, dictionnaire_complet):
                if len(cn.coup.tuiles) < _SEUIL_VOCABULAIRE_LONG:
                    continue
                cle = _cle(cn)
                if cle in vus:
                    continue
                if part_vocabulaire_long is not None and part_vocabulaire_long < 1.0:
                    if not _mot_connu_vocabulaire_long(_mot_principal(cn.coup), part_vocabulaire_long):
                        continue
                vus.add(cle)
                coups.append(cn)

        if profil.mots_favoris:
            trie_favoris = Trie.depuis_iterable(profil.mots_favoris)
            for cn in generer_coups(plateau, chevalet, trie_favoris, dictionnaire_complet):
                cle = _cle(cn)
                if cle in vus:
                    continue
                vus.add(cle)
                coups.append(cn)

    part_vocabulaire_court = profil.part_vocabulaire_court
    if part_vocabulaire_court is not None and part_vocabulaire_court < 1.0:
        coups_filtres = [
            cn
            for cn in coups
            if len(cn.coup.tuiles) >= _SEUIL_VOCABULAIRE_LONG
            or _mot_connu_vocabulaire_court(_mot_principal(cn.coup), part_vocabulaire_court)
        ]
        if coups_filtres:
            coups = coups_filtres

    return coups


def choisir_coup(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: "TrieProtocol",
    niveau: Niveau,
    alea: random.Random | None = None,
    profil: ProfilPersonnage | None = None,
    dictionnaire_complet: "TrieProtocol | None" = None,
) -> Coup | None:
    """Choisit un coup selon le niveau IA, ou None pour passer.

    Le tri par score stratégique (:func:`_trier_par_score_strategique`) est
    fait en deux passes : une première passe sans reliquat, puis une seconde
    qui calcule, pour chaque coup, les lettres restant au chevalet une fois ce
    coup joué (chevalet moins :attr:`~scrabble.moteur.generateur.CoupNote.lettres_du_chevalet`)
    et relance le tri avec ce score enrichi de la leave value (issue #395).

    Args:
        plateau: État courant du plateau de jeu.
        chevalet: Jetons disponibles pour le joueur IA.
        dictionnaire: Trie du dictionnaire (vocabulaire du niveau).
        niveau: Stratégie de sélection à appliquer.
        alea: Générateur aléatoire optionnel pour reproductibilité.
        profil: Surcharges optionnelles de personnage (issue #438, lot A),
            consultées en plus des réglages indexés par ``niveau``, jamais à
            leur place. ``None`` (défaut) reproduit exactement le
            comportement d'avant son introduction.
        dictionnaire_complet: Trie du lexique complet (issue #450, lot H
            bis), consulté en plus de ``dictionnaire`` uniquement si
            ``profil.vocabulaire_long`` ou ``profil.mots_favoris`` (issue
            #452, lot J) est actif (voir :func:`_generer_coups_candidats`) —
            ignoré sinon, y compris si fourni.

    Returns:
        Le coup choisi, ou None si aucun coup n'est jouable (le joueur passe).
    """
    coups = _generer_coups_candidats(
        plateau, chevalet, dictionnaire, profil, dictionnaire_complet
    )
    if not coups:
        return None

    rng = alea if alea is not None else random.Random()

    coups_tries = [
        cn for cn, _ in _trier_par_score_strategique(coups, niveau, chevalet, profil)
    ]

    if niveau in (Niveau.AVANCE, Niveau.CHAMPION_DU_MONDE):
        return _choisir_avance(coups_tries, rng)
    if niveau == Niveau.EXPERT:
        return _choisir_top5(coups_tries, rng, profil)
    if niveau == Niveau.INTERMEDIAIRE:
        return _choisir_intermediaire(coups_tries, rng, profil)
    if niveau == Niveau.FACILE:
        return _choisir_facile(coups_tries, rng, profil)
    return _choisir_debutant(coups_tries, rng, profil)


@dataclass(frozen=True)
class AlternativeCoup:
    """Un coup alternatif pour le journal de décision IA (issue #445).

    ``direction`` est la valeur de :class:`~scrabble.moteur.plateau_partie.Direction`
    (``"H"``/``"V"``), pas l'enum lui-même, pour rester trivialement
    sérialisable (JSON).
    """

    mot: str
    ligne: int
    colonne: int
    direction: str
    score_reel: int
    score_strategique: int


@dataclass(frozen=True)
class EvaluationCoupsIA:
    """Résultat PUR (sans aléa) de l'évaluation de tous les coups possibles.

    Produit uniquement par :func:`evaluer_coups`, jamais par
    :func:`choisir_coup` — sert uniquement à documenter, après coup, ce que
    l'IA avait comme options (journal de décision, issue #445). Les deux
    fonctions sont indépendantes : appeler ou non ``evaluer_coups`` n'a aucune
    incidence sur ce que ``choisir_coup`` renvoie ni sur sa consommation du
    générateur aléatoire.
    """

    nb_coups_possibles: int = 0
    meilleurs: tuple[AlternativeCoup, ...] = ()
    rang_choisi: int | None = None
    coup_choisi: AlternativeCoup | None = None


def _construire_alternative(cn: CoupNote, score_strategique: int) -> AlternativeCoup:
    mot = "".join(tuile.lettre for tuile in cn.coup.tuiles)
    return AlternativeCoup(
        mot=mot,
        ligne=cn.coup.ligne,
        colonne=cn.coup.colonne,
        direction=cn.coup.direction.value,
        score_reel=cn.score,
        score_strategique=score_strategique,
    )


def evaluer_coups(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: "TrieProtocol",
    niveau: Niveau,
    profil: ProfilPersonnage | None = None,
    coup_choisi: Coup | None = None,
    limite: int = 5,
    dictionnaire_complet: "TrieProtocol | None" = None,
) -> EvaluationCoupsIA:
    """Évalue tous les coups possibles, pour le journal de décision (issue #445).

    Fonction PURE et SANS ALÉA : ne choisit rien, ne consomme aucun générateur
    aléatoire. Destinée à être appelée **en plus** de :func:`choisir_coup`
    (jamais à sa place, jamais avant lui), avec le ``coup`` qu'il a réellement
    renvoyé (``coup_choisi``), pour retrouver son rang parmi les coups générés
    et triés par score stratégique — sans que cet appel supplémentaire
    n'influence en rien la sélection réelle.

    ``dictionnaire_complet`` (issue #450, lot H bis) reprend exactement la
    même règle que dans :func:`choisir_coup` : les coups évalués et les
    cinq alternatives du journal de décision portent sur le MÊME ensemble de
    coups candidats élargi (:func:`_generer_coups_candidats`) que celui
    réellement consulté par :func:`choisir_coup` pour ce tour, à condition de
    lui passer le même ``profil`` et le même ``dictionnaire_complet``.

    Renvoie un :class:`EvaluationCoupsIA` avec, au plus, ``limite`` meilleurs
    coups (:attr:`~EvaluationCoupsIA.meilleurs`) et, si ``coup_choisi`` est
    fourni et figure parmi les coups générés, son rang (1 = meilleur,
    :attr:`~EvaluationCoupsIA.rang_choisi`) et sa fiche
    (:attr:`~EvaluationCoupsIA.coup_choisi`) — même s'il ne fait pas partie du
    top ``limite``. ``coup_choisi=None`` (passe, ou aucun coup généré) laisse
    les deux à leur valeur par défaut.
    """
    coups = _generer_coups_candidats(
        plateau, chevalet, dictionnaire, profil, dictionnaire_complet
    )
    resultat = EvaluationCoupsIA(nb_coups_possibles=len(coups))
    if not coups:
        return resultat

    coups_scores = _trier_par_score_strategique(coups, niveau, chevalet, profil)
    resultat = EvaluationCoupsIA(
        nb_coups_possibles=len(coups_scores),
        meilleurs=tuple(
            _construire_alternative(cn, score) for cn, score in coups_scores[:limite]
        ),
    )
    if coup_choisi is not None:
        for indice, (cn, score) in enumerate(coups_scores):
            if cn.coup == coup_choisi:
                resultat = EvaluationCoupsIA(
                    nb_coups_possibles=resultat.nb_coups_possibles,
                    meilleurs=resultat.meilleurs,
                    rang_choisi=indice + 1,
                    coup_choisi=_construire_alternative(cn, score),
                )
                break
    return resultat


def _tirer_dans_tranche(
    tranche: list[CoupNote],
    rng: random.Random,
    profil: ProfilPersonnage | None,
    coups_complets: list[CoupNote] | None = None,
) -> Coup:
    """Tire un coup dans ``tranche`` (issue #451, lot H ter ; généralisé issue
    #452, lot J).

    Neutralité stricte : sans ``profil``, ou avec ``profil.poids_tirage_scrabble``
    ET ``profil.poids_tirage_favori`` tous deux à ``None`` (défaut), c'est
    exactement ``rng.choice(tranche).coup`` — même appel, même consommation
    du générateur aléatoire qu'avant l'introduction de ces champs, pour TOUS
    les niveaux et TOUS les personnages.

    ``poids_tirage_scrabble`` (issue #451) : une valeur renseignée (> 1)
    pondère, À L'INTÉRIEUR de ``tranche`` seulement, les coups posant les 7
    lettres du chevalet (:data:`_SEUIL_BONUS_SCRABBLE`) — la COMPOSITION de
    ``tranche`` ne change pas, seules les probabilités de tirage à
    l'intérieur changent.

    ``poids_tirage_favori`` (issue #452, lot J) diffère : les coups dont le
    mot principal figure dans ``profil.mots_favoris`` sont ajoutés au pool de
    tirage même s'ils sont absents de ``tranche`` (recherchés dans
    ``coups_complets``, l'ensemble COMPLET des coups candidats triés,
    toujours un sur-ensemble de ``tranche`` — fourni par l'appelant). Un mot
    favori qui n'aurait pas suffi à entrer dans la tranche des meilleurs
    coups reste ainsi tirable, avec ce poids. Si un coup cumule les deux
    critères (scrabble ET mot favori), le plus grand des deux poids
    s'applique. ``coups_complets=None`` (défaut) désactive cet ajout, quel
    que soit ``poids_tirage_favori`` — utilisé par les appelants qui ne
    connaissent pas encore l'ensemble complet.
    """
    poids_tirage_scrabble = profil.poids_tirage_scrabble if profil is not None else None
    poids_tirage_favori = profil.poids_tirage_favori if profil is not None else None
    mots_favoris = profil.mots_favoris if profil is not None else None
    # ``poids_tirage_favori`` sans ``mots_favoris`` (ou l'inverse) ne qualifie
    # aucun coup : neutre, au même titre que l'absence des deux — condition
    # nécessaire pour retomber sur ``rng.choice`` (pas ``rng.choices`` à poids
    # uniformes, qui consommerait le générateur différemment) dans ce cas.
    favori_actif = poids_tirage_favori is not None and bool(mots_favoris)

    if poids_tirage_scrabble is None and not favori_actif:
        return rng.choice(tranche).coup

    pool = tranche
    if favori_actif and coups_complets is not None:
        ids_tranche = {id(cn) for cn in tranche}
        extras = [
            cn
            for cn in coups_complets
            if id(cn) not in ids_tranche and _mot_principal(cn.coup) in mots_favoris
        ]
        if extras:
            pool = tranche + extras

    poids = []
    for cn in pool:
        p = 1.0
        if poids_tirage_scrabble is not None and cn.nb_nouvelles == _SEUIL_BONUS_SCRABBLE:
            p = poids_tirage_scrabble
        if favori_actif and _mot_principal(cn.coup) in mots_favoris:
            p = max(p, poids_tirage_favori)
        poids.append(p)
    return rng.choices(pool, weights=poids, k=1)[0].coup


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


def _choisir_top5(
    coups: list[CoupNote], rng: random.Random, profil: ProfilPersonnage | None = None
) -> Coup:
    """EXPERT : aléatoire parmi les 5 % meilleurs coups (top 5 %).

    Nouveau niveau (issue #401), intercalaire entre AVANCE (meilleur coup,
    vocabulaire restreint) et CHAMPION_DU_MONDE (meilleur coup, vocabulaire
    complet). Généré et joué sur le Trie complet ODS8 (pas de palier de
    vocabulaire restreint, voir :func:`resoudre_palier`). ``max(1, ...)``
    garantit un sous-ensemble non vide (repli sur le seul meilleur coup pour
    les listes très courtes), comme les autres niveaux. ``profil`` (issue
    #451, lot H ter) permet un tirage pondéré en faveur des scrabbles dans
    cette tranche — voir :func:`_tirer_dans_tranche`.
    """
    taille_haut = max(1, len(coups) * 5 // 100)
    return _tirer_dans_tranche(coups[:taille_haut], rng, profil, coups)


def _choisir_intermediaire(
    coups: list[CoupNote], rng: random.Random, profil: ProfilPersonnage | None = None
) -> Coup:
    """INTERMEDIAIRE : aléatoire parmi les 15 % meilleurs coups (top 15 %).

    Reprend la stratégie de sélection de l'ancien AVANCE (issue #401).
    ``max(1, ...)`` garantit un sous-ensemble non vide (repli sur le seul
    meilleur coup pour les listes très courtes), comme les autres niveaux.
    ``profil`` (issue #451, lot H ter) permet un tirage pondéré en faveur
    des scrabbles dans cette tranche — voir :func:`_tirer_dans_tranche`.
    """
    taille_haut = max(1, len(coups) * 15 // 100)
    return _tirer_dans_tranche(coups[:taille_haut], rng, profil, coups)


def _choisir_facile(
    coups: list[CoupNote], rng: random.Random, profil: ProfilPersonnage | None = None
) -> Coup:
    """FACILE : aléatoire parmi le meilleur tiers des coups (top 33 %).

    Reprend la stratégie de sélection de l'ancien INTERMEDIAIRE (issue #401).
    ``max(1, ...)`` garantit un sous-ensemble non vide (repli sur le seul
    meilleur coup pour les listes très courtes), comme les autres niveaux.
    ``profil`` (issue #451, lot H ter) permet un tirage pondéré en faveur
    des scrabbles dans cette tranche — voir :func:`_tirer_dans_tranche`.
    """
    taille_tiers = max(1, len(coups) // 3)
    return _tirer_dans_tranche(coups[:taille_tiers], rng, profil, coups)


def _choisir_debutant(
    coups: list[CoupNote], rng: random.Random, profil: ProfilPersonnage | None = None
) -> Coup:
    """DEBUTANT : aléatoire parmi les 70 % meilleurs coups (top 70 %).

    Fusionne les anciens DEBUTANT (top 85 %) et FACILE (top 60 %) en un seul
    niveau d'entrée de gamme (issue #401) : seuls les 30 % de coups les plus
    faibles au sens du score stratégique sont écartés (le malus longueur y
    relègue les hooks les plus pauvres), ce qui laisse ce niveau très proche
    d'un tirage au hasard tout en garantissant qu'il reste le niveau le plus
    faible et strictement sous FACILE (top 33 %, sous-ensemble strictement
    meilleur). ``max(1, ...)`` garantit un sous-ensemble non vide, comme les
    autres niveaux. ``profil`` (issue #451, lot H ter) permet un tirage
    pondéré en faveur des scrabbles dans cette tranche — voir
    :func:`_tirer_dans_tranche`.
    """
    taille_haut = max(1, len(coups) * 70 // 100)
    return _tirer_dans_tranche(coups[:taille_haut], rng, profil, coups)
