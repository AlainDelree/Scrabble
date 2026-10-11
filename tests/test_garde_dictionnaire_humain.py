"""Tests de garde (issue #457) : le joueur humain a accès à TOUT le
dictionnaire de la partie, quel que soit le personnage ou le niveau de
l'ordinateur adverse.

Contexte (voir le rapport de l'issue #457 et les docstrings de
``scrabble.moteur.partie.Partie``/``creer_partie``) : ``Partie.dictionnaire``
(le Trie complet transmis à :func:`~scrabble.moteur.partie.creer_partie`)
valide **toujours** un coup, qu'il soit joué par un humain ou par une IA —
``dictionnaires_ia``/:class:`~scrabble.moteur.ia.ProfilPersonnage`
(vocabulaire par palier, mots longs, mots favoris) ne pilotent QUE la
**génération** des coups candidats de l'IA
(:func:`scrabble.moteur.ia.choisir_coup`), jamais la validation. Ces tests
fabriquent de petits dictionnaires (le dictionnaire réel n'est pas disponible
dans ce worktree isolé, voir la contrainte de l'issue) pour démontrer :

1. :class:`TestValidationHumaineIdentiqueQuelleQueSoitLaConfiguration` — sur
   toutes les combinaisons niveau × personnage du registre, la validation
   d'un coup humain accepte exactement l'échantillon attendu du dictionnaire
   complet de la partie, identique à une partie sans ordinateur ;
2. :class:`TestIdentiteDictionnaireValidation` — l'objet dictionnaire de
   validation de la partie est le MÊME objet, quelle que soit la
   configuration de l'ordinateur, sans qu'aucun filtre de vocabulaire de
   l'IA ne lui soit appliqué ;
3. :class:`TestCoherenceMotsJouesParOrdinateur` — tout mot qu'un personnage à
   liste de mots favoris/longs mots peut réellement jouer (donc absent du
   vocabulaire restreint de son niveau) est un mot que la validation humaine
   accepte ;
4. :class:`TestGardeOptionBelgicisme` — l'option belgicismes (séparée, choisie
   par le joueur) n'est ni activée ni désactivée par cette règle : dans
   chaque état, la validation humaine suit exactement le dictionnaire complet
   de cet état, quelle que soit la configuration de l'ordinateur.
"""

from __future__ import annotations

import random

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau, choisir_coup, resoudre_palier
from scrabble.moteur.partie import creer_partie
from scrabble.moteur.personnages import PERSONNAGES, personnages_disponibles_a_niveau
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)
from scrabble.moteur.validation import coup_valide

# --------------------------------------------------------------------------- #
# Petit dictionnaire fabriqué (le dictionnaire réel n'est pas disponible dans
# ce worktree isolé — voir la contrainte de l'issue #457).
# --------------------------------------------------------------------------- #

#: Mot du vocabulaire courant : connu à tous les paliers restreints.
MOT_COURANT = "SOLEIL"
#: Absent du vocabulaire restreint simulé d'un niveau, présent au complet.
MOT_RARE_HORS_NIVEAU = "ANTILOPE"
#: Présent dans une liste de mots favoris (Titeuf/Lettré).
MOT_FAVORI = "ZINZIN"
#: Mot court, hors vocabulaire restreint simulé d'un niveau.
MOT_COURT_HORS_NIVEAU = "AS"
#: Mot de 7 lettres ou plus, hors vocabulaire restreint simulé d'un niveau.
MOT_LONG_HORS_NIVEAU = "GIRAFON"
#: Totalement absent du dictionnaire complet lui-même.
MOT_ABSENT = "QUIBLOX"

#: Échantillon fabriqué (point 2 de l'issue #457) : chaque mot avec le
#: résultat attendu de la validation humaine, le même dans toute
#: configuration d'ordinateur.
ECHANTILLON: tuple[tuple[str, bool], ...] = (
    (MOT_COURANT, True),
    (MOT_RARE_HORS_NIVEAU, True),
    (MOT_FAVORI, True),
    (MOT_COURT_HORS_NIVEAU, True),
    (MOT_LONG_HORS_NIVEAU, True),
    (MOT_ABSENT, False),
)

#: Mot fabriqué représentant un belgicisme sans équivalent standard (issue
#: #274) : absent du dictionnaire complet « sans belgicisme », présent dans
#: celui « avec belgicisme » — voir :class:`TestGardeOptionBelgicisme`.
MOT_BELGICISME = "WALOU"


def _trie_complet(avec_belgicisme: bool = False) -> Trie:
    """Dictionnaire complet fabriqué de la partie (tous les mots « vrais » de
    :data:`ECHANTILLON`, plus :data:`MOT_BELGICISME` si ``avec_belgicisme``)."""
    mots = [mot for mot, attendu in ECHANTILLON if attendu]
    if avec_belgicisme:
        mots.append(MOT_BELGICISME)
    return Trie.depuis_iterable(mots)


def _trie_restreint() -> Trie:
    """Vocabulaire restreint fabriqué d'un palier (simule un niveau filtré) :
    ne connaît que le mot courant — tous les autres mots de l'échantillon
    (rare, favori, court, long) lui sont étrangers, pour vérifier qu'ils
    restent néanmoins jouables par l'humain."""
    return Trie.depuis_iterable({MOT_COURANT})


def _coup_au_centre(mot: str) -> Coup:
    """Coup fabriqué posant ``mot`` horizontalement à partir de la case
    centrale : couvre toujours la case centrale, donc légal en premier coup
    sur un plateau vide, quel que soit le mot (longueur ≤ 8 lettres, tient
    dans la grille 15×15 depuis la colonne centrale)."""
    ligne, colonne = CENTRE
    return Coup(ligne, colonne, Direction.HORIZONTALE, tuiles_depuis_chaine(mot))


def _dictionnaires_ia_pour_niveau(
    niveau: Niveau, trie_restreint: Trie
) -> dict[Niveau, Trie]:
    """Mapping ``dictionnaires_ia`` fabriqué, sur le modèle exact
    d':meth:`~scrabble.ui.accueil.ApiAccueil._construire_trie_ia` : un palier
    restreint pour les niveaux qui en ont un en production (DEBUTANT, FACILE,
    INTERMEDIAIRE, AVANCE), rien (repli sur le dictionnaire complet) pour
    EXPERT/CHAMPION_DU_MONDE."""
    if resoudre_palier(niveau) is None:
        return {}
    return {niveau: trie_restreint}


def _combinaisons_niveau_personnage() -> list[tuple[Niveau, str]]:
    """Toutes les combinaisons niveau × personnage réellement disponibles,
    dérivées du registre (pas d'une liste codée en dur) pour couvrir
    automatiquement un futur personnage ajouté à ``PERSONNAGES``."""
    return [
        (niveau, personnage.cle)
        for niveau in Niveau
        for personnage in personnages_disponibles_a_niveau(niveau)
    ]


def _partie_avec_ordinateur(
    niveau: Niveau, personnage_cle: str, trie_complet: Trie, trie_restreint: Trie
):
    return creer_partie(
        noms_humains=["Alice"],
        dictionnaire=trie_complet,
        nb_ia=1,
        noms_ia=["Robot"],
        niveaux_ia=[niveau],
        personnages_ia=[personnage_cle],
        dictionnaires_ia=_dictionnaires_ia_pour_niveau(niveau, trie_restreint),
    )


_COMBINAISONS = _combinaisons_niveau_personnage()
_IDS_COMBINAISONS = [f"{niveau.name}-{cle}" for niveau, cle in _COMBINAISONS]


# --------------------------------------------------------------------------- #
# Point 2 de l'issue #457 : validation humaine = dictionnaire complet, quelle
# que soit la configuration de l'ordinateur.
# --------------------------------------------------------------------------- #


class TestValidationHumaineIdentiqueQuelleQueSoitLaConfiguration:
    """La validation d'un coup humain accepte exactement l'échantillon
    attendu du dictionnaire complet, pour toute combinaison niveau ×
    personnage disponible."""

    @pytest.mark.parametrize(
        "niveau,personnage_cle", _COMBINAISONS, ids=_IDS_COMBINAISONS
    )
    def test_echantillon_complet_accepte_quelle_que_soit_la_config(
        self, niveau, personnage_cle
    ):
        trie_complet = _trie_complet()
        partie = _partie_avec_ordinateur(
            niveau, personnage_cle, trie_complet, _trie_restreint()
        )
        for mot, attendu in ECHANTILLON:
            resultat = coup_valide(
                PlateauPartie(), _coup_au_centre(mot), partie.dictionnaire
            )
            assert resultat is attendu, (
                f"{mot!r} : attendu {attendu}, obtenu {resultat} "
                f"(niveau={niveau}, personnage={personnage_cle!r})"
            )

    def test_identique_a_une_partie_sans_ordinateur(self):
        """Même résultat, mot pour mot, qu'une partie purement humaine —
        aucune configuration d'ordinateur ne doit faire dévier la
        validation."""
        trie_complet = _trie_complet()
        partie_solo = creer_partie(noms_humains=["Alice"], dictionnaire=trie_complet)
        resultats_solo = {
            mot: coup_valide(
                PlateauPartie(), _coup_au_centre(mot), partie_solo.dictionnaire
            )
            for mot, _ in ECHANTILLON
        }
        trie_restreint = _trie_restreint()
        for niveau, personnage_cle in _COMBINAISONS:
            partie = _partie_avec_ordinateur(
                niveau, personnage_cle, trie_complet, trie_restreint
            )
            for mot, _ in ECHANTILLON:
                resultat = coup_valide(
                    PlateauPartie(), _coup_au_centre(mot), partie.dictionnaire
                )
                assert resultat == resultats_solo[mot], (
                    f"{mot!r} diverge de la partie solo pour "
                    f"niveau={niveau}, personnage={personnage_cle!r}"
                )


# --------------------------------------------------------------------------- #
# Point 4 de l'issue #457 : identité de l'objet dictionnaire de validation.
# --------------------------------------------------------------------------- #


class TestIdentiteDictionnaireValidation:
    """L'objet dictionnaire de validation (``Partie.dictionnaire``) est
    rigoureusement le même objet, quelle que soit la configuration de
    l'ordinateur — aucun filtre de vocabulaire de l'IA ne lui est jamais
    appliqué."""

    @pytest.mark.parametrize(
        "niveau,personnage_cle", _COMBINAISONS, ids=_IDS_COMBINAISONS
    )
    def test_dictionnaire_de_la_partie_est_exactement_le_trie_fourni(
        self, niveau, personnage_cle
    ):
        trie_complet = _trie_complet()
        trie_restreint = _trie_restreint()
        partie = _partie_avec_ordinateur(
            niveau, personnage_cle, trie_complet, trie_restreint
        )
        assert partie.dictionnaire is trie_complet
        # Quand un palier restreint existe pour ce niveau, il reste un objet
        # séparé — jamais substitué au dictionnaire de validation.
        if niveau in partie.dictionnaires_ia:
            assert partie.dictionnaires_ia[niveau] is trie_restreint
            assert partie.dictionnaires_ia[niveau] is not partie.dictionnaire

    def test_dictionnaire_partage_entre_partie_solo_et_partie_avec_ordinateurs(self):
        """Deux parties construites avec le même Trie complet partagent le
        même objet de validation, peu importe le nombre, le niveau ou le
        personnage des ordinateurs."""
        trie_complet = _trie_complet()
        partie_solo = creer_partie(noms_humains=["Alice"], dictionnaire=trie_complet)
        partie_avec_ia = creer_partie(
            noms_humains=["Alice"],
            dictionnaire=trie_complet,
            nb_ia=1,
            noms_ia=["Robot"],
            niveaux_ia=[Niveau.EXPERT],
            personnages_ia=["lettre"],
        )
        assert partie_solo.dictionnaire is partie_avec_ia.dictionnaire is trie_complet


# --------------------------------------------------------------------------- #
# Point 3 de l'issue #457 : cohérence avec ce que joue réellement l'ordinateur.
# --------------------------------------------------------------------------- #


class TestCoherenceMotsJouesParOrdinateur:
    """Tout mot qu'un personnage peut jouer grâce à ``mots_favoris`` /
    ``vocabulaire_long`` (donc absent du vocabulaire restreint de son
    niveau) doit être un mot accepté par la validation d'un coup humain — la
    même qui gagne le droit de l'appliquer réellement sur le plateau (voir
    ``Partie.jouer_tour_ia`` -> ``Partie.jouer_coup`` ->
    ``valider_coup(..., self.dictionnaire)``, jamais
    ``self.dictionnaires_ia``)."""

    # -- Scénario Titeuf (mot favori court, tirage pondéré) -------------- #

    @staticmethod
    def _plateau_titeuf() -> PlateauPartie:
        plateau = PlateauPartie()
        plateau.poser_coup(
            Coup(7, 6, Direction.HORIZONTALE, tuiles_depuis_chaine("Z"))
        )
        return plateau

    def test_mot_favori_joue_par_titeuf_est_accepte_par_la_validation_humaine(self):
        plateau = self._plateau_titeuf()
        chevalet = list("CACAXYW")
        dico_niveau = Trie.depuis_iterable(("ZX", "ZY", "ZW"))
        dico_complet = Trie.depuis_iterable(("ZX", "ZY", "ZW", "CACA", "ZC"))
        profil = PERSONNAGES["titeuf"].profil

        au_moins_un_favori_joue = False
        for graine in range(100):
            coup = choisir_coup(
                plateau,
                chevalet,
                dico_niveau,
                Niveau.DEBUTANT,
                random.Random(graine),
                profil=profil,
                dictionnaire_complet=dico_complet,
            )
            if coup is None:
                continue
            mot = "".join(tuile.lettre for tuile in coup.tuiles)
            if mot != "CACA":
                continue
            au_moins_un_favori_joue = True
            # Absent du vocabulaire restreint du niveau de l'ordinateur...
            assert not dico_niveau.contient(mot)
            # ... mais accepté par la validation qui gagne un coup humain.
            assert coup_valide(plateau, coup, dico_complet)
        assert au_moins_un_favori_joue

    # -- Scénario Lettré (mot favori long, bonus de score déterministe) -- #

    @staticmethod
    def _plateau_lettre() -> PlateauPartie:
        plateau = PlateauPartie()
        plateau.poser_coup(
            Coup(7, 11, Direction.HORIZONTALE, tuiles_depuis_chaine("Z"))
        )
        plateau.poser_coup(
            Coup(0, 0, Direction.HORIZONTALE, tuiles_depuis_chaine("A"))
        )
        return plateau

    def test_mot_favori_joue_par_lettre_est_accepte_par_la_validation_humaine(self):
        """Niveau AVANCE seulement : à EXPERT/CHAMPION_DU_MONDE, ce même
        scénario fabriqué ne fait déjà plus gagner le mot favori à Lettré
        sur ce dépôt — écart préexistant, confirmé par ``git stash``,
        indépendant de l'issue #457 (voir
        ``TestPersonnageLettre.test_lettre_joue_toujours_le_mot_favori_sur_ce_scenario``
        dans ``tests/test_moteur_personnages.py``, déjà rouge à ces deux
        niveaux avant tout travail de cette issue) — hors périmètre ici."""
        plateau = self._plateau_lettre()
        chevalet = list("OTAZURE")
        dico_niveau = Trie.depuis_iterable(("ZOTA",))
        dico_complet = Trie.depuis_iterable(("ZOTA", "AZOTURE"))
        profil = PERSONNAGES["lettre"].profil

        # Scénario déterministe (voir tests/test_moteur_personnages.py) :
        # Lettré joue toujours AZOTURE sur ce plateau, à AVANCE.
        coup = choisir_coup(
            plateau,
            chevalet,
            dico_niveau,
            Niveau.AVANCE,
            random.Random(0),
            profil=profil,
            dictionnaire_complet=dico_complet,
        )
        assert coup is not None
        mot = "".join(tuile.lettre for tuile in coup.tuiles)
        assert mot == "AZOTURE"
        # Absent du vocabulaire restreint du niveau de l'ordinateur...
        assert not dico_niveau.contient(mot)
        # ... mais accepté par la validation qui gagne un coup humain.
        assert coup_valide(plateau, coup, dico_complet)

    # -- Scénario Chasseur de scrabbles (vocabulaire_long, 7 lettres) ---- #

    @staticmethod
    def _plateau_chasseur() -> PlateauPartie:
        plateau = PlateauPartie()
        plateau.poser_coup(
            Coup(7, 7, Direction.HORIZONTALE, tuiles_depuis_chaine("DA"))
        )
        plateau.poser_coup(
            Coup(0, 10, Direction.HORIZONTALE, tuiles_depuis_chaine("Z"))
        )
        return plateau

    @pytest.mark.parametrize("niveau", [Niveau.INTERMEDIAIRE, Niveau.AVANCE])
    def test_scrabble_long_joue_par_chasseur_est_accepte_par_la_validation_humaine(
        self, niveau
    ):
        plateau = self._plateau_chasseur()
        chevalet = list("KWXOULN")
        # Vocabulaire restreint du niveau : ne connaît que les mots déjà sur
        # le plateau, PAS le mot de 7 lettres qui fait le scrabble.
        dico_niveau = Trie.depuis_iterable(("DA", "Z", "ZOKWX"))
        dico_complet = Trie.depuis_iterable(("DA", "Z", "ZOKWX", "AOKWUXLN"))
        profil = PERSONNAGES["chasseur_de_scrabbles"].profil

        au_moins_un_scrabble_joue = False
        for graine in range(200):
            coup = choisir_coup(
                plateau,
                chevalet,
                dico_niveau,
                niveau,
                random.Random(graine),
                profil=profil,
                dictionnaire_complet=dico_complet,
            )
            if coup is None:
                continue
            mot = "".join(tuile.lettre for tuile in coup.tuiles)
            if mot != "AOKWUXLN":
                continue
            au_moins_un_scrabble_joue = True
            assert not dico_niveau.contient(mot)
            assert coup_valide(plateau, coup, dico_complet)
        assert au_moins_un_scrabble_joue


# --------------------------------------------------------------------------- #
# Contrainte de l'issue #457 : l'option belgicismes reste séparée.
# --------------------------------------------------------------------------- #


class TestGardeOptionBelgicisme:
    """Les belgicismes restent une option séparée, choisie par le joueur au
    lancement (issue #274) : cette règle de garde ne les active ni ne les
    désactive. Dans CHAQUE état, la validation humaine accepte exactement le
    dictionnaire complet de cet état, quelle que soit la configuration de
    l'ordinateur."""

    @pytest.mark.parametrize("avec_belgicisme", [False, True])
    @pytest.mark.parametrize(
        "niveau,personnage_cle", _COMBINAISONS, ids=_IDS_COMBINAISONS
    )
    def test_mot_belgicisme_suit_exactement_letat_actif(
        self, niveau, personnage_cle, avec_belgicisme
    ):
        trie_complet = _trie_complet(avec_belgicisme)
        partie = _partie_avec_ordinateur(
            niveau, personnage_cle, trie_complet, _trie_restreint()
        )
        resultat = coup_valide(
            PlateauPartie(), _coup_au_centre(MOT_BELGICISME), partie.dictionnaire
        )
        assert resultat is avec_belgicisme
