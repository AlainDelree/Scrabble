"""Chargement et interrogation du dictionnaire de mots du Scrabble.

Rôle : construire la liste des mots autorisés à partir d'une source (ODS8 ou
Hunspell déplié), la corriger avec des listes locales d'ajouts/retraits, puis
offrir une validation rapide via un Trie mis en cache sur disque.

Chaîne de construction du dictionnaire final::

    (source_choisie ∪ mots_ajoutes) − mots_retires

où ``source_choisie`` dépend de ``config["source_dictionnaire"]`` :

* ``"ods"``      → liste ODS8 (un mot par ligne) ;
* ``"hunspell"`` → dépliage ("unmunch") du dictionnaire ``fr-toutesvariantes``.

Depuis l'issue #110, les listes d'ajouts/retraits sont **propres à chaque
source** (``mots_ajoutes_<source>.txt`` / ``mots_retires_<source>.txt``) : une
personnalisation faite en mode ODS ne s'applique pas au mode Hunspell et
inversement. La sélection de la paire se fait via :func:`chemins_modifs`.

Normalisation systématique de chaque mot au chargement : passage en MAJUSCULES
(les accents sont conservés — le Scrabble francophone distingue ``ELEVE`` de
``ÉLÈVE``) et suppression des espaces superflus.

Dépliage Hunspell
-----------------
Le dépliage s'appuie sur **spylls** (``pip install spylls``), une
réimplémentation pure-Python de Hunspell qui *parse* de façon fiable les
fichiers ``.aff``/``.dic`` (drapeaux longs, conditions, cross-product…). spylls
ne fournit pas de fonction ``unmunch`` toute faite (c'est un correcteur
orthographique), mais expose les règles d'affixes analysées : on applique donc
nous-mêmes préfixes/suffixes (avec cross-product et drapeaux de continuation)
sur chaque radical. Voir :func:`deplier_hunspell`.

Le cache disque (Trie sérialisé via ``pickle``) est invalidé automatiquement
dès qu'un fichier source est plus récent que le cache, ou que la source
configurée change.
"""

from __future__ import annotations

import json
import pickle
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from scrabble.config import RACINE_PROJET, charger_config

# --------------------------------------------------------------------------- #
# Emplacements des fichiers
# --------------------------------------------------------------------------- #

DOSSIER_DICO = RACINE_PROJET / "data" / "dictionnaire"

CHEMIN_ODS = (
    DOSSIER_DICO / "French-Scrabble-ODS8-main" / "French ODS dictionary.txt"
)
# Base sans extension : spylls ajoute ``.aff`` et ``.dic``.
BASE_HUNSPELL = (
    DOSSIER_DICO / "hunspell-french-dictionaries-v7.7" / "fr-toutesvariantes"
)
# Fichiers de personnalisation (ajouts/retraits) séparés **par source** depuis
# l'issue #110 : les corrections faites en mode ODS ne débordent plus sur le
# mode Hunspell et inversement. Une seule source est active à la fois (pas
# d'agrégation) ; ``chemins_modifs`` sélectionne la paire de la source demandée.
CHEMINS_MODIFS: dict[str, tuple[Path, Path]] = {
    "ods": (
        DOSSIER_DICO / "mots_ajoutes_ods.txt",
        DOSSIER_DICO / "mots_retires_ods.txt",
    ),
    "hunspell": (
        DOSSIER_DICO / "mots_ajoutes_hunspell.txt",
        DOSSIER_DICO / "mots_retires_hunspell.txt",
    ),
}
# Statut « classique du jeu » (issue #204). Contrairement aux personnalisations
# par source ci-dessus, cette étiquette porte sur le **mot lui-même**,
# indépendamment de la source active : elle marque les petits mots à lettre
# chère (WU, SIX, ZOO…) qu'on autorise l'IA à jouer même s'ils sont rares dans
# le langage courant. Une paire ajoutés/retirés, sur le modèle exact des
# fichiers ``mots_ajoutes_*``/``mots_retires_*``, un mot par ligne, même
# normalisation. La liste candidate initiale (~531 mots) est produite par
# ``scripts/generer_classiques.py`` et amorce ``classiques_ajoutes.txt``.
CHEMINS_CLASSIQUES: tuple[Path, Path] = (
    DOSSIER_DICO / "classiques_ajoutes.txt",
    DOSSIER_DICO / "classiques_retires.txt",
)

CHEMIN_CACHE = DOSSIER_DICO / "trie_cache.pkl"
# Index mot → définition(s) restreint aux mots de l'ODS8 (issue #15). Ce fichier
# est volumineux et gitignoré : construit hors-ligne par
# ``scripts/construire_definitions.py``. Son absence est tolérée (dict vide).
CHEMIN_DEFINITIONS = DOSSIER_DICO / "definitions.json"

# Version du format de cache : incrémenter invalide tous les caches existants.
VERSION_CACHE = 1


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

def normaliser_mot(mot: str) -> str:
    """Normalise un mot : espaces supprimés, MAJUSCULES, accents conservés.

    Retourne une chaîne vide si le mot ne contient que des espaces. La forme
    Unicode est normalisée en NFC pour que deux écritures d'un même caractère
    accentué (précomposé vs. combinant) soient considérées identiques.
    """
    return unicodedata.normalize("NFC", mot.strip().upper())


def desaccentuer(mot: str) -> str:
    """Retire accents et ligatures d'un mot déjà normalisé (MAJUSCULES/NFC).

    Reproduit la graphie ASCII des **clés de ``definitions.json``**, indexées
    comme l'ODS8 : ligatures Œ→OE, Æ→AE puis chute de tous les diacritiques
    combinants (É→E, Â→A, Ï→I, Ç→C…). Sert à retrouver la définition d'un mot
    accentué (``ÉLÈVE`` → clé ``ELEVE``). Même logique que la fonction homonyme
    de ``scripts/croiser_formes_lemmes.py`` ayant servi à *construire* l'index.
    """
    mot = mot.replace("Œ", "OE").replace("Æ", "AE")
    decompose = unicodedata.normalize("NFD", mot)
    return "".join(c for c in decompose if not unicodedata.combining(c))


# --------------------------------------------------------------------------- #
# Filtre alphabétique du dépliage Hunspell
# --------------------------------------------------------------------------- #

# Lettres acceptées au Scrabble francophone : les 26 lettres de l'alphabet plus
# les voyelles accentuées usuelles et les ligatures Œ/Æ, en MAJUSCULES (les mots
# passés au filtre sont déjà normalisés par ``normaliser_mot``). Tout mot
# contenant un autre caractère (apostrophe, trait d'union, chiffre, lettre
# grecque, lettre étrangère…) est rejeté par :func:`est_mot_scrabble`.
#
# Les trémas Ä/Ö/Ü sont volontairement conservés : le corpus filtré de
# ``fr-toutesvariantes`` en contient des mots légitimes (vérifié issue #8) —
# Ü dans les graphies rectifiées de 1990 (AIGÜE, AMBIGÜE, AMBIGÜITÉ, ARGÜER,
# 191 formes), Ö dans ANGSTRÖM/RÖNTGEN et dérivés (79 formes), Ä dans les
# emprunts LÄNDER, DOPPELGÄNGER (4 formes). Les retirer amputerait le filtre
# de ces entrées jouables.
LETTRES_SCRABBLE = "A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒÆ"
_MOT_SCRABBLE = re.compile(f"^[{LETTRES_SCRABBLE}]+$")


def est_mot_scrabble(mot: str) -> bool:
    """Vrai si ``mot`` (déjà normalisé) n'est fait que de lettres jouables.

    Voir :data:`LETTRES_SCRABBLE`. Sert à filtrer le dépliage Hunspell, qui
    produit massivement des formes inutilisables au Scrabble (élisions avec
    apostrophe, mots composés à trait d'union, ordinaux, symboles…).
    """
    return bool(_MOT_SCRABBLE.match(mot))


# --------------------------------------------------------------------------- #
# Lecture des listes de mots (un mot par ligne)
# --------------------------------------------------------------------------- #

def lire_liste_mots(chemin: Path) -> set[str]:
    """Lit un fichier « un mot par ligne » et renvoie l'ensemble normalisé.

    Les lignes vides sont ignorées. Un fichier inexistant donne un ensemble
    vide (aucune erreur), ce qui convient aux listes optionnelles.
    """
    mots: set[str] = set()
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            for ligne in fichier:
                mot = normaliser_mot(ligne)
                if mot:
                    mots.add(mot)
    except (FileNotFoundError, IsADirectoryError, OSError):
        return set()
    return mots


def charger_ods(chemin: Path = CHEMIN_ODS) -> set[str]:
    """Charge la liste ODS8 (un mot par ligne) normalisée."""
    return lire_liste_mots(chemin)


# --------------------------------------------------------------------------- #
# Définitions (index mot → liste de définitions), restreint à l'ODS8
# --------------------------------------------------------------------------- #

# Cache mémoire des définitions, chargé paresseusement au premier appel.
_DEFINITIONS_CACHE: dict[str, list[str]] | None = None


def charger_definitions(
    chemin: Path = CHEMIN_DEFINITIONS,
) -> dict[str, list[str]]:
    """Charge l'index mot → liste de définitions (issue #15).

    Le fichier ``definitions.json`` est construit hors-ligne à partir du
    Wiktionnaire filtré, restreint aux seuls mots de l'ODS8 (voir
    ``scripts/construire_definitions.py``). Il est **gitignoré** : son absence
    est un cas normal (par exemple sur une machine fraîchement clonée). On
    renvoie alors un dictionnaire vide plutôt que de lever une erreur — le jeu
    doit rester jouable sans définitions.

    Le résultat est mis en cache mémoire (chargement paresseux, à l'image de
    ``charger_ods``/``obtenir_trie``) : les appels suivants renvoient l'objet
    déjà chargé sans relire le disque. Le chemin par défaut est le seul mis en
    cache ; passer un ``chemin`` explicite relit toujours le fichier (utile en
    test).
    """
    global _DEFINITIONS_CACHE
    if chemin == CHEMIN_DEFINITIONS and _DEFINITIONS_CACHE is not None:
        return _DEFINITIONS_CACHE
    definitions = _lire_definitions(chemin)
    if chemin == CHEMIN_DEFINITIONS:
        _DEFINITIONS_CACHE = definitions
    return definitions


def _lire_definitions(chemin: Path) -> dict[str, list[str]]:
    """Lit et valide le JSON des définitions ; dict vide si absent/illisible."""
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            donnees = json.load(fichier)
    except (FileNotFoundError, IsADirectoryError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(donnees, dict):
        return {}
    return donnees


def definition_mot(
    mot: str, chemin: Path = CHEMIN_DEFINITIONS
) -> list[str] | None:
    """Retourne la liste des définitions d'un mot, ou ``None`` si indisponible.

    Le mot est normalisé (:func:`normaliser_mot`) puis **désaccentué**
    (:func:`desaccentuer`) pour retrouver la clé ASCII de ``definitions.json``
    (indexé comme l'ODS8). Renvoie ``None`` — plutôt qu'une liste vide ou une
    erreur — quand le mot est absent de l'index ou que le fichier de définitions
    n'existe pas : l'onglet Dictionnaire affiche alors « définition
    indisponible ». Rappel (issue #109) : seuls les mots de l'ODS8 ont une
    définition ; un mot présent uniquement dans Hunspell n'en aura pas.
    """
    norme = normaliser_mot(mot)
    if not norme:
        return None
    definitions = charger_definitions(chemin)
    gloses = definitions.get(desaccentuer(norme))
    if not gloses:
        return None
    return gloses


def assurer_fichiers_modifs(
    chemin_ajoutes: Path,
    chemin_retires: Path,
) -> None:
    """Crée les fichiers d'ajouts/retraits vides s'ils n'existent pas."""
    for chemin in (chemin_ajoutes, chemin_retires):
        if not chemin.exists():
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.touch()


# --------------------------------------------------------------------------- #
# Dépliage ("unmunch") du dictionnaire Hunspell via spylls
# --------------------------------------------------------------------------- #

def deplier_hunspell(base: Path = BASE_HUNSPELL) -> set[str]:
    """Déplie un dictionnaire Hunspell en une liste de mots à plat, normalisée.

    ``base`` est le chemin *sans extension* : les fichiers ``base.aff`` et
    ``base.dic`` sont lus. On applique chaque règle d'affixe (préfixe/suffixe)
    dont la condition est satisfaite sur le radical, en gérant le cross-product
    (préfixe + suffixe) et les drapeaux de continuation (affixes en cascade,
    p. ex. conjugaison puis accord). Les radicaux marqués FORBIDDENWORD sont
    exclus, ceux marqués NEEDAFFIX ne sont pas émis seuls.

    Filtre alphabétique
    ~~~~~~~~~~~~~~~~~~~~~
    Seules les formes *purement alphabétiques jouables au Scrabble* sont
    conservées (voir :func:`est_mot_scrabble` / :data:`LETTRES_SCRABBLE`). Le
    diagnostic de l'issue #4 a montré que le dépliage brut de
    ``fr-toutesvariantes`` produit ~2,5 M de formes dont **81 %** sont des
    élisions avec apostrophe (« QU'… ») ou des mots composés à trait d'union,
    plus ~7 200 formes bruitées (chiffres, ordinaux, lettres grecques, lettres
    étrangères hors alphabet français) — toutes inutilisables au Scrabble. On
    exclut donc explicitement apostrophes, traits d'union, chiffres et lettres
    hors des 26 lettres + accents français usuels. Le corpus filtré attendu
    tombe à ~461 000 mots, ordre de grandeur cohérent avec l'ODS8 (411 430).

    Nécessite la bibliothèque ``spylls`` (voir requirements.txt). L'import est
    différé pour que le mode ODS n'en dépende pas.
    """
    try:
        from spylls.hunspell import Dictionary
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError(
            "La source 'hunspell' nécessite la bibliothèque 'spylls' "
            "(pip install spylls)."
        ) from exc

    dico = Dictionary.from_files(str(base))
    aff = dico.aff
    forbid = aff.FORBIDDENWORD
    needaff = aff.NEEDAFFIX

    def _appliquer_suffixe(radical: str, regle: Any) -> str | None:
        if regle.strip:
            if not radical.endswith(regle.strip):
                return None
            base_mot = radical[: -len(regle.strip)]
        else:
            base_mot = radical
        if not base_mot and not aff.FULLSTRIP:
            return None
        if not regle.cond_regexp.search(radical):
            return None
        return base_mot + regle.add

    def _appliquer_prefixe(radical: str, regle: Any) -> str | None:
        if regle.strip:
            if not radical.startswith(regle.strip):
                return None
            base_mot = radical[len(regle.strip):]
        else:
            base_mot = radical
        if not base_mot and not aff.FULLSTRIP:
            return None
        if not regle.cond_regexp.search(radical):
            return None
        return regle.add + base_mot

    def _regles(table: dict, drapeaux: Iterable[str]) -> list:
        regles: list = []
        for drapeau in drapeaux:
            regles.extend(table.get(drapeau, []))
        return regles

    def _developper(radical: str, drapeaux: set, profondeur: int = 0) -> set[str]:
        formes: set[str] = set()
        if forbid and forbid in drapeaux:
            return formes
        suffixes = _regles(aff.SFX, drapeaux)
        prefixes = _regles(aff.PFX, drapeaux)
        # Le radical lui-même est une forme valide, sauf s'il exige un affixe.
        if not (needaff and needaff in drapeaux):
            formes.add(radical)
        for regle in suffixes:
            forme = _appliquer_suffixe(radical, regle)
            if forme is None:
                continue
            # Drapeaux de continuation : nouveaux affixes applicables en cascade.
            if regle.flags and profondeur < 2:
                formes |= _developper(forme, regle.flags, profondeur + 1)
            else:
                formes.add(forme)
            if regle.crossproduct:
                for regle_p in prefixes:
                    if not regle_p.crossproduct:
                        continue
                    croisee = _appliquer_prefixe(forme, regle_p)
                    if croisee:
                        formes.add(croisee)
        for regle in prefixes:
            forme = _appliquer_prefixe(radical, regle)
            if forme is None:
                continue
            if regle.flags and profondeur < 2:
                formes |= _developper(forme, regle.flags, profondeur + 1)
            else:
                formes.add(forme)
        return formes

    resultat: set[str] = set()
    for entree in dico.dic.words:
        for forme in _developper(entree.stem, entree.flags):
            forme_norm = normaliser_mot(forme)
            if forme_norm and est_mot_scrabble(forme_norm):
                resultat.add(forme_norm)
    return resultat


# --------------------------------------------------------------------------- #
# Construction du dictionnaire final : (source ∪ ajouts) − retraits
# --------------------------------------------------------------------------- #

def chemins_modifs(source: str) -> tuple[Path, Path]:
    """Retourne le couple ``(mots_ajoutes, mots_retires)`` propre à la source.

    Chaque source (``"ods"`` / ``"hunspell"``) possède depuis l'issue #110 sa
    propre paire de fichiers de personnalisation, pour que les ajouts/retraits
    faits sous une source ne s'appliquent pas à l'autre. Toute valeur inconnue
    retombe sur la paire ODS — même robustesse que :func:`charger_source` et
    :func:`_sources_pertinentes` face à une configuration inattendue.
    """
    return CHEMINS_MODIFS.get(source, CHEMINS_MODIFS["ods"])


# Sources reconnues, dans l'ordre d'affichage de l'onglet Dictionnaire.
SOURCES: tuple[str, ...] = ("ods", "hunspell")


# --------------------------------------------------------------------------- #
# Statut d'un mot par source + personnalisation manuelle (onglet Dictionnaire)
# --------------------------------------------------------------------------- #

# Cache mémoire de l'ensemble **brut** de chaque source (avant ajouts/retraits).
# Le dépliage Hunspell coûte plusieurs secondes (issue #109, vigilance 4) : on ne
# le rejoue jamais à chaque recherche. La valeur est ``None`` quand la source est
# indisponible (p. ex. spylls absent pour Hunspell), pour éviter de retenter en
# boucle un chargement voué à échouer.
_SOURCE_CACHE: dict[str, set[str] | None] = {}


def charger_source_cache(
    source: str,
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
) -> set[str] | None:
    """Ensemble **brut** d'une source, mis en cache mémoire ; ``None`` si KO.

    Utilisé par le statut « présent dans la source » de l'onglet Dictionnaire.
    Contrairement à :func:`charger_source`, on **avale** l'erreur de chargement
    (typiquement ``RuntimeError`` si ``spylls`` manque pour Hunspell) et on
    renvoie ``None`` : l'UI signalera alors la source « indisponible » plutôt que
    de planter. Le cache n'est renseigné que pour les chemins par défaut (les
    seuls utilisés en production) ; un chemin explicite relit toujours (tests).
    """
    par_defaut = chemin_ods == CHEMIN_ODS and base_hunspell == BASE_HUNSPELL
    if par_defaut and source in _SOURCE_CACHE:
        return _SOURCE_CACHE[source]
    try:
        mots: set[str] | None = charger_source(source, chemin_ods, base_hunspell)
    except Exception:  # noqa: BLE001 - source indisponible : on dégrade proprement
        mots = None
    if par_defaut:
        _SOURCE_CACHE[source] = mots
    return mots


def _reecrire_liste_mots(chemin: Path, mots: set[str]) -> None:
    """Réécrit une liste « un mot par ligne », triée et dédoublonnée."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fichier:
        for mot in sorted(mots):
            fichier.write(mot + "\n")


def statut_source(
    mot_normalise: str,
    source: str,
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
) -> dict[str, Any]:
    """Statut d'un mot déjà normalisé dans une source donnée.

    Retourne ``{"present_brut", "ajout_manuel", "retrait_manuel", "present",
    "indisponible"}`` où :

    * ``present_brut`` : le mot est dans la source d'origine (ODS8 / dépliage
      Hunspell), avant personnalisation ;
    * ``ajout_manuel`` / ``retrait_manuel`` : le mot figure dans
      ``mots_ajoutes_<source>.txt`` / ``mots_retires_<source>.txt`` ;
    * ``present`` : appartenance **effective** au dictionnaire final de la source,
      selon la formule ``(source ∪ ajoutés) − retirés`` ;
    * ``indisponible`` : la source n'a pas pu être chargée (``present_brut`` et
      ``present`` sont alors indéterminés — calculés sur la seule personnalisation).
    """
    brut = charger_source_cache(source, chemin_ods, base_hunspell)
    indisponible = brut is None
    present_brut = (not indisponible) and mot_normalise in brut
    ajoutes, retires = chemins_modifs(source)
    ajout_manuel = mot_normalise in lire_liste_mots(ajoutes)
    retrait_manuel = mot_normalise in lire_liste_mots(retires)
    present = (present_brut or ajout_manuel) and not retrait_manuel
    return {
        "present_brut": present_brut,
        "ajout_manuel": ajout_manuel,
        "retrait_manuel": retrait_manuel,
        "present": present,
        "indisponible": indisponible,
    }


def rechercher_statut(
    mot: str,
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
    chemin_definitions: Path = CHEMIN_DEFINITIONS,
) -> dict[str, Any]:
    """Statut complet d'un mot pour l'onglet Dictionnaire.

    Assemble, pour chaque source de :data:`SOURCES`, le statut renvoyé par
    :func:`statut_source`, plus la définition (:func:`definition_mot`, ODS8
    uniquement) et le statut « classique du jeu » (:func:`statut_classique`,
    issue #204). ``mot`` est le libellé normalisé (accents conservés) ; il est
    aussi renvoyé pour que l'UI affiche la forme réellement interrogée.
    """
    norme = normaliser_mot(mot)
    return {
        "mot": norme,
        "valide_saisie": bool(norme) and est_mot_scrabble(norme),
        "sources": {
            source: statut_source(norme, source, chemin_ods, base_hunspell)
            for source in SOURCES
        },
        "classique": statut_classique(norme),
        "definition": definition_mot(norme, chemin_definitions),
    }


def modifier_appartenance(
    mot: str,
    source: str,
    present: bool,
) -> str:
    """Force la présence (``present=True``) ou l'absence d'un mot dans une source.

    Écrit dans les fichiers de personnalisation **propres à la source**
    (:func:`chemins_modifs`) de façon cohérente avec la formule
    ``(source ∪ ajoutés) − retirés`` :

    * **ajouter** (``present=True``) : le mot entre dans ``mots_ajoutes_<source>``
      et sort de ``mots_retires_<source>`` (on lève un éventuel retrait
      contradictoire) ;
    * **retirer** (``present=False``) : le mot entre dans ``mots_retires_<source>``
      et sort de ``mots_ajoutes_<source>``.

    Les deux fichiers sont réécrits triés/dédoublonnés ; leur mtime change, ce
    qui **périme automatiquement** le cache Trie de la source (via
    :func:`_sources_pertinentes`), sans y toucher explicitement. Le mot est
    normalisé au préalable ; ``ValueError`` est levée s'il n'est pas un mot
    jouable au Scrabble (vide, chiffres, ponctuation…). Retourne le mot normalisé.
    """
    norme = normaliser_mot(mot)
    if not norme or not est_mot_scrabble(norme):
        raise ValueError(f"« {mot} » n'est pas un mot jouable au Scrabble.")
    if source not in CHEMINS_MODIFS:
        raise ValueError(f"Source inconnue : « {source} ».")
    chemin_ajoutes, chemin_retires = chemins_modifs(source)
    assurer_fichiers_modifs(chemin_ajoutes, chemin_retires)
    ajoutes = lire_liste_mots(chemin_ajoutes)
    retires = lire_liste_mots(chemin_retires)
    if present:
        ajoutes.add(norme)
        retires.discard(norme)
    else:
        retires.add(norme)
        ajoutes.discard(norme)
    _reecrire_liste_mots(chemin_ajoutes, ajoutes)
    _reecrire_liste_mots(chemin_retires, retires)
    return norme


# --------------------------------------------------------------------------- #
# Statut « classique du jeu » (issue #204)
# --------------------------------------------------------------------------- #

def chemins_classiques() -> tuple[Path, Path]:
    """Retourne le couple ``(classiques_ajoutes, classiques_retires)``.

    Indirection volontaire (plutôt que l'accès direct à
    :data:`CHEMINS_CLASSIQUES`) pour que les tests puissent réassigner la
    constante du module via ``monkeypatch.setattr`` et voir l'effet ici.
    """
    return CHEMINS_CLASSIQUES


def statut_classique(mot_normalise: str) -> dict[str, Any]:
    """Statut « classique du jeu » d'un mot déjà normalisé (issue #204).

    Contrairement à :func:`statut_source`, il n'y a pas de source « brute » :
    l'étiquette existe uniquement via les fichiers de personnalisation. Un mot
    est classique s'il figure dans ``classiques_ajoutes.txt`` sans figurer dans
    ``classiques_retires.txt`` (même formule ``ajoutés − retirés`` que les
    sources, avec un ensemble brut vide). Retourne ``{"ajout_manuel",
    "retrait_manuel", "classique"}``.
    """
    chemin_ajoutes, chemin_retires = chemins_classiques()
    ajout_manuel = mot_normalise in lire_liste_mots(chemin_ajoutes)
    retrait_manuel = mot_normalise in lire_liste_mots(chemin_retires)
    return {
        "ajout_manuel": ajout_manuel,
        "retrait_manuel": retrait_manuel,
        "classique": ajout_manuel and not retrait_manuel,
    }


def mot_existe_dans_une_source(
    mot_normalise: str,
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
) -> bool:
    """Vrai si le mot appartient (brut) à **au moins une** des deux sources.

    Vérification indépendante de la source active (issue #204) : on teste ODS8
    puis Hunspell, l'existence dans l'une des deux suffisant. L'ordre est
    volontaire (ODS8 d'abord) : la plupart des classiques en viennent, ce qui
    évite d'avoir à déplier Hunspell (plusieurs secondes) dans le cas courant.
    Une source indisponible (``None``) est simplement ignorée.
    """
    for source in SOURCES:
        brut = charger_source_cache(source, chemin_ods, base_hunspell)
        if brut is not None and mot_normalise in brut:
            return True
    return False


def marquer_classique(
    mot: str,
    present: bool,
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
) -> str:
    """Marque (``present=True``) ou démarque un mot comme « classique du jeu ».

    Écrit dans la paire :data:`CHEMINS_CLASSIQUES` sur le modèle exact de
    :func:`modifier_appartenance` (``classiques_ajoutes`` / ``classiques_retires``,
    triés/dédoublonnés). Le mot est normalisé au préalable ; ``ValueError`` est
    levée s'il n'est pas un mot jouable au Scrabble (vide, chiffres, ponctuation…).

    **Refus explicite** (``ValueError``, sans toucher aux fichiers) si l'on tente
    de marquer classique (``present=True``) un mot qui n'existe dans **aucune**
    des deux sources ODS8/Hunspell : un mot non jouable ne peut pas être un
    classique du jeu (issue #204). Le démarquage (``present=False``) ne subit pas
    cette vérification — on doit toujours pouvoir retirer une étiquette. Retourne
    le mot normalisé.
    """
    norme = normaliser_mot(mot)
    if not norme or not est_mot_scrabble(norme):
        raise ValueError(f"« {mot} » n'est pas un mot jouable au Scrabble.")
    if present and not mot_existe_dans_une_source(norme, chemin_ods, base_hunspell):
        raise ValueError(
            f"« {norme} » n'existe dans aucune source (ni ODS8 ni Hunspell) : "
            "un mot non jouable ne peut pas être un classique du jeu."
        )
    chemin_ajoutes, chemin_retires = chemins_classiques()
    assurer_fichiers_modifs(chemin_ajoutes, chemin_retires)
    ajoutes = lire_liste_mots(chemin_ajoutes)
    retires = lire_liste_mots(chemin_retires)
    if present:
        ajoutes.add(norme)
        retires.discard(norme)
    else:
        retires.add(norme)
        ajoutes.discard(norme)
    _reecrire_liste_mots(chemin_ajoutes, ajoutes)
    _reecrire_liste_mots(chemin_retires, retires)
    return norme


def charger_source(
    source: str,
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
) -> set[str]:
    """Charge l'ensemble de mots de la source demandée (normalisé).

    Toute valeur autre que ``"hunspell"`` retombe sur l'ODS (source par défaut
    et robuste face à une configuration inattendue).
    """
    if source == "hunspell":
        return deplier_hunspell(base_hunspell)
    return charger_ods(chemin_ods)


def construire_ensemble_mots(
    mots_source: set[str],
    mots_ajoutes: set[str],
    mots_retires: set[str],
) -> set[str]:
    """Applique ``(source ∪ ajoutes) − retires`` sur des ensembles normalisés."""
    return (mots_source | mots_ajoutes) - mots_retires


# --------------------------------------------------------------------------- #
# Trie
# --------------------------------------------------------------------------- #

class Trie:
    """Arbre préfixe (Trie) minimal pour valider l'appartenance d'un mot.

    Le nœud racine est un dictionnaire imbriqué ; un mot est marqué terminal
    par la clé sentinelle :data:`Trie._FIN`. Cette structure (dictionnaires
    imbriqués de ``str``) se sérialise directement avec ``pickle``.
    """

    _FIN = "$"  # Sentinelle de fin de mot (jamais un caractère de mot normalisé).

    __slots__ = ("racine", "taille")

    def __init__(self) -> None:
        self.racine: dict = {}
        self.taille = 0

    def inserer(self, mot: str) -> None:
        """Insère un mot déjà normalisé dans le Trie."""
        if not mot:
            return
        noeud = self.racine
        for caractere in mot:
            noeud = noeud.setdefault(caractere, {})
        if self._FIN not in noeud:
            noeud[self._FIN] = True
            self.taille += 1

    def contient(self, mot: str) -> bool:
        """Teste l'appartenance d'un mot déjà normalisé."""
        noeud = self.racine
        for caractere in mot:
            noeud = noeud.get(caractere)
            if noeud is None:
                return False
        return self._FIN in noeud

    def __contains__(self, mot: str) -> bool:
        return self.contient(mot)

    def __len__(self) -> int:
        return self.taille

    @classmethod
    def depuis_iterable(cls, mots: Iterable[str]) -> "Trie":
        """Construit un Trie à partir de mots déjà normalisés."""
        trie = cls()
        for mot in mots:
            trie.inserer(mot)
        return trie


# --------------------------------------------------------------------------- #
# Dictionnaire de haut niveau + validation
# --------------------------------------------------------------------------- #

class Dictionnaire:
    """Dictionnaire de mots interrogeable, adossé à un :class:`Trie`."""

    __slots__ = ("trie",)

    def __init__(self, trie: Trie) -> None:
        self.trie = trie

    def mot_valide(self, mot: str) -> bool:
        """Indique si ``mot`` est valide (après normalisation)."""
        return normaliser_mot(mot) in self.trie

    def __len__(self) -> int:
        return len(self.trie)


# --------------------------------------------------------------------------- #
# Cache disque du Trie (pickle) avec invalidation par date de modification
# --------------------------------------------------------------------------- #

def _sources_pertinentes(
    source: str,
    chemin_ods: Path,
    base_hunspell: Path,
    chemin_ajoutes: Path,
    chemin_retires: Path,
) -> list[Path]:
    """Liste des fichiers dont la modification doit invalider le cache."""
    if source == "hunspell":
        fichiers = [
            base_hunspell.with_suffix(".aff"),
            base_hunspell.with_suffix(".dic"),
        ]
    else:
        fichiers = [chemin_ods]
    fichiers += [chemin_ajoutes, chemin_retires]
    return fichiers


def _cache_valide(chemin_cache: Path, source: str, sources: list[Path]) -> bool:
    """Vrai si le cache existe, cible la bonne source et n'est pas périmé."""
    if not chemin_cache.exists():
        return False
    try:
        with open(chemin_cache, "rb") as fichier:
            entete = pickle.load(fichier)
    except (pickle.UnpicklingError, EOFError, OSError, AttributeError, ValueError):
        return False
    if not isinstance(entete, dict):
        return False
    if entete.get("version") != VERSION_CACHE or entete.get("source") != source:
        return False
    mtime_cache = chemin_cache.stat().st_mtime
    for chemin in sources:
        if chemin.exists() and chemin.stat().st_mtime > mtime_cache:
            return False
    return True


def _lire_trie_cache(chemin_cache: Path) -> Trie | None:
    """Charge le Trie depuis le cache, ou ``None`` si illisible."""
    try:
        with open(chemin_cache, "rb") as fichier:
            entete = pickle.load(fichier)
            trie = pickle.load(fichier)
    except (pickle.UnpicklingError, EOFError, OSError, AttributeError, ValueError):
        return None
    if isinstance(trie, Trie):
        return trie
    return None


def _ecrire_trie_cache(chemin_cache: Path, source: str, trie: Trie) -> None:
    """Sérialise le Trie et son en-tête (version + source) dans le cache."""
    chemin_cache.parent.mkdir(parents=True, exist_ok=True)
    entete = {"version": VERSION_CACHE, "source": source}
    with open(chemin_cache, "wb") as fichier:
        pickle.dump(entete, fichier, protocol=pickle.HIGHEST_PROTOCOL)
        pickle.dump(trie, fichier, protocol=pickle.HIGHEST_PROTOCOL)


def construire_trie(
    source: str = "ods",
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
    chemin_ajoutes: Path | None = None,
    chemin_retires: Path | None = None,
) -> Trie:
    """Construit le Trie du dictionnaire final (sans passer par le cache).

    Les fichiers d'ajouts/retraits par défaut sont ceux **propres à la source**
    (voir :func:`chemins_modifs`) ; ``chemin_ajoutes``/``chemin_retires``
    explicites restent prioritaires (utile en test).
    """
    defaut_ajoutes, defaut_retires = chemins_modifs(source)
    if chemin_ajoutes is None:
        chemin_ajoutes = defaut_ajoutes
    if chemin_retires is None:
        chemin_retires = defaut_retires
    assurer_fichiers_modifs(chemin_ajoutes, chemin_retires)
    mots = construire_ensemble_mots(
        charger_source(source, chemin_ods, base_hunspell),
        lire_liste_mots(chemin_ajoutes),
        lire_liste_mots(chemin_retires),
    )
    return Trie.depuis_iterable(mots)


def obtenir_trie(
    source: str = "ods",
    chemin_ods: Path = CHEMIN_ODS,
    base_hunspell: Path = BASE_HUNSPELL,
    chemin_ajoutes: Path | None = None,
    chemin_retires: Path | None = None,
    chemin_cache: Path = CHEMIN_CACHE,
) -> Trie:
    """Retourne le Trie du dictionnaire, en s'appuyant sur le cache disque.

    Le cache est rechargé s'il est présent, cible la même source et est plus
    récent que tous les fichiers sources ; sinon il est reconstruit puis
    réécrit. Les fichiers d'ajouts/retraits par défaut sont ceux **propres à la
    source** (voir :func:`chemins_modifs`) ; des chemins explicites restent
    prioritaires (utile en test).
    """
    defaut_ajoutes, defaut_retires = chemins_modifs(source)
    if chemin_ajoutes is None:
        chemin_ajoutes = defaut_ajoutes
    if chemin_retires is None:
        chemin_retires = defaut_retires
    assurer_fichiers_modifs(chemin_ajoutes, chemin_retires)
    sources = _sources_pertinentes(
        source, chemin_ods, base_hunspell, chemin_ajoutes, chemin_retires
    )
    if _cache_valide(chemin_cache, source, sources):
        trie = _lire_trie_cache(chemin_cache)
        if trie is not None:
            return trie
    trie = construire_trie(
        source, chemin_ods, base_hunspell, chemin_ajoutes, chemin_retires
    )
    try:
        _ecrire_trie_cache(chemin_cache, source, trie)
    except OSError:
        pass  # Un cache non écrit n'empêche pas de fonctionner.
    return trie


def charger_dictionnaire(config: dict[str, Any] | None = None) -> Dictionnaire:
    """Charge le dictionnaire selon la configuration (source par défaut : ODS).

    Point d'entrée principal du module : lit ``config["source_dictionnaire"]``
    (chargée depuis ``config.json`` si ``config`` est ``None``) puis renvoie un
    :class:`Dictionnaire` prêt à valider des mots.
    """
    if config is None:
        config = charger_config()
    source = config.get("source_dictionnaire", "ods")
    return Dictionnaire(obtenir_trie(source))


# Dictionnaire par défaut, chargé paresseusement pour la fonction utilitaire.
_DICTIONNAIRE_DEFAUT: Dictionnaire | None = None


def mot_valide(mot: str) -> bool:
    """Valide un mot avec le dictionnaire par défaut (chargé une seule fois)."""
    global _DICTIONNAIRE_DEFAUT
    if _DICTIONNAIRE_DEFAUT is None:
        _DICTIONNAIRE_DEFAUT = charger_dictionnaire()
    return _DICTIONNAIRE_DEFAUT.mot_valide(mot)


if __name__ == "__main__":  # pragma: no cover
    dico = charger_dictionnaire()
    print(f"Dictionnaire chargé : {len(dico)} mots.")
