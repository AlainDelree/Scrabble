#!/usr/bin/env python3
"""Génération de la liste candidate des « classiques du jeu » (issue #204, suite de #203).

Contexte
--------
Les « classiques du jeu » sont les petits mots à lettre chère (WU, SIX, ZOO, KA…)
qu'on autorise l'IA à jouer même s'ils sont rares dans le langage courant. Le
rapport d'investigation #203 a établi un critère simple et reproductible pour
constituer une **liste candidate initiale** : les mots de l'ODS8 de **2 à 4
lettres** contenant **au moins une lettre chère** parmi J/K/Q/W/X/Z (~531 mots).

Rôle de ce script
-----------------
Cette liste n'est PAS un fichier figé à éditer à la main : elle **amorce** le
mécanisme de stockage décrit à l'issue #204, à savoir la paire
``classiques_ajoutes.txt`` / ``classiques_retires.txt`` (:data:`CHEMINS_CLASSIQUES`),
lue via ``lire_liste_mots`` avec la même normalisation que les autres listes de
personnalisation. Alain retire ensuite depuis l'onglet Dictionnaire des réglages
ce qui ne lui convient pas — sans jamais rééditer de fichier.

On écrit donc la liste candidate dans ``classiques_ajoutes.txt`` (le fichier de
*seed*). Par sécurité, si ce fichier existe déjà et n'est pas vide, on ne
l'écrase pas (la curation d'Alain serait perdue) : il faut alors ``--force``.

Usage
-----
    python scripts/generer_classiques.py            # amorce le fichier
    python scripts/generer_classiques.py --dry-run  # affiche seulement la liste
    python scripts/generer_classiques.py --force    # réécrit même si non vide

Nécessite que l'ODS8 soit présent dans ``data/dictionnaire/`` (voir CONTEXTE.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Exécuté en tant que script (``python scripts/generer_classiques.py``) : on
# ajoute ``src/`` au chemin d'import pour retrouver le paquet ``scrabble``,
# quel que soit le répertoire courant.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scrabble.dictionnaire.dictionnaire import (  # noqa: E402
    CHEMINS_CLASSIQUES,
    _reecrire_liste_mots,
    charger_ods,
    lire_liste_mots,
)

# Lettres « chères » du Scrabble francophone dont la présence, sur un mot court,
# signe un « classique du jeu » potentiel (issue #203). Mots normalisés en
# MAJUSCULES par ``charger_ods`` : la comparaison se fait donc en majuscules.
LETTRES_CHERES = set("JKQWXZ")
LONGUEUR_MIN = 2
LONGUEUR_MAX = 4


def generer_candidats(mots_ods: set[str]) -> set[str]:
    """Sélectionne les mots de 2 à 4 lettres contenant une lettre chère.

    ``mots_ods`` est l'ensemble ODS8 déjà normalisé (:func:`charger_ods`).
    """
    return {
        mot
        for mot in mots_ods
        if LONGUEUR_MIN <= len(mot) <= LONGUEUR_MAX
        and LETTRES_CHERES.intersection(mot)
    }


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "--dry-run",
        action="store_true",
        help="affiche la liste candidate sans écrire le fichier de seed",
    )
    parseur.add_argument(
        "--force",
        action="store_true",
        help="réécrit classiques_ajoutes.txt même s'il existe déjà (non vide)",
    )
    args = parseur.parse_args(argv)

    candidats = generer_candidats(charger_ods())
    print(f"Mots candidats « classiques du jeu » : {len(candidats)}")

    if args.dry_run:
        for mot in sorted(candidats):
            print(mot)
        return 0

    chemin_ajoutes, _ = CHEMINS_CLASSIQUES
    existants = lire_liste_mots(chemin_ajoutes)
    if existants and not args.force:
        print(
            f"« {chemin_ajoutes.name} » contient déjà {len(existants)} mot(s) : "
            "on n'écrase pas (utiliser --force pour réamorcer)."
        )
        return 1

    _reecrire_liste_mots(chemin_ajoutes, candidats)
    print(f"Seed écrit dans {chemin_ajoutes} ({len(candidats)} mots).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
