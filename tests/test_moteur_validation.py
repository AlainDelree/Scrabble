"""Tests de ``scrabble.moteur.validation``.

Couvre chaque règle de rejet avec un message explicite : premier coup hors
centre, coup non connecté, chevauchement conflictuel, mot principal hors
dictionnaire, mot transversal hors dictionnaire — ainsi que l'acceptation d'un
coup légal.
"""

from __future__ import annotations

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.plateau_partie import (
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)
from scrabble.moteur.validation import CoupInvalide, coup_valide, valider_coup


def _trie(*mots: str) -> Trie:
    return Trie.depuis_iterable(mots)


def _plateau_avec_cadre() -> PlateauPartie:
    """Plateau où CADRE est posé horizontalement en (7,3)-(7,7) (couvre le centre)."""
    plateau = PlateauPartie()
    plateau.poser_coup(
        Coup(7, 3, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))
    )
    return plateau


# --------------------------------------------------------------------------- #
# Premier coup
# --------------------------------------------------------------------------- #

def test_premier_coup_hors_centre_rejete():
    plateau = PlateauPartie()
    coup = Coup(7, 0, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))
    with pytest.raises(CoupInvalide, match="centrale"):
        valider_coup(plateau, coup, _trie("CADRE"))


def test_premier_coup_sur_centre_accepte():
    plateau = PlateauPartie()
    coup = Coup(7, 3, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))
    valider_coup(plateau, coup, _trie("CADRE"))  # ne lève pas
    assert coup_valide(plateau, coup, _trie("CADRE"))


# --------------------------------------------------------------------------- #
# Coups suivants
# --------------------------------------------------------------------------- #

def test_coup_non_connecte_rejete():
    plateau = _plateau_avec_cadre()
    coup = Coup(0, 0, Direction.VERTICALE, tuiles_depuis_chaine("AS"))
    with pytest.raises(CoupInvalide, match="connecté"):
        valider_coup(plateau, coup, _trie("CADRE", "AS"))


def test_chevauchement_conflictuel_rejete():
    plateau = _plateau_avec_cadre()
    # (7,3) porte C ; on tente d'y poser X.
    coup = Coup(7, 3, Direction.VERTICALE, tuiles_depuis_chaine("XY"))
    with pytest.raises(CoupInvalide, match="[Cc]hevauchement"):
        valider_coup(plateau, coup, _trie("CADRE", "XY"))


def test_mot_principal_hors_dictionnaire_rejete():
    plateau = _plateau_avec_cadre()
    # D existant en (7,5), on descend un O : mot vertical "DO" absent du trie.
    coup = Coup(7, 5, Direction.VERTICALE, tuiles_depuis_chaine("DO"))
    with pytest.raises(CoupInvalide, match="DO"):
        valider_coup(plateau, coup, _trie("CADRE"))


def test_mot_transversal_hors_dictionnaire_rejete():
    plateau = _plateau_avec_cadre()
    # OK posé en (6,4)-(6,5) : verticaux OA (ok) et KD (absent) formés.
    coup = Coup(6, 4, Direction.HORIZONTALE, tuiles_depuis_chaine("OK"))
    with pytest.raises(CoupInvalide, match="KD"):
        valider_coup(plateau, coup, _trie("CADRE", "OK", "OA"))


def test_coup_connecte_valide_accepte():
    plateau = _plateau_avec_cadre()
    # A existant en (7,4), on descend un S : mot vertical "AS".
    coup = Coup(7, 4, Direction.VERTICALE, tuiles_depuis_chaine("AS"))
    valider_coup(plateau, coup, _trie("CADRE", "AS"))  # ne lève pas


def test_coup_transversal_complet_accepte():
    plateau = _plateau_avec_cadre()
    coup = Coup(6, 4, Direction.HORIZONTALE, tuiles_depuis_chaine("OK"))
    valider_coup(plateau, coup, _trie("CADRE", "OK", "OA", "KD"))  # ne lève pas
