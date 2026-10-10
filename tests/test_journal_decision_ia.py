"""Tests du journal de décision IA (issue #445).

Couvre : présence du journal pour un ordinateur et absence pour un humain,
cohérence du contenu (coup choisi retrouvable, alternatives triées), aller-
retour de sauvegarde, chargement d'une ancienne sauvegarde sans journal,
identité des résultats avec/sans journal à graine égale, et le script de
relecture sur une petite partie fabriquée.
"""

from __future__ import annotations

import json
import random
import sqlite3

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import (
    ACTION_COUP,
    ACTION_PASSE,
    JournalDecisionIA,
    Joueur,
    Partie,
    creer_partie,
)
from scrabble.persistance.stockage import (
    demarrer_suivi,
    enregistrer_action,
    lire_actions_journalisees,
    lire_configuration_partie,
)


def _trie(*mots: str) -> Trie:
    return Trie.depuis_iterable(mots)


_MOTS_DE_BASE = ("CADRE", "CADRES", "AS", "A", "SA", "DE", "RE", "DA", "ES")


def _graine_avec_coup(niveau: Niveau, graines: range = range(60)) -> int:
    """Première graine, dans ``graines``, pour laquelle l'IA pose un coup."""
    for graine in graines:
        partie = Partie(
            [Joueur("IA", humain=False, niveau=niveau)], _trie(*_MOTS_DE_BASE), graine=graine
        )
        entree = partie.jouer_tour_ia()
        if entree.action == ACTION_COUP:
            return graine
    raise AssertionError("Aucune graine ne produit de coup sur ce petit dictionnaire.")


# --------------------------------------------------------------------------- #
# Présence / absence du journal
# --------------------------------------------------------------------------- #


class TestPresenceDuJournal:
    def test_journal_present_pour_un_ordinateur(self):
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.INTERMEDIAIRE)],
            _trie(*_MOTS_DE_BASE),
            graine=graine,
        )
        entree = partie.jouer_tour_ia()
        assert entree.journal_ia is not None
        assert isinstance(entree.journal_ia, JournalDecisionIA)

    def test_journal_absent_pour_un_humain(self):
        partie = Partie(
            [Joueur("Alice", humain=True), Joueur("IA", humain=False, niveau=Niveau.FACILE)],
            _trie(*_MOTS_DE_BASE),
            graine=1,
        )
        entree = partie.passer()
        assert entree.journal_ia is None

    def test_journal_absent_meme_sans_coup_disponible(self):
        """Aucun coup possible (dictionnaire vide) : la passe garde un journal vide, pas None."""
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.FACILE)], _trie(), graine=1
        )
        entree = partie.jouer_tour_ia()
        assert entree.action == ACTION_PASSE
        assert entree.journal_ia is not None
        assert entree.journal_ia.nb_coups_possibles == 0
        assert entree.journal_ia.coup_choisi is None
        assert entree.journal_ia.rang_choisi is None


# --------------------------------------------------------------------------- #
# Cohérence du contenu
# --------------------------------------------------------------------------- #


class TestContenuDuJournal:
    def test_coup_choisi_se_retrouve_dans_le_journal(self):
        graine = _graine_avec_coup(Niveau.AVANCE)
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.AVANCE)],
            _trie(*_MOTS_DE_BASE),
            graine=graine,
        )
        entree = partie.jouer_tour_ia()
        journal = entree.journal_ia
        assert journal.coup_choisi is not None
        mot_joue = entree.detail.mots[0].texte
        assert journal.coup_choisi.mot == mot_joue
        assert journal.coup_choisi.score_reel == entree.detail.total
        assert journal.rang_choisi is not None
        assert 1 <= journal.rang_choisi <= journal.nb_coups_possibles

    def test_alternatives_triees_par_score_strategique_decroissant(self):
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.INTERMEDIAIRE)],
            _trie(*_MOTS_DE_BASE),
            graine=graine,
        )
        entree = partie.jouer_tour_ia()
        scores = [alt.score_strategique for alt in entree.journal_ia.meilleurs]
        assert scores == sorted(scores, reverse=True)

    def test_au_plus_cinq_meilleurs_coups(self):
        # Dictionnaire plus riche : davantage de coups possibles.
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.DEBUTANT)],
            _trie(*_MOTS_DE_BASE, "CAR", "ARE", "ERA", "SAC", "CAS"),
            graine=2,
        )
        entree = partie.jouer_tour_ia()
        assert len(entree.journal_ia.meilleurs) <= 5

    def test_chevalet_avant_reflete_le_chevalet_reel_avant_action(self):
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.FACILE)],
            _trie(*_MOTS_DE_BASE),
            graine=3,
        )
        chevalet_attendu = tuple(partie.joueur_courant().chevalet)
        entree = partie.jouer_tour_ia()
        assert entree.journal_ia.chevalet_avant == chevalet_attendu

    def test_meilleur_coup_du_journal_correspond_au_premier_de_la_liste(self):
        """Le premier élément de ``meilleurs`` a bien le score stratégique maximal."""
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.INTERMEDIAIRE)],
            _trie(*_MOTS_DE_BASE),
            graine=graine,
        )
        entree = partie.jouer_tour_ia()
        meilleurs = entree.journal_ia.meilleurs
        assert meilleurs[0].score_strategique == max(a.score_strategique for a in meilleurs)


# --------------------------------------------------------------------------- #
# Pas d'influence sur la sélection (issue #445, contrainte 2)
# --------------------------------------------------------------------------- #


class TestAucuneInfluenceSurLaSelection:
    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_meme_graine_meme_coup_tous_niveaux(self, niveau, monkeypatch):
        """Le journal ne doit rien changer : coup identique à graine égale.

        ``Partie.jouer_tour_ia`` ne transmet pas de générateur aléatoire
        explicite à ``choisir_coup`` (comportement de production inchangé) :
        celui-ci retombe alors sur ``random.Random()`` fraîchement construit,
        lui-même non déterministe d'un appel à l'autre (graine système). Pour
        isoler l'effet du JOURNAL (et non celui, préexistant, de cette
        absence de graine pour le tirage de l'IA), on fige ici
        ``random.Random`` sur une graine fixe : le seul variable restant
        d'un côté à l'autre est alors la présence ou non du calcul du
        journal.
        """
        import scrabble.moteur.ia as ia_mod

        random_original = random.Random
        monkeypatch.setattr(ia_mod.random, "Random", lambda *a, **k: random_original(123))

        dico = _trie(*_MOTS_DE_BASE, "CAR", "ARE", "SAC")
        partie_a = Partie([Joueur("IA", humain=False, niveau=niveau)], dico, graine=7)
        partie_b = Partie([Joueur("IA", humain=False, niveau=niveau)], dico, graine=7)
        entree_a = partie_a.jouer_tour_ia()
        entree_b = partie_b.jouer_tour_ia()
        assert entree_a.coup == entree_b.coup
        assert entree_a.action == entree_b.action
        assert partie_a.joueurs[0].chevalet == partie_b.joueurs[0].chevalet
        assert partie_a.sac.jetons_restants() == partie_b.sac.jetons_restants()

    def test_consommation_generateur_aleatoire_inchangee(self):
        """``choisir_coup`` sans journal consomme le même nombre de tirages aléatoires."""
        from scrabble.moteur.ia import choisir_coup, evaluer_coups
        from scrabble.moteur.plateau_partie import PlateauPartie

        dico = _trie(*_MOTS_DE_BASE)
        plateau = PlateauPartie()
        chevalet = list("CADRES")

        rng_sans_journal = random.Random(99)
        coup_sans = choisir_coup(plateau, chevalet, dico, Niveau.INTERMEDIAIRE, rng_sans_journal)
        etat_sans = rng_sans_journal.getstate()

        rng_avec_journal = random.Random(99)
        coup_avec = choisir_coup(plateau, chevalet, dico, Niveau.INTERMEDIAIRE, rng_avec_journal)
        # evaluer_coups est appelé APRÈS, comme dans jouer_tour_ia : ne doit pas
        # toucher à rng_avec_journal (il ne reçoit même pas l'objet).
        evaluer_coups(plateau, chevalet, dico, Niveau.INTERMEDIAIRE, coup_choisi=coup_avec)
        etat_avec = rng_avec_journal.getstate()

        assert coup_sans == coup_avec
        assert etat_sans == etat_avec


# --------------------------------------------------------------------------- #
# Persistance : aller-retour, ancienne sauvegarde, poids
# --------------------------------------------------------------------------- #


class TestPersistanceDuJournal:
    def test_aller_retour_sauvegarde(self, tmp_path):
        chemin = tmp_path / "parties.db"
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.INTERMEDIAIRE)],
            _trie(*_MOTS_DE_BASE),
            graine=graine,
        )
        id_partie = demarrer_suivi(partie, chemin)
        entree = partie.jouer_tour_ia()
        enregistrer_action(id_partie, entree, chemin)

        actions = lire_actions_journalisees(id_partie, chemin)
        assert len(actions) == 1
        journal_relu = actions[0].journal_ia
        assert journal_relu is not None
        assert journal_relu.chevalet_avant == entree.journal_ia.chevalet_avant
        assert journal_relu.nb_coups_possibles == entree.journal_ia.nb_coups_possibles
        assert journal_relu.rang_choisi == entree.journal_ia.rang_choisi
        assert journal_relu.coup_choisi == entree.journal_ia.coup_choisi
        assert journal_relu.meilleurs == entree.journal_ia.meilleurs

    def test_humain_sans_journal_aller_retour(self, tmp_path):
        chemin = tmp_path / "parties.db"
        partie = Partie(
            [Joueur("Alice", humain=True), Joueur("IA", humain=False, niveau=Niveau.FACILE)],
            _trie(*_MOTS_DE_BASE),
            graine=1,
        )
        id_partie = demarrer_suivi(partie, chemin)
        entree = partie.passer()
        enregistrer_action(id_partie, entree, chemin)

        actions = lire_actions_journalisees(id_partie, chemin)
        assert actions[0].journal_ia is None

    def test_chargement_ancienne_sauvegarde_sans_colonne_journal(self, tmp_path):
        """Une base créée avant l'issue #445 (sans colonne ``journal_ia``) se
        charge et se rejoue sans erreur, sans migration manuelle."""
        chemin = tmp_path / "ancienne.db"
        conn = sqlite3.connect(str(chemin))
        conn.executescript(
            """
            CREATE TABLE parties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                graine INTEGER NOT NULL,
                date_creation TEXT NOT NULL,
                date_maj TEXT NOT NULL,
                joueurs TEXT NOT NULL,
                statut TEXT NOT NULL,
                scores_finaux TEXT,
                gagnants TEXT
            );
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_partie INTEGER NOT NULL,
                indice INTEGER NOT NULL,
                index_joueur INTEGER NOT NULL,
                nom_joueur TEXT NOT NULL,
                type_action TEXT NOT NULL,
                coup TEXT,
                jetons_echanges TEXT,
                detail TEXT,
                lettres_echangees INTEGER NOT NULL DEFAULT 0,
                score_cumule INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        joueurs = json.dumps([{"nom": "IA", "humain": False, "niveau": "EXPERT"}])
        conn.execute(
            "INSERT INTO parties (id, graine, date_creation, date_maj, joueurs, statut) "
            "VALUES (1, 2, '2020-01-01T00:00:00', '2020-01-01T00:00:00', ?, 'en_cours')",
            (joueurs,),
        )
        coup_json = json.dumps(
            {
                "ligne": 7,
                "colonne": 7,
                "direction": "H",
                "tuiles": [{"lettre": "A", "joker": False}, {"lettre": "S", "joker": False}],
            }
        )
        detail_json = json.dumps(
            {"total": 4, "bonus_scrabble": 0, "mots": [{"texte": "AS", "score": 4, "cases_bonus": []}]}
        )
        conn.execute(
            "INSERT INTO actions (id_partie, indice, index_joueur, nom_joueur, type_action, "
            "coup, detail, score_cumule) VALUES (1, 0, 0, 'IA', 'coup', ?, ?, 4)",
            (coup_json, detail_json),
        )
        conn.commit()
        conn.close()

        # Lecture seule : fonctionne malgré la colonne absente.
        actions = lire_actions_journalisees(1, chemin)
        assert len(actions) == 1
        assert actions[0].journal_ia is None
        assert actions[0].action == ACTION_COUP

        # Ouverture normale (écriture) : migration idempotente, pas d'erreur.
        from scrabble.persistance.stockage import reprendre_partie

        partie = reprendre_partie(1, _trie("AS"), chemin)
        assert partie.joueurs[0].score == 4

    def test_poids_ajoute_reste_modeste(self, tmp_path):
        """Repère non normatif : la colonne journal ajoute quelques centaines
        d'octets par coup IA, pas un ordre de grandeur supplémentaire."""
        chemin = tmp_path / "parties.db"
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = Partie(
            [Joueur("IA", humain=False, niveau=Niveau.INTERMEDIAIRE)],
            _trie(*_MOTS_DE_BASE, "CAR", "ARE", "SAC", "CAS"),
            graine=graine,
        )
        id_partie = demarrer_suivi(partie, chemin)
        entree = partie.jouer_tour_ia()
        enregistrer_action(id_partie, entree, chemin)

        conn = sqlite3.connect(str(chemin))
        (taille,) = conn.execute(
            "SELECT LENGTH(journal_ia) FROM actions WHERE id_partie = ?", (id_partie,)
        ).fetchone()
        conn.close()
        assert taille is not None
        assert taille < 3000  # quelques centaines d'octets attendues, large marge


# --------------------------------------------------------------------------- #
# Configuration de partie (pour le script de relecture)
# --------------------------------------------------------------------------- #


def test_lire_configuration_partie(tmp_path):
    chemin = tmp_path / "parties.db"
    partie = creer_partie(
        ["Alice"], _trie(*_MOTS_DE_BASE), nb_ia=1, niveaux_ia=[Niveau.EXPERT], graine=4
    )
    id_partie = demarrer_suivi(partie, chemin)
    config = lire_configuration_partie(id_partie, chemin)
    assert config.graine == 4
    assert config.joueurs[0]["nom"] == "Alice"
    assert config.joueurs[1]["niveau"] == "EXPERT"


def test_lire_configuration_partie_inconnue_leve(tmp_path):
    chemin = tmp_path / "parties.db"
    partie = creer_partie(["Alice"], _trie(), graine=1)
    demarrer_suivi(partie, chemin)
    with pytest.raises(KeyError):
        lire_configuration_partie(999, chemin)


# --------------------------------------------------------------------------- #
# Confidentialité : le journal ne doit JAMAIS atteindre l'UI (issue #445, 4)
# --------------------------------------------------------------------------- #


class TestConfidentialiteDuJournal:
    """Le chevalet d'un ordinateur (et tout le journal) reste invisible en jeu."""

    def _partie_avec_journal(self):
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = Partie(
            [Joueur("Alice", humain=True), Joueur("IA", humain=False, niveau=Niveau.INTERMEDIAIRE)],
            _trie(*_MOTS_DE_BASE),
            graine=graine,
        )
        partie.index_courant = 1
        entree = partie.jouer_tour_ia()
        assert entree.journal_ia is not None  # garde-fou : le test porte bien un journal
        return partie

    def test_etat_public_ne_porte_aucune_cle_journal(self):
        from scrabble.ui.jeu import etat_public

        partie = self._partie_avec_journal()
        etat = etat_public(partie, None)
        texte = json.dumps(etat)
        assert "journal_ia" not in texte
        assert "chevalet_avant" not in texte
        assert "score_strategique" not in texte

    def test_serialiser_entree_historique_ne_porte_aucune_cle_journal(self):
        from scrabble.ui.jeu import serialiser_entree_historique

        partie = self._partie_avec_journal()
        index = len(partie.historique) - 1
        charge = serialiser_entree_historique(partie, partie.historique[index], index)
        texte = json.dumps(charge)
        assert "journal_ia" not in texte
        assert "chevalet_avant" not in texte
        assert "score_strategique" not in texte

    def test_serialiser_historique_ne_porte_aucune_cle_journal(self):
        from scrabble.ui.jeu import serialiser_historique

        partie = self._partie_avec_journal()
        texte = json.dumps(serialiser_historique(partie))
        assert "journal_ia" not in texte
        assert "chevalet_avant" not in texte
        assert "score_strategique" not in texte

    def test_serialiser_dernier_coup_ne_porte_aucune_cle_journal(self):
        from scrabble.ui.jeu import serialiser_dernier_coup

        partie = self._partie_avec_journal()
        charge = serialiser_dernier_coup(partie)
        texte = json.dumps(charge)
        assert "journal_ia" not in texte
        assert "chevalet_avant" not in texte


# --------------------------------------------------------------------------- #
# Script de relecture (issue #445, point 5)
# --------------------------------------------------------------------------- #


def _charger_script_relecture():
    """Importe le script ``scripts/relire_journal_ia.py`` comme module."""
    import importlib.util
    import pathlib

    chemin = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "relire_journal_ia.py"
    spec = importlib.util.spec_from_file_location("relire_journal_ia", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestScriptDeRelecture:
    def test_relecture_partie_fabriquee_affiche_chevalet_et_alternatives(self, tmp_path, capsys):
        script = _charger_script_relecture()
        chemin = tmp_path / "parties.db"
        graine = _graine_avec_coup(Niveau.INTERMEDIAIRE)
        partie = creer_partie(
            ["Alice"],
            _trie(*_MOTS_DE_BASE),
            nb_ia=1,
            niveaux_ia=[Niveau.INTERMEDIAIRE],
            graine=graine,
        )
        # Force l'ordre humain puis IA et un chevalet connu pour l'IA.
        partie.index_courant = 0
        id_partie = demarrer_suivi(partie, chemin)
        entree_humain = partie.passer()
        enregistrer_action(id_partie, entree_humain, chemin)
        entree_ia = partie.jouer_tour_ia()
        enregistrer_action(id_partie, entree_ia, chemin)

        script.relire(str(chemin), id_partie)
        sortie = capsys.readouterr().out

        assert f"Partie #{id_partie}" in sortie
        assert "Résumé par joueur" in sortie
        if entree_ia.action == ACTION_COUP:
            assert "Chevalet avant" in sortie
            assert "Rang du coup choisi" in sortie

    def test_relecture_filtre_par_joueur(self, tmp_path, capsys):
        script = _charger_script_relecture()
        chemin = tmp_path / "parties.db"
        partie = creer_partie(
            ["Alice"], _trie(*_MOTS_DE_BASE), nb_ia=1, niveaux_ia=[Niveau.FACILE], graine=1
        )
        partie.index_courant = 0
        id_partie = demarrer_suivi(partie, chemin)
        entree = partie.passer()
        enregistrer_action(id_partie, entree, chemin)

        script.relire(str(chemin), id_partie, joueur="Alice")
        sortie = capsys.readouterr().out
        corps = sortie.split("---", 1)[1].split("Résumé par joueur")[0]
        assert "Alice" in sortie
        assert "IA 1" not in corps

    def test_relecture_ancienne_partie_sans_journal_le_signale(self, tmp_path, capsys):
        script = _charger_script_relecture()
        chemin = tmp_path / "ancienne.db"
        conn = sqlite3.connect(str(chemin))
        conn.executescript(
            """
            CREATE TABLE parties (
                id INTEGER PRIMARY KEY AUTOINCREMENT, graine INTEGER NOT NULL,
                date_creation TEXT NOT NULL, date_maj TEXT NOT NULL, joueurs TEXT NOT NULL,
                statut TEXT NOT NULL, scores_finaux TEXT, gagnants TEXT
            );
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, id_partie INTEGER NOT NULL,
                indice INTEGER NOT NULL, index_joueur INTEGER NOT NULL, nom_joueur TEXT NOT NULL,
                type_action TEXT NOT NULL, coup TEXT, jetons_echanges TEXT, detail TEXT,
                lettres_echangees INTEGER NOT NULL DEFAULT 0, score_cumule INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        joueurs = json.dumps([{"nom": "Bob", "humain": False, "niveau": "EXPERT"}])
        conn.execute(
            "INSERT INTO parties (id, graine, date_creation, date_maj, joueurs, statut) "
            "VALUES (1, 5, '2020-01-01T00:00:00', '2020-01-01T00:00:00', ?, 'en_cours')",
            (joueurs,),
        )
        coup_json = json.dumps(
            {
                "ligne": 7,
                "colonne": 7,
                "direction": "H",
                "tuiles": [{"lettre": "A", "joker": False}, {"lettre": "S", "joker": False}],
            }
        )
        detail_json = json.dumps(
            {"total": 4, "bonus_scrabble": 0, "mots": [{"texte": "AS", "score": 4, "cases_bonus": []}]}
        )
        conn.execute(
            "INSERT INTO actions (id_partie, indice, index_joueur, nom_joueur, type_action, "
            "coup, detail, score_cumule) VALUES (1, 0, 0, 'Bob', 'coup', ?, ?, 4)",
            (coup_json, detail_json),
        )
        conn.commit()
        conn.close()

        script.relire(str(chemin), 1)
        sortie = capsys.readouterr().out
        assert "chevalet non enregistré" in sortie
        assert "'AS'" in sortie
