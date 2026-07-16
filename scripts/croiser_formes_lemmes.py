#!/usr/bin/env python3
"""Diagnostic : table forme→lemme et gain de couverture ODS8 (issue #17, suite de #16).

Le croisement direct ``fr-filtre.jsonl`` × ODS8 (issue #15) plafonnait à
**61,48 %** de couverture (252 958 / 411 430 mots). Deux causes se cumulent :

1. Le Wiktionnaire attache ses gloses au **lemme** (infinitif, masculin
   singulier…), pas aux **formes fléchies** (conjugaisons, féminins, pluriels).
   L'ODS8, lui, liste toutes les formes jouables : d'où des formes orphelines.
2. **Le fichier ODS8 est purement ASCII (sans accents ni ligatures)** :
   ``ABAISSAMES``, ``ELEVE``, ``COEUR``… alors que ``normaliser_mot`` et le
   Wiktionnaire **conservent** les accents (``ABAISSÂMES``, ``ÉLÈVE``, ``CŒUR``).
   Conséquence mesurée : ``definitions.json`` ne contient **aucune** clé
   accentuée — la construction de l'issue #15 a rejeté silencieusement tout
   mot français accentué. Le matching « accents conservés » demandé par
   l'issue rate donc mécaniquement toutes les formes accentuées.

Ce script mesure les DEUX approches pour éclairer la décision de fusion :

* **Passe A — accents conservés** (normalisation stricte ``normaliser_mot``,
  comme demandé littéralement par l'issue) ;
* **Passe B — insensible aux accents** (``désaccentuer`` : Œ→OE, Æ→AE, chute
  des diacritiques), qui reflète la réalité du fichier ODS8 et donne le
  **gain de couverture réel** exploitable.

C'est un **diagnostic de faisabilité** : il ne modifie AUCUN fichier de
données (``definitions.json`` reste intact). Toutes les lectures de fichiers
volumineux se font **en streaming** ligne à ligne.

Nettoyage des formes
--------------------
Les formes verbales sont livrées avec leur habillage pronominal/périphrastique :
``"je lis"``, ``"il/elle/on lit"``, ``"qu'ils/elles lisent"``, ``"en lisant"``,
``"avoir lu"``, ``"je me baisse"``… On n'en garde que le mot simple jouable :

1. normalisation de l'apostrophe typographique U+2019 → U+0027 d'abord ;
2. retrait **itératif** des préfixes pronominaux / périphrastiques / élidés en
   tête (``"je "``, ``"il/elle/on "``, ``"qu'"``, ``"j'"``, ``"me "``,
   ``"avoir "``, ``"en "``…) — un verbe pronominal en empile plusieurs
   (``"nous nous baissons"`` → ``"baissons"``) ;
3. après nettoyage, la forme doit être un **mot simple Scrabble** (via
   :func:`est_mot_scrabble` : lettres jouables uniquement, donc ni espace
   résiduel, ni apostrophe, ni barre oblique, ni trait d'union). Toute forme
   composée survivante (temps composés ``"ai lu"``…) est rejetée — son
   participe est de toute façon capté par la forme simple.
"""

from __future__ import annotations

import json
import time
import unicodedata
from pathlib import Path

from scrabble.dictionnaire.dictionnaire import (
    charger_definitions,
    charger_ods,
    est_mot_scrabble,
    normaliser_mot,
)

BASE = Path("/home/alain/Scrabble/data/dictionnaire/wiktionnaire-kaikki")
SOURCE_FORMES = BASE / "fr-filtre-formes.jsonl"
SOURCE_FILTRE = BASE / "fr-filtre.jsonl"

# --------------------------------------------------------------------------- #
# Préfixes à retirer en tête de forme (après normalisation de l'apostrophe)
# --------------------------------------------------------------------------- #

# Préfixes terminés par une espace : pronoms sujets (isolés et groupés tels que
# le Wiktionnaire les écrit), pronoms réfléchis/objets, conjonction « que »,
# marqueurs de gérondif/négation, auxiliaires des infinitifs/gérondifs passés.
PREFIXES_ESPACE = [
    "je ", "tu ", "il ", "elle ", "on ", "nous ", "vous ", "ils ", "elles ",
    "il/elle/on ", "ils/elles ", "il/elle ", "elle/on ",
    "me ", "te ", "se ", "y ",
    "ne ", "en ", "que ",
    "avoir ", "être ",
]
# Préfixes élidés terminés par une apostrophe simple.
PREFIXES_ELISION = [
    "j'", "n'", "qu'", "m'", "t'", "s'", "c'", "l'", "d'",
]
# Correspondance gloutonne : les plus longs d'abord.
PREFIXES = sorted(PREFIXES_ESPACE + PREFIXES_ELISION, key=len, reverse=True)


def desaccentuer(mot: str) -> str:
    """Retire accents et ligatures d'un mot déjà normalisé (MAJUSCULES/NFC).

    Reproduit la graphie ASCII de l'ODS8 : ligatures Œ→OE, Æ→AE puis chute de
    tous les diacritiques combinants (É→E, Â→A, Ï→I, Ç→C…).
    """
    mot = mot.replace("Œ", "OE").replace("Æ", "AE")
    decompose = unicodedata.normalize("NFD", mot)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def nettoyer_forme(forme: str) -> str | None:
    """Nettoie une forme fléchie ; renvoie le mot simple normalisé ou ``None``."""
    f = forme.replace("’", "'").strip()

    change = True
    while change:
        change = False
        for prefixe in PREFIXES:
            if f.startswith(prefixe):
                f = f[len(prefixe):].strip()
                change = True
                break

    norm = normaliser_mot(f)
    if norm and est_mot_scrabble(norm):
        return norm
    return None


def _ajouter(table: dict[str, object], cle: str, lemme: str) -> None:
    """Ajoute ``lemme`` à ``table[cle]`` : str tant qu'unique, list dès collision."""
    courant = table.get(cle)
    if courant is None:
        table[cle] = lemme
    elif isinstance(courant, str):
        if courant != lemme:
            table[cle] = [courant, lemme]
    else:  # list
        if lemme not in courant:
            courant.append(lemme)


def _lemmes(valeur: object) -> list[str]:
    if valeur is None:
        return []
    if isinstance(valeur, str):
        return [valeur]
    return list(valeur)  # type: ignore[arg-type]


def construire_tables() -> tuple[dict[str, object], dict[str, object], dict]:
    """Construit en un seul passage les deux tables forme→lemme(s).

    * ``table_strict`` : forme normalisée (accents conservés) → lemme(s)
      normalisé(s) — l'approche littérale de l'issue.
    * ``table_da`` : forme désaccentuée → lemme(s) désaccentué(s) — l'approche
      réaliste alignée sur la graphie ASCII de l'ODS8.
    """
    table_strict: dict[str, object] = {}
    table_da: dict[str, object] = {}
    stats = {
        "lignes": 0,
        "entrees_avec_formes": 0,
        "formes_vues": 0,
        "formes_retenues": 0,
        "exemples": [],
    }

    with SOURCE_FORMES.open("r", encoding="utf-8") as source:
        for ligne in source:
            stats["lignes"] += 1
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue

            formes = entree.get("forms")
            if not formes:
                continue
            stats["entrees_avec_formes"] += 1

            lemme = normaliser_mot(entree.get("word") or "")
            if not lemme:
                continue
            lemme_da = desaccentuer(lemme)

            for objet in formes:
                brut = objet.get("form") if isinstance(objet, dict) else None
                if not brut:
                    continue
                stats["formes_vues"] += 1

                propre = nettoyer_forme(brut)
                if propre is None:
                    continue
                stats["formes_retenues"] += 1

                if (
                    len(stats["exemples"]) < 12
                    and brut.strip() != propre
                    and " " in brut
                ):
                    stats["exemples"].append((brut, propre))

                _ajouter(table_strict, propre, lemme)
                _ajouter(table_da, desaccentuer(propre), lemme_da)

    return table_strict, table_da, stats


def charger_gloses() -> tuple[dict[str, str], dict[str, str]]:
    """Index lemme→première glose, en versions stricte et désaccentuée.

    Un seul passage streaming sur ``fr-filtre.jsonl``. On ne conserve que la
    première glose (tronquée) de chaque lemme : suffisant pour compter la
    présence d'une définition et fournir un échantillon, mémoire bornée.
    """
    gloses_strict: dict[str, str] = {}
    gloses_da: dict[str, str] = {}
    with SOURCE_FILTRE.open("r", encoding="utf-8") as source:
        for ligne in source:
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            lemme = normaliser_mot(entree.get("word") or "")
            if not lemme:
                continue
            gloses = entree.get("glosses") or []
            premiere = next((g for g in gloses if g), None)
            if not premiere:
                continue
            premiere = premiere[:200]
            gloses_strict.setdefault(lemme, premiere)
            gloses_da.setdefault(desaccentuer(lemme), premiere)
    return gloses_strict, gloses_da


def mesurer_passe(
    nom: str,
    ods_cles: set[str],
    directs: set[str],
    table: dict[str, object],
    gloses: dict[str, str],
) -> dict:
    """Mesure la couverture d'une passe (directs + rattachement forme→lemme).

    ``ods_cles`` : ensemble des mots ODS8 selon la clé de la passe (stricte ou
    désaccentuée). ``directs`` : clés ODS déjà couvertes en direct pour cette
    passe. Renvoie un dict de métriques + échantillons.
    """
    non_couverts = ods_cles - directs
    nouveaux: dict[str, tuple[str, str]] = {}
    candidats_sans_glose: dict[str, list[str]] = {}
    for mot in non_couverts:
        lemmes = _lemmes(table.get(mot))
        if not lemmes:
            continue
        trouve = False
        for lemme in lemmes:
            glose = gloses.get(lemme)
            if glose:
                nouveaux[mot] = (lemme, glose)
                trouve = True
                break
        if not trouve:
            candidats_sans_glose[mot] = lemmes

    total = len(ods_cles)
    avant = 100 * len(directs) / total if total else 0.0
    apres = 100 * (len(directs) + len(nouveaux)) / total if total else 0.0
    return {
        "nom": nom,
        "total": total,
        "directs": len(directs),
        "non_couverts_avant": len(non_couverts),
        "nouveaux": nouveaux,
        "encore_non_couverts": non_couverts - set(nouveaux),
        "candidats_sans_glose": candidats_sans_glose,
        "avant": avant,
        "apres": apres,
    }


def _afficher_passe(res: dict, ods_da_de_strict: dict | None = None) -> None:
    print(f"\n===== {res['nom']} =====")
    print(f"Mots ODS8 (clé passe)           : {res['total']}")
    print(f"Couverts en direct              : {res['directs']}")
    print(f"Non couverts avant rattachement : {res['non_couverts_avant']}")
    print(f"Nouvellement couverts (forme→lemme) : {len(res['nouveaux'])}")
    print(f"Couverture avant                : {res['avant']:.2f} %")
    print(f"Couverture après                : {res['apres']:.2f} %")
    print(f"Gain                            : +{res['apres'] - res['avant']:.2f} points")
    print(f"Mots encore non couverts        : {len(res['encore_non_couverts'])}")

    print("\n  Échantillon 10 mots nouvellement couverts (mot → lemme : déf) :")
    for mot in sorted(res["nouveaux"])[:10]:
        lemme, glose = res["nouveaux"][mot]
        g = glose if len(glose) <= 88 else glose[:85] + "…"
        print(f"    {mot:16s} → {lemme:16s} : {g}")

    print("\n  Échantillon 10 mots encore non couverts :")
    for mot in sorted(res["encore_non_couverts"])[:10]:
        if mot in res["candidats_sans_glose"]:
            raison = "lemme(s) sans glose : " + ", ".join(res["candidats_sans_glose"][mot])
        else:
            raison = "aucun lemme dans la table"
        print(f"    {mot:16s} ({raison})")


def diagnostiquer() -> None:
    debut = time.monotonic()

    print("Construction des tables forme→lemme (streaming fr-filtre-formes)…")
    table_strict, table_da, stats = construire_tables()
    collisions_s = sum(1 for v in table_strict.values() if isinstance(v, list))
    collisions_d = sum(1 for v in table_da.values() if isinstance(v, list))
    t_tables = time.monotonic() - debut

    print(f"Lignes lues (formes)            : {stats['lignes']}")
    print(f"Entrées avec forms non vide     : {stats['entrees_avec_formes']}")
    print(f"Formes brutes examinées         : {stats['formes_vues']}")
    print(f"Formes retenues (mot simple)    : {stats['formes_retenues']}")
    print(f"Table STRICTE : {len(table_strict)} formes, {collisions_s} collisions")
    print(f"Table DÉSACC. : {len(table_da)} formes, {collisions_d} collisions")
    print(f"Temps construction tables       : {t_tables:.1f} s")

    print("\nExemples de nettoyage de formes (avant → après) :")
    for brut, propre in stats["exemples"][:5]:
        print(f"    {brut!r:42s} → {propre}")

    # --- ODS8 et gloses -----------------------------------------------------
    ods = charger_ods()
    definitions = charger_definitions()  # clés = mots ODS couverts en direct (strict)
    print(f"\nMots ODS8 (fichier)             : {len(ods)}")

    print("Chargement des gloses des lemmes (streaming fr-filtre.jsonl)…")
    gloses_strict, gloses_da = charger_gloses()
    print(f"Lemmes glosés (strict / désacc.) : {len(gloses_strict)} / {len(gloses_da)}")

    # --- PASSE A : stricte (accents conservés), comme demandé ----------------
    directs_strict = set(definitions)
    res_a = mesurer_passe(
        "PASSE A — accents conservés (littéral issue)",
        ods, directs_strict, table_strict, gloses_strict,
    )
    _afficher_passe(res_a)

    # --- PASSE B : insensible aux accents (réalité ODS8 ASCII) ----------------
    ods_da = {desaccentuer(m) for m in ods}
    # Couverture directe désaccentuée : un mot ODS est couvert si un lemme glosé
    # se désaccentue vers lui (ods_da ∩ clés gloses_da).
    directs_da = ods_da & set(gloses_da)
    res_b = mesurer_passe(
        "PASSE B — insensible aux accents (réalité ODS8)",
        ods_da, directs_da, table_da, gloses_da,
    )
    _afficher_passe(res_b)

    duree = time.monotonic() - debut
    print(f"\nTemps d'exécution total         : {duree:.1f} s")


if __name__ == "__main__":
    diagnostiquer()
