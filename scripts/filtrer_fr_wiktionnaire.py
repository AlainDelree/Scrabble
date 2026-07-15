#!/usr/bin/env python3
"""Extraction française filtrée depuis ``fr-extract.jsonl`` (issue #13, suite de #9).

Le dump Kaikki ``fr-extract.jsonl`` (~6,7 Go) contient une entrée JSON par ligne,
toutes langues confondues, avec quantité de champs inutiles pour le Scrabble
(étymologie, prononciation, exemples, traductions, formes fléchies détaillées…).
Deux tentatives d'analyse directe ont timeout : on isole donc d'abord une
extraction minimale.

Principe (impératif pour tenir le temps) :

* **une seule lecture** du fichier source, en streaming ligne par ligne ;
* pour chaque ligne, on parse le JSON, on ne garde que les entrées dont
  ``lang_code == "fr"`` et on ne conserve que ``word``, ``pos`` et les gloses
  (``senses[].glosses[]``) — tout le reste est jeté immédiatement ;
* **écriture en streaming** (une ligne JSON par mot au fil de l'eau).

Ni ``orjson`` ni ``ujson`` n'étant présents dans le venv, on utilise le module
``json`` standard.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

BASE = Path("/home/alain/Scrabble/data/dictionnaire/wiktionnaire-kaikki")
SOURCE = BASE / "fr-extract.jsonl"
DESTINATION = BASE / "fr-filtre.jsonl"


def extraire() -> None:
    debut = time.monotonic()
    lignes_lues = 0
    entrees_retenues = 0

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
            sortie.write(json.dumps(minimal, ensure_ascii=False))
            sortie.write("\n")
            entrees_retenues += 1

    duree = time.monotonic() - debut
    taille = DESTINATION.stat().st_size

    print(f"Lignes lues (source)     : {lignes_lues}")
    print(f"Entrées françaises retenues : {entrees_retenues}")
    print(f"Temps d'exécution total  : {duree:.1f} s")
    print(f"Taille de {DESTINATION.name} : {taille} octets ({taille / 1_048_576:.1f} Mio)")


if __name__ == "__main__":
    extraire()
