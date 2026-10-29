"""Isolation du dossier de données utilisateur du serveur (issue #475).

Par défaut, ``scrabble.config``/``scrabble.persistance.stockage`` écrivent
``config.json``/``data/parties.db``/``logs/`` sous ``RACINE_DONNEES_
UTILISATEUR``, qui vaut la racine du dépôt en mode non gelé (dev). Lancer le
serveur tel quel partagerait donc le MÊME ``config.json`` et la MÊME base de
parties que l'application de bureau lancée en dev sur ce même poste — exactement
ce que le point 7 de l'issue #475 interdit.

``persistance/`` ne doit pas être modifié (périmètre de l'issue) et ``config.py``
ne propose aucun point d'extension (``RACINE_DONNEES_UTILISATEUR`` est calculée
une fois à l'import, les chemins par défaut des fonctions de ``scrabble.config``/
``scrabble.reglages``/``scrabble.persistance.stockage`` sont de simples valeurs
de paramètre par défaut figées au moment de la définition de chaque fonction).
On ne peut donc pas se contenter de réaffecter l'attribut de module : une
valeur par défaut déjà liée à l'ancien ``Path`` ne change pas quand on
réaffecte le nom de module qui l'a produite.

:func:`isoler_donnees_utilisateur` corrige donc, à l'exécution et uniquement
depuis ce sous-paquet serveur, la valeur par défaut déjà liée de chaque
fonction concernée (``__defaults__``), en substituant l'ancien chemin par le
nouveau. Aucun fichier de ``scrabble/config.py``, ``scrabble/reglages.py`` ni
``scrabble/persistance/stockage.py`` n'est modifié sur disque ; seul l'objet
fonction en mémoire, dans CE processus, est ajusté.

Portée volontairement limitée à « parties, réglages, journal » (texte de
l'issue #475, point 7) : le dictionnaire lui-même (``data/dictionnaire/``,
lu via ``RACINE_PROJET``, jamais ``RACINE_DONNEES_UTILISATEUR``) n'est pas
concerné et reste partagé/en lecture seule, comme demandé.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def _repointer_defaut(fonction: Callable, ancien: object, nouveau: object) -> None:
    """Remplace ``ancien`` par ``nouveau`` dans les défauts déjà liés de ``fonction``.

    Ne touche que les emplacements de ``__defaults__`` qui référencent
    exactement l'ancien objet (comparaison ``is``) : les autres paramètres par
    défaut (booléens, ``None``...) sont laissés intacts.
    """
    if fonction.__defaults__ is None:
        return
    fonction.__defaults__ = tuple(
        nouveau if d is ancien else d for d in fonction.__defaults__
    )


def isoler_donnees_utilisateur(dossier: Path) -> dict[str, Path]:
    """Redirige config/parties/journal vers ``dossier`` pour ce processus.

    À appeler une seule fois, tout en début de vie du processus serveur,
    avant toute création d'``ApiAccueil``/``ApiJeu``. Crée ``dossier`` (et
    ``dossier/data``, ``dossier/logs``) si besoin. Retourne les chemins
    effectivement utilisés (``config``, ``base_parties``, ``logs``), pour
    affichage/tests.
    """
    import scrabble.config as config
    import scrabble.persistance.stockage as stockage
    import scrabble.reglages as reglages

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "data").mkdir(exist_ok=True)
    (dossier / "logs").mkdir(exist_ok=True)

    nouveau_config = dossier / "config.json"
    nouvelle_base = dossier / "data" / "parties.db"

    ancien_config = config.CHEMIN_CONFIG
    for nom in ("charger_config", "sauvegarder_config"):
        _repointer_defaut(getattr(config, nom), ancien_config, nouveau_config)
    for nom in ("lister_reglages", "lire_reglage", "modifier_reglage"):
        _repointer_defaut(getattr(reglages, nom), ancien_config, nouveau_config)
    config.CHEMIN_CONFIG = nouveau_config

    ancienne_base = stockage.CHEMIN_DEFAUT
    for nom in (
        "demarrer_suivi",
        "enregistrer_action",
        "finaliser_partie",
        "supprimer_partie",
        "lister_parties",
        "niveaux_ia_stockes",
        "reprendre_partie",
        "lire_configuration_partie",
        "lire_actions_journalisees",
    ):
        _repointer_defaut(getattr(stockage, nom), ancienne_base, nouvelle_base)
    stockage.CHEMIN_DEFAUT = nouvelle_base

    return {
        "config": nouveau_config,
        "base_parties": nouvelle_base,
        "logs": dossier / "logs",
    }
