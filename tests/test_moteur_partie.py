"""Tests de ``scrabble.moteur.partie``.

Couvre l'initialisation (1 joueur, 4 joueurs, mix humains/IA), le déroulement
d'un tour (pose, passe, échange), la mise à jour du chevalet et du score, les
deux conditions de fin de partie (sac vide + chevalet vide, passes
consécutives), le calcul du score final avec pénalité des lettres restantes, la
gestion d'égalité, et l'intégration basique des tours IA (tests approfondis des
niveaux dans ``test_moteur_ia.py``).
"""

from __future__ import annotations

import random

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    PlateauPartie,
    tuiles_depuis_chaine,
)
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import (
    ACTION_COUP,
    ACTION_ECHANGE,
    ACTION_PASSE,
    ActionInvalide,
    Joueur,
    Partie,
    TAILLE_CHEVALET,
    creer_partie,
    recreer_partie_meme_joueurs,
)
from scrabble.regles.lettres import JOKER


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
# Personnages IA : choix explicite et tirage « Aléatoire » (issue #440, lot D)
# --------------------------------------------------------------------------- #

def test_creer_partie_sans_personnages_ia_laisse_personnage_vide():
    """Non-régression : ``personnages_ia`` omis == comportement d'avant le lot D."""
    partie = creer_partie(["Alice"], _trie(), nb_ia=1, graine=1)
    assert partie.joueurs[1].personnage == ""
    assert partie.joueurs[1].personnage_aleatoire is False


def test_creer_partie_personnage_explicite_est_repris_tel_quel():
    partie = creer_partie(
        ["Alice"],
        _trie(),
        nb_ia=1,
        personnages_ia=["opportuniste"],
        graine=1,
    )
    assert partie.joueurs[1].personnage == "opportuniste"
    assert partie.joueurs[1].personnage_aleatoire is False


def test_creer_partie_aleatoire_tire_un_personnage_reel_et_le_marque():
    from scrabble.moteur.personnages import PERSONNAGES

    partie = creer_partie(
        ["Alice"],
        _trie(),
        nb_ia=1,
        personnages_ia=["aleatoire"],
        generateur_aleatoire=random.Random(0),
        graine=1,
    )
    joueur = partie.joueurs[1]
    # Le libellé « Aléatoire » n'est JAMAIS l'identité enregistrée : seule une
    # clé réelle du registre doit s'y trouver.
    assert joueur.personnage in PERSONNAGES
    assert joueur.personnage != "aleatoire"
    assert joueur.personnage_aleatoire is True


def test_creer_partie_aleatoire_est_deterministe_avec_meme_generateur():
    partie_a = creer_partie(
        ["Alice"], _trie(), nb_ia=1, personnages_ia=["aleatoire"],
        generateur_aleatoire=random.Random(123), graine=1,
    )
    partie_b = creer_partie(
        ["Alice"], _trie(), nb_ia=1, personnages_ia=["aleatoire"],
        generateur_aleatoire=random.Random(123), graine=1,
    )
    assert partie_a.joueurs[1].personnage == partie_b.joueurs[1].personnage


def test_creer_partie_aleatoire_peut_tirer_classique():
    """Le tirage « Aléatoire » porte sur TOUT le registre, Classique compris."""
    from scrabble.moteur.personnages import PERSONNAGES

    tires = set()
    for graine in range(50):
        partie = creer_partie(
            ["Alice"], _trie(), nb_ia=1, personnages_ia=["aleatoire"],
            generateur_aleatoire=random.Random(graine), graine=1,
        )
        tires.add(partie.joueurs[1].personnage)
        if tires == set(PERSONNAGES):
            return
    raise AssertionError(
        f"Le tirage n'a jamais couvert tout le registre : obtenu {tires}, "
        f"attendu {set(PERSONNAGES)}."
    )


def test_creer_partie_aleatoire_restreint_au_niveau_de_cette_ia():
    """Issue #447 (lot G, point 4) : le tirage « Aléatoire » ne choisit que
    parmi les personnages disponibles au NIVEAU de cette IA — à Débutant,
    seul Classique étant disponible, le tirage ne doit jamais renvoyer
    Opportuniste. ``creer_partie`` lui-même reste sans garde-fou (seule l'UI
    refuse la combinaison en amont) : ce test porte sur le comportement du
    tirage, pas sur un refus."""
    for graine in range(50):
        partie = creer_partie(
            ["Alice"], _trie(), nb_ia=1,
            niveaux_ia=[Niveau.DEBUTANT],
            personnages_ia=["aleatoire"],
            generateur_aleatoire=random.Random(graine), graine=1,
        )
        assert partie.joueurs[1].personnage == "classique"


def test_creer_partie_aleatoire_niveau_facile_peut_tirer_opportuniste():
    tires = set()
    for graine in range(50):
        partie = creer_partie(
            ["Alice"], _trie(), nb_ia=1,
            niveaux_ia=[Niveau.FACILE],
            personnages_ia=["aleatoire"],
            generateur_aleatoire=random.Random(graine), graine=1,
        )
        tires.add(partie.joueurs[1].personnage)
    assert tires == {"classique", "opportuniste"}


# --------------------------------------------------------------------------- #
# Recommencer : nouvelle partie avec les mêmes joueurs (issue #142)
# --------------------------------------------------------------------------- #

def _cle_joueurs(partie: Partie) -> set[tuple[str, bool, object]]:
    """Ensemble (nom, humain, niveau) des joueurs, indépendant de l'ordre."""
    return {(j.nom, j.humain, j.niveau) for j in partie.joueurs}


def test_recreer_partie_conserve_les_memes_joueurs():
    # Partie d'origine mixte humains/IA avec des niveaux distincts.
    origine = creer_partie(
        ["Alice", "Bob"],
        _trie("CADRE"),
        nb_ia=2,
        noms_ia=["Ordi Nord", "Ordi Sud"],
        niveaux_ia=[Niveau.EXPERT, Niveau.FACILE],
        graine=1,
    )
    nouvelle = recreer_partie_meme_joueurs(origine, _trie("CADRE"), graine=2)

    # Mêmes joueurs (noms, nature humain/IA, niveaux) — à l'ordre près, car le
    # tirage d'ordre peut réordonner.
    assert _cle_joueurs(nouvelle) == _cle_joueurs(origine)
    assert {j.nom for j in nouvelle.joueurs} == {"Alice", "Bob", "Ordi Nord", "Ordi Sud"}
    # Chaque IA garde bien son niveau, chaque humain reste sans niveau.
    for joueur in nouvelle.joueurs:
        if joueur.humain:
            assert joueur.niveau is None
    niveaux = {j.nom: j.niveau for j in nouvelle.joueurs if not j.humain}
    assert niveaux == {"Ordi Nord": Niveau.EXPERT, "Ordi Sud": Niveau.FACILE}


def test_recreer_partie_est_une_partie_neuve():
    origine = creer_partie(["Alice"], _trie("CADRE"), nb_ia=1, graine=1)
    # On fait avancer l'origine (score, historique) pour prouver qu'elle n'est
    # PAS copiée dans la nouvelle partie.
    origine.joueurs[0].chevalet[:] = list("CADRE")
    origine.jouer_coup(_coup_cadre_au_centre())
    assert origine.historique  # l'origine a bien un historique

    nouvelle = recreer_partie_meme_joueurs(origine, _trie("CADRE"), graine=2)
    assert nouvelle is not origine
    assert nouvelle.historique == []
    assert not nouvelle.terminee
    assert all(j.score == 0 for j in nouvelle.joueurs)
    # Plateau vierge : aucune tuile posée, sac complet moins les chevalets.
    assert nouvelle.sac.jetons_restants() == 102 - len(nouvelle.joueurs) * TAILLE_CHEVALET
    # L'origine n'a pas été modifiée par la re-création.
    assert origine.historique


def test_recreer_partie_conserve_le_personnage_de_chaque_ia():
    """« Recommencer » garde le même style de jeu (issue #440, lot D).

    Pas de nouveau tirage même pour un personnage obtenu par « Aléatoire » :
    ``Joueur.personnage`` porte déjà l'identité réelle, reprise telle quelle.
    """
    origine = creer_partie(
        ["Alice"],
        _trie("CADRE"),
        nb_ia=1,
        personnages_ia=["opportuniste"],
        graine=1,
    )
    nouvelle = recreer_partie_meme_joueurs(origine, _trie("CADRE"), graine=2)
    ia_nouvelle = next(j for j in nouvelle.joueurs if not j.humain)
    assert ia_nouvelle.personnage == "opportuniste"


def test_recreer_partie_herite_du_bonus_fin_partie():
    origine = creer_partie(["Alice"], _trie(), nb_ia=1, graine=1, bonus_fin_partie=True)
    nouvelle = recreer_partie_meme_joueurs(origine, _trie(), graine=2)
    assert nouvelle.bonus_fin_partie is True


def test_recreer_partie_nouveau_tirage_change_ordre_ou_lettres():
    # Avec une graine différente, on obtient un déroulement différent : au moins
    # l'ordre des joueurs OU la distribution des chevalets diffère de l'origine.
    origine = creer_partie(
        ["Alice", "Bob", "Carol", "Dan"], _trie(), graine=7, tirage_ordre=True
    )
    ordre_origine = [j.nom for j in origine.joueurs]
    chevalets_origine = [tuple(j.chevalet) for j in origine.joueurs]
    for graine in range(50):
        nouvelle = recreer_partie_meme_joueurs(origine, _trie(), graine=graine)
        ordre_nouveau = [j.nom for j in nouvelle.joueurs]
        chevalets_nouveau = [tuple(j.chevalet) for j in nouvelle.joueurs]
        if ordre_nouveau != ordre_origine or chevalets_nouveau != chevalets_origine:
            return
    raise AssertionError("Aucun nouveau tirage n'a produit de déroulement différent.")


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


def test_bonus_desactive_par_defaut_ne_change_rien():
    # Non-régression stricte : réglage désactivé (défaut) => pénalité seule,
    # aucun bonus au finisseur, exactement comme avant l'issue #134.
    partie = Partie(
        [Joueur("Alice"), Joueur("Bob")], _trie("CADRE"), graine=1
    )
    partie.joueurs[0].chevalet[:] = list("CADRE")
    partie.joueurs[1].chevalet[:] = ["K", "Z"]  # 20 points de reste
    partie.joueurs[0].score = 0
    partie.joueurs[1].score = 100
    _vider_sac(partie)
    entree = partie.jouer_coup(_coup_cadre_au_centre())
    assert partie.terminee
    # Alice : score du coup, aucun bonus (chevalet vidé => pas de pénalité).
    assert partie.joueurs[0].score == entree.detail.total
    # Bob : pénalisé de ses 20 points restants, rien de plus.
    assert partie.joueurs[1].score == 100 - 20


def test_bonus_active_credite_le_finisseur():
    # Réglage activé + fin par chevalet vidé => le finisseur reçoit la somme des
    # lettres restant chez les autres, en plus de la pénalité de ceux-ci.
    partie = Partie(
        [Joueur("Alice"), Joueur("Bob")],
        _trie("CADRE"),
        graine=1,
        bonus_fin_partie=True,
    )
    partie.joueurs[0].chevalet[:] = list("CADRE")
    partie.joueurs[1].chevalet[:] = ["K", "Z"]  # 20 points de reste
    partie.joueurs[0].score = 0
    partie.joueurs[1].score = 100
    _vider_sac(partie)
    entree = partie.jouer_coup(_coup_cadre_au_centre())
    assert partie.terminee
    # Alice : score du coup + bonus de 20 (le reste de Bob).
    assert partie.joueurs[0].score == entree.detail.total + 20
    # Bob : toujours pénalisé de ses 20 points (la déduction reste appliquée).
    assert partie.joueurs[1].score == 100 - 20


def test_bonus_active_joker_adverse_contribue_zero():
    # Un joker restant chez un adversaire vaut 0 : il ne gonfle pas le bonus.
    partie = Partie(
        [Joueur("Alice"), Joueur("Bob")],
        _trie("CADRE"),
        graine=1,
        bonus_fin_partie=True,
    )
    partie.joueurs[0].chevalet[:] = list("CADRE")
    partie.joueurs[1].chevalet[:] = [JOKER, "K"]  # joker=0, K=10 => 10 points
    partie.joueurs[0].score = 0
    partie.joueurs[1].score = 0
    _vider_sac(partie)
    entree = partie.jouer_coup(_coup_cadre_au_centre())
    assert partie.terminee
    # Bonus = 10 (le joker ne compte pas), et non 10 + quelque chose.
    assert partie.joueurs[0].score == entree.detail.total + 10
    assert partie.joueurs[1].score == 0 - 10


def test_bonus_active_mais_fin_par_blocage_sans_bonus():
    # Le bonus ne concerne que la fin par chevalet vidé : une fin par blocage
    # (passes consécutives) n'attribue jamais de bonus, même réglage activé.
    partie = Partie(
        [Joueur("Alice"), Joueur("Bob")],
        _trie(),
        graine=1,
        bonus_fin_partie=True,
    )
    partie.joueurs[0].chevalet[:] = ["A"]   # 1 point de reste
    partie.joueurs[1].chevalet[:] = ["K", "Z"]  # 20 points de reste
    partie.joueurs[0].score = 50
    partie.joueurs[1].score = 50
    partie.passer()  # Alice passe (compteur 1)
    partie.passer()  # Bob passe (compteur 2 == nb joueurs) -> fin par blocage
    assert partie.terminee
    # Chacun est seulement pénalisé de son reste, aucun bonus croisé.
    assert partie.joueurs[0].score == 50 - 1
    assert partie.joueurs[1].score == 50 - 20


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


def test_jouer_tour_ia_sans_profil_ne_transmet_pas_profil(monkeypatch):
    """Sans ``profil``, l'appel à ``choisir_coup`` ne porte pas ce kwarg.

    Garde-fou issue #438 (lot A) : un faux ``choisir_coup`` sans paramètre
    ``profil`` (comme ceux déjà monkeypatchés par les tests existants) doit
    continuer de fonctionner tant qu'aucun personnage n'est renseigné.
    """
    import scrabble.moteur.ia as ia_mod

    partie = Partie(
        [Joueur("IA", humain=False, niveau=Niveau.EXPERT)], _trie("CADRE"), graine=1
    )
    captures: dict = {}

    def faux_choisir(plateau, chevalet, dictionnaire, niveau):
        captures["appele"] = True
        return None

    monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir)
    partie.jouer_tour_ia()
    assert captures.get("appele") is True


def test_jouer_tour_ia_avec_profil_le_transmet_a_choisir_coup(monkeypatch):
    """Avec un ``profil`` explicite, il est bien transmis à ``choisir_coup``."""
    import scrabble.moteur.ia as ia_mod

    partie = Partie(
        [Joueur("IA", humain=False, niveau=Niveau.EXPERT)], _trie("CADRE"), graine=1
    )
    profil = ia_mod.ProfilPersonnage(bonus_premium=0)
    captures: dict = {}

    def faux_choisir(plateau, chevalet, dictionnaire, niveau, profil=None):
        captures["profil"] = profil
        return None

    monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir)
    partie.jouer_tour_ia(profil=profil)
    assert captures["profil"] is profil


def test_jouer_tours_ia_enchaine_jusqu_a_un_humain():
    partie = creer_partie(["Humain"], _trie("CADRE"), nb_ia=1, graine=1)
    # Humain d'abord (index 0) : jouer_tours_ia ne doit rien faire.
    assert partie.jouer_tours_ia() == []
    assert partie.joueur_courant().humain


# --------------------------------------------------------------------------- #
# Vocabulaire de l'IA par niveau (issues #206, #369 lot C) :
# mapping {Niveau: Trie} optionnel, fin du Trie IA unique
# --------------------------------------------------------------------------- #

def test_dictionnaires_ia_defaut_vide():
    """Par défaut, dictionnaires_ia est un mapping vide (coût nul)."""
    trie = _trie("CHAT")
    partie = Partie([Joueur("Alice")], trie, graine=1)
    assert partie.dictionnaires_ia == {}


def test_dictionnaire_ia_par_niveau_distinct_quand_fourni():
    """Un Trie par niveau explicite est conservé, distinct du dictionnaire complet."""
    complet = _trie("CHAT", "CHIEN")
    restreint = _trie("CHAT")
    partie = Partie(
        [Joueur("Alice")],
        complet,
        graine=1,
        dictionnaires_ia={Niveau.EXPERT: restreint},
    )
    assert partie.dictionnaire is complet
    assert partie.dictionnaires_ia[Niveau.EXPERT] is restreint
    assert partie.dictionnaires_ia[Niveau.EXPERT] is not partie.dictionnaire


def test_jouer_tour_ia_genere_sur_dictionnaire_du_niveau(monkeypatch):
    """La génération des coups IA reçoit le Trie de SON niveau, pas le dico complet."""
    import scrabble.moteur.ia as ia_mod

    complet = _trie("CHAT")
    restreint = _trie("CHIEN")
    partie = Partie(
        [Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
        complet,
        graine=1,
        dictionnaires_ia={Niveau.EXPERT: restreint},
    )
    captures: dict = {}

    def faux_choisir(plateau, chevalet, dictionnaire, niveau):
        captures["dico"] = dictionnaire
        return None

    monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir)
    partie.jouer_tour_ia()
    assert captures["dico"] is restreint


def test_jouer_tour_ia_niveau_absent_du_mapping_retombe_sur_dictionnaire(monkeypatch):
    """Un niveau absent de ``dictionnaires_ia`` retombe sur le dico complet."""
    import scrabble.moteur.ia as ia_mod

    complet = _trie("CHAT")
    restreint = _trie("CHIEN")
    partie = Partie(
        [Joueur("IA", humain=False, niveau=Niveau.DEBUTANT)],
        complet,
        graine=1,
        # Seul EXPERT a un Trie propre : DEBUTANT (le niveau joué ici) n'y
        # figure pas et doit retomber sur le dictionnaire complet.
        dictionnaires_ia={Niveau.EXPERT: restreint},
    )
    captures: dict = {}

    def faux_choisir(plateau, chevalet, dictionnaire, niveau):
        captures["dico"] = dictionnaire
        return None

    monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir)
    partie.jouer_tour_ia()
    assert captures["dico"] is complet


def test_deux_ia_niveaux_differents_utilisent_deux_tries_distincts(monkeypatch):
    """Test central du lot C : deux IA de niveaux différents, deux Tries distincts.

    Fin du Trie IA unique (rapport de lecture #366) : une partie avec un
    Débutant et un Expert utilise bien un Trie propre à chacun, pas un Trie
    global partagé.
    """
    import scrabble.moteur.ia as ia_mod

    complet = _trie("CHAT", "CHIEN", "CANOT")
    trie_debutant = _trie("CHAT")
    trie_expert = _trie("CHIEN")
    partie = Partie(
        [
            Joueur("Debutant", humain=False, niveau=Niveau.DEBUTANT),
            Joueur("Expert", humain=False, niveau=Niveau.EXPERT),
        ],
        complet,
        graine=1,
        dictionnaires_ia={
            Niveau.DEBUTANT: trie_debutant,
            Niveau.EXPERT: trie_expert,
        },
    )
    captures: list = []

    def faux_choisir(plateau, chevalet, dictionnaire, niveau):
        captures.append((niveau, dictionnaire))
        return None

    monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir)
    partie.jouer_tour_ia()  # Débutant (index 0)
    partie.jouer_tour_ia()  # Expert (index 1)

    assert captures == [
        (Niveau.DEBUTANT, trie_debutant),
        (Niveau.EXPERT, trie_expert),
    ]
    assert captures[0][1] is not captures[1][1]


def test_valider_coup_humain_reste_sur_dictionnaire_complet():
    """Un coup humain est validé sur le dico complet, même IA restreinte (à vide)."""
    complet = _trie("CADRE")
    restreint = _trie()  # vocabulaire IA vide : n'affecte pas l'humain
    joueur = Joueur("Alice")
    partie = Partie(
        [joueur],
        complet,
        graine=1,
        dictionnaires_ia={Niveau.EXPERT: restreint},
    )
    joueur.chevalet[:] = list("CADRE")

    entree = partie.jouer_coup(_coup_cadre_au_centre())

    assert entree.action == ACTION_COUP        # CADRE validé via le dico complet


def test_ia_restreinte_ne_joue_pas_hors_vocabulaire():
    """Avec le filtre actif, l'IA ne propose jamais un mot hors vocabulaire restreint.

    Le mot « AS » existe dans le dictionnaire complet mais pas dans le
    vocabulaire restreint de l'IA (limité à « CADRE »). L'IA, ne pouvant former
    « CADRE » (ni C ni D dans son chevalet), passe — alors que le même « AS »
    resterait jouable par un humain (dico complet).
    """
    complet = _trie("CADRE", "AS", "CADRES")
    restreint = _trie("CADRE")
    partie = Partie(
        [Joueur("Humain"), Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
        complet,
        graine=1,
        dictionnaires_ia={Niveau.EXPERT: restreint},
    )
    partie.joueurs[0].chevalet[:] = list("CADRE")
    partie.jouer_coup(_coup_cadre_au_centre())   # pose CADRE, main à l'IA
    partie.joueurs[1].chevalet[:] = ["S", "A", "T", "E", "R", "I", "O"]

    entree = partie.jouer_tour_ia()

    assert entree.action == ACTION_PASSE
    # Le vocabulaire humain (dico complet) reste strictement plus large.
    assert partie.dictionnaire.contient("AS")
    assert not partie.dictionnaires_ia[Niveau.EXPERT].contient("AS")


def test_recreer_partie_conserve_dictionnaires_ia():
    """« Recommencer » repropage le mapping de Tries restreints tel quel."""
    complet = _trie("CHAT", "CHIEN")
    restreint = _trie("CHAT")
    joueurs = [
        Joueur("Alice"),
        Joueur("IA", humain=False, niveau=Niveau.FACILE),
    ]
    partie = Partie(
        joueurs, complet, graine=1, dictionnaires_ia={Niveau.FACILE: restreint}
    )

    nouvelle = recreer_partie_meme_joueurs(
        partie, complet, graine=2, tirage_ordre=False
    )

    assert nouvelle.dictionnaire is complet
    assert nouvelle.dictionnaires_ia == {Niveau.FACILE: restreint}


def test_recreer_partie_sans_restriction_reste_sur_dictionnaire():
    """Sans restriction d'origine, la nouvelle partie retombe sur son dictionnaire."""
    complet = _trie("CHAT")
    joueurs = [
        Joueur("Alice"),
        Joueur("IA", humain=False, niveau=Niveau.FACILE),
    ]
    partie = Partie(joueurs, complet, graine=1)  # dictionnaires_ia vide
    assert partie.dictionnaires_ia == {}

    nouveau_complet = _trie("CHAT", "CHIEN")
    nouvelle = recreer_partie_meme_joueurs(
        partie, nouveau_complet, graine=2, tirage_ordre=False
    )

    assert nouvelle.dictionnaire is nouveau_complet
    assert nouvelle.dictionnaires_ia == {}
