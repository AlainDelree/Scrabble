"""État d'un plateau de Scrabble en cours de partie et pose d'un mot.

Rôle : représenter l'**état vivant** des 225 cases du plateau (chacune vide ou
portant une tuile), poser un mot sur cette grille, et extraire les mots formés
par un coup. C'est la couche mutable qui s'appuie sur la géométrie figée de
:mod:`scrabble.regles.plateau` (cases bonus) et sur les valeurs de
:mod:`scrabble.regles.lettres`.

Séparation des responsabilités
------------------------------
Ce module ne connaît **ni les règles de validité** (case centrale, contiguïté,
appartenance au dictionnaire — voir :mod:`scrabble.moteur.validation`) **ni le
calcul du score** (voir :mod:`scrabble.moteur.score`). Il fournit uniquement la
structure de données du plateau, la pose des tuiles et l'extraction des mots
contigus, briques communes réutilisées par ces deux modules.

Tuiles et jokers
----------------
Une case occupée porte une :class:`Tuile` : sa **lettre affichée** (majuscule
``A``–``Z``) et un drapeau ``joker``. Un joker affiche bien une lettre (celle
qu'il représente sur le plateau) mais vaut **0 point** — la distinction entre la
lettre montrée et la valeur sous-jacente est ainsi conservée, comme demandé.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from scrabble.regles import plateau as regles_plateau
from scrabble.regles.lettres import valeur_lettre

#: Dimension de la grille (réexportée depuis la géométrie de référence).
TAILLE = regles_plateau.TAILLE

#: Coordonnées de la case centrale (étoile de départ).
CENTRE = regles_plateau.CENTRE


class Direction(enum.Enum):
    """Sens de pose d'un mot sur le plateau."""

    HORIZONTALE = "H"  # progresse vers la droite (colonnes croissantes)
    VERTICALE = "V"    # progresse vers le bas (lignes croissantes)

    @property
    def delta(self) -> tuple[int, int]:
        """Vecteur ``(dligne, dcolonne)`` d'avance d'une case dans ce sens."""
        return (0, 1) if self is Direction.HORIZONTALE else (1, 0)

    @property
    def perpendiculaire(self) -> "Direction":
        """La direction orthogonale (sens des mots transversaux)."""
        return (
            Direction.VERTICALE
            if self is Direction.HORIZONTALE
            else Direction.HORIZONTALE
        )


@dataclass(frozen=True)
class Tuile:
    """Une tuile posée : lettre affichée (``A``–``Z``) et drapeau ``joker``.

    La :attr:`valeur` vaut ``0`` pour un joker quelle que soit la lettre qu'il
    représente, sinon la valeur officielle de la lettre.
    """

    lettre: str
    joker: bool = False

    def __post_init__(self) -> None:
        if not (len(self.lettre) == 1 and "A" <= self.lettre <= "Z"):
            raise ValueError(
                f"Lettre de tuile invalide : {self.lettre!r} ; attendu une "
                f"majuscule 'A'-'Z' (les jokers affichent aussi une lettre)."
            )

    @property
    def valeur(self) -> int:
        """Valeur en points de la tuile (``0`` si joker)."""
        return 0 if self.joker else valeur_lettre(self.lettre)


@dataclass(frozen=True)
class Coup:
    """Description d'un coup : point de départ, direction et tuiles à poser.

    ``tuiles`` est la **suite complète** des tuiles du mot principal, dans
    l'ordre, à partir de ``(ligne, colonne)`` et en avançant selon
    ``direction``. Certaines de ces cases peuvent déjà être occupées sur le
    plateau : la tuile fournie doit alors coïncider avec celle déjà posée (voir
    :mod:`scrabble.moteur.validation`).
    """

    ligne: int
    colonne: int
    direction: Direction
    tuiles: tuple[Tuile, ...]

    def cases(self) -> list[tuple[int, int, Tuile]]:
        """Positions ``(ligne, colonne, tuile)`` du coup, dans l'ordre.

        Non borné : les positions peuvent sortir de la grille ; c'est à la
        validation (ou à :meth:`PlateauPartie.poser_coup`) de le détecter.
        """
        dl, dc = self.direction.delta
        return [
            (self.ligne + i * dl, self.colonne + i * dc, tuile)
            for i, tuile in enumerate(self.tuiles)
        ]


def dans_plateau(ligne: int, colonne: int) -> bool:
    """Vrai si ``(ligne, colonne)`` est dans la grille ``TAILLE`` × ``TAILLE``."""
    return 0 <= ligne < TAILLE and 0 <= colonne < TAILLE


def tuiles_depuis_chaine(mot: str, jokers: frozenset[int] = frozenset()) -> tuple[Tuile, ...]:
    """Construit une suite de :class:`Tuile` depuis une chaîne (aide aux tests).

    ``mot`` est une chaîne de majuscules ``A``–``Z`` ; ``jokers`` est l'ensemble
    des **indices** (base 0) des lettres à traiter comme jokers (valeur 0).
    """
    return tuple(
        Tuile(lettre, joker=(i in jokers)) for i, lettre in enumerate(mot)
    )


class PlateauPartie:
    """État mutable des 225 cases : chaque case est ``None`` ou une :class:`Tuile`."""

    __slots__ = ("_cases",)

    def __init__(self) -> None:
        self._cases: list[list[Tuile | None]] = [
            [None] * TAILLE for _ in range(TAILLE)
        ]

    # -- Lecture --------------------------------------------------------- #

    def tuile(self, ligne: int, colonne: int) -> Tuile | None:
        """Tuile posée en ``(ligne, colonne)``, ou ``None`` si la case est vide.

        :raises IndexError: si la position est hors du plateau.
        """
        if not dans_plateau(ligne, colonne):
            raise IndexError(
                f"Position hors plateau : (ligne={ligne}, colonne={colonne})."
            )
        return self._cases[ligne][colonne]

    def case_vide(self, ligne: int, colonne: int) -> bool:
        """Vrai si la case ``(ligne, colonne)`` ne porte aucune tuile."""
        return self.tuile(ligne, colonne) is None

    def est_vide(self) -> bool:
        """Vrai si aucune tuile n'est posée (plateau de début de partie)."""
        return all(case is None for rangee in self._cases for case in rangee)

    def copie(self) -> "PlateauPartie":
        """Renvoie une copie indépendante de l'état (les tuiles sont figées)."""
        clone = PlateauPartie()
        clone._cases = [rangee.copy() for rangee in self._cases]
        return clone

    # -- Écriture -------------------------------------------------------- #

    def poser_tuile(self, ligne: int, colonne: int, tuile: Tuile) -> None:
        """Pose ``tuile`` en ``(ligne, colonne)`` (écrase le contenu éventuel)."""
        if not dans_plateau(ligne, colonne):
            raise IndexError(
                f"Position hors plateau : (ligne={ligne}, colonne={colonne})."
            )
        self._cases[ligne][colonne] = tuile

    def poser_coup(self, coup: Coup) -> list[tuple[int, int]]:
        """Applique ``coup`` au plateau et renvoie les positions **nouvelles**.

        Filet de sécurité structurel — les règles complètes du jeu relèvent de
        :mod:`scrabble.moteur.validation`, mais cette pose garantit l'intégrité
        de la grille :

        * lève :class:`ValueError` si une case du coup sort du plateau ;
        * lève :class:`ValueError` si une case déjà occupée porte une lettre
          différente de celle qu'on tente d'y poser (chevauchement conflictuel).

        Les cases déjà occupées par la **même** lettre sont laissées en l'état
        (elles ne comptent pas comme nouvelles) ; seules les cases vides
        reçoivent la tuile et figurent dans la liste renvoyée.
        """
        nouvelles: list[tuple[int, int]] = []
        for ligne, colonne, tuile in coup.cases():
            if not dans_plateau(ligne, colonne):
                raise ValueError(
                    f"Le coup sort du plateau en (ligne={ligne}, "
                    f"colonne={colonne})."
                )
            existante = self._cases[ligne][colonne]
            if existante is not None:
                if existante.lettre != tuile.lettre:
                    raise ValueError(
                        f"Chevauchement conflictuel en (ligne={ligne}, "
                        f"colonne={colonne}) : la case porte "
                        f"{existante.lettre!r}, tuile posée {tuile.lettre!r}."
                    )
                continue
            self._cases[ligne][colonne] = tuile
            nouvelles.append((ligne, colonne))
        return nouvelles


# --------------------------------------------------------------------------- #
# Extraction des mots formés par un coup (brique commune validation/score)
# --------------------------------------------------------------------------- #

def mot_contigu(
    plateau: PlateauPartie, ligne: int, colonne: int, direction: Direction
) -> list[tuple[int, int, Tuile]]:
    """Mot contigu passant par ``(ligne, colonne)`` dans ``direction``.

    Remonte jusqu'au début du segment de cases occupées puis le parcourt en
    avant. Renvoie la liste ordonnée ``(ligne, colonne, tuile)`` (longueur 1 si
    la case est isolée). Suppose ``(ligne, colonne)`` occupée.
    """
    dl, dc = direction.delta
    # Reculer jusqu'au début du segment occupé.
    while (
        dans_plateau(ligne - dl, colonne - dc)
        and not plateau.case_vide(ligne - dl, colonne - dc)
    ):
        ligne, colonne = ligne - dl, colonne - dc
    # Avancer en collectant les tuiles.
    mot: list[tuple[int, int, Tuile]] = []
    while dans_plateau(ligne, colonne) and not plateau.case_vide(ligne, colonne):
        mot.append((ligne, colonne, plateau.tuile(ligne, colonne)))
        ligne, colonne = ligne + dl, colonne + dc
    return mot


def mots_formes(
    plateau: PlateauPartie,
    nouvelles_positions: list[tuple[int, int]],
    direction: Direction,
) -> list[list[tuple[int, int, Tuile]]]:
    """Liste des mots (≥ 2 lettres) formés par un coup déjà posé.

    ``nouvelles_positions`` sont les cases posées lors de ce coup ;
    ``direction`` est celle du mot principal. On renvoie le **mot principal**
    (segment contigu dans ``direction`` traversant les nouvelles cases) puis un
    **mot transversal** par nouvelle case dont le segment perpendiculaire fait
    au moins deux lettres. Les segments d'une seule lettre (aucun mot réel) sont
    ignorés.
    """
    mots: list[list[tuple[int, int, Tuile]]] = []
    if not nouvelles_positions:
        return mots

    ligne, colonne = nouvelles_positions[0]
    principal = mot_contigu(plateau, ligne, colonne, direction)
    if len(principal) >= 2:
        mots.append(principal)

    perpendiculaire = direction.perpendiculaire
    for ligne, colonne in nouvelles_positions:
        transversal = mot_contigu(plateau, ligne, colonne, perpendiculaire)
        if len(transversal) >= 2:
            mots.append(transversal)
    return mots


def lettres_du_mot(mot: list[tuple[int, int, Tuile]]) -> str:
    """Chaîne des lettres affichées d'un mot extrait (jokers inclus)."""
    return "".join(tuile.lettre for _, _, tuile in mot)
