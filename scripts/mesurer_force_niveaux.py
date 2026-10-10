#!/usr/bin/env python3
"""Mesure la force relative de deux configurations IA sur des parties complètes (issues #362, #372).

Contexte
--------
``tests/test_moteur_ia.py`` prouve la monotonie des niveaux IA (score moyen par
coup, sur deux positions figées, à graine variable), mais ne dit rien de la
force relative sur une **partie complète** : score cumulé, gestion du chevalet
au fil des tirages, milieu de partie riche en hooks — précisément le contexte
des issues #359/#361. Ce script comble ce manque en faisant s'affronter deux
configurations IA sur ``N`` parties jouées entièrement.

Principe : même partie, pas deux parties séparées
--------------------------------------------------
Les deux IA s'affrontent **dans la même partie** (même sac au départ, même
plateau, même ordre de jeu tiré une seule fois) : c'est le seul moyen d'isoler
l'effet de la stratégie de sélection du bruit du tirage. Deux parties séparées
avec des sacs indépendants mesureraient surtout la chance du tirage, pas la
force de la configuration. Le sac divergera malgré tout **en cours** de partie
(les deux joueurs posent un nombre de lettres différent par tour, donc
repiochent différemment) : c'est attendu — l'égalité des conditions vaut au
départ, pas à chaque tour.

Déterminisme
------------
Chaque partie ``i`` dérive toutes ses sources d'aléa d'une unique graine de
partie ``i`` (:func:`_deriver_graines`) : graine du sac, graine du tirage
d'ordre, et une graine de ``random.Random`` **distincte pour chaque joueur
IA**. Deux exécutions avec les mêmes paramètres (mêmes configurations, même
nombre de parties, même graine de départ) produisent donc **exactement** le
même résultat — condition nécessaire pour comparer deux runs avant/après un
changement de calibrage (``_MALUS_LONGUEUR``, ``_BONUS_PREMIUM``, ``_POIDS_LEAVE``
dans ``moteur/ia.py``), ce que ce script permet désormais **sans éditer le code
de production** (voir « Paramètres surchargeables » ci-dessous).

Ce que la mesure sait faire (issue #372)
----------------------------------------
Chaque camp (A et B) est une **configuration** indépendante, pas seulement un
niveau. Une configuration se compose de :

* un **niveau** (:class:`~scrabble.moteur.ia.Niveau`) — la stratégie de
  sélection (tranche de coups) *et* la tranche de malus/bonus stratégiques ;
* un **vocabulaire** — le Trie sur lequel l'IA génère ses coups. Par défaut il
  suit le niveau (voir ``--vocab`` ci-dessous), mais on peut le **forcer**
  indépendamment (``--vocab-a``/``--vocab-b``) pour séparer l'effet du
  vocabulaire de celui de la stratégie ;
* des **surcharges stratégiques** optionnelles (``--malus-a``/``--bonus-a``/
  ``--poids-leave-a`` et leurs équivalents B) qui remplacent, *le temps de la
  mesure uniquement*, l'entrée de ``_MALUS_LONGUEUR``/``_BONUS_PREMIUM``/
  ``_POIDS_LEAVE`` du niveau considéré. La surcharge est appliquée par un
  gestionnaire de contexte (:func:`_strategie_surchargee`) qui restaure les
  valeurs de production en sortie : **le code de production n'est jamais
  modifié** ;
* un **personnage** optionnel (``--personnage-a``/``--personnage-b``, issue
  #439, lot B) — une clé de
  :data:`scrabble.moteur.personnages.PERSONNAGES` dont le
  ``ProfilPersonnage`` est transmis à
  :func:`~scrabble.moteur.ia.choisir_coup`, la même voie qu'emprunterait un
  futur appelant en production (lot A, issue #438). Se compose sans conflit
  avec les surcharges stratégiques ci-dessus (voir :meth:`ConfigJoueur.profil`).

Vocabulaire par palier
----------------------
Depuis le lot C (#369), chaque niveau du jeu réel génère ses coups sur un Trie
**restreint à son palier de fréquence** — sauf EXPERT et CHAMPION_DU_MONDE, qui
utilisent tous deux l'ODS8 complet (issue #401 : EXPERT a rejoint
CHAMPION_DU_MONDE hors palier restreint). Le mode ``--vocab`` choisit ce que
le script reproduit :

* ``complet`` (défaut, comportement historique #362) : les deux camps génèrent
  sur l'ODS8 complet, quel que soit le niveau. Utile pour isoler l'effet de la
  seule stratégie, à vocabulaire constant ;
* ``palier`` : chaque camp génère sur le palier de son niveau, **comme le jeu
  réel** (via :func:`~scrabble.moteur.ia.resoudre_palier`). C'est la mesure la
  plus proche de l'expérience d'une joueuse humaine.

``--vocab-a``/``--vocab-b`` forcent un vocabulaire précis pour un camp,
indépendamment de son niveau et du mode ``--vocab`` global. Valeurs possibles :
``debutant``, ``facile``, ``intermediaire``, ``avance`` (paliers restreints)
ou ``complet`` (ODS8 entier, issue #401 : plus de palier ``expert`` séparé).
Si le fichier de vocabulaire d'un palier requis est absent, le script s'arrête
avec un message clair, comme il le fait déjà pour l'ODS8.

Comparer deux runs
------------------
Le déterminisme permet de rejouer exactement les mêmes parties. Deux voies pour
comparer sans lire des chiffres à l'œil entre deux consoles :

* **Dans une seule invocation** : opposer directement les deux configurations
  (A vs B). Le résumé affiche l'écart de score moyen A−B, aligné graine par
  graine. C'est la voie recommandée pour la question du malus (voir exemples).
* **Entre deux CSV** : ``--comparer run1.csv run2.csv`` relit deux exports
  produits par ``--csv`` et affiche, par graine commune, l'écart de score et de
  taux de victoire entre les deux runs.

Ce que la mesure établit — et ce qu'elle n'établit pas
-------------------------------------------------------
Établit : le taux de victoire (avec intervalle de confiance à 95 %) et l'écart
de score moyen entre deux configurations, sur des parties complètes.

N'établit PAS : un niveau de confiance absolu sur le pourcentage de victoire
« vrai » (l'IC à 95 % donne une fourchette, pas un point) ; l'expérience d'une
partie IA contre un **humain** (les deux camps mesurés ici sont l'un contre
l'autre) ; le comportement à plus de 2 IA en table (seul le face-à-face à deux
est mesuré).

Indicateurs de style (issue #446)
----------------------------------
Mesurer la force relative de deux configurations (ci-dessus) ne dit rien de
leur **style** de jeu : Opportuniste peut être aussi fort que Classique sans
jouer pareil, mais une seule partie à la main ne permet pas de trancher (le
style y est noyé dans le hasard du tirage). Ce script calcule donc, en plus du
résumé de force (inchangé), des indicateurs de style par joueur sur l'ensemble
des parties : part des coups touchant une case à multiplicateur ou un mot
double/triple, lettres posées et points par coup, longueur du mot principal,
scrabbles/jokers/passes par partie, points et tour de pose du joker, pénalité
des lettres restantes en fin de partie — avec écart-type ou IC95 selon le cas
(voir :class:`IndicateursPartieJoueur` pour la définition exacte de chacun).
Affichés en tableau comparatif A vs B à la fin du résumé (sauf en mode
``--comparer``, qui relit un CSV sans le détail par coup nécessaire), et
exportés par partie et par joueur dans le CSV (``--csv``) pour être rejoués
ultérieurement.

Ces indicateurs sont calculés **après coup**, en relecture pure de
``Partie.historique`` et des chevalets finaux (voir
:func:`_calculer_indicateurs_joueur`) : ils ne touchent ni au moteur d'IA, ni
aux réglages par niveau, ni aux personnages, ni au tirage aléatoire — les
graines, les parties jouées et les résultats de force (victoire, score moyen)
restent rigoureusement identiques à une mesure sans ces indicateurs.

Pourquoi hors de la suite pytest
---------------------------------
Une mesure statistiquement significative demande des dizaines à centaines de
parties complètes (chacune plusieurs dizaines de tours, génération exhaustive
de coups à chaque tour) : plusieurs minutes, incompatible avec une suite pytest
qui doit rester rapide. Ce script est donc un outil de mesure **manuel**, lancé
ponctuellement par Alain (typiquement après un changement de calibrage IA),
jamais par la suite de tests normale.

Exemples d'usage
----------------
Effet du malus longueur, à niveau et vocabulaire constants (la question qui a
motivé le lot G) — CHAMPION_DU_MONDE avec le malus -25 actuel contre le même
niveau avec malus 0, dans la même partie, mêmes graines ::

    python scripts/mesurer_force_niveaux.py CHAMPION_DU_MONDE CHAMPION_DU_MONDE \\
        --malus-a -25 --malus-b 0 --parties 200 --csv malus.csv

Effet du vocabulaire à stratégie constante — un EXPERT jouant sur le palier
restreint ``avance`` contre un EXPERT jouant sur l'ODS8 complet (son
vocabulaire normal depuis l'issue #401) ::

    python scripts/mesurer_force_niveaux.py EXPERT EXPERT \\
        --vocab-a avance --vocab-b complet --parties 200

Effet de la tranche (stratégie) à vocabulaire constant — AVANCE contre EXPERT,
tous deux sur l'ODS8 complet ::

    python scripts/mesurer_force_niveaux.py AVANCE EXPERT --vocab complet

Mesure fidèle au jeu réel (chaque niveau sur son palier) ::

    python scripts/mesurer_force_niveaux.py FACILE DEBUTANT --vocab palier

Effet de la leave value (issue #395) — AVANCE contre CHAMPION_DU_MONDE, ce
dernier sans leave value ::

    python scripts/mesurer_force_niveaux.py AVANCE CHAMPION_DU_MONDE \\
        --vocab palier --poids-leave-b 0.0

Comparer deux exports CSV ::

    python scripts/mesurer_force_niveaux.py --comparer avant.csv apres.csv

Personnage contre Classique, au même niveau (issue #439, lot B) — Opportuniste
contre Classique en INTERMEDIAIRE, vocabulaire du jeu réel ::

    python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \\
        --personnage-a opportuniste --personnage-b classique --vocab palier \\
        --parties 200

Style de jeu Opportuniste contre Classique, à force égale (issue #446) — mêmes
commandes que ci-dessus, deux niveaux, avec export CSV pour réanalyse des
indicateurs de style (voir « Indicateurs de style » ci-dessus) ::

    python scripts/mesurer_force_niveaux.py AVANCE AVANCE \\
        --personnage-a opportuniste --personnage-b classique --vocab palier \\
        --parties 200 --csv style_opportuniste_vs_classique_avance.csv

    python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \\
        --personnage-a opportuniste --personnage-b classique --vocab palier \\
        --parties 200 --csv style_opportuniste_vs_classique_intermediaire.csv

Style de jeu Chasseur de scrabbles contre Classique (issue #450, lot H bis) —
même commande qu'Opportuniste ci-dessus, à chacun des quatre niveaux où la
mesure du lot H (issue #448) avait montré un style indiscernable
(Intermédiaire, Avancé, Expert, Champion du monde) : le vocabulaire étendu
(``vocabulaire_long``) ne devrait faire la différence qu'aux deux premiers
(vocabulaire du niveau restreint) — Expert/Champion du monde jouent déjà sur
le lexique complet, donc sans aucun avantage de style attendu ::

    python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \\
        --personnage-a chasseur_de_scrabbles --personnage-b classique \\
        --vocab palier --parties 100 \\
        --csv style_chasseur_vs_classique_intermediaire.csv

    python scripts/mesurer_force_niveaux.py AVANCE AVANCE \\
        --personnage-a chasseur_de_scrabbles --personnage-b classique \\
        --vocab palier --parties 100 \\
        --csv style_chasseur_vs_classique_avance.csv

    python scripts/mesurer_force_niveaux.py EXPERT EXPERT \\
        --personnage-a chasseur_de_scrabbles --personnage-b classique \\
        --vocab palier --parties 100 \\
        --csv style_chasseur_vs_classique_expert.csv

    python scripts/mesurer_force_niveaux.py CHAMPION_DU_MONDE CHAMPION_DU_MONDE \\
        --personnage-a chasseur_de_scrabbles --personnage-b classique \\
        --vocab palier --parties 100 \\
        --csv style_chasseur_vs_classique_champion.csv

Sans argument, oppose FACILE à DEBUTANT sur 100 parties, vocabulaire ``complet``
(comportement historique #362). Les niveaux valides sont les noms de
:class:`~scrabble.moteur.ia.Niveau` : DEBUTANT, FACILE, INTERMEDIAIRE, AVANCE,
EXPERT, CHAMPION_DU_MONDE.

Nécessite le dictionnaire réellement installé dans ``data/dictionnaire/``
(gitignoré, déposé manuellement — voir ``data/dictionnaire/README.md`` et
``CONTEXTE.md``) : le script s'arrête avec un message clair s'il est absent,
plutôt que de mesurer sur un dictionnaire vide.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Exécuté en tant que script : on ajoute ``src/`` au chemin d'import pour
# retrouver le paquet ``scrabble`` quel que soit le répertoire courant.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scrabble.dictionnaire.dictionnaire import (  # noqa: E402
    CHEMIN_ODS,
    FICHIERS_CACHE_IA_PALIER,
    FICHIERS_VOCABULAIRE_PALIER,
    obtenir_trie,
    obtenir_trie_ia,
)
from scrabble.moteur import ia  # noqa: E402
from scrabble.moteur.ia import Niveau, ProfilPersonnage, resoudre_palier  # noqa: E402
from scrabble.moteur.ordre import determiner_ordre_jeu  # noqa: E402
from scrabble.moteur.partie import ACTION_COUP, ACTION_PASSE, Joueur, Partie  # noqa: E402
from scrabble.moteur.personnages import PERSONNAGES  # noqa: E402
from scrabble.regles.plateau import TypeCase  # noqa: E402

#: Nombre de parties par défaut : modeste pour qu'un lancement sans argument
#: ne parte pas pour 20 minutes (quelques minutes seulement).
PARTIES_DEFAUT = 100

#: Graine de départ par défaut (partie 0..N-1 utilise les graines
#: graine_depart..graine_depart+N-1).
GRAINE_DEPART_DEFAUT = 0

#: Garde-fou : nombre de tours maximum avant d'abandonner une partie comme
#: anormale (une partie normale dure au plus quelques dizaines de tours par
#: joueur). Évite une boucle infinie en cas de bug du moteur.
MAX_TOURS = 400

#: Intervalle (en nombre de parties) entre deux affichages de progression.
_INTERVALLE_PROGRES_MIN = 1

#: Source du dictionnaire (ODS8 par défaut, comme le jeu réel).
SOURCE_DICO = "ods"

#: Clé de vocabulaire désignant l'ODS8 complet (sans filtre de palier). Distincte
#: des clés de palier restreint (:data:`FICHIERS_VOCABULAIRE_PALIER`).
VOCAB_COMPLET = "complet"

#: Clés acceptées pour ``--vocab-a``/``--vocab-b`` : les paliers restreints plus
#: ``complet`` (ODS8 entier).
_CLES_VOCAB_VALIDES = tuple(FICHIERS_VOCABULAIRE_PALIER) + (VOCAB_COMPLET,)


@dataclass
class ConfigJoueur:
    """Configuration d'un camp (A ou B) pour une mesure (issue #372).

    Découple la stratégie (``niveau``), le vocabulaire (``vocab``) et le
    calibrage stratégique (``malus``/``bonus``/``poids_leave``, ou
    ``personnage``), pour pouvoir faire varier un seul facteur à la fois.
    ``vocab`` à ``None`` signifie « suivre le mode ``--vocab`` global » (voir
    :func:`_cle_vocab_effective`) ; ``malus``/``bonus``/``poids_leave`` à
    ``None`` signifient « valeur de production du niveau, non surchargée ».

    ``personnage`` (issue #439, lot B) nomme une clé de
    :data:`scrabble.moteur.personnages.PERSONNAGES` — son
    :class:`~scrabble.moteur.ia.ProfilPersonnage` est transmis directement à
    :func:`~scrabble.moteur.ia.choisir_coup` (voir :meth:`profil`), la même
    voie que celle qu'emprunterait un futur appelant en production (lot A,
    issue #438), par opposition aux surcharges ``malus``/``bonus``/
    ``poids_leave`` ci-dessus qui patchent transitoirement les dicts indexés
    par niveau (:func:`_strategie_surchargee`). Les deux mécanismes se
    composent sans conflit (le profil de personnage s'applique par-dessus la
    valeur — éventuellement déjà patchée — du niveau), exactement comme en
    production.
    """

    niveau: Niveau
    vocab: str | None = None
    malus: int | None = None
    bonus: int | None = None
    poids_leave: float | None = None
    personnage: str | None = None

    def profil(self) -> ProfilPersonnage | None:
        """Résout :attr:`personnage` vers son :class:`~scrabble.moteur.ia.ProfilPersonnage`.

        ``None`` si aucun personnage n'est renseigné (comportement standard du
        niveau, éventuellement patché par ``malus``/``bonus``/``poids_leave``).
        """
        if self.personnage is None:
            return None
        return PERSONNAGES[self.personnage].profil

    def label(self) -> str:
        """Libellé lisible du camp, annotant les écarts à la config par défaut.

        Ex. ``CHAMPION_DU_MONDE[malus=0]`` ou ``EXPERT[vocab=avance]``. Sert de
        base aux entêtes CSV et aux lignes de résumé pour distinguer deux camps
        de même niveau mais de calibrage/vocabulaire/personnage différent.
        """
        annotations: list[str] = []
        if self.vocab is not None:
            annotations.append(f"vocab={self.vocab}")
        if self.malus is not None:
            annotations.append(f"malus={self.malus}")
        if self.bonus is not None:
            annotations.append(f"bonus={self.bonus}")
        if self.poids_leave is not None:
            annotations.append(f"poids_leave={self.poids_leave}")
        if self.personnage is not None:
            annotations.append(f"personnage={self.personnage}")
        if not annotations:
            return self.niveau.name
        return f"{self.niveau.name}[{','.join(annotations)}]"


@dataclass
class IndicateursPartieJoueur:
    """Indicateurs de style d'un joueur sur UNE partie (issue #446).

    Calculés après coup depuis ``Partie.historique`` et le chevalet final —
    aucune incidence sur le déroulement de la partie (voir
    :func:`_calculer_indicateurs_joueur`). Deux familles de champs :

    * des **compteurs cumulés sur la partie** (``coups_poses``,
      ``coups_touchant_multiplicateur``, ``coups_touchant_mot_double_triple``,
      ``scrabbles``, ``nb_jokers``, ``passes``) et le solde final
      (``penalite_fin``) — un entier par partie, agrégé ensuite par
      :func:`_stats_style` en moyenne ± IC95 sur les ``N`` parties ;
    * des **listes par coup** (``lettres_posees``, ``points_par_coup``,
      ``longueur_mot_principal``, ``points_coups_joker``,
      ``tours_coups_joker``) — une valeur par coup concerné, mises à plat sur
      toutes les parties avant d'en tirer moyenne ± IC95 (voir
      :func:`_stats_style`).

    Définitions exactes (point 1 de l'issue) :

    * « touche une case à multiplicateur » : au moins une case **nouvellement
      posée** du coup porte un bonus (:class:`~scrabble.regles.plateau.TypeCase`
      différent de ``NORMALE``), toutes lettres/mots confondus — reflet direct
      de :attr:`~scrabble.moteur.score.DetailMot.cases_bonus`, qui ne liste déjà
      que les cases neuves.
    * « touche un mot double ou triple » : pareil, restreint aux types
      ``MOT_DOUBLE``, ``MOT_TRIPLE`` **et** ``CENTRE`` — la case centrale
      comptant elle-même comme un mot double (voir
      :mod:`scrabble.regles.plateau`), l'ignorer aurait sous-compté le tout
      premier coup de chaque partie, qui la couvre toujours.
    * « lettres posées » : ``len(positions_posees)`` de l'entrée d'historique,
      c'est-à-dire le nombre de tuiles **neuves** de ce coup (cases déjà
      occupées traversées exclues) — pas la longueur du mot formé.
    * « mot principal » : le premier mot de ``detail.mots`` (toujours le mot
      porté par la direction du coup, voir
      :func:`~scrabble.moteur.plateau_partie.mots_formes`) ; repli sur
      ``len(coup.tuiles)`` dans le cas limite où aucun mot n'est recensé.
    * « joker joué » : une tuile **neuve** de ce coup dont
      :attr:`~scrabble.moteur.plateau_partie.Tuile.joker` est vrai (la réutilisation
      ultérieure du même joker, sur une case déjà occupée, ne recompte pas).
    * « tour de sa pose » : rang (1-indexé) de l'action dans l'historique
      **complet** de la partie, les deux joueurs confondus — même convention que
      ``ResultatPartie.tours``/``MAX_TOURS`` ailleurs dans ce script.
    * « pénalité lettres restantes » : :meth:`~scrabble.moteur.partie.Joueur.valeur_chevalet`
      du joueur en fin de partie (le chevalet n'est pas vidé par
      :meth:`Partie._terminer`, seul le score l'intègre déjà en soustraction).
    """

    coups_poses: int = 0
    coups_touchant_multiplicateur: int = 0
    coups_touchant_mot_double_triple: int = 0
    lettres_posees: list[int] = field(default_factory=list)
    points_par_coup: list[int] = field(default_factory=list)
    longueur_mot_principal: list[int] = field(default_factory=list)
    scrabbles: int = 0
    nb_jokers: int = 0
    points_coups_joker: list[int] = field(default_factory=list)
    tours_coups_joker: list[int] = field(default_factory=list)
    passes: int = 0
    penalite_fin: int = 0


#: Types de case comptant comme « mot double ou triple » pour les indicateurs
#: de style — la case centrale y est incluse car elle compte comme un mot
#: double (voir :mod:`scrabble.regles.plateau`).
_TYPES_MOT_DOUBLE_TRIPLE = frozenset({TypeCase.MOT_DOUBLE, TypeCase.MOT_TRIPLE, TypeCase.CENTRE})


def _calculer_indicateurs_joueur(
    historique: list, prefixe_nom: str, penalite_fin: int
) -> IndicateursPartieJoueur:
    """Calcule les indicateurs de style d'un joueur depuis l'historique d'une partie.

    ``historique`` est ``Partie.historique`` (liste d':class:`~scrabble.moteur.partie.EntreeHistorique`),
    ``prefixe_nom`` distingue le camp (``"A:"`` ou ``"B:"`` dans ce script, voir
    :func:`jouer_une_partie`) et ``penalite_fin`` la pénalité déjà calculée par
    l'appelant (:meth:`~scrabble.moteur.partie.Joueur.valeur_chevalet` en fin de
    partie). Ne lit **que** des données déjà produites par le moteur — aucun
    appel à :func:`~scrabble.moteur.ia.choisir_coup` ni au générateur aléatoire,
    donc aucune incidence sur le déroulement ou le résultat de la partie (point
    3 de l'issue #446).
    """
    ind = IndicateursPartieJoueur(penalite_fin=penalite_fin)
    for tour, entree in enumerate(historique, start=1):
        if not entree.nom_joueur.startswith(prefixe_nom):
            continue
        if entree.action == ACTION_PASSE:
            ind.passes += 1
            continue
        if entree.action != ACTION_COUP:
            continue  # échange : hors périmètre des indicateurs de style demandés
        detail = entree.detail
        ind.coups_poses += 1
        types_bonus = {
            type_case for mot in detail.mots for _, _, type_case in mot.cases_bonus
        }
        if types_bonus:
            ind.coups_touchant_multiplicateur += 1
        if types_bonus & _TYPES_MOT_DOUBLE_TRIPLE:
            ind.coups_touchant_mot_double_triple += 1
        ind.lettres_posees.append(len(entree.positions_posees))
        ind.points_par_coup.append(detail.total)
        if detail.mots:
            ind.longueur_mot_principal.append(len(detail.mots[0].texte))
        else:
            ind.longueur_mot_principal.append(len(entree.coup.tuiles))
        if detail.bonus_scrabble > 0:
            ind.scrabbles += 1
        positions_neuves = set(entree.positions_posees)
        nb_jokers_coup = sum(
            1
            for ligne, colonne, tuile in entree.coup.cases()
            if (ligne, colonne) in positions_neuves and tuile.joker
        )
        if nb_jokers_coup:
            ind.nb_jokers += nb_jokers_coup
            ind.points_coups_joker.append(detail.total)
            ind.tours_coups_joker.append(tour)
    return ind


@dataclass
class ResultatPartie:
    """Issue d'une partie A contre B."""

    graine: int
    score_a: int
    score_b: int
    commence: str  # "a" ou "b"
    tours: int
    #: Indicateurs de style de chacun des deux camps sur cette partie (issue
    #: #446) — n'influence jamais ``score_a``/``score_b``/``commence``/``tours``
    #: ci-dessus, calculés exactement comme avant leur introduction.
    indicateurs_a: IndicateursPartieJoueur = field(default_factory=IndicateursPartieJoueur)
    indicateurs_b: IndicateursPartieJoueur = field(default_factory=IndicateursPartieJoueur)


def _deriver_graines(graine_partie: int) -> tuple[int, int, int, int]:
    """Dérive (graine_sac, graine_ordre, graine_ia_a, graine_ia_b) depuis ``graine_partie``.

    Toutes les sources d'aléa d'une partie découlent d'une unique graine
    « maîtresse » : même ``graine_partie`` → mêmes quatre graines dérivées →
    partie strictement identique d'une exécution à l'autre.
    """
    maitre = random.Random(graine_partie)
    return (
        maitre.randrange(2**31),
        maitre.randrange(2**31),
        maitre.randrange(2**31),
        maitre.randrange(2**31),
    )


def _verifier_dictionnaire_installe() -> None:
    """Arrête le script avec un message clair si le dictionnaire est absent.

    ``obtenir_trie``/``charger_ods`` ne lèvent aucune exception sur un fichier
    manquant (comportement volontaire pour les listes optionnelles) : sans ce
    garde-fou, le script mesurerait silencieusement sur un dictionnaire vide
    (0 coup généré, parties immédiatement passées).
    """
    if not CHEMIN_ODS.exists():
        raise SystemExit(
            "Dictionnaire introuvable : "
            f"{CHEMIN_ODS} n'existe pas.\n"
            "Dépose manuellement le dictionnaire ODS8 dans "
            "data/dictionnaire/French-Scrabble-ODS8-main/ avant de lancer ce "
            "script (voir data/dictionnaire/README.md et CONTEXTE.md — le "
            "dictionnaire est gitignoré, jamais commité)."
        )


def _cle_vocab_effective(config: ConfigJoueur, mode_vocab: str) -> str:
    """Résout la clé de vocabulaire à utiliser pour un camp.

    Priorité : un vocabulaire **forcé** (``config.vocab``) l'emporte toujours.
    Sinon, le mode global décide :

    * ``palier`` → le palier du niveau (:func:`~scrabble.moteur.ia.resoudre_palier`),
      ou :data:`VOCAB_COMPLET` pour CHAMPION_DU_MONDE (qui n'a pas de palier
      restreint), reproduisant le jeu réel ;
    * ``complet`` → l'ODS8 entier pour tout le monde (comportement #362).

    Renvoie soit une clé de :data:`FICHIERS_VOCABULAIRE_PALIER`, soit
    :data:`VOCAB_COMPLET`.
    """
    if config.vocab is not None:
        return config.vocab
    if mode_vocab == "palier":
        return resoudre_palier(config.niveau) or VOCAB_COMPLET
    return VOCAB_COMPLET


def _resoudre_trie(cle_vocab: str, mode_belgicisme: bool, trie_complet):
    """Construit le Trie de génération correspondant à une clé de vocabulaire.

    Miroir volontaire de ``ApiAccueil._construire_trie_ia`` (``ui/accueil.py``,
    issue #369) : mêmes briques publiques (:func:`obtenir_trie` pour l'ODS8
    complet, :func:`obtenir_trie_ia` avec les chemins de
    :data:`FICHIERS_VOCABULAIRE_PALIER`/:data:`FICHIERS_CACHE_IA_PALIER` pour un
    palier restreint). On ne **réutilise pas** directement cette méthode car
    elle est couplée à l'UI (``import webview``, ``@staticmethod`` sur la classe
    ``ApiAccueil``) et, surtout, elle indexe le Trie par :class:`Niveau` — or ce
    script doit pouvoir **forcer un vocabulaire indépendant du niveau** (deux
    camps de même niveau, vocabulaires différents), ce que le mapping
    ``{Niveau: Trie}`` ne permet pas d'exprimer.

    Si le fichier de vocabulaire d'un palier restreint est absent, s'arrête avec
    un message clair (comme :func:`_verifier_dictionnaire_installe` pour l'ODS8),
    plutôt que de mesurer sur un vocabulaire vide.
    """
    if cle_vocab == VOCAB_COMPLET:
        return trie_complet
    chemin_vocab = FICHIERS_VOCABULAIRE_PALIER[cle_vocab]
    if not chemin_vocab.exists():
        raise SystemExit(
            f"Vocabulaire du palier « {cle_vocab} » introuvable : "
            f"{chemin_vocab} n'existe pas.\n"
            "Génère les vocabulaires par palier avec "
            "scripts/generer_mots_courants.py --tous avant de mesurer avec "
            "--vocab palier ou --vocab-a/--vocab-b (voir CONTEXTE.md — ces "
            "fichiers sont gitignorés, jamais commités)."
        )
    return obtenir_trie_ia(
        SOURCE_DICO,
        chemin_mots_courants=chemin_vocab,
        chemin_cache=FICHIERS_CACHE_IA_PALIER[cle_vocab],
        mode_belgicisme=mode_belgicisme,
        palier=cle_vocab,
    )


@contextmanager
def _strategie_surchargee(
    niveau: Niveau,
    malus: int | None,
    bonus: int | None,
    poids_leave: float | None = None,
) -> Iterator[None]:
    """Surcharge transitoirement le malus/bonus/poids-leave stratégique d'un niveau (issues #372, #399).

    Remplace, le temps du bloc ``with``, l'entrée ``niveau`` de
    :data:`scrabble.moteur.ia._MALUS_LONGUEUR`, :data:`~scrabble.moteur.ia._BONUS_PREMIUM`
    et/ou :data:`~scrabble.moteur.ia._POIDS_LEAVE`, puis **restaure** les valeurs
    d'origine en sortie (y compris sur exception). Le code de production n'est
    donc jamais modifié de façon durable : la surcharge reste cantonnée à
    l'outil de mesure, exactement comme le demande le point 2 de l'issue #372.

    Un ``None`` laisse la valeur de production inchangée. Le script étant
    séquentiel et mono-thread, envelopper chaque appel à
    :func:`~scrabble.moteur.ia.choisir_coup` d'un camp est sûr même si les deux
    camps partagent le même :class:`Niveau` (ex. CHAMPION_DU_MONDE vs
    CHAMPION_DU_MONDE avec deux malus différents).
    """
    malus_origine = ia._MALUS_LONGUEUR[niveau]
    bonus_origine = ia._BONUS_PREMIUM[niveau]
    poids_leave_origine = ia._POIDS_LEAVE[niveau]
    if malus is not None:
        ia._MALUS_LONGUEUR[niveau] = malus
    if bonus is not None:
        ia._BONUS_PREMIUM[niveau] = bonus
    if poids_leave is not None:
        ia._POIDS_LEAVE[niveau] = poids_leave
    try:
        yield
    finally:
        ia._MALUS_LONGUEUR[niveau] = malus_origine
        ia._BONUS_PREMIUM[niveau] = bonus_origine
        ia._POIDS_LEAVE[niveau] = poids_leave_origine


def jouer_une_partie(
    config_a: ConfigJoueur,
    config_b: ConfigJoueur,
    graine_partie: int,
    dictionnaire,
    trie_a,
    trie_b,
) -> ResultatPartie:
    """Joue une partie complète FACE À FACE entre deux configs IA, jusqu'à sa fin.

    Construit la :class:`Partie` directement (pas via ``creer_partie``, qui
    exige au moins un joueur humain) avec deux joueurs IA, un ordre de jeu tiré
    depuis une graine dérivée, et un ``random.Random`` distinct par joueur pour
    le choix de coup (voir :func:`_deriver_graines`).

    Chaque camp génère ses coups sur **son propre** Trie (``trie_a``/``trie_b``,
    résolus par :func:`_resoudre_trie`) — on passe donc le dictionnaire de
    génération explicitement à :func:`~scrabble.moteur.ia.choisir_coup` plutôt
    que de s'en remettre au mapping ``{Niveau: Trie}`` de la partie, qui ne
    saurait distinguer deux camps de même niveau au vocabulaire différent. Le
    Trie complet ``dictionnaire`` sert à la **validation** des coups et, pour
    un personnage ``vocabulaire_long`` (issue #450, lot H bis, Chasseur de
    scrabbles), de lexique complet transmis à ``choisir_coup`` — même chemin
    que le jeu réel (``Partie.jouer_tour_ia``), ignoré par tout profil qui ne
    le demande pas. Les surcharges stratégiques du camp sont appliquées, coup
    par coup, par :func:`_strategie_surchargee`.
    """
    graine_sac, graine_ordre, graine_ia_a, graine_ia_b = _deriver_graines(graine_partie)

    joueur_a = Joueur(nom=f"A:{config_a.niveau.name}", humain=False, niveau=config_a.niveau)
    joueur_b = Joueur(nom=f"B:{config_b.niveau.name}", humain=False, niveau=config_b.niveau)
    joueurs = [joueur_a, joueur_b]

    resultat_ordre = determiner_ordre_jeu(joueurs, random.Random(graine_ordre))
    joueurs = [joueurs[indice] for indice in resultat_ordre.ordre]
    commence = "a" if joueurs[0] is joueur_a else "b"

    partie = Partie(joueurs, dictionnaire, graine=graine_sac)

    # Contexte par joueur : (Trie de génération, config, rng dédié).
    contexte_par_joueur = {
        id(joueur_a): (trie_a, config_a, random.Random(graine_ia_a)),
        id(joueur_b): (trie_b, config_b, random.Random(graine_ia_b)),
    }

    tours = 0
    while not partie.terminee:
        if tours >= MAX_TOURS:
            raise RuntimeError(
                f"Partie graine={graine_partie} : {MAX_TOURS} tours atteints "
                "sans fin de partie — comportement anormal, abandon."
            )
        joueur = partie.joueur_courant()
        trie_joueur, config_joueur, rng_joueur = contexte_par_joueur[id(joueur)]
        with _strategie_surchargee(
            joueur.niveau,
            config_joueur.malus,
            config_joueur.bonus,
            config_joueur.poids_leave,
        ):
            coup = ia.choisir_coup(
                partie.plateau,
                joueur.chevalet,
                trie_joueur,
                joueur.niveau,
                rng_joueur,
                profil=config_joueur.profil(),
                # Lexique complet pour le style « vocabulaire long » (issue
                # #450, lot H bis, Chasseur de scrabbles) : ``dictionnaire``
                # est déjà le Trie complet chargé pour la validation — même
                # chemin que le jeu réel (``Partie.jouer_tour_ia``). Ignoré
                # par ``choisir_coup`` pour tout profil qui ne le demande
                # pas, donc aucun effet sur les configs sans ce personnage.
                dictionnaire_complet=dictionnaire,
            )
        if coup is None:
            partie.passer()
        else:
            partie.jouer_coup(coup)
        tours += 1

    # Indicateurs de style (issue #446) : calculés APRÈS la fin de la partie,
    # en relecture pure de ``partie.historique`` et des chevalets finaux — rien
    # ici n'appelle ``ia.choisir_coup`` ni ne consomme le générateur aléatoire,
    # donc aucune incidence sur ``score_a``/``score_b``/``commence``/``tours``
    # ci-dessus (point 3 de l'issue). Les noms de joueurs ``f"A:{...}"`` /
    # ``f"B:{...}"`` fixés plus haut servent de préfixe pour distinguer les
    # deux camps dans l'historique, indépendamment de qui a commencé.
    indicateurs_a = _calculer_indicateurs_joueur(
        partie.historique, "A:", joueur_a.valeur_chevalet()
    )
    indicateurs_b = _calculer_indicateurs_joueur(
        partie.historique, "B:", joueur_b.valeur_chevalet()
    )

    return ResultatPartie(
        graine=graine_partie,
        score_a=joueur_a.score,
        score_b=joueur_b.score,
        commence=commence,
        tours=tours,
        indicateurs_a=indicateurs_a,
        indicateurs_b=indicateurs_b,
    )


def _ic_95(proportion: float, n: int) -> float:
    """Demi-largeur de l'intervalle de confiance à 95 % (approximation normale).

    ``1.96 * sqrt(p * (1 - p) / n)`` : sans cette marge, un taux de victoire de
    57 % sur un petit échantillon pourrait être lu comme significatif alors
    qu'il ne l'est pas.
    """
    if n == 0:
        return 0.0
    return 1.96 * math.sqrt(proportion * (1 - proportion) / n)


def _ic_95_moyenne(valeurs: list[float]) -> float:
    """Demi-largeur de l'IC à 95 % d'une moyenne (approximation normale).

    ``1.96 * écart-type-échantillon / sqrt(n)`` — pendant continu de
    :func:`_ic_95` pour les indicateurs de style qui ne sont pas des
    proportions (points par coup, longueur de mot, etc.). Renvoie ``0.0`` pour
    moins de deux valeurs (écart-type indéfini).
    """
    if len(valeurs) < 2:
        return 0.0
    return 1.96 * statistics.stdev(valeurs) / math.sqrt(len(valeurs))


#: Un indicateur de style est soit une proportion de coups (dénominateur =
#: nombre de coups posés), soit une moyenne « par partie » (dénominateur = N
#: parties), soit une moyenne « par occurrence » optionnelle (jokers — peut
#: être absente si aucun joker n'a jamais été joué).
_INDICATEURS_STYLE = (
    ("part_bonus", "Coups touchant une case à multiplicateur", "proportion"),
    ("part_mot_double_triple", "  dont mot double/triple (ou centre)", "proportion"),
    ("lettres_par_coup", "Lettres posées par coup", "moyenne"),
    ("part_1_2_lettres", "Coups de une ou deux lettres", "proportion"),
    ("points_par_coup", "Points par coup", "moyenne"),
    ("longueur_mot_principal", "Longueur du mot principal", "moyenne"),
    ("scrabbles_par_partie", "Scrabbles (7 lettres) par partie", "moyenne"),
    ("jokers_par_partie", "Jokers joués par partie", "moyenne"),
    ("points_coup_joker", "  points du coup où un joker est posé", "moyenne_opt"),
    ("tour_coup_joker", "  tour de pose du joker", "moyenne_opt"),
    ("passes_par_partie", "Passes par partie", "moyenne"),
    ("penalite_fin_partie", "Pénalité lettres restantes en fin de partie", "moyenne"),
)


def _stats_style(resultats: list[ResultatPartie], cote: str) -> dict[str, tuple[float, float, int]]:
    """Agrège les indicateurs de style d'un camp sur l'ensemble des parties.

    ``cote`` est ``"a"`` ou ``"b"``. Renvoie, par clé de
    :data:`_INDICATEURS_STYLE`, un triplet ``(valeur, demi-largeur IC95, n)`` —
    ``n`` étant la taille de l'échantillon utilisé (nombre de coups, de
    parties, ou d'occurrences de joker selon l'indicateur), pour que l'affichage
    puisse distinguer un ``0.0`` véritable d'un échantillon vide (jamais de
    joker joué, notamment).
    """
    inds = [r.indicateurs_a if cote == "a" else r.indicateurs_b for r in resultats]

    total_coups = sum(i.coups_poses for i in inds)
    total_bonus = sum(i.coups_touchant_multiplicateur for i in inds)
    total_mdt = sum(i.coups_touchant_mot_double_triple for i in inds)
    lettres = [l for i in inds for l in i.lettres_posees]
    points_coup = [p for i in inds for p in i.points_par_coup]
    longueur_mot = [l for i in inds for l in i.longueur_mot_principal]
    coups_1_2 = sum(1 for l in lettres if l <= 2)

    scrabbles_partie = [i.scrabbles for i in inds]
    jokers_partie = [i.nb_jokers for i in inds]
    passes_partie = [i.passes for i in inds]
    penalite_partie = [i.penalite_fin for i in inds]
    points_joker = [p for i in inds for p in i.points_coups_joker]
    tour_joker = [t for i in inds for t in i.tours_coups_joker]

    def proportion(nombre: int, n: int) -> tuple[float, float, int]:
        p = nombre / n if n else 0.0
        return p, _ic_95(p, n), n

    def moyenne(valeurs: list[float]) -> tuple[float, float, int]:
        n = len(valeurs)
        m = statistics.mean(valeurs) if n else 0.0
        return m, _ic_95_moyenne(valeurs), n

    return {
        "part_bonus": proportion(total_bonus, total_coups),
        "part_mot_double_triple": proportion(total_mdt, total_coups),
        "lettres_par_coup": moyenne(lettres),
        "part_1_2_lettres": proportion(coups_1_2, total_coups),
        "points_par_coup": moyenne(points_coup),
        "longueur_mot_principal": moyenne(longueur_mot),
        "scrabbles_par_partie": moyenne(scrabbles_partie),
        "jokers_par_partie": moyenne(jokers_partie),
        "points_coup_joker": moyenne(points_joker),
        "tour_coup_joker": moyenne(tour_joker),
        "passes_par_partie": moyenne(passes_partie),
        "penalite_fin_partie": moyenne(penalite_partie),
    }


def _formater_indicateur(valeur: float, ic: float, n: int, type_valeur: str) -> str:
    """Formate une cellule du tableau de style : valeur ± IC95 (ou « n/a »)."""
    if n == 0:
        return "n/a"
    if type_valeur == "proportion":
        return f"{valeur:.1%} ± {ic:.1%}"
    return f"{valeur:.2f} ± {ic:.2f}"


def _formater_ecart(valeur_a: float, valeur_b: float, n_a: int, n_b: int, type_valeur: str) -> str:
    """Formate l'écart A-B d'une cellule du tableau de style (« n/a » si l'un des deux camps n'a pas l'indicateur)."""
    if n_a == 0 or n_b == 0:
        return "n/a"
    ecart = valeur_a - valeur_b
    if type_valeur == "proportion":
        return f"{ecart:+.1%}"
    return f"{ecart:+.2f}"


def _afficher_tableau_style(
    label_a: str, label_b: str, resultats: list[ResultatPartie]
) -> None:
    """Affiche le tableau comparatif des indicateurs de style A vs B (issue #446).

    Ajouté à la fin du résumé existant (:func:`_afficher_resume`), sans en
    modifier l'affichage ni les chiffres de force déjà produits. Voir
    :data:`_INDICATEURS_STYLE` pour la liste des indicateurs et
    :class:`IndicateursPartieJoueur` pour leur définition exacte.
    """
    stats_a = _stats_style(resultats, "a")
    stats_b = _stats_style(resultats, "b")

    largeur_libelle = max(len(libelle) for _, libelle, _ in _INDICATEURS_STYLE)
    largeur_a = max(len(label_a), 10)
    largeur_b = max(len(label_b), 10)

    print()
    print("=" * 60)
    print(f"STYLE DE JEU — {label_a} (A) vs {label_b} (B)")
    print("=" * 60)
    entete = (
        f"{'Indicateur':<{largeur_libelle}}  {label_a:>{largeur_a}}  "
        f"{label_b:>{largeur_b}}  {'Écart (A-B)':>14}"
    )
    print(entete)
    for cle, libelle, type_valeur in _INDICATEURS_STYLE:
        valeur_a, ic_a, n_a = stats_a[cle]
        valeur_b, ic_b, n_b = stats_b[cle]
        colonne_a = _formater_indicateur(valeur_a, ic_a, n_a, type_valeur)
        colonne_b = _formater_indicateur(valeur_b, ic_b, n_b, type_valeur)
        ecart = _formater_ecart(valeur_a, valeur_b, n_a, n_b, type_valeur)
        print(
            f"{libelle:<{largeur_libelle}}  {colonne_a:>{largeur_a}}  "
            f"{colonne_b:>{largeur_b}}  {ecart:>14}"
        )
    print("=" * 60)


def _formater_duree(secondes: float) -> str:
    secondes = int(secondes)
    minutes, sec = divmod(secondes, 60)
    if minutes:
        return f"{minutes}min{sec:02d}s"
    return f"{sec}s"


def executer_mesure(
    config_a: ConfigJoueur,
    config_b: ConfigJoueur,
    nb_parties: int,
    graine_depart: int,
    fichier_csv: Path | None = None,
    mode_vocab: str = "complet",
    mode_belgicisme: bool = False,
) -> list[ResultatPartie]:
    """Joue ``nb_parties`` parties A vs B, affiche la progression, renvoie les résultats."""
    _verifier_dictionnaire_installe()
    label_a, label_b = config_a.label(), config_b.label()

    print(f"Chargement du dictionnaire ({CHEMIN_ODS.parent.parent.name})...")
    trie_complet = obtenir_trie(SOURCE_DICO, mode_belgicisme=mode_belgicisme)
    print(f"Dictionnaire de validation chargé : {len(trie_complet)} mots.")

    cle_a = _cle_vocab_effective(config_a, mode_vocab)
    cle_b = _cle_vocab_effective(config_b, mode_vocab)
    trie_a = _resoudre_trie(cle_a, mode_belgicisme, trie_complet)
    trie_b = _resoudre_trie(cle_b, mode_belgicisme, trie_complet)
    print(
        f"Vocabulaire de génération — A ({label_a}) : {cle_a} "
        f"({len(trie_a)} mots) ; B ({label_b}) : {cle_b} ({len(trie_b)} mots)."
    )
    print(
        f"Mesure : {label_a} (A) vs {label_b} (B) sur {nb_parties} partie(s) "
        f"(graines {graine_depart}..{graine_depart + nb_parties - 1})."
    )

    resultats: list[ResultatPartie] = []
    intervalle_progres = max(_INTERVALLE_PROGRES_MIN, nb_parties // 20)
    debut = time.monotonic()

    for i in range(nb_parties):
        graine = graine_depart + i
        resultat = jouer_une_partie(
            config_a, config_b, graine, trie_complet, trie_a, trie_b
        )
        resultats.append(resultat)

        jouees = i + 1
        if jouees % intervalle_progres == 0 or jouees == nb_parties:
            ecoule = time.monotonic() - debut
            rythme = ecoule / jouees
            restant = rythme * (nb_parties - jouees)
            print(
                f"  {jouees}/{nb_parties} parties — "
                f"écoulé {_formater_duree(ecoule)} — "
                f"restant estimé {_formater_duree(restant)}"
            )

    if fichier_csv is not None:
        _ecrire_csv(fichier_csv, label_a, label_b, resultats)
        print(f"Détail exporté vers {fichier_csv}")

    _afficher_resume(label_a, label_b, resultats)
    # Tableau de style (issue #446) : volontairement distinct de
    # ``_afficher_resume`` (laissé inchangé), ajouté seulement sur le chemin
    # d'une mesure jouée ici — pas sur ``--comparer``, qui relit un CSV sans
    # les colonnes de détail par coup nécessaires à ces indicateurs.
    _afficher_tableau_style(label_a, label_b, resultats)
    return resultats


#: Suffixes (et ordre) des colonnes d'indicateurs de style par joueur dans le
#: CSV (issue #446) — préfixées ``a_``/``b_`` par :func:`_ecrire_csv`. Valeurs
#: par partie (pas de liste) : les comptages sont bruts, les moyennes (lettres,
#: points, longueur de mot, jokers) sont la moyenne **de cette seule partie**
#: pour ce joueur, vides (``""``) si l'indicateur ne s'applique à aucun coup de
#: la partie (ex. aucun joker joué).
_COLONNES_STYLE = (
    "coups",
    "part_bonus",
    "part_mot_double_triple",
    "lettres_moy",
    "part_1_2_lettres",
    "points_moy",
    "longueur_mot_moy",
    "scrabbles",
    "jokers",
    "points_coup_joker_moy",
    "tour_joker_moy",
    "passes",
    "penalite_fin",
)


def _valeurs_style_csv(ind: IndicateursPartieJoueur) -> list:
    """Valeurs CSV des indicateurs de style d'un joueur pour UNE partie.

    Ordre et noms alignés sur :data:`_COLONNES_STYLE`. Une moyenne sur une
    liste vide (ex. aucun joker joué cette partie) est exportée comme chaîne
    vide, pas comme ``0`` — pour ne pas confondre « jamais » et « zéro point ».
    """

    def moyenne(valeurs: list[int]) -> str:
        return f"{statistics.mean(valeurs):.3f}" if valeurs else ""

    part_bonus = ind.coups_touchant_multiplicateur / ind.coups_poses if ind.coups_poses else ""
    part_mdt = ind.coups_touchant_mot_double_triple / ind.coups_poses if ind.coups_poses else ""
    part_1_2 = (
        sum(1 for l in ind.lettres_posees if l <= 2) / len(ind.lettres_posees)
        if ind.lettres_posees
        else ""
    )
    return [
        ind.coups_poses,
        part_bonus,
        part_mdt,
        moyenne(ind.lettres_posees),
        part_1_2,
        moyenne(ind.points_par_coup),
        moyenne(ind.longueur_mot_principal),
        ind.scrabbles,
        ind.nb_jokers,
        moyenne(ind.points_coups_joker),
        moyenne(ind.tours_coups_joker),
        ind.passes,
        ind.penalite_fin,
    ]


def _ecrire_csv(
    chemin: Path, label_a: str, label_b: str, resultats: list[ResultatPartie]
) -> None:
    """Exporte le détail partie par partie. Les entêtes de score portent les

    **libellés de configuration** (``config_a.label()``) et non le seul nom de
    niveau : deux camps de même niveau mais de calibrage différent restent ainsi
    distinguables, y compris par :func:`_lire_csv` lors d'une comparaison.

    Depuis l'issue #446, chaque ligne porte aussi, par joueur (préfixe ``a_``/
    ``b_``, colonnes :data:`_COLONNES_STYLE`), les indicateurs de style de cette
    partie — voir :func:`_valeurs_style_csv`. Ces colonnes s'ajoutent **après**
    les six colonnes historiques : :func:`_lire_csv` continue de les lire par
    position et ignore le reste, donc ``--comparer`` reste compatible avec les
    CSV produits avant et après cet ajout.
    """
    with open(chemin, "w", newline="", encoding="utf-8") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(
            [
                "graine",
                f"score_{label_a}",
                f"score_{label_b}",
                "vainqueur",
                "a_commence",
                "tours",
                *(f"a_{suffixe}" for suffixe in _COLONNES_STYLE),
                *(f"b_{suffixe}" for suffixe in _COLONNES_STYLE),
            ]
        )
        for r in resultats:
            if r.score_a > r.score_b:
                vainqueur = label_a
            elif r.score_b > r.score_a:
                vainqueur = label_b
            else:
                vainqueur = "nul"
            a_commence = label_a if r.commence == "a" else label_b
            ecrivain.writerow(
                [
                    r.graine,
                    r.score_a,
                    r.score_b,
                    vainqueur,
                    a_commence,
                    r.tours,
                    *_valeurs_style_csv(r.indicateurs_a),
                    *_valeurs_style_csv(r.indicateurs_b),
                ]
            )


def _afficher_resume(
    label_a: str, label_b: str, resultats: list[ResultatPartie]
) -> None:
    n = len(resultats)
    victoires_a = sum(1 for r in resultats if r.score_a > r.score_b)
    victoires_b = sum(1 for r in resultats if r.score_b > r.score_a)
    nuls = n - victoires_a - victoires_b

    p_a = victoires_a / n
    p_b = victoires_b / n
    ic_a = _ic_95(p_a, n)
    ic_b = _ic_95(p_b, n)

    moy_a = sum(r.score_a for r in resultats) / n
    moy_b = sum(r.score_b for r in resultats) / n
    ecart_moyen = sum(r.score_a - r.score_b for r in resultats) / n

    commence_a = sum(1 for r in resultats if r.commence == "a")
    commence_b = n - commence_a

    print()
    print("=" * 60)
    print(f"RÉSUMÉ — {label_a} (A) vs {label_b} (B) sur {n} partie(s)")
    print("=" * 60)
    print(f"Taux de victoire {label_a} : {p_a:.1%} ± {ic_a:.1%} ({victoires_a}/{n})")
    print(f"Taux de victoire {label_b} : {p_b:.1%} ± {ic_b:.1%} ({victoires_b}/{n})")
    print(f"Matchs nuls : {nuls}/{n}")
    print(f"Score moyen {label_a} : {moy_a:.1f}")
    print(f"Score moyen {label_b} : {moy_b:.1f}")
    print(f"Écart moyen par partie ({label_a} - {label_b}) : {ecart_moyen:+.1f}")
    print(
        f"A commencé la partie : {commence_a}/{n} ({commence_a / n:.1%}) — "
        f"B : {commence_b}/{n} ({commence_b / n:.1%})"
    )
    # Un déséquilibre marqué de qui commence biaiserait le résultat (léger
    # avantage au premier joueur) : on le signale au-delà de 60/40.
    if n >= 10 and (commence_a / n < 0.4 or commence_a / n > 0.6):
        print(
            "  ATTENTION : répartition de l'ordre de jeu déséquilibrée "
            "(hors 40-60 %) — le résultat peut être biaisé par cet effet, "
            "distinct de la force des configurations."
        )
    print("=" * 60)


def _lire_csv(chemin: Path) -> tuple[str, str, list[ResultatPartie]]:
    """Relit un CSV produit par :func:`_ecrire_csv` (mode ``--comparer``).

    Récupère les libellés de configuration depuis les deux colonnes de score
    (préfixe ``score_``) et reconstruit la liste des :class:`ResultatPartie`.
    """
    if not chemin.exists():
        raise SystemExit(f"Fichier CSV introuvable : {chemin}")
    with open(chemin, newline="", encoding="utf-8") as fichier:
        lecteur = csv.reader(fichier)
        try:
            entete = next(lecteur)
        except StopIteration:
            raise SystemExit(f"CSV vide : {chemin}")
        if len(entete) < 6 or not entete[1].startswith("score_"):
            raise SystemExit(
                f"En-tête CSV inattendu dans {chemin} : ce mode attend un "
                "fichier produit par ce script (option --csv)."
            )
        label_a = entete[1][len("score_"):]
        label_b = entete[2][len("score_"):]
        resultats: list[ResultatPartie] = []
        for ligne in lecteur:
            resultats.append(
                ResultatPartie(
                    graine=int(ligne[0]),
                    score_a=int(ligne[1]),
                    score_b=int(ligne[2]),
                    commence="a" if ligne[4] == label_a else "b",
                    tours=int(ligne[5]),
                )
            )
    return label_a, label_b, resultats


def comparer_csv(chemin1: Path, chemin2: Path) -> None:
    """Compare deux runs exportés en CSV, sans lecture manuelle (issue #372, point 3).

    Affiche le résumé de chaque run, puis — sur les graines **communes** aux
    deux — l'écart de score moyen et de taux de victoire du camp A entre run 1
    et run 2. Le déterminisme du script garantit que deux runs joués aux mêmes
    graines ne diffèrent que par la configuration : l'écart mesure donc l'effet
    de ce seul changement.
    """
    label_a1, label_b1, res1 = _lire_csv(chemin1)
    label_a2, label_b2, res2 = _lire_csv(chemin2)

    print(f"Run 1 ({chemin1}) :")
    _afficher_resume(label_a1, label_b1, res1)
    print()
    print(f"Run 2 ({chemin2}) :")
    _afficher_resume(label_a2, label_b2, res2)

    par_graine1 = {r.graine: r for r in res1}
    par_graine2 = {r.graine: r for r in res2}
    communes = sorted(set(par_graine1) & set(par_graine2))

    print()
    print("=" * 60)
    print("COMPARAISON DES DEUX RUNS")
    print("=" * 60)
    if not communes:
        print(
            "Aucune graine commune aux deux runs : comparaison graine à graine "
            "impossible (relance-les avec la même --graine-depart et le même "
            "--parties pour un appariement exact)."
        )
        print("=" * 60)
        return

    n = len(communes)
    # Camp A de chaque run, apparié par graine.
    ecart_score_a = sum(par_graine2[g].score_a - par_graine1[g].score_a for g in communes) / n
    moy_a1 = sum(par_graine1[g].score_a for g in communes) / n
    moy_a2 = sum(par_graine2[g].score_a for g in communes) / n
    vict_a1 = sum(1 for g in communes if par_graine1[g].score_a > par_graine1[g].score_b)
    vict_a2 = sum(1 for g in communes if par_graine2[g].score_a > par_graine2[g].score_b)

    print(f"Graines communes appariées : {n}")
    print(f"Camp A — run 1 : {label_a1}  |  run 2 : {label_a2}")
    print(f"  Score moyen A : run 1 = {moy_a1:.1f}, run 2 = {moy_a2:.1f}")
    print(f"  Écart score moyen A (run 2 - run 1) : {ecart_score_a:+.1f}")
    print(
        f"  Victoires A : run 1 = {vict_a1}/{n} ({vict_a1 / n:.1%}), "
        f"run 2 = {vict_a2}/{n} ({vict_a2 / n:.1%}) "
        f"(écart {((vict_a2 - vict_a1) / n):+.1%})"
    )
    print("=" * 60)


def _parse_niveau(valeur: str) -> Niveau:
    try:
        return Niveau[valeur.upper()]
    except KeyError as exc:
        noms = ", ".join(n.name for n in Niveau)
        raise argparse.ArgumentTypeError(
            f"Niveau inconnu : {valeur!r}. Valeurs possibles : {noms}."
        ) from exc


def _parse_personnage(valeur: str) -> str:
    cle = valeur.lower()
    if cle not in PERSONNAGES:
        noms = ", ".join(sorted(PERSONNAGES))
        raise argparse.ArgumentTypeError(
            f"Personnage inconnu : {valeur!r}. Valeurs possibles : {noms}."
        )
    return cle


def _parse_vocab(valeur: str) -> str:
    cle = valeur.lower()
    if cle not in _CLES_VOCAB_VALIDES:
        possibles = ", ".join(_CLES_VOCAB_VALIDES)
        raise argparse.ArgumentTypeError(
            f"Vocabulaire inconnu : {valeur!r}. Valeurs possibles : {possibles}."
        )
    return cle


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mesure la force relative de deux configurations IA sur des parties "
            "complètes jouées l'une contre l'autre (issues #362, #372)."
        )
    )
    parser.add_argument(
        "niveau_a", type=_parse_niveau, nargs="?", default=Niveau.FACILE,
        help="Niveau IA du camp A (défaut : FACILE).",
    )
    parser.add_argument(
        "niveau_b", type=_parse_niveau, nargs="?", default=Niveau.DEBUTANT,
        help="Niveau IA du camp B (défaut : DEBUTANT).",
    )
    parser.add_argument(
        "--parties", "-n", type=int, default=PARTIES_DEFAUT,
        help=f"Nombre de parties à jouer (défaut : {PARTIES_DEFAUT}).",
    )
    parser.add_argument(
        "--graine-depart", "-g", type=int, default=GRAINE_DEPART_DEFAUT,
        help=f"Graine de la première partie (défaut : {GRAINE_DEPART_DEFAUT}). "
        "La partie i utilise la graine graine_depart + i.",
    )
    parser.add_argument(
        "--csv", type=Path, default=None,
        help="Chemin d'un fichier CSV où exporter le détail partie par partie "
        "(une ligne par partie : graine, scores, vainqueur, qui a commencé).",
    )
    parser.add_argument(
        "--vocab", choices=("complet", "palier"), default="complet",
        help="Vocabulaire de génération par défaut : 'complet' (ODS8 entier "
        "pour les deux camps, comportement #362, défaut) ou 'palier' (chaque "
        "niveau sur son palier, comme le jeu réel).",
    )
    parser.add_argument(
        "--vocab-a", type=_parse_vocab, default=None,
        help="Force le vocabulaire du camp A, indépendamment de son niveau et "
        f"de --vocab. Valeurs : {', '.join(_CLES_VOCAB_VALIDES)}.",
    )
    parser.add_argument(
        "--vocab-b", type=_parse_vocab, default=None,
        help="Force le vocabulaire du camp B (mêmes valeurs que --vocab-a).",
    )
    parser.add_argument(
        "--malus-a", type=int, default=None,
        help="Surcharge _MALUS_LONGUEUR du niveau du camp A, le temps de la "
        "mesure uniquement (le code de production n'est pas modifié).",
    )
    parser.add_argument(
        "--malus-b", type=int, default=None,
        help="Surcharge _MALUS_LONGUEUR du niveau du camp B (idem).",
    )
    parser.add_argument(
        "--bonus-a", type=int, default=None,
        help="Surcharge _BONUS_PREMIUM du niveau du camp A (idem --malus-a).",
    )
    parser.add_argument(
        "--bonus-b", type=int, default=None,
        help="Surcharge _BONUS_PREMIUM du niveau du camp B (idem).",
    )
    parser.add_argument(
        "--poids-leave-a", type=float, default=None,
        help="Surcharge _POIDS_LEAVE du niveau du camp A, le temps de la "
        "mesure uniquement (le code de production n'est pas modifié).",
    )
    parser.add_argument(
        "--poids-leave-b", type=float, default=None,
        help="Surcharge _POIDS_LEAVE du niveau du camp B (idem).",
    )
    parser.add_argument(
        "--personnage-a", type=_parse_personnage, default=None,
        help="Personnage IA du camp A (issue #439, lot B), en plus de son "
        f"niveau. Valeurs : {', '.join(sorted(PERSONNAGES))}. Son "
        "ProfilPersonnage est transmis à choisir_coup en plus de "
        "--malus-a/--bonus-a/--poids-leave-a (les deux mécanismes se "
        "composent).",
    )
    parser.add_argument(
        "--personnage-b", type=_parse_personnage, default=None,
        help="Personnage IA du camp B (idem --personnage-a).",
    )
    parser.add_argument(
        "--comparer", type=Path, nargs=2, metavar=("CSV1", "CSV2"), default=None,
        help="Mode comparaison : relit deux CSV produits par --csv et affiche "
        "l'écart graine par graine, sans rejouer de partie.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _construire_parser()
    args = parser.parse_args(argv)

    if args.comparer is not None:
        comparer_csv(args.comparer[0], args.comparer[1])
        return

    if args.parties <= 0:
        parser.error("--parties doit être strictement positif.")

    config_a = ConfigJoueur(
        niveau=args.niveau_a,
        vocab=args.vocab_a,
        malus=args.malus_a,
        bonus=args.bonus_a,
        poids_leave=args.poids_leave_a,
        personnage=args.personnage_a,
    )
    config_b = ConfigJoueur(
        niveau=args.niveau_b,
        vocab=args.vocab_b,
        malus=args.malus_b,
        bonus=args.bonus_b,
        poids_leave=args.poids_leave_b,
        personnage=args.personnage_b,
    )
    executer_mesure(
        config_a,
        config_b,
        args.parties,
        args.graine_depart,
        args.csv,
        mode_vocab=args.vocab,
    )


if __name__ == "__main__":
    main()
