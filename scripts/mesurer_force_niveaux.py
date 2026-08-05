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
changement de calibrage (``_MALUS_LONGUEUR``, ``_BONUS_PREMIUM`` dans
``moteur/ia.py``), ce que ce script permet désormais **sans éditer le code de
production** (voir « Paramètres surchargeables » ci-dessous).

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
* des **surcharges stratégiques** optionnelles (``--malus-a``/``--bonus-a`` et
  leurs équivalents B) qui remplacent, *le temps de la mesure uniquement*,
  l'entrée de ``_MALUS_LONGUEUR``/``_BONUS_PREMIUM`` du niveau considéré. La
  surcharge est appliquée par un gestionnaire de contexte
  (:func:`_strategie_surchargee`) qui restaure les valeurs de production en
  sortie : **le code de production n'est jamais modifié**.

Vocabulaire par palier
----------------------
Depuis le lot C (#369), chaque niveau du jeu réel génère ses coups sur un Trie
**restreint à son palier de fréquence** (CHAMPION_DU_MONDE seul utilise l'ODS8
complet). Le mode ``--vocab`` choisit ce que le script reproduit :

* ``complet`` (défaut, comportement historique #362) : les deux camps génèrent
  sur l'ODS8 complet, quel que soit le niveau. Utile pour isoler l'effet de la
  seule stratégie, à vocabulaire constant ;
* ``palier`` : chaque camp génère sur le palier de son niveau, **comme le jeu
  réel** (via :func:`~scrabble.moteur.ia.resoudre_palier`). C'est la mesure la
  plus proche de l'expérience d'une joueuse humaine.

``--vocab-a``/``--vocab-b`` forcent un vocabulaire précis pour un camp,
indépendamment de son niveau et du mode ``--vocab`` global. Valeurs possibles :
``debutant``, ``facile``, ``intermediaire``, ``avance``, ``expert`` (paliers
restreints) ou ``complet`` (ODS8 entier). Si le fichier de vocabulaire d'un
palier requis est absent, le script s'arrête avec un message clair, comme il le
fait déjà pour l'ODS8.

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
``avance`` contre un EXPERT jouant sur son palier normal ::

    python scripts/mesurer_force_niveaux.py EXPERT EXPERT \\
        --vocab-a avance --vocab-b expert --parties 200

Effet de la tranche (stratégie) à vocabulaire constant — AVANCE contre EXPERT,
tous deux sur l'ODS8 complet ::

    python scripts/mesurer_force_niveaux.py AVANCE EXPERT --vocab complet

Mesure fidèle au jeu réel (chaque niveau sur son palier) ::

    python scripts/mesurer_force_niveaux.py FACILE DEBUTANT --vocab palier

Comparer deux exports CSV ::

    python scripts/mesurer_force_niveaux.py --comparer avant.csv apres.csv

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
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
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
from scrabble.moteur.ia import Niveau, resoudre_palier  # noqa: E402
from scrabble.moteur.ordre import determiner_ordre_jeu  # noqa: E402
from scrabble.moteur.partie import Joueur, Partie  # noqa: E402

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
    calibrage stratégique (``malus``/``bonus``), pour pouvoir faire varier un
    seul facteur à la fois. ``vocab`` à ``None`` signifie « suivre le mode
    ``--vocab`` global » (voir :func:`_cle_vocab_effective`) ; ``malus``/``bonus``
    à ``None`` signifient « valeur de production du niveau, non surchargée ».
    """

    niveau: Niveau
    vocab: str | None = None
    malus: int | None = None
    bonus: int | None = None

    def label(self) -> str:
        """Libellé lisible du camp, annotant les écarts à la config par défaut.

        Ex. ``CHAMPION_DU_MONDE[malus=0]`` ou ``EXPERT[vocab=avance]``. Sert de
        base aux entêtes CSV et aux lignes de résumé pour distinguer deux camps
        de même niveau mais de calibrage/vocabulaire différent.
        """
        annotations: list[str] = []
        if self.vocab is not None:
            annotations.append(f"vocab={self.vocab}")
        if self.malus is not None:
            annotations.append(f"malus={self.malus}")
        if self.bonus is not None:
            annotations.append(f"bonus={self.bonus}")
        if not annotations:
            return self.niveau.name
        return f"{self.niveau.name}[{','.join(annotations)}]"


@dataclass
class ResultatPartie:
    """Issue d'une partie A contre B."""

    graine: int
    score_a: int
    score_b: int
    commence: str  # "a" ou "b"
    tours: int


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
    niveau: Niveau, malus: int | None, bonus: int | None
) -> Iterator[None]:
    """Surcharge transitoirement le malus/bonus stratégique d'un niveau (issue #372).

    Remplace, le temps du bloc ``with``, l'entrée ``niveau`` de
    :data:`scrabble.moteur.ia._MALUS_LONGUEUR` et/ou
    :data:`~scrabble.moteur.ia._BONUS_PREMIUM`, puis **restaure** les valeurs
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
    if malus is not None:
        ia._MALUS_LONGUEUR[niveau] = malus
    if bonus is not None:
        ia._BONUS_PREMIUM[niveau] = bonus
    try:
        yield
    finally:
        ia._MALUS_LONGUEUR[niveau] = malus_origine
        ia._BONUS_PREMIUM[niveau] = bonus_origine


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
    Trie complet ``dictionnaire`` sert uniquement à la **validation** des coups.
    Les surcharges stratégiques du camp sont appliquées, coup par coup, par
    :func:`_strategie_surchargee`.
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
            joueur.niveau, config_joueur.malus, config_joueur.bonus
        ):
            coup = ia.choisir_coup(
                partie.plateau,
                joueur.chevalet,
                trie_joueur,
                joueur.niveau,
                rng_joueur,
            )
        if coup is None:
            partie.passer()
        else:
            partie.jouer_coup(coup)
        tours += 1

    return ResultatPartie(
        graine=graine_partie,
        score_a=joueur_a.score,
        score_b=joueur_b.score,
        commence=commence,
        tours=tours,
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
    return resultats


def _ecrire_csv(
    chemin: Path, label_a: str, label_b: str, resultats: list[ResultatPartie]
) -> None:
    """Exporte le détail partie par partie. Les entêtes de score portent les

    **libellés de configuration** (``config_a.label()``) et non le seul nom de
    niveau : deux camps de même niveau mais de calibrage différent restent ainsi
    distinguables, y compris par :func:`_lire_csv` lors d'une comparaison.
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
                [r.graine, r.score_a, r.score_b, vainqueur, a_commence, r.tours]
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
        niveau=args.niveau_a, vocab=args.vocab_a, malus=args.malus_a, bonus=args.bonus_a
    )
    config_b = ConfigJoueur(
        niveau=args.niveau_b, vocab=args.vocab_b, malus=args.malus_b, bonus=args.bonus_b
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
