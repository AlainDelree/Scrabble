"""Chargement et interrogation du dictionnaire de mots du Scrabble.

Rôle : construire la liste des mots autorisés à partir d'une source (ODS8 ou
Hunspell déplié), la corriger avec des listes locales d'ajouts/retraits, puis
offrir une validation rapide via un Trie mis en cache sur disque.

Chaîne de construction du dictionnaire final::

    (source_choisie ∪ mots_ajoutes) − mots_retires

où ``source_choisie`` dépend de ``config["source_dictionnaire"]`` :

* ``"ods"``      → liste ODS8 (un mot par ligne) ;
* ``"hunspell"`` → dépliage ("unmunch") du dictionnaire ``fr-toutesvariantes``.

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
CHEMIN_MOTS_AJOUTES = DOSSIER_DICO / "mots_ajoutes.txt"
CHEMIN_MOTS_RETIRES = DOSSIER_DICO / "mots_retires.txt"
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


def assurer_fichiers_modifs(
    chemin_ajoutes: Path = CHEMIN_MOTS_AJOUTES,
    chemin_retires: Path = CHEMIN_MOTS_RETIRES,
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
    chemin_ajoutes: Path = CHEMIN_MOTS_AJOUTES,
    chemin_retires: Path = CHEMIN_MOTS_RETIRES,
) -> Trie:
    """Construit le Trie du dictionnaire final (sans passer par le cache)."""
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
    chemin_ajoutes: Path = CHEMIN_MOTS_AJOUTES,
    chemin_retires: Path = CHEMIN_MOTS_RETIRES,
    chemin_cache: Path = CHEMIN_CACHE,
) -> Trie:
    """Retourne le Trie du dictionnaire, en s'appuyant sur le cache disque.

    Le cache est rechargé s'il est présent, cible la même source et est plus
    récent que tous les fichiers sources ; sinon il est reconstruit puis
    réécrit.
    """
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
