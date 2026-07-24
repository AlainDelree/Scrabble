"""Test anti-collision de noms entre les mixins d'ApiJeu (issues #251, #252).

Ce test vérifie mécaniquement :

1. Qu'aucun nom de méthode **avec une vraie implémentation** (non-stub) n'apparaît
   dans plus d'un des mixins ou dans ApiJeu de base — un doublon serait un bug
   silencieux où l'un écraserait l'autre selon l'ordre du MRO.

2. Que pour tout nom présent à la fois comme stub (corps ``...``) dans un mixin
   ET comme vraie implémentation dans un autre, l'ordre d'héritage déclaré sur
   ApiJeu place bien le mixin avec la vraie implémentation AVANT celui avec le
   stub — sinon le MRO ferait passer le stub en premier, masquant silencieusement
   la vraie méthode.

**Point important** : plusieurs mixins déclarent des méthodes "stub" à but de
typage uniquement (corps réduit à ``...``, ex. ``def _diffuser(self) -> None: ...``).
Ce ne sont PAS de vraies collisions et le test les ignore.
"""

import ast
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

    Utilise l'AST pour une détection fiable : le corps est un stub si et seulement
    s'il ne contient que :
    - ``...`` seul (``Expr(Constant(Ellipsis))``), ou
    - une docstring suivie de ``...`` (``Expr(Constant(str))``, puis ``Expr(Constant(Ellipsis))``).
    """
    if isinstance(valeur, staticmethod):
        valeur = valeur.__func__
    elif isinstance(valeur, classmethod):
        valeur = valeur.__func__
    if not inspect.isfunction(valeur):
        return False
    try:
        source = inspect.getsource(valeur)
        # Dé-indenter la source pour que l'AST la parse (elle peut être indentée
        # dans la classe).
        source = inspect.cleandoc(source)
        tree = ast.parse(source)
        # L'AST contient un Module avec une seule FunctionDef.
        if not tree.body or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        func_def = tree.body[0]
        body = func_def.body
        # Corps vide interdit en Python, mais bon.
        if not body:
            return False
        # Ignorer une éventuelle docstring en tête.
        debut = 0
        if (
            isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            debut = 1
        reste = body[debut:]
        # Le corps est un stub s'il ne contient qu'un ``...`` après la docstring.
        if len(reste) == 1 and isinstance(reste[0], ast.Expr):
            noeud = reste[0].value
            # ``Ellipsis`` peut être représenté comme Constant(Ellipsis) ou Ellipsis.
            if isinstance(noeud, ast.Constant) and noeud.value is ...:
                return True
            if isinstance(noeud, ast.Ellipsis):  # Python < 3.8 (compat)
                return True
        return False
    except (OSError, TypeError, SyntaxError):
        return False


def _methodes_directes(cls: type) -> dict[str, bool]:
    """Renvoie les méthodes définies directement sur ``cls`` avec leur nature.

    On ne considère que les attributs appelables (``callable``) définis dans le
    ``__dict__`` de la classe — pas ceux hérités via le MRO. Les annotations de
    type et les attributs de données (non-callable) sont exclus.

    Retourne un dictionnaire ``{nom: est_stub}``, où ``est_stub`` vaut ``True``
    si la méthode est un stub de typage (corps ``...``), ``False`` sinon.
    """
    resultat: dict[str, bool] = {}
    for nom, valeur in vars(cls).items():
        if callable(valeur) or isinstance(valeur, (classmethod, staticmethod, property)):
            est_stub = _est_stub_protocole(valeur)
            resultat[nom] = est_stub
    return resultat


# Ordre d'héritage selon le MRO réel de Python : la classe elle-même est
# en premier, puis les mixins dans l'ordre de déclaration (premier = priorité
# MRO la plus haute).
ORDRE_HERITAGE = [
    "ApiJeu",
    "MixinDiffusion",
    "MixinTirageOrdre",
    "MixinTourEtFinPartie",
    "MixinPose",
    "MixinEchange",
]

CLASSES = {
    "ApiJeu": ApiJeu,
    "MixinDiffusion": MixinDiffusion,
    "MixinTirageOrdre": MixinTirageOrdre,
    "MixinTourEtFinPartie": MixinTourEtFinPartie,
    "MixinPose": MixinPose,
    "MixinEchange": MixinEchange,
}


def test_absence_collision_noms_mixins():
    """Vérifie qu'aucun nom de méthode réelle n'apparaît dans plus d'un mixin."""
    # Dictionnaire : nom de méthode -> liste des classes où il est défini
    # avec une vraie implémentation (non-stub).
    occurrences_reelles: dict[str, list[str]] = {}

    for nom_classe, cls in CLASSES.items():
        methodes = _methodes_directes(cls)
        for methode, est_stub in methodes.items():
            if not est_stub:
                if methode not in occurrences_reelles:
                    occurrences_reelles[methode] = []
                occurrences_reelles[methode].append(nom_classe)

    # Filtrer les doublons (noms définis dans plus d'une source AVEC une vraie
    # implémentation).
    doublons = {
        nom: sources
        for nom, sources in occurrences_reelles.items()
        if len(sources) > 1
    }

    if doublons:
        lignes = ["Collision(s) de noms entre mixins ApiJeu (vraies implémentations) :"]
        for nom, sources in sorted(doublons.items()):
            lignes.append(f"  - {nom!r} défini dans : {', '.join(sources)}")
        raise AssertionError("\n".join(lignes))


def test_ordre_mro_stub_vs_implementation():
    """Vérifie que les stubs ne masquent pas les vraies implémentations via le MRO.

    Pour chaque nom de méthode qui apparaît à la fois comme stub dans un mixin
    et comme vraie implémentation dans un autre, vérifie que le mixin avec
    l'implémentation réelle apparaît AVANT le mixin avec le stub dans l'ordre
    d'héritage déclaré sur ApiJeu. Sinon, le MRO Python ferait passer le stub
    en premier, masquant silencieusement la vraie méthode.
    """
    # Collecte de toutes les méthodes avec leur nature par classe.
    methodes_par_classe: dict[str, dict[str, bool]] = {}
    for nom_classe, cls in CLASSES.items():
        methodes_par_classe[nom_classe] = _methodes_directes(cls)

    # Pour chaque nom de méthode, trouver où il apparaît comme stub et où comme
    # vraie implémentation.
    tous_noms: set[str] = set()
    for methodes in methodes_par_classe.values():
        tous_noms.update(methodes.keys())

    erreurs: list[str] = []

    for nom in sorted(tous_noms):
        classes_stub: list[str] = []
        classes_impl: list[str] = []

        for nom_classe in ORDRE_HERITAGE:
            methodes = methodes_par_classe[nom_classe]
            if nom in methodes:
                if methodes[nom]:  # est_stub
                    classes_stub.append(nom_classe)
                else:
                    classes_impl.append(nom_classe)

        # S'il y a à la fois des stubs ET des implémentations, vérifier l'ordre.
        if classes_stub and classes_impl:
            # Trouver le rang du premier stub et de la première implémentation
            # dans l'ordre d'héritage (MRO).
            rang_premier_stub = min(ORDRE_HERITAGE.index(c) for c in classes_stub)
            rang_premiere_impl = min(ORDRE_HERITAGE.index(c) for c in classes_impl)

            # Si un stub apparaît AVANT la première implémentation, c'est un
            # problème : le MRO fera passer le stub en premier, masquant
            # silencieusement la vraie méthode.
            if rang_premier_stub < rang_premiere_impl:
                premier_stub = ORDRE_HERITAGE[rang_premier_stub]
                premiere_impl = ORDRE_HERITAGE[rang_premiere_impl]
                erreurs.append(
                    f"  - {nom!r} : stub dans {premier_stub} (rang {rang_premier_stub}) "
                    f"AVANT implémentation dans {premiere_impl} (rang {rang_premiere_impl})"
                )

    if erreurs:
        msg = (
            "Ordre MRO dangereux : stub(s) masquant silencieusement la vraie implémentation :\n"
            + "\n".join(erreurs)
            + "\n\nSolution : réordonner les mixins dans la déclaration de ApiJeu "
            "pour que le mixin avec l'implémentation apparaisse AVANT celui avec le stub."
        )
        raise AssertionError(msg)
