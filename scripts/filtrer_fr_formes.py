#!/usr/bin/env python3
"""Extraction française avec formes fléchies depuis ``fr-extract.jsonl`` (issue #16, suite de #13).

Le fichier ``fr-filtre.jsonl`` produit à l'issue #13 a jeté le champ ``forms``
lors de son extraction. Or le croisement avec l'ODS8 a montré que la majorité
des 158 472 mots ODS8 sans définition sont des formes fléchies (conjugaisons,
féminins, pluriels) dont le Wiktionnaire attache la glose au lemme, pas à la
forme. Il faut donc un nouveau passage sur le fichier brut pour récupérer ce
champ et pouvoir, dans une issue ultérieure, construire une table forme→lemme.

Structure réelle du champ ``forms`` (observée, non supposée) : une liste
d'objets ``{"form": <str>, "tags": [<str>...], "raw_tags": [...], "ipas": [...],
"source": <str>}``. Seule la clé ``form`` est systématiquement présente ; les
autres sont optionnelles. On conserve les objets tels quels pour ne rien perdre.

Principe (identique à l'issue #13, impératif pour tenir le temps) :

* **une seule lecture** du fichier source, en streaming ligne par ligne ;
* pour chaque entrée ``lang_code == "fr"`` on ne garde que ``word``, ``pos``,
  les gloses (``senses[].glosses[]``) et ``forms`` (seulement si présent et non
  vide — sinon on omet la clé plutôt que de stocker une liste vide) ;
* **écriture en streaming** (une ligne JSON par mot au fil de l'eau).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

BASE = Path("/home/alain/Scrabble/data/dictionnaire/wiktionnaire-kaikki")
SOURCE = BASE / "fr-extract.jsonl"
DESTINATION = BASE / "fr-filtre-formes.jsonl"


def extraire() -> None:
    debut = time.monotonic()
    lignes_lues = 0
    entrees_retenues = 0
    entrees_avec_formes = 0

    with (
        SOURCE.open("r", encoding="utf-8") as source,
        DESTINATION.open("w", encoding="utf-8") as sortie,
    ):
        for ligne in source:
            lignes_lues += 1
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue

            if entree.get("lang_code") != "fr":
                continue

            # On ne conserve que les gloses de chaque sens, rien d'autre.
            gloses: list[str] = []
            for sens in entree.get("senses", []) or []:
                for glose in sens.get("glosses", []) or []:
                    gloses.append(glose)

            minimal = {
                "word": entree.get("word"),
                "pos": entree.get("pos"),
                "glosses": gloses,
            }

            # Champ forms : seulement s'il existe et est non vide, conservé tel quel.
            formes = entree.get("forms")
            if formes:
                minimal["forms"] = formes
                entrees_avec_formes += 1

            sortie.write(json.dumps(minimal, ensure_ascii=False))
            sortie.write("\n")
            entrees_retenues += 1

    duree = time.monotonic() - debut
    taille = DESTINATION.stat().st_size

    print(f"Lignes lues (source)          : {lignes_lues}")
    print(f"Entrées françaises retenues   : {entrees_retenues}")
    print(f"Entrées avec forms non vide   : {entrees_avec_formes}")
    print(f"Temps d'exécution total       : {duree:.1f} s")
    print(f"Taille de {DESTINATION.name} : {taille} octets ({taille / 1_048_576:.1f} Mio)")


if __name__ == "__main__":
    extraire()
