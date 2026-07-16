"""Générateur exhaustif de coups valides pour un plateau et chevalet donnés.

Rôle : trouver TOUS les coups légaux possibles pour un chevalet donné sur un
plateau donné, avec leur score. Cette génération exhaustive servira de base
aux stratégies de sélection IA (seule la sélection variera selon le niveau).

Algorithme
----------
1. Identifier les « ancrages » : sur plateau vide, la case centrale uniquement ;
   sinon toute case vide adjacente à une case occupée.
2. Pour chaque ancrage et chaque direction (H/V), explorer les mots possibles
   en s'appuyant sur le Trie du dictionnaire pour élaguer (on ne poursuit que
   si le préfixe courant existe dans le Trie).
3. Pour chaque candidat complet, valider via :func:`validation.coup_valide`
   (pas de duplication de logique) et si valide, scorer via
   :func:`score.detailler_score`.

Jokers
------
Un jeton joker (``*``) peut représenter n'importe quelle lettre A-Z. La
recherche explore les 26 lettres possibles pour chaque joker utilisé. Pour
contenir la combinatoire, on limite à un seul joker utilisé par coup
(un chevalet avec 2 jokers utilisera au plus un des deux par placement).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    TAILLE,
    Tuile,
    dans_plateau,
)
from scrabble.moteur.score import DetailScore, detailler_score
from scrabble.moteur.validation import coup_valide
from scrabble.regles.lettres import JOKER


class TrieProtocol(Protocol):
    """Interface minimale du Trie : navigation par préfixe + test d'appartenance."""

    racine: dict

    def contient(self, mot: str) -> bool: ...


@dataclass(frozen=True)
class CoupNote:
    """Un coup valide associé à son score détaillé."""

    coup: Coup
    detail: DetailScore

    @property
    def score(self) -> int:
        """Score total du coup (raccourci)."""
        return self.detail.total


_VOISINS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FIN = "$"


def _ancrages(plateau: PlateauPartie) -> list[tuple[int, int]]:
    """Cases d'ancrage : centre si vide, sinon cases vides adjacentes à occupées."""
    if plateau.est_vide():
        return [CENTRE]
    ancrages: list[tuple[int, int]] = []
    for ligne in range(TAILLE):
        for colonne in range(TAILLE):
            if not plateau.case_vide(ligne, colonne):
                continue
            for dl, dc in _VOISINS:
                vl, vc = ligne + dl, colonne + dc
                if dans_plateau(vl, vc) and not plateau.case_vide(vl, vc):
                    ancrages.append((ligne, colonne))
                    break
    return ancrages


def _lettres_disponibles(chevalet: list[str]) -> tuple[dict[str, int], int]:
    """Compte des lettres ordinaires et nombre de jokers dans le chevalet."""
    compteur: dict[str, int] = {}
    jokers = 0
    for jeton in chevalet:
        if jeton == JOKER:
            jokers += 1
        else:
            compteur[jeton] = compteur.get(jeton, 0) + 1
    return compteur, jokers


def _explorer_direction(
    plateau: PlateauPartie,
    ancrage: tuple[int, int],
    direction: Direction,
    trie: TrieProtocol,
    compteur: dict[str, int],
    jokers_dispo: int,
) -> list[Coup]:
    """Génère tous les coups candidats partant de l'ancrage dans la direction.

    Utilise une exploration récursive avec élagage par préfixe Trie.
    """
    coups: list[Coup] = []
    dl, dc = direction.delta
    ligne_ancrage, col_ancrage = ancrage

    # Trouver le début du mot (cases occupées avant l'ancrage)
    ligne_debut, col_debut = ligne_ancrage, col_ancrage
    while True:
        nl, nc = ligne_debut - dl, col_debut - dc
        if not dans_plateau(nl, nc) or plateau.case_vide(nl, nc):
            break
        ligne_debut, col_debut = nl, nc

    # Collecter le préfixe existant (tuiles avant l'ancrage)
    prefixe_tuiles: list[Tuile] = []
    l, c = ligne_debut, col_debut
    while (l, c) != ancrage:
        tuile = plateau.tuile(l, c)
        if tuile is not None:
            prefixe_tuiles.append(tuile)
        l, c = l + dl, c + dc

    def _explorer(
        ligne: int,
        colonne: int,
        tuiles: list[Tuile],
        noeud: dict,
        restant: dict[str, int],
        jokers_restants: int,
        joker_utilise: bool,
        a_pose_lettre: bool,
    ) -> None:
        """Exploration récursive avec backtracking."""
        # Vérifier si on a un mot complet (et au moins une lettre posée)
        if _FIN in noeud and a_pose_lettre:
            # Construire le coup
            coup = Coup(ligne_debut, col_debut, direction, tuple(tuiles))
            coups.append(coup)

        # Continuer l'exploration si dans les bornes
        if not dans_plateau(ligne, colonne):
            return

        tuile_existante = plateau.tuile(ligne, colonne)
        if tuile_existante is not None:
            # Case occupée : on doit utiliser cette lettre
            lettre = tuile_existante.lettre
            if lettre in noeud:
                _explorer(
                    ligne + dl,
                    colonne + dc,
                    tuiles + [tuile_existante],
                    noeud[lettre],
                    restant,
                    jokers_restants,
                    joker_utilise,
                    a_pose_lettre,
                )
        else:
            # Case vide : on pose une lettre du chevalet
            # Essayer chaque lettre disponible
            for lettre, compte in restant.items():
                if compte <= 0:
                    continue
                if lettre not in noeud:
                    continue
                nouveau_restant = restant.copy()
                nouveau_restant[lettre] -= 1
                _explorer(
                    ligne + dl,
                    colonne + dc,
                    tuiles + [Tuile(lettre, joker=False)],
                    noeud[lettre],
                    nouveau_restant,
                    jokers_restants,
                    joker_utilise,
                    True,
                )

            # Essayer le joker (max 1 par coup pour limiter la combinatoire)
            if jokers_restants > 0 and not joker_utilise:
                for lettre in _ALPHABET:
                    if lettre not in noeud:
                        continue
                    _explorer(
                        ligne + dl,
                        colonne + dc,
                        tuiles + [Tuile(lettre, joker=True)],
                        noeud[lettre],
                        restant,
                        jokers_restants - 1,
                        True,
                        True,
                    )

    # Naviguer dans le Trie pour le préfixe existant
    noeud_depart = trie.racine
    for tuile in prefixe_tuiles:
        if tuile.lettre not in noeud_depart:
            return []
        noeud_depart = noeud_depart[tuile.lettre]

    # Lancer l'exploration depuis l'ancrage
    _explorer(
        ligne_ancrage,
        col_ancrage,
        list(prefixe_tuiles),
        noeud_depart,
        compteur.copy(),
        jokers_dispo,
        False,
        False,
    )

    return coups


def generer_coups(
    plateau: PlateauPartie,
    chevalet: list[str],
    dictionnaire: TrieProtocol,
) -> list[CoupNote]:
    """Génère tous les coups valides pour le chevalet sur le plateau.

    Renvoie une liste de :class:`CoupNote` triée par score décroissant.
    Chaque coup est validé par :func:`validation.coup_valide` et scoré
    par :func:`score.detailler_score`.

    Args:
        plateau: État courant du plateau de jeu.
        chevalet: Liste des jetons disponibles (lettres A-Z ou ``*`` pour joker).
        dictionnaire: Trie du dictionnaire (doit exposer ``.racine`` et ``.contient``).

    Returns:
        Liste de :class:`CoupNote` triée par score total décroissant.
    """
    compteur, jokers_dispo = _lettres_disponibles(chevalet)
    ancrages = _ancrages(plateau)

    candidats: list[Coup] = []
    vus: set[tuple[int, int, str, str]] = set()  # (ligne, col, direction, mot)

    for ancrage in ancrages:
        for direction in (Direction.HORIZONTALE, Direction.VERTICALE):
            coups_dir = _explorer_direction(
                plateau, ancrage, direction, dictionnaire, compteur, jokers_dispo
            )
            for coup in coups_dir:
                # Dédupliquer les coups identiques
                mot = "".join(t.lettre for t in coup.tuiles)
                cle = (coup.ligne, coup.colonne, coup.direction.value, mot)
                if cle not in vus:
                    vus.add(cle)
                    candidats.append(coup)

    # Valider et scorer chaque candidat
    resultats: list[CoupNote] = []
    for coup in candidats:
        if not coup_valide(plateau, coup, dictionnaire):
            continue
        # Appliquer le coup sur une copie pour calculer le score
        copie = plateau.copie()
        nouvelles = copie.poser_coup(coup)
        if not nouvelles:
            continue
        detail = detailler_score(copie, nouvelles, coup.direction)
        resultats.append(CoupNote(coup, detail))

    # Trier par score décroissant
    resultats.sort(key=lambda cn: cn.score, reverse=True)
    return resultats
