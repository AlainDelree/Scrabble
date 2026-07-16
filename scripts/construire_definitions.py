#!/usr/bin/env python3
"""Construction du fichier final de définitions Scrabble (issue #18, suite de #17).

À partir du Wiktionnaire français filtré ``fr-filtre.jsonl`` (une entrée JSON par
ligne : ``word`` / ``pos`` / ``glosses``, cf. issue #13), on reconstruit l'index
mot → liste de définitions **restreint aux seuls mots de l'ODS8**.

Pourquoi cette version diffère de l'issue #15
---------------------------------------------
La première construction (issue #15) faisait un croisement *strict* (accents
conservés) entre ``normaliser_mot(word)`` et l'ODS8. Elle plafonnait à
**61,48 %** de couverture. Le diagnostic de l'issue #17
(``scripts/croiser_formes_lemmes.py``) a établi que la cause principale est un
**décalage d'accents** : le fichier ODS8 est purement ASCII (``ELEVE``,
``COEUR``, ``ABAISSAMES``) alors que le Wiktionnaire et ``normaliser_mot``
conservent les accents et ligatures (``ÉLÈVE``, ``CŒUR``, ``ABAISSÂMES``).
Aucune clé accentuée ne pouvait donc matcher un mot ODS8.

Deux gains cumulés, mesurés par le diagnostic :

1. **Désaccentuation du matching** (Œ→OE, Æ→AE, chute des diacritiques) : porte
   la couverture directe à **97,46 %**. La clé stockée reste le mot ODS8 tel
   quel (ASCII), la ou les définitions viennent du/des lemme(s) trouvé(s) par
   équivalence désaccentuée.
2. **Rattachement forme→lemme** (``fr-filtre-formes.jsonl``) : pour un mot ODS8
   sans correspondance directe (une forme fléchie, dont le Wiktionnaire ne
   glose que le lemme), on remonte au(x) lemme(s) via la table forme→lemme
   désaccentuée et on prend leurs définitions. Gain : **+0,36 pt → 97,82 %**.

Principe et invariants
----------------------
* lectures **en streaming** ligne par ligne des deux fichiers volumineux ;
* la **clé** de ``definitions.json`` est toujours le mot ODS8 (ASCII, cohérent
  avec le reste du dictionnaire) — on ne stocke jamais de clé accentuée ;
* **fusion des homographes et des variantes d'accent** : toutes les gloses des
  entrées dont le lemme se désaccentue vers le même mot ODS8 sont concaténées
  (ordre de lecture préservé, gloses strictement dupliquées ignorées) — c'est
  le comportement « homographes fusionnés » de l'issue #15, étendu au fait que
  ``ÉLÈVE`` (nom), ``ÉLEVÉ`` (adjectif)… retombent tous sur ``ELEVE`` ;
* le rattachement forme→lemme n'est tenté **que** pour les mots ODS8 sans
  correspondance directe (point 3 de l'issue #18) ;
* en cas de plusieurs lemmes candidats (collision), leurs définitions sont
  toutes fusionnées (dédupliquées) dans la liste (point 4).

La logique de désaccentuation et de nettoyage des formes est **réutilisée** du
script de diagnostic ``croiser_formes_lemmes.py`` (fonctions ``desaccentuer``,
``nettoyer_forme``, ``_ajouter``, ``_lemmes``) plutôt que réécrite.

Sérialisation JSON dans ``data/dictionnaire/definitions.json`` (gitignoré).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Le script de diagnostic vit dans le même dossier ``scripts/`` : quand ce
# fichier est exécuté (``python scripts/construire_definitions.py``), Python
# place son dossier en tête de ``sys.path`` et l'import direct fonctionne. On
# l'assure explicitement pour rester robuste quel que soit le répertoire courant.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from croiser_formes_lemmes import (  # noqa: E402  (import après ajustement sys.path)
    _ajouter,
    _lemmes,
    desaccentuer,
    nettoyer_forme,
)

from scrabble.dictionnaire.dictionnaire import (  # noqa: E402
    CHEMIN_DEFINITIONS,
    charger_ods,
    normaliser_mot,
)

BASE = Path("/home/alain/Scrabble/data/dictionnaire/wiktionnaire-kaikki")
SOURCE_FILTRE = BASE / "fr-filtre.jsonl"
SOURCE_FORMES = BASE / "fr-filtre-formes.jsonl"


def construire_table_da(ods_da: set[str]) -> tuple[dict[str, object], int]:
    """Construit la table forme→lemme **désaccentuée** (fallback forme→lemme).

    Un seul passage streaming sur ``fr-filtre-formes.jsonl``. Pour économiser la
    mémoire (par rapport à ``croiser_formes_lemmes.construire_tables`` qui bâtit
    aussi la table stricte), on ne retient que les entrées ``forme_da → lemme_da``
    **dont la forme désaccentuée correspond à un mot ODS8** : seules celles-là
    pourront servir de rattachement. Renvoie la table et le nombre de collisions.
    """
    table_da: dict[str, object] = {}
    with SOURCE_FORMES.open("r", encoding="utf-8") as source:
        for ligne in source:
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue

            formes = entree.get("forms")
            if not formes:
                continue

            lemme = normaliser_mot(entree.get("word") or "")
            if not lemme:
                continue
            lemme_da = desaccentuer(lemme)

            for objet in formes:
                brut = objet.get("form") if isinstance(objet, dict) else None
                if not brut:
                    continue
                propre = nettoyer_forme(brut)
                if propre is None:
                    continue
                forme_da = desaccentuer(propre)
                if forme_da in ods_da:
                    _ajouter(table_da, forme_da, lemme_da)

    collisions = sum(1 for v in table_da.values() if isinstance(v, list))
    return table_da, collisions


def charger_gloses_par_lemme_da(besoins: set[str]) -> dict[str, list[str]]:
    """Index lemme_da → liste de **toutes** les gloses, restreint aux ``besoins``.

    Un seul passage streaming sur ``fr-filtre.jsonl``. On n'accumule les gloses
    que pour les lemmes désaccentués effectivement utiles (mot ODS8 en direct,
    ou lemme cible d'un rattachement forme→lemme) : mémoire bornée. Les gloses
    des homographes / variantes d'accent d'un même lemme_da sont fusionnées,
    dupliquées ignorées, ordre de lecture préservé.
    """
    gloses_par_lemme: dict[str, list[str]] = {}
    with SOURCE_FILTRE.open("r", encoding="utf-8") as source:
        for ligne in source:
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue

            lemme = normaliser_mot(entree.get("word") or "")
            if not lemme:
                continue
            lemme_da = desaccentuer(lemme)
            if lemme_da not in besoins:
                continue

            gloses = entree.get("glosses") or []
            if not gloses:
                continue
            liste = gloses_par_lemme.setdefault(lemme_da, [])
            for glose in gloses:
                if glose and glose not in liste:
                    liste.append(glose)
    return gloses_par_lemme


def construire() -> None:
    debut = time.monotonic()

    ods = charger_ods()
    print(f"Mots ODS8 chargés               : {len(ods)}")

    # L'ODS8 est purement ASCII : ``desaccentuer`` y est l'identité et il n'y a
    # donc pas de collision entre deux mots ODS distincts. On garde malgré tout
    # la correspondance da → mot ODS pour rester robuste et lisible.
    ods_da: dict[str, str] = {desaccentuer(mot): mot for mot in ods}
    print(f"Clés ODS8 désaccentuées         : {len(ods_da)}")

    # --- Table de rattachement forme→lemme (désaccentuée), bornée à l'ODS8 ----
    print("Construction table forme→lemme (streaming fr-filtre-formes)…")
    table_da, collisions = construire_table_da(set(ods_da))
    print(f"Formes ODS8 rattachables         : {len(table_da)} ({collisions} collisions)")

    # --- Lemmes dont on aura besoin des gloses --------------------------------
    # Direct : le lemme_da est lui-même un mot ODS8 (clé de ods_da).
    # Fallback : tous les lemmes cibles de la table forme→lemme.
    besoins: set[str] = set(ods_da)
    for valeur in table_da.values():
        besoins.update(_lemmes(valeur))

    print("Chargement des gloses des lemmes (streaming fr-filtre)…")
    gloses_par_lemme = charger_gloses_par_lemme_da(besoins)
    print(f"Lemmes glosés retenus            : {len(gloses_par_lemme)}")

    # --- Assemblage de l'index final ------------------------------------------
    definitions: dict[str, list[str]] = {}
    directs = 0
    fallback = 0
    for mot in ods:
        mot_da = desaccentuer(mot)

        # 1) Correspondance directe désaccentuée : le mot ODS8 est (une variante
        #    d'accent d')un lemme glosé. Toutes ses gloses (homographes inclus)
        #    ont été fusionnées sous mot_da.
        gloses = gloses_par_lemme.get(mot_da)
        if gloses:
            definitions[mot] = list(gloses)
            directs += 1
            continue

        # 2) Pas de direct : rattachement forme→lemme. On fusionne (dédupliqué)
        #    les gloses de tous les lemmes candidats de la forme.
        liste: list[str] = []
        for lemme_da in _lemmes(table_da.get(mot_da)):
            for glose in gloses_par_lemme.get(lemme_da, ()):  # type: ignore[arg-type]
                if glose not in liste:
                    liste.append(glose)
        if liste:
            definitions[mot] = liste
            fallback += 1

    CHEMIN_DEFINITIONS.parent.mkdir(parents=True, exist_ok=True)
    with CHEMIN_DEFINITIONS.open("w", encoding="utf-8") as sortie:
        json.dump(definitions, sortie, ensure_ascii=False)

    duree = time.monotonic() - debut
    total_defs = sum(len(g) for g in definitions.values())
    couverts = len(definitions)
    couverture = 100 * couverts / len(ods) if ods else 0
    moyenne = total_defs / couverts if couverts else 0
    taille = CHEMIN_DEFINITIONS.stat().st_size

    print(f"Couverts en direct (désacc.)     : {directs}")
    print(f"Couverts via forme→lemme         : {fallback}")
    print(f"Mots ODS8 avec définition        : {couverts}")
    print(f"Couverture ODS8                  : {couverture:.2f} %")
    print(f"Définitions totales              : {total_defs} ({moyenne:.2f} déf/mot)")
    print(f"Temps d'exécution total          : {duree:.1f} s")
    print(
        f"Taille de {CHEMIN_DEFINITIONS.name} : {taille} octets "
        f"({taille / 1_048_576:.1f} Mio)"
    )


if __name__ == "__main__":
    construire()
