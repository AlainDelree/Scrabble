"""Configuration auto-réparante du projet Scrabble.

Ce module lit ``config.json`` à la racine du projet. Si le fichier est
absent ou corrompu (JSON invalide, structure inattendue, clés manquantes ou
valeurs du mauvais type), des valeurs par défaut *sûres* sont utilisées ET un
fichier propre est réécrit.

L'écriture est atomique (fichier temporaire + ``os.replace``) : on ne laisse
jamais un fichier ``config.json`` à moitié écrit, même en cas d'interruption.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Racine du projet : ce fichier est src/scrabble/config.py, donc parents[2].
RACINE_PROJET = Path(__file__).resolve().parents[2]
CHEMIN_CONFIG = RACINE_PROJET / "config.json"

# Valeurs par défaut sûres, utilisées quand le fichier est absent/corrompu.
CONFIG_DEFAUT: dict[str, Any] = {
    "niveau_ia": "amateur",
    "mode_saisie": "clic",
    # Source du dictionnaire de mots : "ods" (dictionnaire officiel du Scrabble
    # francophone, défaut) ou "hunspell" (dictionnaire orthographique déplié).
    "source_dictionnaire": "ods",
    # Prénom de l'utilisatrice principale, retenu d'une partie à l'autre pour
    # éviter de le redemander. Vide par défaut (aucun prénom mémorisé).
    "prenom_principal": "",
    # Thème visuel (habillage couleurs/étiquettes) du plateau de l'écran de jeu.
    # Voir THEMES_PLATEAU pour les valeurs acceptées ; défaut = "classique".
    "theme_plateau": "classique",
}

# Clés dont la valeur est du texte libre : une chaîne vide y est légitime
# (contrairement aux autres champs où le vide déclenche une réparation).
CLES_TEXTE_LIBRE: frozenset[str] = frozenset({"prenom_principal"})

# Thèmes visuels de plateau reconnus. Doivent rester alignés avec les classes
# CSS ``theme-<nom>`` de ``ui/web/jeu.css`` et les libellés de ``ui/web/jeu.js``.
THEMES_PLATEAU: tuple[str, ...] = ("classique", "vert", "abrege")

# Clés dont la valeur est contrainte à un ensemble fini : toute valeur hors de
# cet ensemble déclenche une réparation vers le défaut (auto-réparation).
VALEURS_VALIDES: dict[str, frozenset[str]] = {
    "theme_plateau": frozenset(THEMES_PLATEAU),
}


def charger_config(chemin: os.PathLike[str] | str = CHEMIN_CONFIG) -> dict[str, Any]:
    """Charge la configuration, en réparant le fichier si nécessaire.

    Retourne toujours un dictionnaire valide contenant exactement les clés
    connues. Si le fichier lu était absent, corrompu, incomplet ou pollué par
    des clés inconnues, il est réécrit proprement de façon atomique.
    """
    chemin = Path(chemin)
    brut = _lire_json(chemin)
    config, doit_reparer = _fusionner_defauts(brut)
    if doit_reparer:
        _ecrire_atomique(chemin, config)
    return config


def sauvegarder_config(
    config: dict[str, Any], chemin: os.PathLike[str] | str = CHEMIN_CONFIG
) -> None:
    """Écrit la configuration de manière atomique après normalisation."""
    normalisee, _ = _fusionner_defauts(config)
    _ecrire_atomique(Path(chemin), normalisee)


def _lire_json(chemin: Path) -> Any:
    """Retourne le contenu JSON du fichier, ou ``None`` si illisible."""
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            return json.load(fichier)
    except (FileNotFoundError, IsADirectoryError, json.JSONDecodeError, OSError, ValueError):
        return None


def _fusionner_defauts(brut: Any) -> tuple[dict[str, Any], bool]:
    """Fusionne ``brut`` avec les défauts et indique s'il faut réparer.

    ``doit_reparer`` vaut ``True`` dès que le contenu diffère d'un fichier
    propre : contenu non-dict, clé manquante, valeur de mauvais type ou vide,
    ou présence de clés inconnues.
    """
    if not isinstance(brut, dict):
        return dict(CONFIG_DEFAUT), True

    config: dict[str, Any] = {}
    doit_reparer = False

    for cle, defaut in CONFIG_DEFAUT.items():
        if cle not in brut:
            doit_reparer = True
            config[cle] = defaut
            continue
        valeur = brut[cle]
        if not isinstance(valeur, str):
            # Type incorrect : on retombe toujours sur le défaut.
            doit_reparer = True
            valeur = defaut
        elif not valeur.strip() and cle not in CLES_TEXTE_LIBRE:
            # Chaîne vide interdite, sauf pour les champs en texte libre.
            doit_reparer = True
            valeur = defaut
        elif cle in VALEURS_VALIDES and valeur not in VALEURS_VALIDES[cle]:
            # Valeur hors de l'ensemble autorisé : on retombe sur le défaut.
            doit_reparer = True
            valeur = defaut
        config[cle] = valeur

    # Toute clé inconnue signifie que le fichier doit être nettoyé.
    if set(brut) - set(CONFIG_DEFAUT):
        doit_reparer = True

    return config, doit_reparer


def _ecrire_atomique(chemin: Path, config: dict[str, Any]) -> None:
    """Écrit ``config`` en JSON de façon atomique (aucun fichier partiel)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur, chemin_tmp = tempfile.mkstemp(
        dir=str(chemin.parent), prefix=".config-", suffix=".tmp"
    )
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
            json.dump(config, fichier, ensure_ascii=False, indent=2, sort_keys=True)
            fichier.write("\n")
            fichier.flush()
            os.fsync(fichier.fileno())
        # os.replace est atomique sur un même système de fichiers.
        os.replace(chemin_tmp, chemin)
    except BaseException:
        try:
            os.unlink(chemin_tmp)
        except OSError:
            pass
        raise


if __name__ == "__main__":  # pragma: no cover
    print(charger_config())
