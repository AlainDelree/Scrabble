#!/usr/bin/env python3
"""Mesure la force relative de deux niveaux IA sur des parties complètes (issue #362).

Contexte
--------
``tests/test_moteur_ia.py`` prouve la monotonie des niveaux IA (score moyen par
coup, sur deux positions figées, à graine variable), mais ne dit rien de la
force relative sur une **partie complète** : score cumulé, gestion du chevalet
au fil des tirages, milieu de partie riche en hooks — précisément le contexte
des issues #359/#361. Ce script comble ce manque en faisant s'affronter deux
niveaux IA sur ``N`` parties jouées entièrement.

Principe : même partie, pas deux parties séparées
--------------------------------------------------
Les deux IA s'affrontent **dans la même partie** (même sac au départ, même
plateau, même ordre de jeu tiré une seule fois) : c'est le seul moyen d'isoler
l'effet de la stratégie de sélection du bruit du tirage. Deux parties séparées
avec des sacs indépendants mesureraient surtout la chance du tirage, pas la
force du niveau. Le sac divergera malgré tout **en cours** de partie (les deux
joueurs posent un nombre de lettres différent par tour, donc repiochent
différemment) : c'est attendu — l'égalité des conditions vaut au départ, pas à
chaque tour.

Déterminisme
------------
Chaque partie ``i`` dérive toutes ses sources d'aléa d'une unique graine de
partie ``i`` (:func:`_deriver_graines`) : graine du sac, graine du tirage
d'ordre, et une graine de ``random.Random`` **distincte pour chaque joueur
IA**. Deux exécutions avec les mêmes paramètres (mêmes niveaux, même nombre de
parties, même graine de départ) produisent donc **exactement** le même
résultat — condition nécessaire pour comparer deux runs avant/après un
changement de calibrage (``_MALUS_LONGUEUR``, ``_BONUS_PREMIUM`` dans
``moteur/ia.py``).

Ce que la mesure établit — et ce qu'elle n'établit pas
-------------------------------------------------------
Établit : le taux de victoire (avec intervalle de confiance à 95 %) et l'écart
de score moyen entre deux niveaux, sur des parties complètes jouées avec le
dictionnaire réellement installé. C'est la mesure la plus proche de
l'expérience d'une joueuse humaine choisissant un niveau.

N'établit PAS : un niveau de confiance absolu sur le pourcentage de victoire
« vrai » (l'IC à 95 % donne une fourchette, pas un point) ; l'expérience d'une
partie IA contre un **humain** (les deux niveaux mesurés ici sont l'un contre
l'autre, une joueuse humaine n'est ni FACILE ni DEBUTANT) ; l'effet du filtre
« vocabulaire humain » (issue #206, non activé ici — le script utilise le même
dictionnaire pour la validation et la génération IA, comme le fait
``creer_partie`` par défaut) ; le comportement à plus de 2 IA en table (seul le
face-à-face à deux est mesuré).

Pourquoi hors de la suite pytest
---------------------------------
Une mesure statistiquement significative demande des dizaines à centaines de
parties complètes (chacune plusieurs dizaines de tours, génération exhaustive
de coups à chaque tour) : plusieurs minutes, incompatible avec une suite
pytest qui doit rester rapide (~66 s pour l'ensemble actuel). Ce script est
donc un outil de mesure **manuel**, lancé ponctuellement par Alain (typiquement
après un changement de calibrage IA), jamais par la suite de tests normale.

Usage
-----
    python scripts/mesurer_force_niveaux.py FACILE DEBUTANT
    python scripts/mesurer_force_niveaux.py FACILE DEBUTANT --parties 400 --graine-depart 1000
    python scripts/mesurer_force_niveaux.py EXPERT INTERMEDIAIRE --csv resultats.csv

Sans argument, oppose FACILE à DEBUTANT sur 100 parties (quelques minutes) —
volontairement modeste pour qu'un lancement sans réflexion ne parte pas pour
20 minutes. Les niveaux valides sont les noms de :class:`~scrabble.moteur.
ia.Niveau` : DEBUTANT, FACILE, INTERMEDIAIRE, AVANCE, EXPERT.

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
from dataclasses import dataclass
from pathlib import Path

# Exécuté en tant que script : on ajoute ``src/`` au chemin d'import pour
# retrouver le paquet ``scrabble`` quel que soit le répertoire courant.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scrabble.dictionnaire.dictionnaire import CHEMIN_ODS, obtenir_trie  # noqa: E402
from scrabble.moteur import ia  # noqa: E402
from scrabble.moteur.ia import Niveau  # noqa: E402
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


def jouer_une_partie(
    niveau_a: Niveau, niveau_b: Niveau, graine_partie: int, dictionnaire
) -> ResultatPartie:
    """Joue une partie complète FACE À FACE entre deux IA, jusqu'à sa fin.

    Construit la :class:`Partie` directement (pas via ``creer_partie``, qui
    exige au moins un joueur humain) avec deux joueurs IA, un ordre de jeu tiré
    depuis une graine dérivée, et un ``random.Random`` distinct par joueur pour
    le choix de coup (voir :func:`_deriver_graines`).
    """
    graine_sac, graine_ordre, graine_ia_a, graine_ia_b = _deriver_graines(graine_partie)

    joueur_a = Joueur(nom=f"A:{niveau_a.name}", humain=False, niveau=niveau_a)
    joueur_b = Joueur(nom=f"B:{niveau_b.name}", humain=False, niveau=niveau_b)
    joueurs = [joueur_a, joueur_b]

    resultat_ordre = determiner_ordre_jeu(joueurs, random.Random(graine_ordre))
    joueurs = [joueurs[indice] for indice in resultat_ordre.ordre]
    commence = "a" if joueurs[0] is joueur_a else "b"

    partie = Partie(joueurs, dictionnaire, graine=graine_sac)

    rng_par_joueur = {
        id(joueur_a): random.Random(graine_ia_a),
        id(joueur_b): random.Random(graine_ia_b),
    }

    tours = 0
    while not partie.terminee:
        if tours >= MAX_TOURS:
            raise RuntimeError(
                f"Partie graine={graine_partie} : {MAX_TOURS} tours atteints "
                "sans fin de partie — comportement anormal, abandon."
            )
        joueur = partie.joueur_courant()
        coup = ia.choisir_coup(
            partie.plateau,
            joueur.chevalet,
            partie.dictionnaire_ia,
            joueur.niveau,
            rng_par_joueur[id(joueur)],
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
    niveau_a: Niveau,
    niveau_b: Niveau,
    nb_parties: int,
    graine_depart: int,
    fichier_csv: Path | None = None,
) -> list[ResultatPartie]:
    """Joue ``nb_parties`` parties A vs B, affiche la progression, renvoie les résultats."""
    _verifier_dictionnaire_installe()
    print(f"Chargement du dictionnaire ({CHEMIN_ODS.parent.parent.name})...")
    dictionnaire = obtenir_trie()
    print(f"Dictionnaire chargé : {len(dictionnaire)} mots.")
    print(
        f"Mesure : {niveau_a.name} vs {niveau_b.name} sur {nb_parties} partie(s) "
        f"(graines {graine_depart}..{graine_depart + nb_parties - 1})."
    )

    resultats: list[ResultatPartie] = []
    intervalle_progres = max(_INTERVALLE_PROGRES_MIN, nb_parties // 20)
    debut = time.monotonic()

    for i in range(nb_parties):
        graine = graine_depart + i
        resultat = jouer_une_partie(niveau_a, niveau_b, graine, dictionnaire)
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
        _ecrire_csv(fichier_csv, niveau_a, niveau_b, resultats)
        print(f"Détail exporté vers {fichier_csv}")

    _afficher_resume(niveau_a, niveau_b, resultats)
    return resultats


def _ecrire_csv(
    chemin: Path, niveau_a: Niveau, niveau_b: Niveau, resultats: list[ResultatPartie]
) -> None:
    with open(chemin, "w", newline="", encoding="utf-8") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(
            [
                "graine",
                f"score_{niveau_a.name}",
                f"score_{niveau_b.name}",
                "vainqueur",
                "a_commence",
                "tours",
            ]
        )
        for r in resultats:
            if r.score_a > r.score_b:
                vainqueur = niveau_a.name
            elif r.score_b > r.score_a:
                vainqueur = niveau_b.name
            else:
                vainqueur = "nul"
            a_commence = niveau_a.name if r.commence == "a" else niveau_b.name
            ecrivain.writerow(
                [r.graine, r.score_a, r.score_b, vainqueur, a_commence, r.tours]
            )


def _afficher_resume(
    niveau_a: Niveau, niveau_b: Niveau, resultats: list[ResultatPartie]
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
    print(f"RÉSUMÉ — {niveau_a.name} (A) vs {niveau_b.name} (B) sur {n} partie(s)")
    print("=" * 60)
    print(
        f"Taux de victoire {niveau_a.name} : {p_a:.1%} ± {ic_a:.1%} "
        f"({victoires_a}/{n})"
    )
    print(
        f"Taux de victoire {niveau_b.name} : {p_b:.1%} ± {ic_b:.1%} "
        f"({victoires_b}/{n})"
    )
    print(f"Matchs nuls : {nuls}/{n}")
    print(f"Score moyen {niveau_a.name} : {moy_a:.1f}")
    print(f"Score moyen {niveau_b.name} : {moy_b:.1f}")
    print(f"Écart moyen par partie ({niveau_a.name} - {niveau_b.name}) : {ecart_moyen:+.1f}")
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
            "distinct de la force des niveaux."
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


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mesure la force relative de deux niveaux IA sur des parties "
            "complètes jouées l'une contre l'autre (issue #362)."
        )
    )
    parser.add_argument(
        "niveau_a", type=_parse_niveau, nargs="?", default=Niveau.FACILE,
        help="Premier niveau IA (défaut : FACILE).",
    )
    parser.add_argument(
        "niveau_b", type=_parse_niveau, nargs="?", default=Niveau.DEBUTANT,
        help="Second niveau IA (défaut : DEBUTANT).",
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
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _construire_parser()
    args = parser.parse_args(argv)
    if args.parties <= 0:
        parser.error("--parties doit être strictement positif.")
    executer_mesure(
        args.niveau_a, args.niveau_b, args.parties, args.graine_depart, args.csv
    )


if __name__ == "__main__":
    main()
