"""Tests de ``scrabble.moteur.partie``.

Couvre l'initialisation (1 joueur, 4 joueurs, mix humains/IA), le déroulement
d'un tour (pose, passe, échange), la mise à jour du chevalet et du score, les
deux conditions de fin de partie (sac vide + chevalet vide, passes
consécutives), le calcul du score final avec pénalité des lettres restantes, la
gestion d'égalité, et l'intégration basique des tours IA (tests approfondis des
niveaux dans ``test_moteur_ia.py``).
"""

from __future__ import annotations

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)
from scrabble.moteur.partie import (
    ACTION_COUP,
    ACTION_ECHANGE,
    ACTION_PASSE,
    ActionInvalide,
    Joueur,
    Partie,
    TAILLE_CHEVALET,
    creer_partie,
)


def _trie(*mots: str) -> Trie:
    return Trie.depuis_iterable(mots)


def _coup_cadre_au_centre() -> Coup:
    """CADRE horizontal à partir de la case centrale (couvre le centre)."""
    ligne, colonne = CENTRE
    return Coup(ligne, colonne, Direction.HORIZONTALE, tuiles_depuis_chaine("CADRE"))


def _vider_sac(partie: Partie) -> None:
    partie.sac.tirer(partie.sac.jetons_restants())


# --------------------------------------------------------------------------- #
# Initialisation
# --------------------------------------------------------------------------- #

def test_init_un_joueur():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    assert len(partie.joueurs) == 1
    assert len(partie.joueurs[0].chevalet) == TAILLE_CHEVALET
    assert partie.sac.jetons_restants() == 102 - TAILLE_CHEVALET
    assert partie.index_courant == 0
    assert not partie.terminee


def test_init_quatre_joueurs():
    joueurs = [Joueur(nom) for nom in ("A", "B", "C", "D")]
    partie = Partie(joueurs, _trie(), graine=1)
    assert len(partie.joueurs) == 4
    for joueur in partie.joueurs:
        assert len(joueur.chevalet) == TAILLE_CHEVALET
    assert partie.sac.jetons_restants() == 102 - 4 * TAILLE_CHEVALET


def test_init_mix_humains_ia():
    partie = creer_partie(["Alice", "Bob"], _trie(), nb_ia=2, graine=1)
    assert [j.humain for j in partie.joueurs] == [True, True, False, False]
    assert partie.joueurs[2].nom == "IA 1"
    assert partie.joueurs[3].nom == "IA 2"
    assert partie.sac.jetons_restants() == 102 - 4 * TAILLE_CHEVALET


def test_creer_partie_refuse_zero_humain():
    with pytest.raises(ValueError):
        creer_partie([], _trie(), nb_ia=2)


def test_creer_partie_refuse_plus_de_quatre():
    with pytest.raises(ValueError, match="Trop de joueurs"):
        creer_partie(["A", "B", "C"], _trie(), nb_ia=3)


def test_partie_refuse_nombre_joueurs_invalide():
    with pytest.raises(ValueError):
        Partie([], _trie())


def test_creer_partie_sans_tirage_ordre_preserve_ordre_creation():
    # Non-régression : par défaut, l'ordre reste celui de création.
    partie = creer_partie(["Alice", "Bob"], _trie(), nb_ia=1, graine=1)
    assert [j.nom for j in partie.joueurs] == ["Alice", "Bob", "IA 1"]
    for joueur in partie.joueurs:
        assert len(joueur.chevalet) == TAILLE_CHEVALET


def test_creer_partie_tirage_ordre_reordonne_selon_le_tirage():
    import random

    from scrabble.moteur.ordre import determiner_ordre_jeu

    noms = ["Alice", "Bob", "Carol", "Dan"]
    # L'ordre attendu est celui que produit la même graine sur les 4 joueurs.
    attendu = determiner_ordre_jeu(noms, random.Random(42))
    ordre_noms = [noms[i] for i in attendu.ordre]

    partie = creer_partie(noms, _trie(), graine=42, tirage_ordre=True)
    assert [j.nom for j in partie.joueurs] == ordre_noms
    # La distribution des chevalets a bien eu lieu ensuite, sur le sac complet.
    for joueur in partie.joueurs:
        assert len(joueur.chevalet) == TAILLE_CHEVALET
    assert partie.sac.jetons_restants() == 102 - 4 * TAILLE_CHEVALET


def test_creer_partie_tirage_ordre_change_effectivement_l_ordre():
    # Sur au moins une graine, l'ordre tiré diffère de l'ordre de création :
    # preuve que le paramètre a un effet observable.
    noms = ["Alice", "Bob", "Carol", "Dan"]
    for graine in range(50):
        partie = creer_partie(noms, _trie(), graine=graine, tirage_ordre=True)
        if [j.nom for j in partie.joueurs] != noms:
            return
    raise AssertionError("tirage_ordre n'a jamais modifié l'ordre de création.")


# --------------------------------------------------------------------------- #
# Déroulement d'un tour : pose
# --------------------------------------------------------------------------- #

def test_jouer_coup_met_a_jour_score_chevalet_et_historique():
    partie = Partie([Joueur("Alice")], _trie("CADRE"), graine=1)
    partie.joueurs[0].chevalet[:] = list("CADRE")
    entree = partie.jouer_coup(_coup_cadre_au_centre())

    assert entree.action == ACTION_COUP
    assert entree.detail is not None and entree.detail.total > 0
    assert partie.joueurs[0].score == entree.detail.total
    assert entree.score_cumule == partie.joueurs[0].score
    # Chevalet vidé des 5 lettres posées puis complété à 7 depuis le sac.
    assert len(partie.joueurs[0].chevalet) == TAILLE_CHEVALET
    assert not partie.plateau.est_vide()
    assert partie.passes_consecutives == 0
    assert partie.historique == [entree]


def test_jouer_coup_enregistre_les_positions_posees():
    # Issue #58 : l'entrée d'historique d'un coup mémorise les cases NOUVELLES
    # (celles renvoyées par PlateauPartie.poser_coup), sans recalcul. CADRE est
    # posé horizontalement depuis le centre (7, 7).
    partie = Partie([Joueur("Alice")], _trie("CADRE"), graine=1)
    partie.joueurs[0].chevalet[:] = list("CADRE")
    entree = partie.jouer_coup(_coup_cadre_au_centre())
    assert entree.positions_posees == [(7, 7), (7, 8), (7, 9), (7, 10), (7, 11)]


def test_passe_et_echange_sans_positions_posees():
    # Une passe ou un échange ne pose aucune tuile : positions_posees vide.
    partie = Partie([Joueur("Alice"), Joueur("Bob")], _trie("CADRE"), graine=1)
    entree_passe = partie.passer()
    assert entree_passe.positions_posees == []
    entree_echange = partie.echanger(partie.joueurs[1].chevalet[:1])
    assert entree_echange.positions_posees == []


def test_jouer_coup_complement_limite_par_sac_presque_vide():
    partie = Partie([Joueur("Alice"), Joueur("Bob")], _trie("CADRE"), graine=1)
    partie.joueurs[0].chevalet[:] = list("CADRE")
    _vider_sac(partie)
    partie.sac.remettre(["A", "B"])  # exactement 2 jetons disponibles
    partie.jouer_coup(_coup_cadre_au_centre())
    # 5 lettres posées, chevalet vidé, seul 2 jetons pour compléter.
    assert len(partie.joueurs[0].chevalet) == 2


def test_jouer_coup_lettres_absentes_du_chevalet_rejete():
    partie = Partie([Joueur("Alice")], _trie("CADRE"), graine=1)
    partie.joueurs[0].chevalet[:] = list("XYZTKW")  # pas les lettres de CADRE
    with pytest.raises(ActionInvalide, match="chevalet"):
        partie.jouer_coup(_coup_cadre_au_centre())


# --------------------------------------------------------------------------- #
# Déroulement d'un tour : passe et échange
# --------------------------------------------------------------------------- #

def test_passer_avance_le_joueur_et_incremente_le_compteur():
    partie = Partie([Joueur("A"), Joueur("B")], _trie(), graine=1)
    entree = partie.passer()
    assert entree.action == ACTION_PASSE
    assert partie.passes_consecutives == 1
    assert partie.index_courant == 1
    assert not partie.terminee


def test_echanger_conserve_la_taille_du_sac_et_du_chevalet():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    avant_sac = partie.sac.jetons_restants()
    a_echanger = partie.joueur_courant().chevalet[:3]
    entree = partie.echanger(a_echanger)
    assert entree.action == ACTION_ECHANGE
    assert entree.lettres_echangees == 3
    assert len(partie.joueur_courant().chevalet) == TAILLE_CHEVALET
    assert partie.sac.jetons_restants() == avant_sac  # 3 tirés, 3 remis


def test_echanger_refuse_si_sac_trop_pauvre():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    _vider_sac(partie)
    partie.sac.remettre(["A", "B"])  # 2 jetons seulement
    with pytest.raises(ActionInvalide, match="sac"):
        partie.echanger(partie.joueur_courant().chevalet[:3])


def test_echanger_refuse_lettres_absentes():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    partie.joueurs[0].chevalet[:] = list("AAAAAAA")
    with pytest.raises(ActionInvalide, match="chevalet"):
        partie.echanger(["Z"])


# --------------------------------------------------------------------------- #
# Fin de partie
# --------------------------------------------------------------------------- #

def test_fin_sur_sac_vide_et_chevalet_vide():
    partie = Partie([Joueur("Alice")], _trie("CADRE"), graine=1)
    partie.joueurs[0].chevalet[:] = list("CADRE")
    _vider_sac(partie)
    partie.jouer_coup(_coup_cadre_au_centre())
    assert partie.terminee
    assert partie.joueurs[0].chevalet == []
    assert partie.gagnants == [partie.joueurs[0]]


def test_fin_sur_passes_consecutives():
    partie = Partie([Joueur("A"), Joueur("B")], _trie(), graine=1)
    partie.passer()  # A passe (compteur 1)
    partie.passer()  # B passe (compteur 2 == nb joueurs) -> fin
    assert partie.terminee
    assert partie.passes_consecutives == 2


def test_score_final_penalise_les_lettres_restantes():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    partie.joueurs[0].chevalet[:] = ["K", "Z"]  # 10 + 10 = 20 points
    partie.joueurs[0].score = 30
    partie.passer()  # un seul joueur : une passe suffit à terminer
    assert partie.terminee
    assert partie.joueurs[0].score == 30 - 20


def test_gagnants_gere_les_egalites():
    joueurs = [Joueur("A"), Joueur("B")]
    partie = Partie(joueurs, _trie(), graine=1)
    for joueur in partie.joueurs:
        joueur.chevalet.clear()  # aucune pénalité
        joueur.score = 42
    partie.passer()
    partie.passer()
    assert partie.terminee
    assert len(partie.gagnants) == 2
    assert all(any(g is j for j in partie.joueurs) for g in partie.gagnants)


def test_action_sur_partie_terminee_rejetee():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    partie.passer()  # termine la partie (1 joueur)
    with pytest.raises(ActionInvalide, match="terminée"):
        partie.passer()


# --------------------------------------------------------------------------- #
# Tours IA (tests basiques — tests approfondis dans test_moteur_ia.py)
# --------------------------------------------------------------------------- #

def test_ia_pose_un_premier_coup():
    from scrabble.moteur.ia import Niveau
    partie = Partie(
        [Joueur("IA", humain=False, niveau=Niveau.EXPERT)], _trie("CADRE"), graine=1
    )
    partie.joueurs[0].chevalet[:] = list("CADRE")
    entree = partie.jouer_tour_ia()
    assert entree.action == ACTION_COUP
    assert partie.joueurs[0].score > 0
    assert not partie.plateau.est_vide()


def test_ia_passe_si_aucun_coup():
    from scrabble.moteur.ia import Niveau
    # Deux joueurs pour qu'une passe IA ne termine pas la partie.
    partie = Partie(
        [Joueur("IA", humain=False, niveau=Niveau.EXPERT), Joueur("Humain")],
        _trie("CADRE"),
        graine=1,
    )
    partie.joueurs[0].chevalet[:] = list("BCDFGHJ")  # aucune voyelle jouable
    entree = partie.jouer_tour_ia()
    assert entree.action == ACTION_PASSE
    assert not partie.terminee
    assert partie.index_courant == 1


def test_ia_joue_un_mot_existant():
    from scrabble.moteur.ia import Niveau
    partie = Partie(
        [Joueur("Humain"), Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
        _trie("CADRE", "AS", "CADRES"),
        graine=1,
    )
    partie.joueurs[0].chevalet[:] = list("CADRE")
    partie.jouer_coup(_coup_cadre_au_centre())  # pose CADRE, main à l'IA
    partie.joueurs[1].chevalet[:] = ["S", "A", "T", "E", "R", "I", "O"]
    entree = partie.jouer_tour_ia()
    assert entree.action == ACTION_COUP
    assert partie.joueurs[1].score > 0


def test_jouer_tour_ia_refuse_joueur_humain():
    partie = Partie([Joueur("Alice")], _trie(), graine=1)
    with pytest.raises(ActionInvalide, match="humain"):
        partie.jouer_tour_ia()


def test_jouer_tours_ia_enchaine_jusqu_a_un_humain():
    partie = creer_partie(["Humain"], _trie("CADRE"), nb_ia=1, graine=1)
    # Humain d'abord (index 0) : jouer_tours_ia ne doit rien faire.
    assert partie.jouer_tours_ia() == []
    assert partie.joueur_courant().humain
