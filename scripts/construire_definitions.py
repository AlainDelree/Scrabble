#!/usr/bin/env python3
"""Construction du fichier final de définitions Scrabble (issue #15, suite de #13).

À partir du Wiktionnaire français filtré ``fr-filtre.jsonl`` (une entrée JSON par
ligne : ``word`` / ``pos`` / ``glosses``, cf. issue #13), on reconstruit l'index
mot → liste de définitions, puis on le **restreint aux seuls mots de l'ODS8** :
les ~1,68 M de mots hors ODS8 sont inutiles au jeu et ne sont pas conservés.

Principe (mêmes règles que le diagnostic de couvertures précédent) :

* lecture **en streaming** ligne par ligne de ``fr-filtre.jsonl`` (~279 Mio) ;
* clé = ``normaliser_mot(word)`` (MAJUSCULES, accents conservés, NFC) ;
* **homographes fusionnés** : toutes les gloses des entrées d'un même mot
  normalisé sont concaténées dans une seule liste (l'ordre de lecture est
  préservé ; les gloses strictement dupliquées sont ignorées) ;
* on ne garde en mémoire l'index que pour les mots présents dans l'ODS8 ;
* sérialisation JSON dans ``data/dictionnaire/definitions.json`` (gitignoré).

Le croisement de l'issue précédente a mesuré 61,48 % de couverture
(252 958 / 411 430 mots, 1,73 déf/mot) : on retrouve cet ordre de grandeur.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from scrabble.dictionnaire.dictionnaire import (
    CHEMIN_DEFINITIONS,
    charger_ods,
    normaliser_mot,
)

BASE = Path("/home/alain/Scrabble/data/dictionnaire/wiktionnaire-kaikki")
SOURCE = BASE / "fr-filtre.jsonl"


def construire() -> None:
    debut = time.monotonic()

    ods = charger_ods()
    print(f"Mots ODS8 chargés        : {len(ods)}")

    definitions: dict[str, list[str]] = {}
    lignes_lues = 0

    with SOURCE.open("r", encoding="utf-8") as source:
        for ligne in source:
            lignes_lues += 1
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue

            mot = normaliser_mot(entree.get("word") or "")
            if not mot or mot not in ods:
                continue

            gloses = entree.get("glosses") or []
            if not gloses:
                continue

            liste = definitions.setdefault(mot, [])
            for glose in gloses:
                if glose and glose not in liste:
                    liste.append(glose)

    # Un mot ODS peut n'avoir eu que des entrées sans glose : on ne garde que
    # les mots effectivement dotés d'au moins une définition.
    definitions = {mot: gloses for mot, gloses in definitions.items() if gloses}

    CHEMIN_DEFINITIONS.parent.mkdir(parents=True, exist_ok=True)
    with CHEMIN_DEFINITIONS.open("w", encoding="utf-8") as sortie:
        json.dump(definitions, sortie, ensure_ascii=False)

    duree = time.monotonic() - debut
    total_defs = sum(len(g) for g in definitions.values())
    couverture = 100 * len(definitions) / len(ods) if ods else 0
    moyenne = total_defs / len(definitions) if definitions else 0
    taille = CHEMIN_DEFINITIONS.stat().st_size

    print(f"Lignes lues (fr-filtre)  : {lignes_lues}")
    print(f"Mots ODS8 avec définition: {len(definitions)}")
    print(f"Couverture ODS8          : {couverture:.2f} %")
    print(f"Définitions totales      : {total_defs} ({moyenne:.2f} déf/mot)")
    print(f"Temps d'exécution total  : {duree:.1f} s")
    print(
        f"Taille de {CHEMIN_DEFINITIONS.name} : {taille} octets "
        f"({taille / 1_048_576:.1f} Mio)"
    )


if __name__ == "__main__":
    construire()
