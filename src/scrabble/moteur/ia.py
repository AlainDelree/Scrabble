"""Adversaire artificiel minimal (stub) pour la boucle de partie.

Rôle : choisir, au tour d'un joueur IA, un **premier coup simple jouable** sans
aucune optimisation de score. Volontairement rudimentaire — c'est le
comportement de remplacement demandé par l'issue #22 en attendant une vraie
stratégie.

Ce module est **séparé** de :mod:`scrabble.moteur.partie` précisément pour
pouvoir être remplacé (les 4 niveaux de difficulté prévus à l'architecture)
sans toucher à la boucle de partie. Il ne dépend que des briques figées du
moteur (:mod:`scrabble.moteur.plateau_partie`, :mod:`scrabble.moteur.validation`)
et jamais de :mod:`scrabble.moteur.partie` (pas de cycle d'import).

Heuristique du stub
-------------------
* **Plateau vide** (premier coup) : on cherche un mot du dictionnaire formable
  avec les lettres du chevalet et on le pose horizontalement à partir de la
  case centrale.
* **Plateau non vide** : on « accroche » une seule lettre du chevalet
  directement à côté d'une lettre déjà posée pour former un mot de deux lettres
  valide (le cas d'école cité par l'issue). La validation complète — mots
  transversaux inclus — est déléguée à :func:`scrabble.moteur.validation.coup_valide`.
* Si rien de simple n'est trouvé, on renvoie ``None`` : le joueur passera.

Les jokers du chevalet ne sont pas exploités par ce stub (ils resteraient à
choisir une lettre) : ils sont simplement ignorés lors de la recherche.
"""

from __future__ import annotations

import itertools

from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    TAILLE,
    Tuile,
    dans_plateau,
)
from scrabble.moteur.validation import DictionnaireMots, coup_valide
from scrabble.regles.lettres import JOKER

#: Nombre maximal de lettres qu'un chevalet peut fournir pour un premier coup.
_MAX_LETTRES = 7


def _lettres_jouables(chevalet: list[str]) -> list[str]:
    """Lettres ordinaires du chevalet (jokers écartés pour ce stub)."""
    return [jeton for jeton in chevalet if jeton != JOKER]


def trouver_coup(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: DictionnaireMots,
) -> Coup | None:
    """Renvoie un coup simple jouable, ou ``None`` s'il faut passer.

    Ne modifie ni le plateau ni le chevalet : la fonction se contente de
    proposer un :class:`~scrabble.moteur.plateau_partie.Coup` que l'appelant
    (la boucle de partie) validera de nouveau et appliquera.
    """
    lettres = _lettres_jouables(chevalet)
    if not lettres:
        return None
    if plateau.est_vide():
        return _premier_coup(plateau, lettres, dictionnaire)
    return _coup_par_extension(plateau, lettres, dictionnaire)


def _premier_coup(
    plateau: PlateauPartie,
    lettres: list[str],
    dictionnaire: DictionnaireMots,
) -> Coup | None:
    """Cherche un mot du chevalet posable horizontalement depuis le centre."""
    ligne, colonne = CENTRE
    taille_max = min(len(lettres), _MAX_LETTRES)
    for taille in range(taille_max, 1, -1):
        deja_vus: set[str] = set()
        for permutation in itertools.permutations(lettres, taille):
            mot = "".join(permutation)
            if mot in deja_vus:
                continue
            deja_vus.add(mot)
            if not dictionnaire.contient(mot):
                continue
            tuiles = tuple(Tuile(lettre) for lettre in permutation)
            coup = Coup(ligne, colonne, Direction.HORIZONTALE, tuiles)
            if coup_valide(plateau, coup, dictionnaire):
                return coup
    return None


# Déplacements (dligne, dcolonne, direction du mot) pour accrocher une lettre
# nouvelle à une lettre existante : à droite, à gauche, en bas, en haut.
_ACCROCHES = (
    (0, 1, Direction.HORIZONTALE),
    (0, -1, Direction.HORIZONTALE),
    (1, 0, Direction.VERTICALE),
    (-1, 0, Direction.VERTICALE),
)


def _coup_par_extension(
    plateau: PlateauPartie,
    lettres: list[str],
    dictionnaire: DictionnaireMots,
) -> Coup | None:
    """Accroche une lettre du chevalet à une lettre posée (mot de 2 lettres)."""
    lettres_uniques = list(dict.fromkeys(lettres))
    for ligne in range(TAILLE):
        for colonne in range(TAILLE):
            existante = plateau.tuile(ligne, colonne)
            if existante is None:
                continue
            for dligne, dcolonne, direction in _ACCROCHES:
                nligne, ncolonne = ligne + dligne, colonne + dcolonne
                if not dans_plateau(nligne, ncolonne):
                    continue
                if plateau.tuile(nligne, ncolonne) is not None:
                    continue
                coup = _essayer_accroche(
                    existante,
                    (ligne, colonne),
                    (nligne, ncolonne),
                    (dligne, dcolonne),
                    direction,
                    lettres_uniques,
                    plateau,
                    dictionnaire,
                )
                if coup is not None:
                    return coup
    return None


def _essayer_accroche(
    existante: Tuile,
    case_existante: tuple[int, int],
    case_nouvelle: tuple[int, int],
    delta: tuple[int, int],
    direction: Direction,
    lettres: list[str],
    plateau: PlateauPartie,
    dictionnaire: DictionnaireMots,
) -> Coup | None:
    """Teste chaque lettre disponible pour former un mot de 2 lettres valide."""
    apres = delta in ((0, 1), (1, 0))  # la nouvelle case suit-elle l'existante ?
    for lettre in lettres:
        nouvelle = Tuile(lettre)
        if apres:
            depart = case_existante
            tuiles = (existante, nouvelle)
        else:
            depart = case_nouvelle
            tuiles = (nouvelle, existante)
        coup = Coup(depart[0], depart[1], direction, tuiles)
        if coup_valide(plateau, coup, dictionnaire):
            return coup
    return None
