#!/usr/bin/env python3
"""Croisement ODS8 × Lexique 3 → ensemble des « mots courants » (issue #205, suite de #203).

Contexte
--------
Le rapport d'investigation #203 a retenu **Lexique 3** (lexique.org, v3.83,
licence CC-BY-SA 4.0) comme source de fréquence lexicale. Le but : distinguer,
parmi les 411 430 formes de l'ODS8, celles qui sont réellement *courantes* dans
le français écrit/parlé de celles (formes fléchies rares, termes techniques…)
qui n'apparaissent dans aucun corpus de fréquence usuel. La future issue C
consommera l'ensemble produit ici pour restreindre le vocabulaire par défaut de
l'IA — ce script se contente de **construire et mesurer**, il ne câble aucun
filtre.

Le fichier de fréquence
-----------------------
``Lexique383.tsv`` (~25 Mo) est un dictionnaire tiers volumineux : comme l'ODS8
et Hunspell, il est déposé **manuellement** par Alain dans ``data/dictionnaire/``
(gitignoré, jamais commité). Source : https://www.lexique.org (CC-BY-SA 4.0).
Colonnes utilisées (repérées par leur en-tête, pas par position) : ``ortho``
(forme de surface), ``freqlivres`` et ``freqfilms2`` (occurrences par million de
mots, corpus de livres et de sous-titres de films). Si le fichier est absent, le
script s'arrête proprement avec un message clair (aucun plantage).

Normalisation — le piège des accents (point 4 de l'issue)
---------------------------------------------------------
Le fichier ODS8 de ce projet est stocké **entièrement sans accents** (``ABBE``,
``ELEVE``, ``ABCES`` — vérifié : 0 ligne accentuée sur 411 430), ce qui est
naturel puisque les tuiles du Scrabble ne portent pas d'accent. Lexique, lui,
est accentué (``abbé``, ``élève``, ``abcès``). Un croisement naïf (accents
conservés) perd donc **~42 000 correspondances** (toutes les formes accentuées).
On croise donc sur la clé **désaccentuée** (:func:`desaccentuer`), qui reproduit
exactement la graphie ASCII de l'ODS8. C'est cette désaccentuation qui fait
remonter l'intersection de ~75 k (18 %) à ~112 k (27 %), confirmant l'ordre de
grandeur 100-130 k / 25-35 % annoncé par le rapport #203.

Seuil de fréquence
------------------
L'appartenance à Lexique se double d'un **seuil de fréquence** : une forme peut
figurer dans Lexique tout en étant quasi absente des corpus (fréquence proche de
0). Le seuil par défaut est **1 occurrence par million** (``--seuil 1.0``) sur
l'**union** des deux corpus (``--corpus union`` : ``max(freqlivres, freqfilms2)``) :
1/million est un seuil de familiarité classique en psycholinguistique, et
combiner livres + sous-titres capte à la fois le vocabulaire écrit et le
vocabulaire parlé courant. Le seuil et le corpus sont réglables en ligne de
commande ; ``--dry-run`` affiche la mesure de couverture sans rien écrire.

Le script rapporte systématiquement, en plus de l'ensemble retenu, l'intersection
**brute** (présence dans Lexique, sans seuil) et un balayage de seuils, pour que
l'issue C ou Alain puisse retendre le curseur en connaissance de cause.

Format de sortie (point 3)
--------------------------
Un fichier texte simple, **un mot par ligne, trié, normalisé comme l'ODS8**
(``data/dictionnaire/mots_courants.txt``, gitignoré comme les autres). Ce format
est directement relisible par ``lire_liste_mots`` (même convention que
``mots_ajoutes_*`` / ``classiques_ajoutes.txt``) : l'issue C n'aura qu'à charger
cet ensemble et le croiser avec le dictionnaire actif.

Usage
-----
    python scripts/generer_mots_courants.py            # construit mots_courants.txt
    python scripts/generer_mots_courants.py --dry-run  # mesure seule, sans écrire
    python scripts/generer_mots_courants.py --seuil 2  # seuil 2/million
    python scripts/generer_mots_courants.py --corpus livres  # freqlivres seul

Nécessite l'ODS8 et ``Lexique383.tsv`` présents dans ``data/dictionnaire/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Exécuté en tant que script : on ajoute ``src/`` au chemin d'import pour
# retrouver le paquet ``scrabble`` quel que soit le répertoire courant.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scrabble.dictionnaire.dictionnaire import (  # noqa: E402
    DOSSIER_DICO,
    _reecrire_liste_mots,
    charger_ods,
    desaccentuer,
    normaliser_mot,
)

# Emplacements par défaut (dans le dossier gitignoré des dictionnaires tiers).
CHEMIN_LEXIQUE = DOSSIER_DICO / "Lexique383.tsv"
CHEMIN_MOTS_COURANTS = DOSSIER_DICO / "mots_courants.txt"

# Corpus de fréquence sélectionnables et colonnes Lexique correspondantes.
COLONNES_CORPUS: dict[str, tuple[str, ...]] = {
    "livres": ("freqlivres",),
    "films": ("freqfilms2",),
    "union": ("freqlivres", "freqfilms2"),
}

SEUIL_DEFAUT = 1.0
CORPUS_DEFAUT = "union"

# Nombre total de formes de l'ODS8, utilisé comme dénominateur de couverture.
# (Mesuré dynamiquement, mais rappelé ici pour le rapport #203 : 411 430.)


def lire_frequences_lexique(
    chemin: Path = CHEMIN_LEXIQUE,
) -> dict[str, tuple[float, float]]:
    """Lit ``Lexique383.tsv`` → ``{clé_désaccentuée: (freqlivres, freqfilms2)}``.

    La clé est ``desaccentuer(normaliser_mot(ortho))`` (MAJUSCULES, sans accent),
    exactement la graphie de l'ODS8. Les colonnes sont repérées par leur en-tête
    (``ortho``, ``freqlivres``, ``freqfilms2``), pas par position, pour survivre à
    un éventuel réordonnancement. Plusieurs lignes peuvent partager la même clé
    (homographes, ou formes accentuées distinctes fondues par désaccentuation :
    p. ex. ``côté`` et ``cote`` → ``COTE``) : on retient le **maximum** de chaque
    fréquence, la forme la plus courante primant.

    Lève ``FileNotFoundError`` si le fichier est absent (le fichier est déposé
    manuellement — voir l'en-tête du module) ; l'appelant (:func:`main`) traduit
    cela en message clair. Les lignes malformées (fréquence non numérique) sont
    ignorées silencieusement.
    """
    frequences: dict[str, tuple[float, float]] = {}
    with open(chemin, "r", encoding="utf-8") as fichier:
        entete = fichier.readline().rstrip("\n").split("\t")
        try:
            i_ortho = entete.index("ortho")
            i_livres = entete.index("freqlivres")
            i_films = entete.index("freqfilms2")
        except ValueError as exc:
            raise ValueError(
                "En-tête Lexique inattendu : colonnes 'ortho', 'freqlivres' et "
                "'freqfilms2' introuvables. Fichier corrompu ou format différent ?"
            ) from exc
        largeur_min = max(i_ortho, i_livres, i_films) + 1
        for ligne in fichier:
            colonnes = ligne.rstrip("\n").split("\t")
            if len(colonnes) < largeur_min:
                continue
            cle = desaccentuer(normaliser_mot(colonnes[i_ortho]))
            if not cle:
                continue
            try:
                freq_livres = float(colonnes[i_livres])
                freq_films = float(colonnes[i_films])
            except ValueError:
                continue
            precedent = frequences.get(cle)
            if precedent is None:
                frequences[cle] = (freq_livres, freq_films)
            else:
                frequences[cle] = (
                    max(precedent[0], freq_livres),
                    max(precedent[1], freq_films),
                )
    return frequences


def frequence_corpus(
    valeurs: tuple[float, float], corpus: str
) -> float:
    """Fréquence retenue pour un mot selon le ``corpus`` choisi.

    ``valeurs`` est le couple ``(freqlivres, freqfilms2)``. ``union`` prend le
    maximum des deux (le mot est courant s'il l'est dans au moins un corpus) ;
    ``livres`` / ``films`` isolent une colonne.
    """
    freq_livres, freq_films = valeurs
    if corpus == "livres":
        return freq_livres
    if corpus == "films":
        return freq_films
    return max(freq_livres, freq_films)


def selectionner_mots_courants(
    frequences: dict[str, tuple[float, float]],
    mots_ods: set[str],
    seuil: float = SEUIL_DEFAUT,
    corpus: str = CORPUS_DEFAUT,
) -> set[str]:
    """Mots de l'ODS8 présents dans Lexique avec une fréquence ≥ ``seuil``.

    On n'itère que sur l'intersection (mots ODS8 réellement dans Lexique), puis
    on applique le seuil sur la fréquence du ``corpus`` demandé. Le résultat est
    un sous-ensemble de ``mots_ods`` (donc de formes ODS8 valides).
    """
    return {
        mot
        for mot in mots_ods
        if mot in frequences
        and frequence_corpus(frequences[mot], corpus) >= seuil
    }


def mesurer_couverture(
    frequences: dict[str, tuple[float, float]],
    mots_ods: set[str],
    corpus: str = CORPUS_DEFAUT,
) -> dict[str, object]:
    """Calcule les statistiques de couverture (rapport #203).

    Retourne l'effectif ODS8, l'intersection brute (présence dans Lexique, tous
    seuils confondus) et un balayage de seuils pour le ``corpus`` demandé.
    """
    total = len(mots_ods)
    intersection = {mot for mot in mots_ods if mot in frequences}
    balayage = []
    for seuil in (0.5, 1.0, 2.0, 3.0, 5.0):
        retenus = selectionner_mots_courants(frequences, mots_ods, seuil, corpus)
        balayage.append((seuil, len(retenus)))
    return {
        "total_ods": total,
        "intersection_brute": len(intersection),
        "balayage": balayage,
        "corpus": corpus,
    }


def _pourcent(part: int, total: int) -> str:
    return f"{100 * part / total:.1f}%" if total else "n/a"


def afficher_couverture(stats: dict[str, object]) -> None:
    """Affiche le rapport de couverture sur stdout."""
    total = stats["total_ods"]
    brute = stats["intersection_brute"]
    print(f"ODS8 total ............................. {total}")
    print(
        f"Intersection brute ODS×Lexique ......... {brute} "
        f"({_pourcent(brute, total)}) "
        "— présence dans Lexique, sans seuil"
    )
    print(f"Balayage de seuils (corpus « {stats['corpus']} », occ./million) :")
    for seuil, effectif in stats["balayage"]:
        print(
            f"  freq ≥ {seuil:>3} .................... {effectif} "
            f"({_pourcent(effectif, total)})"
        )


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "--lexique",
        type=Path,
        default=CHEMIN_LEXIQUE,
        help="chemin du fichier Lexique383.tsv (défaut : data/dictionnaire/)",
    )
    parseur.add_argument(
        "--sortie",
        type=Path,
        default=CHEMIN_MOTS_COURANTS,
        help="fichier de sortie « un mot par ligne » (défaut : mots_courants.txt)",
    )
    parseur.add_argument(
        "--seuil",
        type=float,
        default=SEUIL_DEFAUT,
        help=f"seuil de fréquence (occ./million ; défaut : {SEUIL_DEFAUT})",
    )
    parseur.add_argument(
        "--corpus",
        choices=sorted(COLONNES_CORPUS),
        default=CORPUS_DEFAUT,
        help=f"corpus de fréquence (défaut : {CORPUS_DEFAUT})",
    )
    parseur.add_argument(
        "--dry-run",
        action="store_true",
        help="mesure la couverture sans écrire le fichier de sortie",
    )
    args = parseur.parse_args(argv)

    mots_ods = charger_ods()
    if not mots_ods:
        print(
            "ERREUR : ODS8 introuvable ou vide. Déposez le dictionnaire ODS8 "
            "dans data/dictionnaire/ (voir CONTEXTE.md).",
            file=sys.stderr,
        )
        return 2

    try:
        frequences = lire_frequences_lexique(args.lexique)
    except FileNotFoundError:
        print(
            f"ERREUR : fichier de fréquence introuvable : {args.lexique}\n"
            "  → Déposez « Lexique383.tsv » (~25 Mo) dans data/dictionnaire/.\n"
            "    Source : https://www.lexique.org (Lexique 3, v3.83, "
            "licence CC-BY-SA 4.0).\n"
            "  → Voir data/dictionnaire/README.md pour la procédure de dépôt.",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    print(f"Formes Lexique distinctes (désaccentuées) : {len(frequences)}")
    stats = mesurer_couverture(frequences, mots_ods, args.corpus)
    afficher_couverture(stats)

    courants = selectionner_mots_courants(
        frequences, mots_ods, args.seuil, args.corpus
    )
    print(
        f"\nMots courants retenus (corpus « {args.corpus} », seuil "
        f"{args.seuil}) : {len(courants)} "
        f"({_pourcent(len(courants), stats['total_ods'])} de l'ODS8)"
    )

    if args.dry_run:
        print("(--dry-run : aucun fichier écrit.)")
        return 0

    _reecrire_liste_mots(args.sortie, courants)
    print(f"Écrit dans {args.sortie} ({len(courants)} mots, triés).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
