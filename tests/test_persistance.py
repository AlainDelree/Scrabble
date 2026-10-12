"""Tests de ``scrabble.persistance.stockage``.

Couvre le suivi au fil de l'eau et la reprise après plantage :

* démarrage du suivi d'une partie fraîche (id renvoyé, graine obligatoire) ;
* enregistrement d'actions et reflet dans :func:`lister_parties` (statut « en
  cours », joueurs) ;
* reprise d'une partie partiellement jouée : la ``Partie`` reconstruite est dans
  **le même état exact** que l'originale (plateau, chevalets, scores, sac,
  joueur courant) — comparaison directe des attributs, pas juste « ça tourne » ;
* finalisation et reflet du statut terminé (scores + gagnant·s) ;
* reprise d'une partie contenant un **échange** : le sac reconstitué est
  identique au sac d'origine (preuve que les lettres *précises* échangées, pas
  seulement leur nombre, ont été rejouées) ;
* idempotence de l'initialisation du schéma sur une base existante.

Chaque test travaille sur une base temporaire (``tmp_path``) : la base par
défaut (``data/parties.db``) n'est jamais touchée.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie, creer_partie
from scrabble.moteur.plateau_partie import (
    CENTRE,
    Coup,
    Direction,
    tuiles_depuis_chaine,
)
from scrabble.persistance import stockage
from scrabble.persistance.stockage import (
    STATUT_EN_COURS,
    STATUT_TERMINEE,
    demarrer_suivi,
    enregistrer_action,
    finaliser_partie,
    lister_parties,
    niveaux_ia_stockes,
    reprendre_partie,
    supprimer_partie,
)

# Petit dictionnaire de mots plausibles à poser en ouverture : il en faut
# suffisamment pour qu'une graine « ouvrable » (chevalet formant l'un d'eux)
# se trouve rapidement.
MOTS = [
    "CADRE", "MAISON", "TOMATE", "AIRE", "POSER", "LIRE", "SEL", "OSE",
    "TON", "NOTE", "ROI", "SIROP", "RATE", "TIARE", "SATIRE", "RETINE",
    "OURS", "PORTE", "RAISON", "TISANE", "SENIOR", "RONDE", "AMIE", "RIDE",
]


def _trie() -> Trie:
    return Trie.depuis_iterable(MOTS)


def _partie_ouvrable(trie: Trie, **kwargs) -> tuple[Partie, int, str]:
    """Crée une partie dont le joueur 0 peut poser un mot de :data:`MOTS`.

    Balaie les graines jusqu'à en trouver une où le chevalet initial du premier
    joueur contient les lettres d'un mot connu. Renvoie ``(partie, graine, mot)``.
    """
    for graine in range(2000):
        partie = creer_partie(["Alice"], trie, graine=graine, **kwargs)
        disponibles = Counter(partie.joueur_courant().chevalet)
        for mot in MOTS:
            if all(disponibles[lettre] >= n for lettre, n in Counter(mot).items()):
                return partie, graine, mot
    raise AssertionError("Aucune graine ouvrable trouvée dans l'intervalle testé.")


def _coup_ouverture(mot: str) -> Coup:
    """Coup horizontal de ``mot`` posé à partir de la case centrale."""
    ligne, colonne = CENTRE
    return Coup(ligne, colonne, Direction.HORIZONTALE, tuiles_depuis_chaine(mot))


def _snapshot(partie: Partie) -> dict:
    """Capture comparable de l'état vivant d'une partie."""
    return {
        "cases": partie.plateau._cases,
        "chevalets": [list(j.chevalet) for j in partie.joueurs],
        "scores": [j.score for j in partie.joueurs],
        "sac": list(partie.sac._jetons),
        "index_courant": partie.index_courant,
        "passes": partie.passes_consecutives,
        "terminee": partie.terminee,
    }


def _partie_coup_puis_echange(chemin) -> tuple[Partie, int, Trie]:
    """Scénario partagé : p0 pose un mot, l'IA (p1) échange deux lettres.

    Enregistre le suivi et les deux actions dans ``chemin``. La partie n'est pas
    terminée et la main revient au joueur 0. Renvoie ``(partie, id, trie)``.
    """
    trie = _trie()
    partie, _graine, mot = _partie_ouvrable(trie, nb_ia=1)
    id_partie = demarrer_suivi(partie, chemin)

    entree = partie.jouer_coup(_coup_ouverture(mot))
    enregistrer_action(id_partie, entree, chemin)

    a_echanger = list(partie.joueur_courant().chevalet[:2])
    entree = partie.echanger(a_echanger)
    enregistrer_action(id_partie, entree, chemin)

    return partie, id_partie, trie


# --------------------------------------------------------------------------- #
# Démarrage du suivi
# --------------------------------------------------------------------------- #

def test_demarrer_suivi_renvoie_id(tmp_path):
    chemin = tmp_path / "parties.db"
    partie = creer_partie(["Alice"], _trie(), nb_ia=1, graine=7)
    id_partie = demarrer_suivi(partie, chemin)
    assert isinstance(id_partie, int)
    assert id_partie >= 1
    # Deux parties fraîches reçoivent des identifiants distincts.
    autre = demarrer_suivi(creer_partie(["Bob"], _trie(), graine=8), chemin)
    assert autre != id_partie


def test_demarrer_suivi_sans_graine_refuse(tmp_path):
    chemin = tmp_path / "parties.db"
    partie = creer_partie(["Alice"], _trie())  # graine=None
    with pytest.raises(ValueError):
        demarrer_suivi(partie, chemin)


# --------------------------------------------------------------------------- #
# Enregistrement + listing
# --------------------------------------------------------------------------- #

def test_lister_reflete_en_cours_et_joueurs(tmp_path):
    chemin = tmp_path / "parties.db"
    partie, id_partie, _trie_ = _partie_coup_puis_echange(chemin)

    resumes = lister_parties(chemin)
    assert len(resumes) == 1
    resume = resumes[0]
    assert resume.id == id_partie
    assert resume.statut == STATUT_EN_COURS
    assert not resume.terminee
    assert resume.scores_finaux is None
    assert resume.gagnants is None
    noms = [j["nom"] for j in resume.joueurs]
    assert noms == [j.nom for j in partie.joueurs]
    # L'IA garde sa nature et son niveau ; l'humain a niveau None.
    assert resume.joueurs[0]["humain"] is True
    assert resume.joueurs[0]["niveau"] is None
    assert resume.joueurs[1]["humain"] is False
    assert resume.joueurs[1]["niveau"] == Niveau.INTERMEDIAIRE.name


def test_scores_actuels_refletent_historique(tmp_path):
    """``scores_actuels`` donne le score courant de chaque joueur (issue #76).

    Il est déduit du dernier ``score_cumule`` de l'historique sans rejouer la
    partie : après un coup de p0 et un échange de p1, il doit correspondre aux
    scores vivants de la partie, dans l'ordre des joueurs.
    """
    chemin = tmp_path / "parties.db"
    partie, _id, _trie_ = _partie_coup_puis_echange(chemin)

    resume = lister_parties(chemin)[0]
    assert resume.scores_actuels == [j.score for j in partie.joueurs]
    # p0 a marqué en posant un mot ; p1 a échangé (score nul).
    assert resume.scores_actuels[0] > 0
    assert resume.scores_actuels[1] == 0


def test_scores_actuels_zero_sans_action(tmp_path):
    """Une partie sans aucune action expose des scores à 0 pour chaque joueur."""
    chemin = tmp_path / "parties.db"
    partie = creer_partie(["Alice"], _trie(), nb_ia=1, graine=7)
    demarrer_suivi(partie, chemin)

    resume = lister_parties(chemin)[0]
    assert resume.scores_actuels == [0, 0]


def test_lister_trie_par_maj_decroissante(tmp_path):
    chemin = tmp_path / "parties.db"
    partie1 = creer_partie(["A"], _trie(), graine=1)
    id1 = demarrer_suivi(partie1, chemin)
    id2 = demarrer_suivi(creer_partie(["B"], _trie(), graine=2), chemin)
    # Sans nouvelle action, la plus récemment créée (id2) est en tête.
    assert [r.id for r in lister_parties(chemin)] == [id2, id1]
    # Une action sur la première partie met à jour sa date_maj et la remonte.
    enregistrer_action(id1, partie1.passer(), chemin)
    assert lister_parties(chemin)[0].id == id1


# --------------------------------------------------------------------------- #
# Reprise après plantage — état identique
# --------------------------------------------------------------------------- #

def test_reprise_partie_partiellement_jouee(tmp_path):
    chemin = tmp_path / "parties.db"
    partie, id_partie, trie = _partie_coup_puis_echange(chemin)
    attendu = _snapshot(partie)

    reprise = reprendre_partie(id_partie, trie, chemin)
    obtenu = _snapshot(reprise)

    assert obtenu["cases"] == attendu["cases"]
    assert obtenu["chevalets"] == attendu["chevalets"]
    assert obtenu["scores"] == attendu["scores"]
    assert obtenu["sac"] == attendu["sac"]
    assert obtenu["index_courant"] == attendu["index_courant"]
    assert obtenu["passes"] == attendu["passes"]
    assert obtenu["terminee"] == attendu["terminee"] is False
    # La partie reprise est prête à continuer : une action reste possible.
    assert not reprise.terminee


@pytest.mark.parametrize("niveau", list(Niveau))
def test_reprise_tous_les_niveaux_ia(tmp_path, niveau):
    """Une partie sauvegardée avec n'importe quel niveau IA reste chargeable.

    Paramétré sur TOUS les membres de :class:`Niveau` (plutôt qu'une liste en
    dur) pour garantir que ``Niveau[niveau]`` (``stockage.py``) résout
    correctement chaque valeur, y compris ``CHAMPION_DU_MONDE`` ajouté par
    l'issue #368 (lot D) — rétro-compatibilité du blob JSON stocké par
    ``.name``, garde-fou contre un futur ajout de niveau non résolvable.
    """
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [Joueur("Humain"), Joueur("IA", humain=False, niveau=niveau)],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[1].niveau == niveau


# --------------------------------------------------------------------------- #
# Personnage (issue #438, lot A) : sérialisation symétrique au niveau
# --------------------------------------------------------------------------- #

def test_reprise_personnage_vide_par_defaut(tmp_path):
    """Un joueur sans personnage (défaut) se recharge avec ``personnage=""``."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [Joueur("Humain"), Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[0].personnage == ""
    assert reprise.joueurs[1].personnage == ""


def test_reprise_personnage_aller_retour(tmp_path):
    """Un personnage renseigné survit à l'aller-retour en base, symétrique au niveau."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain", personnage="Le Capitaine"),
            Joueur("IA", humain=False, niveau=Niveau.EXPERT, personnage="Le Pirate"),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[0].personnage == "Le Capitaine"
    assert reprise.joueurs[1].personnage == "Le Pirate"


def test_reprise_partie_avec_lettre(tmp_path):
    """Reprise d'une partie sauvegardée avec un Lettré (issue #454, lot K) :
    même mécanique générique que :func:`test_reprise_personnage_aller_retour`
    (``personnage`` est une simple chaîne), vérifiée explicitement avec la
    clé réelle du registre pour ce nouveau personnage."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humaine"),
            Joueur("IA", humain=False, niveau=Niveau.AVANCE, personnage="lettre"),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[1].personnage == "lettre"
    assert reprise.joueurs[1].niveau == Niveau.AVANCE


@pytest.mark.parametrize(
    "personnage_cle", ["chasseur_de_scrabbles", "lettre", "opportuniste"]
)
def test_reprise_partie_avec_personnage_desactive_se_joue_normalement(
    tmp_path, personnage_cle
):
    """Issues #459/#461 : Chasseur de scrabbles, Lettré et Opportuniste sont
    désactivés (``Personnage.actif`` à ``False``), mais une partie
    sauvegardée avant leur désactivation se charge et se joue normalement,
    sans erreur ni changement de comportement — ``reprendre_partie`` ne
    vérifie aucune disponibilité, et le profil résolu par
    :func:`~scrabble.moteur.personnages.profil_pour_niveau` reste le profil
    complet du personnage, actif ou non. Titeuf (également inactif depuis
    l'issue #461) n'est disponible qu'à Débutant : couvert séparément par
    ``test_reprise_partie_avec_titeuf_desactive_se_joue_normalement``
    ci-dessous."""
    from scrabble.moteur.personnages import PERSONNAGES, profil_pour_niveau

    assert PERSONNAGES[personnage_cle].actif is False

    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie, _graine, mot = _partie_ouvrable(
        trie, nb_ia=1, niveaux_ia=[Niveau.AVANCE],
        personnages_ia=[personnage_cle],
    )
    id_partie = demarrer_suivi(partie, chemin)
    entree = partie.jouer_coup(_coup_ouverture(mot))
    enregistrer_action(id_partie, entree, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)

    assert reprise.joueurs[1].personnage == personnage_cle
    profil = profil_pour_niveau(personnage_cle, reprise.joueurs[1].niveau)
    # La partie reste jouable : l'IA produit une entrée d'historique (coup
    # ou passe) sans exception, avec le profil complet du personnage.
    entree_ia = reprise.jouer_tour_ia(profil)
    assert entree_ia is not None


def test_reprise_partie_avec_titeuf_desactive_se_joue_normalement(tmp_path):
    """Même garantie que ci-dessus pour Titeuf (issue #461), disponible
    uniquement à Débutant (:data:`~scrabble.moteur.personnages.
    NIVEAUX_TITEUF`), donc testé séparément à ce niveau."""
    from scrabble.moteur.personnages import PERSONNAGES, profil_pour_niveau

    assert PERSONNAGES["titeuf"].actif is False

    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie, _graine, mot = _partie_ouvrable(
        trie, nb_ia=1, niveaux_ia=[Niveau.DEBUTANT],
        personnages_ia=["titeuf"],
    )
    id_partie = demarrer_suivi(partie, chemin)
    entree = partie.jouer_coup(_coup_ouverture(mot))
    enregistrer_action(id_partie, entree, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)

    assert reprise.joueurs[1].personnage == "titeuf"
    profil = profil_pour_niveau("titeuf", reprise.joueurs[1].niveau)
    entree_ia = reprise.jouer_tour_ia(profil)
    assert entree_ia is not None


def test_reprise_ancienne_sauvegarde_sans_cle_personnage(tmp_path):
    """Une partie sauvegardée avant l'issue #438, sans clé ``personnage`` dans
    le JSON des joueurs, se recharge normalement avec un personnage vide.

    Simule une ancienne sauvegarde en retirant la clé directement en base,
    plutôt qu'en passant par :func:`demarrer_suivi` qui l'écrirait toujours.
    """
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [Joueur("Humain"), Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    with sqlite3.connect(chemin) as connexion:
        joueurs = json.loads(
            connexion.execute(
                "SELECT joueurs FROM parties WHERE id = ?", (id_partie,)
            ).fetchone()[0]
        )
        for j in joueurs:
            del j["personnage"]
        connexion.execute(
            "UPDATE parties SET joueurs = ? WHERE id = ?",
            (json.dumps(joueurs, ensure_ascii=False), id_partie),
        )
        connexion.commit()

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[0].personnage == ""
    assert reprise.joueurs[1].personnage == ""


# --------------------------------------------------------------------------- #
# personnage_aleatoire : révélation en fin de partie (issue #440, lot D)
# --------------------------------------------------------------------------- #

def test_reprise_personnage_aleatoire_faux_par_defaut(tmp_path):
    """Un joueur sans tirage au hasard (défaut) se recharge avec ``False``."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [Joueur("Humain"), Joueur("IA", humain=False, niveau=Niveau.EXPERT)],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[0].personnage_aleatoire is False
    assert reprise.joueurs[1].personnage_aleatoire is False


def test_reprise_personnage_aleatoire_aller_retour(tmp_path):
    """``personnage_aleatoire`` survit à l'aller-retour en base, pour qu'une
    partie « Aléatoire » reprise avant sa fin garde son identité cachée."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain"),
            Joueur(
                "Thomas",
                humain=False,
                niveau=Niveau.EXPERT,
                personnage="opportuniste",
                personnage_aleatoire=True,
            ),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[1].personnage == "opportuniste"
    assert reprise.joueurs[1].personnage_aleatoire is True


def test_reprise_ancienne_sauvegarde_sans_cle_personnage_aleatoire(tmp_path):
    """Une sauvegarde d'avant l'issue #440, sans ``personnage_aleatoire`` dans
    le JSON, se recharge normalement avec ``personnage_aleatoire=False``."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain"),
            Joueur("IA", humain=False, niveau=Niveau.EXPERT, personnage="opportuniste"),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    with sqlite3.connect(chemin) as connexion:
        joueurs = json.loads(
            connexion.execute(
                "SELECT joueurs FROM parties WHERE id = ?", (id_partie,)
            ).fetchone()[0]
        )
        for j in joueurs:
            del j["personnage_aleatoire"]
        connexion.execute(
            "UPDATE parties SET joueurs = ? WHERE id = ?",
            (json.dumps(joueurs, ensure_ascii=False), id_partie),
        )
        connexion.commit()

    reprise = reprendre_partie(id_partie, trie, chemin)
    assert reprise.joueurs[0].personnage_aleatoire is False
    assert reprise.joueurs[1].personnage_aleatoire is False
    # Le personnage réel (choisi explicitement, pas par tirage) reste intact.
    assert reprise.joueurs[1].personnage == "opportuniste"


def test_reprise_combinaison_personnage_niveau_non_disponible_se_charge_normalement(
    tmp_path,
):
    """Issue #447 (lot G, point 6) : une partie sauvegardée dont la
    combinaison personnage/niveau ne serait plus disponible aujourd'hui
    (Opportuniste à Débutant) doit se charger et se jouer normalement —
    aucune vérification de disponibilité n'a lieu au chargement, seulement à
    l'ajout d'un ordinateur (``ui.accueil.ApiAccueil.ajouter_ordinateur``)."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain"),
            Joueur(
                "IA",
                humain=False,
                niveau=Niveau.DEBUTANT,
                personnage="opportuniste",
            ),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)

    assert reprise.joueurs[1].niveau == Niveau.DEBUTANT
    assert reprise.joueurs[1].personnage == "opportuniste"
    # La partie reste jouable : un coup IA peut être généré sans exception.
    assert reprise.joueur_courant() is not None


def test_reprise_combinaison_personnage_nb_joueurs_non_disponible_se_charge_normalement(
    tmp_path,
):
    """Issue #449 (lot I, point 6) : une partie sauvegardée à trois joueurs
    dont un adversaire porte Opportuniste (indisponible aujourd'hui à cette
    taille de table) doit se charger et se jouer normalement — aucune
    vérification de disponibilité n'a lieu au chargement, seulement à
    l'ajout d'un ordinateur (``ui.accueil.ApiAccueil.ajouter_ordinateur``)."""
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain"),
            Joueur(
                "IA1",
                humain=False,
                niveau=Niveau.EXPERT,
                personnage="opportuniste",
            ),
            Joueur("IA2", humain=False, niveau=Niveau.EXPERT, personnage="classique"),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)

    assert len(reprise.joueurs) == 3
    assert reprise.joueurs[1].personnage == "opportuniste"
    # La partie reste jouable : un coup IA peut être généré sans exception.
    assert reprise.joueur_courant() is not None


# --------------------------------------------------------------------------- #
# Vocabulaire IA par niveau à la reprise (issue #369, lot C)
# --------------------------------------------------------------------------- #

def test_niveaux_ia_stockes_reflete_les_niveaux_des_ia_sans_reconstruire(tmp_path):
    """``niveaux_ia_stockes`` lit les niveaux stockés sans rejouer la partie.

    Doit ignorer les joueurs humains (``niveau`` vaut ``None``) et refléter
    exactement les niveaux des IA, dans l'ordre des joueurs — c'est ce que
    ``ui.accueil.ApiAccueil.reprendre`` consulte pour savoir quels paliers de
    vocabulaire charger, avant de reconstruire la partie.
    """
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain"),
            Joueur("Debutant", humain=False, niveau=Niveau.DEBUTANT),
            Joueur("Champion", humain=False, niveau=Niveau.CHAMPION_DU_MONDE),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    assert niveaux_ia_stockes(id_partie, chemin) == [
        Niveau.DEBUTANT,
        Niveau.CHAMPION_DU_MONDE,
    ]


def test_niveaux_ia_stockes_partie_inconnue_leve(tmp_path):
    chemin = tmp_path / "parties.db"
    with pytest.raises(KeyError):
        niveaux_ia_stockes(999, chemin)


def test_reprise_avec_dictionnaires_ia_par_niveau(tmp_path):
    """Une partie reprise utilise, par IA, le Trie de son niveau (issue #369).

    Deux IA de niveaux différents (Débutant et Expert) reçoivent chacune un
    Trie IA distinct via ``dictionnaires_ia`` : la reprise doit préserver
    cette distinction, pas retomber sur un seul Trie partagé.
    """
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie = Partie(
        [
            Joueur("Humain"),
            Joueur("Debutant", humain=False, niveau=Niveau.DEBUTANT),
            Joueur("Expert", humain=False, niveau=Niveau.EXPERT),
        ],
        trie,
        graine=1,
    )
    id_partie = demarrer_suivi(partie, chemin)

    trie_debutant = Trie.depuis_iterable(["CHAT"])
    trie_expert = Trie.depuis_iterable(["CHIEN"])
    reprise = reprendre_partie(
        id_partie,
        trie,
        chemin,
        dictionnaires_ia={
            Niveau.DEBUTANT: trie_debutant,
            Niveau.EXPERT: trie_expert,
        },
    )

    assert reprise.dictionnaires_ia[Niveau.DEBUTANT] is trie_debutant
    assert reprise.dictionnaires_ia[Niveau.EXPERT] is trie_expert
    assert (
        reprise.dictionnaires_ia[Niveau.DEBUTANT]
        is not reprise.dictionnaires_ia[Niveau.EXPERT]
    )


def test_reprise_echange_sac_identique(tmp_path):
    """Le sac après reprise doit être identique : preuve que les lettres

    *précises* échangées ont été rejouées (et pas seulement leur nombre).
    """
    chemin = tmp_path / "parties.db"
    trie = _trie()
    partie, _graine, _mot = _partie_ouvrable(trie, nb_ia=1)
    id_partie = demarrer_suivi(partie, chemin)

    # Le premier joueur échange directement quelques lettres connues.
    a_echanger = list(partie.joueur_courant().chevalet[:3])
    entree = partie.echanger(a_echanger)
    enregistrer_action(id_partie, entree, chemin)

    reprise = reprendre_partie(id_partie, trie, chemin)
    # Comparaison de l'ordre exact des jetons du sac : sensible au mélange, donc
    # aux lettres remises. Un simple « bon nombre » ne suffirait pas à l'égaler.
    assert reprise.sac._jetons == partie.sac._jetons
    assert [list(j.chevalet) for j in reprise.joueurs] == [
        list(j.chevalet) for j in partie.joueurs
    ]


# --------------------------------------------------------------------------- #
# Finalisation
# --------------------------------------------------------------------------- #

def test_finaliser_reflete_statut_termine(tmp_path):
    chemin = tmp_path / "parties.db"
    partie = creer_partie(["Alice"], _trie(), nb_ia=1, graine=3)
    id_partie = demarrer_suivi(partie, chemin)

    # Deux passes consécutives (2 joueurs) terminent la partie.
    enregistrer_action(id_partie, partie.passer(), chemin)
    enregistrer_action(id_partie, partie.passer(), chemin)
    assert partie.terminee

    finaliser_partie(id_partie, partie, chemin)
    resume = lister_parties(chemin)[0]
    assert resume.statut == STATUT_TERMINEE
    assert resume.terminee
    assert resume.scores_finaux == [j.score for j in partie.joueurs]
    assert resume.gagnants == [j.nom for j in partie.gagnants]
    assert resume.gagnants  # au moins un gagnant


def test_finaliser_refuse_partie_en_cours(tmp_path):
    chemin = tmp_path / "parties.db"
    partie = creer_partie(["Alice"], _trie(), nb_ia=1, graine=3)
    id_partie = demarrer_suivi(partie, chemin)
    assert not partie.terminee
    with pytest.raises(ValueError):
        finaliser_partie(id_partie, partie, chemin)


# --------------------------------------------------------------------------- #
# Idempotence du schéma
# --------------------------------------------------------------------------- #

def test_init_schema_idempotente(tmp_path):
    chemin = tmp_path / "parties.db"
    # Premier accès : crée le fichier et le schéma.
    id_partie = demarrer_suivi(creer_partie(["Alice"], _trie(), graine=5), chemin)
    assert chemin.exists()
    # Accès répétés sur une base existante : ne plantent pas, ne perdent rien.
    for _ in range(3):
        resumes = lister_parties(chemin)
    assert [r.id for r in resumes] == [id_partie]
    # Un nouveau suivi reste possible après réouvertures.
    autre = demarrer_suivi(creer_partie(["Bob"], _trie(), graine=6), chemin)
    assert autre != id_partie
    assert len(lister_parties(chemin)) == 2


def test_reprendre_partie_inconnue_leve(tmp_path):
    chemin = tmp_path / "parties.db"
    demarrer_suivi(creer_partie(["Alice"], _trie(), graine=5), chemin)
    with pytest.raises(KeyError):
        reprendre_partie(999, _trie(), chemin)


# --------------------------------------------------------------------------- #
# Suppression d'une partie (issue #67)
# --------------------------------------------------------------------------- #

def test_supprimer_partie_retire_de_la_liste(tmp_path):
    chemin = tmp_path / "parties.db"
    id1 = demarrer_suivi(creer_partie(["Alice"], _trie(), graine=1), chemin)
    id2 = demarrer_suivi(creer_partie(["Bob"], _trie(), graine=2), chemin)

    assert supprimer_partie(id1, chemin) is True
    # Seule la partie non supprimée subsiste.
    assert [r.id for r in lister_parties(chemin)] == [id2]


def test_supprimer_partie_avec_actions(tmp_path):
    """La suppression retire aussi les actions rattachées (clé étrangère)."""
    chemin = tmp_path / "parties.db"
    partie, id_partie, _trie_ = _partie_coup_puis_echange(chemin)

    assert supprimer_partie(id_partie, chemin) is True
    assert lister_parties(chemin) == []
    # La partie n'est plus reprenable : plus aucune ligne.
    with pytest.raises(KeyError):
        reprendre_partie(id_partie, _trie_, chemin)


def test_supprimer_partie_inconnue_renvoie_faux(tmp_path):
    chemin = tmp_path / "parties.db"
    demarrer_suivi(creer_partie(["Alice"], _trie(), graine=5), chemin)
    assert supprimer_partie(999, chemin) is False
    # Aucune partie existante n'a été touchée.
    assert len(lister_parties(chemin)) == 1
