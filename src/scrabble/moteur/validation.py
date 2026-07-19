"""Validation d'un coup de Scrabble (règles de légalité d'un placement).

Rôle : décider si un :class:`~scrabble.moteur.plateau_partie.Coup` est **légal**
sur un état de plateau donné, et **rejeter avec un message explicite** en cas de
violation (jamais d'échec silencieux). Ce module ne calcule aucun score (voir
:mod:`scrabble.moteur.score`) et ne modifie pas le plateau réel : il raisonne
sur une copie de travail.

Règles vérifiées (dans l'ordre)
-------------------------------
1. Le coup pose au moins une tuile et reste dans les bornes du plateau.
2. Aucun chevauchement conflictuel (une case occupée doit porter la même lettre).
3. Le coup pose au moins une **lettre nouvelle** (il ne se contente pas de
   recouvrir des tuiles existantes).
4. Premier coup de la partie : il doit couvrir la case centrale. Coups suivants :
   le mot doit être connecté à au moins une tuile déjà posée (contiguïté).
5. Le mot principal **et** tous les mots transversaux formés existent dans le
   dictionnaire (Trie ODS8). En cas d'échec, **tous** les mots invalides sont
   listés dans le message (issue #126), pas seulement le premier rencontré.

Le caractère « premier coup » est déduit de l'état du plateau
(:meth:`PlateauPartie.est_vide`), pas d'un compteur externe.
"""

from __future__ import annotations

from typing import Protocol

from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    PlateauPartie,
    dans_plateau,
    lettres_du_mot,
    mots_formes,
)


class CoupInvalide(ValueError):
    """Levée quand un coup viole une règle de placement (message explicite)."""


class DictionnaireMots(Protocol):
    """Interface minimale attendue d'un dictionnaire : test d'appartenance.

    Compatible avec :class:`scrabble.dictionnaire.dictionnaire.Trie` (méthode
    ``contient``). Tout objet exposant ``contient(mot) -> bool`` convient.
    """

    def contient(self, mot: str) -> bool: ...


# Voisinages orthogonaux d'une case (haut, bas, gauche, droite).
_VOISINS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def valider_coup(
    plateau: PlateauPartie, coup: Coup, dictionnaire: DictionnaireMots
) -> None:
    """Valide ``coup`` sur ``plateau`` ; lève :class:`CoupInvalide` si illégal.

    Ne modifie pas ``plateau``. Le dictionnaire (Trie ODS8) sert à vérifier que
    chaque mot formé existe. En l'absence d'exception, le coup est légal et peut
    être appliqué via :meth:`PlateauPartie.poser_coup`.
    """
    cases = coup.cases()
    if not cases:
        raise CoupInvalide("Le coup ne pose aucune tuile.")

    # 1. Bornes du plateau.
    for ligne, colonne, _ in cases:
        if not dans_plateau(ligne, colonne):
            raise CoupInvalide(
                f"Le mot sort du plateau en (ligne={ligne}, colonne={colonne})."
            )

    # 2. Chevauchements conflictuels + recensement des nouvelles cases.
    nouvelles: list[tuple[int, int]] = []
    for ligne, colonne, tuile in cases:
        existante = plateau.tuile(ligne, colonne)
        if existante is None:
            nouvelles.append((ligne, colonne))
        elif existante.lettre != tuile.lettre:
            raise CoupInvalide(
                f"Chevauchement conflictuel en (ligne={ligne}, colonne={colonne}) : "
                f"la case porte déjà {existante.lettre!r}, "
                f"tuile posée {tuile.lettre!r}."
            )

    # 3. Au moins une lettre nouvelle.
    if not nouvelles:
        raise CoupInvalide(
            "Le coup ne pose aucune lettre nouvelle (il ne recouvre que des "
            "tuiles déjà présentes)."
        )

    # 4. Case centrale (premier coup) ou contiguïté (coups suivants).
    premier_coup = plateau.est_vide()
    if premier_coup:
        if CENTRE not in {(l, c) for l, c, _ in cases}:
            raise CoupInvalide(
                f"Le premier coup doit couvrir la case centrale {CENTRE}."
            )
    elif not _est_connecte(plateau, nouvelles):
        raise CoupInvalide(
            "Le mot doit être connecté à au moins une lettre déjà posée."
        )

    # 5. Validité de tous les mots formés (sur une copie de travail).
    travail = plateau.copie()
    travail.poser_coup(coup)
    mots = mots_formes(travail, nouvelles, coup.direction)
    if not mots:
        raise CoupInvalide("Le coup ne forme aucun mot d'au moins deux lettres.")
    # On collecte **tous** les mots invalides (pas seulement le premier) afin que
    # le joueur puisse corriger son coup en une seule fois (issue #126).
    invalides: list[str] = []
    for mot in mots:
        texte = lettres_du_mot(mot)
        if not dictionnaire.contient(texte) and texte not in invalides:
            invalides.append(texte)
    if invalides:
        raise CoupInvalide(_message_mots_invalides(invalides))


def _message_mots_invalides(invalides: list[str]) -> str:
    """Compose le message d'erreur listant les mots absents du dictionnaire.

    Reprend le libellé historique au singulier pour un seul mot, et passe au
    pluriel (« Les mots 'GE' et 'EE' n'existent pas… ») dès qu'il y en a
    plusieurs, en énumérant tous les mots invalides dans l'ordre de rencontre.
    """
    if len(invalides) == 1:
        return f"Le mot {invalides[0]!r} n'existe pas dans le dictionnaire."
    liste = ", ".join(repr(mot) for mot in invalides[:-1])
    liste = f"{liste} et {invalides[-1]!r}"
    return f"Les mots {liste} n'existent pas dans le dictionnaire."


def coup_valide(
    plateau: PlateauPartie, coup: Coup, dictionnaire: DictionnaireMots
) -> bool:
    """Variante booléenne de :func:`valider_coup` (avale :class:`CoupInvalide`)."""
    try:
        valider_coup(plateau, coup, dictionnaire)
    except CoupInvalide:
        return False
    return True


def _est_connecte(
    plateau: PlateauPartie, nouvelles: list[tuple[int, int]]
) -> bool:
    """Vrai si une nouvelle case touche une tuile déjà présente sur le plateau.

    La contiguïté est établie dès qu'une case nouvellement posée a un voisin
    orthogonal déjà occupé **avant** ce coup. Un coup qui recouvre (traverse)
    des tuiles existantes est connecté par construction : chaque tuile traversée
    est voisine d'une nouvelle case.
    """
    ensemble_nouvelles = set(nouvelles)
    for ligne, colonne in nouvelles:
        for dl, dc in _VOISINS:
            vl, vc = ligne + dl, colonne + dc
            if not dans_plateau(vl, vc):
                continue
            if (vl, vc) in ensemble_nouvelles:
                continue
            if not plateau.case_vide(vl, vc):
                return True
    return False
