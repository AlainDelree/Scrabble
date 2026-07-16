"""Gestion du sac de jetons restants (pioche du Scrabble).

Rôle : représenter le **sac** des jetons non encore posés et offrir les
opérations de pioche et de remise en jeu. Le sac part de la répartition
officielle française (:func:`scrabble.regles.lettres.constituer_sac`, 102 jetons
dont 2 jokers) puis est mélangé.

Périmètre volontairement restreint
----------------------------------
Ce module ne connaît **ni les joueurs, ni les tours, ni les chevalets** : c'est
de la pure gestion de sac. Le tirage retire des jetons du sac ; la remise les y
réintroduit (par exemple pour un échange de lettres) et re-mélange. Brancher ces
opérations sur une boucle de tour relève d'un module de jeu séparé.
"""

from __future__ import annotations

import random

from scrabble.regles.lettres import constituer_sac


class Sac:
    """Sac de jetons mélangé, avec tirage et remise en jeu.

    Chaque jeton est une chaîne d'un caractère : une majuscule ``A``–``Z`` ou le
    joker :data:`scrabble.regles.lettres.JOKER` (``"*"``). Le sac est mélangé à
    la construction. Fournir ``graine`` rend le mélange (et donc les tirages)
    reproductible — utile en test.
    """

    __slots__ = ("_jetons", "_alea")

    def __init__(self, graine: int | None = None) -> None:
        self._alea = random.Random(graine)
        self._jetons: list[str] = constituer_sac()
        self._alea.shuffle(self._jetons)

    def __len__(self) -> int:
        return len(self._jetons)

    def est_vide(self) -> bool:
        """Vrai si le sac ne contient plus aucun jeton."""
        return not self._jetons

    def jetons_restants(self) -> int:
        """Nombre de jetons encore dans le sac."""
        return len(self._jetons)

    def tirer(self, nombre: int) -> list[str]:
        """Retire et renvoie jusqu'à ``nombre`` jetons du sac.

        Si le sac contient moins de ``nombre`` jetons, on renvoie tout ce qui
        reste (le sac devient alors vide) : la pioche ne lève pas quand le sac
        s'épuise, elle rend simplement moins de jetons que demandé.

        :raises ValueError: si ``nombre`` est négatif.
        """
        if nombre < 0:
            raise ValueError(
                f"Nombre de jetons à tirer négatif : {nombre}."
            )
        pris = min(nombre, len(self._jetons))
        tires = self._jetons[:pris]
        del self._jetons[:pris]
        return tires

    def remettre(self, jetons: list[str]) -> None:
        """Remet ``jetons`` dans le sac puis re-mélange (ex. échange de lettres).

        Aucune vérification n'est faite sur la provenance des jetons : le sac ne
        suit pas les chevalets. La composition du sac n'est donc cohérente que
        si l'appelant y remet des jetons effectivement sortis du jeu.
        """
        self._jetons.extend(jetons)
        self._alea.shuffle(self._jetons)
