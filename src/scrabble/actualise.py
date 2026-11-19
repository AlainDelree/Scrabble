"""Mécanisme de mise à jour piloté par Actualise (issues #386, #484).

Actualise (outil externe, dépôt séparé) dépose un fichier JSON
``actualise_update.flag`` à côté de l'exécutable Scrabble quand une mise à
jour est prête, avec les clés ``bat`` (script de mise à jour) et
``actualise_ui`` (interface de progression). Ce module centralise la lecture
de ce flag et la validation des chemins qu'il contient, utilisée à la fois au
démarrage (``main.py``) et à la fermeture (``scrabble.ui.application``) avant
tout lancement de processus (issue #482 : aucune vérification n'était faite
sur ces chemins).

Le format du flag et le comportement normal d'Actualise ne changent pas : un
flag légitime continue de déclencher exactement le même lancement qu'avant.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scrabble import journal

#: Dossier d'installation d'Actualise, seul emplacement où un chemin lu dans
#: le flag est accepté (déjà utilisé en dur par ``main.py`` au démarrage pour
#: lancer Actualise lui-même).
DOSSIER_ACTUALISE = Path(r"C:\Actualise")

#: Extensions de fichier acceptées pour un chemin lu dans le flag.
_EXTENSIONS_AUTORISEES = frozenset({".bat", ".exe"})


def chemin_actualise_valide(chemin: str | None) -> Path | None:
    """Valide un chemin lu dans le flag Actualise.

    Accepté seulement si ``chemin`` est non vide, pointe vers un fichier
    existant, a l'extension ``.bat`` ou ``.exe``, et se trouve dans
    :data:`DOSSIER_ACTUALISE` (un chemin qui en sort, y compris via des
    ``..``, est refusé). Retourne le chemin résolu, ou ``None``.
    """
    if not chemin:
        return None
    try:
        candidat = Path(chemin).resolve(strict=True)
    except OSError:
        return None
    if not candidat.is_file():
        return None
    if candidat.suffix.lower() not in _EXTENSIONS_AUTORISEES:
        return None
    try:
        candidat.relative_to(DOSSIER_ACTUALISE.resolve())
    except (OSError, ValueError):
        return None
    return candidat


def _flag_courant() -> Path:
    return Path(sys.executable).parent / "actualise_update.flag"


def traiter_flag_actualise(contexte: str) -> None:
    """Lit le flag Actualise courant et lance l'action associée au contexte.

    ``contexte`` vaut ``"demarrage"`` (appelé par ``main.py``, avant
    l'ouverture de la fenêtre) ou ``"fermeture"`` (appelé par
    ``scrabble.ui.application``, dans le handler de fermeture de fenêtre).
    Un refus ou une erreur — flag absent, JSON illisible, chemin hors du
    dossier d'Actualise, extension inattendue, etc. — n'est jamais remonté :
    seul le motif (jamais le contenu complet du flag) est journalisé via
    ``scrabble.journal``, et aucun processus n'est lancé.
    """
    flag = _flag_courant()
    if not flag.exists():
        return

    # Au démarrage, appelé avant l'ouverture de la fenêtre pywebview, donc
    # avant que ``lancer_application_unifiee`` n'ouvre la session de journal
    # habituelle : on l'ouvre nous-mêmes si besoin pour que tout refus soit
    # bien tracé dans ``scrabble.journal`` (elle ne sera pas réouverte, cf.
    # ``if journal.session_courante() is None`` côté application.py).
    if journal.session_courante() is None:
        journal.demarrer_session()

    try:
        data: dict[str, Any] = json.loads(flag.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        journal.erreur(f"flag Actualise illisible ({contexte}) : {exc}")
        return

    try:
        if contexte == "fermeture":
            bat = chemin_actualise_valide(data.get("bat"))
            flag.unlink(missing_ok=True)
            if bat is None:
                journal.erreur(
                    "flag Actualise (fermeture) : chemin 'bat' refusé"
                )
                return
            # S603 : chemin « bat » déjà validé juste au-dessus par
            # chemin_actualise_valide ; les autres arguments sont des constantes.
            # S607 : « cmd.exe » est l'interpréteur de commandes système de
            # Windows, lancé par son nom court ; le risque (un faux « cmd.exe »
            # placé dans le chemin de recherche) est accepté parce que le
            # lancement exige un fichier-drapeau lu à côté de l'exécutable du
            # jeu (_flag_courant) et un « .bat » situé sous C:\Actualise
            # (chemin_actualise_valide), donc l'attaquant devrait déjà pouvoir
            # écrire dans le dossier de l'application ; un chemin complet vers
            # « cmd.exe » n'apporterait pas de protection réelle ici et
            # nuirait à la portabilité entre versions de Windows.
            subprocess.Popen(["cmd.exe", "/c", str(bat)])  # nosec B603,B607
        elif contexte == "demarrage":
            actualise_ui = chemin_actualise_valide(data.get("actualise_ui"))
            bat = chemin_actualise_valide(data.get("bat"))
            if actualise_ui is None or bat is None:
                journal.erreur(
                    "flag Actualise (demarrage) : chemin 'actualise_ui' ou "
                    "'bat' refusé"
                )
                return
            # Chemins « actualise_ui » et « bat » déjà validés juste au-dessus.
            subprocess.Popen([  # nosec B603
                str(actualise_ui),
                "--bat", str(bat),
                "--flag", str(flag),
                "--relancer", sys.executable,
            ])
        else:  # pragma: no cover - erreur de programmation interne
            raise ValueError(f"contexte inconnu : {contexte!r}")
    except Exception as exc:  # noqa: BLE001 - le traitement du flag Actualise ne doit jamais faire échouer le démarrage ou l'arrêt de Scrabble
        journal.erreur(f"lancement Actualise ignoré ({contexte}) : {exc}")
