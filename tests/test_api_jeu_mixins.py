"""Test anti-collision de noms entre les mixins d'ApiJeu (issue #251).

Ce test vérifie mécaniquement qu'aucun nom de méthode n'est défini dans plus
d'un mixin (ou dans ApiJeu de base), ce qui serait un bug silencieux où l'un
écraserait l'autre selon l'ordre du MRO.
"""

import inspect

from scrabble.ui.api_diffusion import MixinDiffusion
from scrabble.ui.api_echange import MixinEchange
from scrabble.ui.api_pose import MixinPose
from scrabble.ui.api_tirage_ordre import MixinTirageOrdre
from scrabble.ui.api_tour_fin_partie import MixinTourEtFinPartie
from scrabble.ui.jeu import ApiJeu


def _est_stub_protocole(valeur) -> bool:
    """Détecte si une fonction est un stub de protocole (corps = ``...``).

    Les mixins déclarent des méthodes attendues d'autres mixins pour l'annotation
    de type, avec un corps réduit à ``...``. Ces stubs ne sont pas de vraies
    implémentations et ne constituent pas des collisions.
    """
    # Déballer les staticmethod/classmethod pour accéder à la fonction sous-jacente
    if isinstance(valeur, staticmethod):
        valeur = valeur.__func__
    elif isinstance(valeur, classmethod):
        valeur = valeur.__func__
    if not inspect.isfunction(valeur):
        return False
    try:
        source = inspect.getsource(valeur)
        lignes = [l.strip() for l in source.splitlines() if l.strip()]
        # Stub simple sur une ligne ou décorateur + stub sur deux lignes
        if len(lignes) == 1 and lignes[0].endswith(": ..."):
            return True
        if len(lignes) == 2 and lignes[0].startswith("@") and lignes[1].endswith(": ..."):
            return True
        return False
    except (OSError, TypeError):
        return False


def _methodes_directes(cls: type) -> set[str]:
    """Renvoie les noms de méthodes/fonctions définies directement sur ``cls``.

    On ne considère que les attributs appelables (``callable``) définis dans le
    ``__dict__`` de la classe — pas ceux hérités via le MRO. Les annotations de
    type, les attributs de données (non-callable) et les stubs de protocole
    (méthodes avec corps ``...``) sont exclus.
    """
    noms = set()
    for nom, valeur in vars(cls).items():
        if _est_stub_protocole(valeur):
            continue
        if callable(valeur) or isinstance(valeur, (classmethod, staticmethod, property)):
            noms.add(nom)
    return noms


def test_absence_collision_noms_mixins():
    """Vérifie qu'aucun nom de méthode n'apparaît dans plus d'un mixin/classe."""
    classes = {
        "MixinDiffusion": MixinDiffusion,
        "MixinTirageOrdre": MixinTirageOrdre,
        "MixinPose": MixinPose,
        "MixinEchange": MixinEchange,
        "MixinTourEtFinPartie": MixinTourEtFinPartie,
        "ApiJeu": ApiJeu,
    }

    # Dictionnaire : nom de méthode -> liste des classes où il est défini
    occurrences: dict[str, list[str]] = {}

    for nom_classe, cls in classes.items():
        for methode in _methodes_directes(cls):
            if methode not in occurrences:
                occurrences[methode] = []
            occurrences[methode].append(nom_classe)

    # Filtrer les doublons (noms définis dans plus d'une source)
    doublons = {nom: sources for nom, sources in occurrences.items() if len(sources) > 1}

    if doublons:
        # Construire un message d'erreur clair listant les doublons
        lignes = ["Collision(s) de noms entre mixins ApiJeu :"]
        for nom, sources in sorted(doublons.items()):
            lignes.append(f"  - {nom!r} défini dans : {', '.join(sources)}")
        raise AssertionError("\n".join(lignes))
