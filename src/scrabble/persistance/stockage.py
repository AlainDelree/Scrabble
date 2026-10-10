"""Persistance des parties : historique et reprise après plantage (SQLite).

Rôle : conserver sur disque, au fil de l'eau, de quoi (1) retrouver
l'historique des parties terminées et (2) **reprendre une partie en cours**
après une coupure — sans jamais sérialiser l'état vivant (plateau, chevalets,
sac).

Principe de conception
----------------------
Le déroulement d'une partie est **entièrement déterministe** à partir de deux
ingrédients :

* la **graine** du sac (:attr:`scrabble.moteur.partie.Partie.graine`, passée à
  :class:`scrabble.moteur.tirage.Sac`) ;
* la **suite ordonnée des actions** jouées (coup / passe / échange).

On ne sauvegarde donc que ces deux choses. Reprendre une partie consiste à
recréer une :class:`~scrabble.moteur.partie.Partie` avec la **même graine**,
puis à **rejouer** chaque action via les méthodes existantes
(:meth:`~scrabble.moteur.partie.Partie.jouer_coup`,
:meth:`~scrabble.moteur.partie.Partie.passer`,
:meth:`~scrabble.moteur.partie.Partie.echanger`). Aucune reconstruction d'état
ad hoc n'est écrite ici : le moteur refait le travail à l'identique.

Point clé sur l'échange
-----------------------
Pour qu'un rejeu retombe sur le **même tirage**, il ne suffit pas de connaître
*combien* de lettres ont été échangées : il faut les lettres **précises**, dans
l'ordre où elles ont été remises au sac (le mélange de
:meth:`scrabble.moteur.tirage.Sac.remettre` en dépend). C'est
:attr:`~scrabble.moteur.partie.EntreeHistorique.jetons_echanges` qui les porte.

Schéma
------
Deux tables (voir :func:`_initialiser_schema`) :

* ``parties`` — une ligne par partie : graine, dates, configuration des joueurs
  (JSON), statut, et, une fois finie, scores finaux et gagnant(s) ;
* ``actions`` — une ligne par action, rattachée à sa partie par ``id_partie`` et
  ordonnée par ``indice`` ; reflète
  :class:`~scrabble.moteur.partie.EntreeHistorique` sérialisé.

``sqlite3`` fait partie de la bibliothèque standard : aucune installation.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from scrabble.config import RACINE_DONNEES_UTILISATEUR
from scrabble.moteur.ia import AlternativeCoup, Niveau
from scrabble.moteur.partie import (
    ACTION_COUP,
    ACTION_ECHANGE,
    ACTION_PASSE,
    EntreeHistorique,
    JournalDecisionIA,
    Joueur,
    Partie,
)
from scrabble.moteur.plateau_partie import Coup, Direction, Tuile
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.moteur.validation import DictionnaireMots
from scrabble.regles.plateau import TypeCase

#: Emplacement par défaut de la base (dans ``data/``, gitignoré), sous
#: ``RACINE_DONNEES_UTILISATEUR`` (issue #421) : inscriptible sans droits admin.
CHEMIN_DEFAUT = RACINE_DONNEES_UTILISATEUR / "data" / "parties.db"

#: Valeurs de la colonne ``parties.statut``.
STATUT_EN_COURS = "en_cours"
STATUT_TERMINEE = "terminee"

_TypeChemin = str | Path


# --------------------------------------------------------------------------- #
# Résumé renvoyé par lister_parties
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ResumePartie:
    """Fiche synthétique d'une partie pour un écran de sélection/historique.

    ``joueurs`` liste des dictionnaires ``{"nom", "humain", "niveau",
    "personnage", "personnage_aleatoire"}`` (niveau ``None`` pour un humain ;
    personnage une chaîne vide par défaut, issue #438 lot A ;
    personnage_aleatoire un booléen, issue #440 lot D). ``scores_finaux`` et
    ``gagnants`` valent ``None`` tant que la partie n'est pas terminée.

    ``scores_actuels`` donne, dans l'ordre de ``joueurs``, le score courant de
    chaque joueur (issue #76). Il est déduit sans rejeu de la partie : c'est le
    ``score_cumule`` de la **dernière action** de chaque joueur dans la table
    ``actions`` (0 pour un joueur qui n'a pas encore joué). Utile pour afficher
    l'état d'une partie en cours avant de la reprendre.
    """

    id: int
    statut: str
    graine: int
    date_creation: str
    date_maj: str
    joueurs: list[dict]
    scores_finaux: list[int] | None = None
    gagnants: list[str] | None = None
    scores_actuels: list[int] | None = None
    mode_belgicisme: bool = False

    @property
    def terminee(self) -> bool:
        """Vrai si la partie est marquée terminée."""
        return self.statut == STATUT_TERMINEE


# --------------------------------------------------------------------------- #
# Sérialisation des objets du moteur <-> types stockables (JSON)
# --------------------------------------------------------------------------- #

def _tuile_vers_dict(tuile: Tuile) -> dict:
    return {"lettre": tuile.lettre, "joker": tuile.joker}


def _tuile_depuis_dict(donnees: dict) -> Tuile:
    return Tuile(lettre=donnees["lettre"], joker=bool(donnees["joker"]))


def coup_vers_json(coup: Coup) -> str:
    """Sérialise un :class:`Coup` en chaîne JSON stockable."""
    return json.dumps(
        {
            "ligne": coup.ligne,
            "colonne": coup.colonne,
            "direction": coup.direction.value,
            "tuiles": [_tuile_vers_dict(t) for t in coup.tuiles],
        },
        ensure_ascii=False,
    )


def coup_depuis_json(texte: str) -> Coup:
    """Reconstruit un :class:`Coup` depuis sa forme JSON (inverse de :func:`coup_vers_json`)."""
    donnees = json.loads(texte)
    return Coup(
        ligne=donnees["ligne"],
        colonne=donnees["colonne"],
        direction=Direction(donnees["direction"]),
        tuiles=tuple(_tuile_depuis_dict(t) for t in donnees["tuiles"]),
    )


def _detail_vers_json(detail: DetailScore) -> str:
    return json.dumps(
        {
            "total": detail.total,
            "bonus_scrabble": detail.bonus_scrabble,
            "mots": [
                {
                    "texte": mot.texte,
                    "score": mot.score,
                    "cases_bonus": [
                        [ligne, colonne, type_case.name]
                        for ligne, colonne, type_case in mot.cases_bonus
                    ],
                }
                for mot in detail.mots
            ],
        },
        ensure_ascii=False,
    )


def _detail_depuis_json(texte: str) -> DetailScore:
    donnees = json.loads(texte)
    mots = [
        DetailMot(
            texte=mot["texte"],
            score=mot["score"],
            cases_bonus=[
                (ligne, colonne, TypeCase[nom])
                for ligne, colonne, nom in mot["cases_bonus"]
            ],
        )
        for mot in donnees["mots"]
    ]
    return DetailScore(
        mots=mots,
        bonus_scrabble=donnees["bonus_scrabble"],
        total=donnees["total"],
    )


def _alternative_vers_dict(alt: AlternativeCoup) -> dict:
    return {
        "mot": alt.mot,
        "ligne": alt.ligne,
        "colonne": alt.colonne,
        "direction": alt.direction,
        "score_reel": alt.score_reel,
        "score_strategique": alt.score_strategique,
    }


def _alternative_depuis_dict(donnees: dict) -> AlternativeCoup:
    return AlternativeCoup(
        mot=donnees["mot"],
        ligne=donnees["ligne"],
        colonne=donnees["colonne"],
        direction=donnees["direction"],
        score_reel=donnees["score_reel"],
        score_strategique=donnees["score_strategique"],
    )


def _journal_ia_vers_json(journal: JournalDecisionIA | None) -> str | None:
    """Sérialise le journal de décision IA (issue #445), ``None`` si absent.

    Absent pour une action humaine, ou pour une ancienne partie enregistrée
    avant cette fonctionnalité (voir la colonne ``journal_ia``, facultative,
    de la table ``actions``).
    """
    if journal is None:
        return None
    return json.dumps(
        {
            "chevalet_avant": list(journal.chevalet_avant),
            "nb_coups_possibles": journal.nb_coups_possibles,
            "meilleurs": [_alternative_vers_dict(a) for a in journal.meilleurs],
            "rang_choisi": journal.rang_choisi,
            "coup_choisi": (
                None
                if journal.coup_choisi is None
                else _alternative_vers_dict(journal.coup_choisi)
            ),
        },
        ensure_ascii=False,
    )


def _journal_ia_depuis_json(texte: str | None) -> JournalDecisionIA | None:
    """Reconstruit le journal de décision IA depuis sa forme JSON (issue #445).

    ``None`` si ``texte`` est ``None`` — colonne absente (ancienne sauvegarde)
    ou action humaine.
    """
    if texte is None:
        return None
    donnees = json.loads(texte)
    return JournalDecisionIA(
        chevalet_avant=tuple(donnees["chevalet_avant"]),
        nb_coups_possibles=donnees["nb_coups_possibles"],
        meilleurs=tuple(
            _alternative_depuis_dict(a) for a in donnees["meilleurs"]
        ),
        rang_choisi=donnees["rang_choisi"],
        coup_choisi=(
            None
            if donnees["coup_choisi"] is None
            else _alternative_depuis_dict(donnees["coup_choisi"])
        ),
    )


def _joueurs_vers_json(joueurs: list[Joueur]) -> str:
    return json.dumps(
        [
            {
                "nom": j.nom,
                "humain": j.humain,
                "niveau": None if j.niveau is None else j.niveau.name,
                "personnage": j.personnage,
                "personnage_aleatoire": j.personnage_aleatoire,
            }
            for j in joueurs
        ],
        ensure_ascii=False,
    )


def _joueurs_depuis_json(texte: str) -> list[dict]:
    return json.loads(texte)


# --------------------------------------------------------------------------- #
# Accès bas niveau à la base
# --------------------------------------------------------------------------- #

@contextmanager
def _connexion(chemin: _TypeChemin) -> Iterator[sqlite3.Connection]:
    """Ouvre la base (créant le dossier et le schéma au besoin), la referme.

    Utilisée comme gestionnaire de contexte : la transaction est validée à la
    sortie normale (ou annulée sur exception), puis la connexion est **toujours
    fermée** — important pour ne pas laisser de handle sur le fichier (nettoyage
    des bases temporaires en test, verrous sous Windows).
    """
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(str(chemin))
    try:
        connexion.execute("PRAGMA foreign_keys = ON")
        connexion.row_factory = sqlite3.Row
        _initialiser_schema(connexion)
        with connexion:
            yield connexion
    finally:
        connexion.close()


def _initialiser_schema(connexion: sqlite3.Connection) -> None:
    """Crée les tables si elles n'existent pas (idempotent)."""
    connexion.executescript(
        """
        CREATE TABLE IF NOT EXISTS parties (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            graine         INTEGER NOT NULL,
            date_creation  TEXT    NOT NULL,
            date_maj       TEXT    NOT NULL,
            joueurs        TEXT    NOT NULL,
            statut         TEXT    NOT NULL,
            scores_finaux  TEXT,
            gagnants       TEXT
        );

        CREATE TABLE IF NOT EXISTS actions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            id_partie        INTEGER NOT NULL,
            indice           INTEGER NOT NULL,
            index_joueur     INTEGER NOT NULL,
            nom_joueur       TEXT    NOT NULL,
            type_action      TEXT    NOT NULL,
            coup             TEXT,
            jetons_echanges  TEXT,
            detail           TEXT,
            lettres_echangees INTEGER NOT NULL DEFAULT 0,
            score_cumule     INTEGER NOT NULL DEFAULT 0,
            journal_ia       TEXT,
            FOREIGN KEY (id_partie) REFERENCES parties(id),
            UNIQUE (id_partie, indice)
        );

        CREATE INDEX IF NOT EXISTS idx_actions_partie
            ON actions (id_partie, indice);
        """
    )
    # Migration (issue #305) : ajoute la colonne ``mode_belgicisme`` aux bases
    # créées avant son introduction. Les parties existantes reçoivent la
    # valeur par défaut 0 (France), comportement souhaité.
    colonnes = [
        row[1] for row in connexion.execute("PRAGMA table_info(parties)").fetchall()
    ]
    if "mode_belgicisme" not in colonnes:
        connexion.execute(
            "ALTER TABLE parties ADD COLUMN "
            "mode_belgicisme INTEGER NOT NULL DEFAULT 0"
        )
    # Migration (issue #445) : ajoute la colonne facultative ``journal_ia`` aux
    # bases créées avant cette fonctionnalité. ``NULL`` pour toutes les actions
    # déjà enregistrées (comportement voulu : ces anciennes parties n'ont
    # jamais eu de journal, voir :func:`_journal_ia_depuis_json`), le ``CREATE
    # TABLE`` ci-dessus couvrant déjà les bases toutes neuves.
    colonnes_actions = [
        row[1] for row in connexion.execute("PRAGMA table_info(actions)").fetchall()
    ]
    if "journal_ia" not in colonnes_actions:
        connexion.execute("ALTER TABLE actions ADD COLUMN journal_ia TEXT")
    connexion.commit()


def _maintenant() -> str:
    """Horodatage ISO 8601 en UTC (colonnes de dates)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Fonctions principales
# --------------------------------------------------------------------------- #

def demarrer_suivi(
    partie: Partie,
    chemin: _TypeChemin = CHEMIN_DEFAUT,
    mode_belgicisme: bool = False,
) -> int:
    """Enregistre une partie fraîche (graine + joueurs), statut « en cours ».

    À appeler juste après :func:`~scrabble.moteur.partie.creer_partie`. Renvoie
    l'identifiant attribué, à passer ensuite à :func:`enregistrer_action` et
    :func:`finaliser_partie`.

    :raises ValueError: si la partie n'a pas de graine explicite
        (``partie.graine is None``) : sans graine fixe le déroulement n'est pas
        reproductible, donc la reprise serait impossible.
    """
    if partie.graine is None:
        raise ValueError(
            "Impossible de suivre une partie sans graine : le sac ne serait pas "
            "reproductible. Créez la partie avec un argument graine explicite."
        )
    horodatage = _maintenant()
    with _connexion(chemin) as connexion:
        curseur = connexion.execute(
            "INSERT INTO parties "
            "(graine, date_creation, date_maj, joueurs, statut, mode_belgicisme) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                partie.graine,
                horodatage,
                horodatage,
                _joueurs_vers_json(partie.joueurs),
                STATUT_EN_COURS,
                int(mode_belgicisme),
            ),
        )
        return int(curseur.lastrowid)


def enregistrer_action(
    id_partie: int,
    entree: EntreeHistorique,
    chemin: _TypeChemin = CHEMIN_DEFAUT,
) -> None:
    """Ajoute ``entree`` à la suite des actions de la partie ``id_partie``.

    À appeler après chaque :meth:`~scrabble.moteur.partie.Partie.jouer_coup`,
    :meth:`~scrabble.moteur.partie.Partie.passer` ou
    :meth:`~scrabble.moteur.partie.Partie.echanger` réussi. Économe : une seule
    petite insertion (l'indice séquentiel est déduit du nombre d'actions déjà
    stockées) plus la mise à jour de la date de dernière modification de la
    partie — aucune récriture de la partie entière.
    """
    coup_json = coup_vers_json(entree.coup) if entree.coup is not None else None
    detail_json = (
        _detail_vers_json(entree.detail) if entree.detail is not None else None
    )
    jetons_json = (
        json.dumps(entree.jetons_echanges, ensure_ascii=False)
        if entree.jetons_echanges
        else None
    )
    journal_json = _journal_ia_vers_json(entree.journal_ia)
    with _connexion(chemin) as connexion:
        (indice_suivant,) = connexion.execute(
            "SELECT COUNT(*) FROM actions WHERE id_partie = ?", (id_partie,)
        ).fetchone()
        connexion.execute(
            "INSERT INTO actions "
            "(id_partie, indice, index_joueur, nom_joueur, type_action, coup, "
            " jetons_echanges, detail, lettres_echangees, score_cumule, journal_ia) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                id_partie,
                indice_suivant,
                entree.index_joueur,
                entree.nom_joueur,
                entree.action,
                coup_json,
                jetons_json,
                detail_json,
                entree.lettres_echangees,
                entree.score_cumule,
                journal_json,
            ),
        )
        connexion.execute(
            "UPDATE parties SET date_maj = ? WHERE id = ?",
            (_maintenant(), id_partie),
        )


def finaliser_partie(
    id_partie: int,
    partie: Partie,
    chemin: _TypeChemin = CHEMIN_DEFAUT,
) -> None:
    """Marque ``id_partie`` terminée et enregistre scores finaux + gagnant(s).

    À appeler une fois ``partie.terminee`` vrai. Les scores sont ceux des
    joueurs dans l'ordre de la partie ; les gagnants sont donnés par nom (gère
    les égalités, plusieurs gagnants possibles).

    :raises ValueError: si la partie n'est pas terminée.
    """
    if not partie.terminee:
        raise ValueError(
            "finaliser_partie appelée sur une partie non terminée "
            "(partie.terminee est faux)."
        )
    scores = [j.score for j in partie.joueurs]
    gagnants = [j.nom for j in partie.gagnants]
    with _connexion(chemin) as connexion:
        connexion.execute(
            "UPDATE parties SET statut = ?, scores_finaux = ?, gagnants = ?, "
            "date_maj = ? WHERE id = ?",
            (
                STATUT_TERMINEE,
                json.dumps(scores),
                json.dumps(gagnants, ensure_ascii=False),
                _maintenant(),
                id_partie,
            ),
        )


def supprimer_partie(id_partie: int, chemin: _TypeChemin = CHEMIN_DEFAUT) -> bool:
    """Supprime définitivement la partie ``id_partie`` et toutes ses actions.

    Renvoie ``True`` si une partie portait cet identifiant (et a donc été
    supprimée), ``False`` sinon. Les actions rattachées sont retirées d'abord :
    la contrainte de clé étrangère ``actions.id_partie -> parties.id``
    (``PRAGMA foreign_keys = ON``) empêcherait sinon la suppression de la ligne
    ``parties``.

    Usage prévu (issue #67) : annuler une partie tout juste créée
    (:func:`demarrer_suivi`) mais dont aucun coup n'a encore été joué, afin
    qu'elle n'apparaisse pas comme partie fantôme dans la liste de reprise.
    """
    with _connexion(chemin) as connexion:
        connexion.execute("DELETE FROM actions WHERE id_partie = ?", (id_partie,))
        curseur = connexion.execute(
            "DELETE FROM parties WHERE id = ?", (id_partie,)
        )
        return curseur.rowcount > 0


def _scores_actuels_par_partie(
    connexion: sqlite3.Connection,
) -> dict[int, dict[int, int]]:
    """Score courant de chaque joueur de chaque partie, sans rejeu (issue #76).

    Renvoie ``{id_partie: {index_joueur: score_cumule}}`` en ne retenant, pour
    chaque couple (partie, joueur), que le ``score_cumule`` de sa **dernière**
    action (indice maximal) — c'est-à-dire son score courant. Un joueur sans
    action n'apparaît pas (score implicite 0, complété par l'appelant).

    Une seule requête pour toutes les parties : la sous-requête agrège l'indice
    maximal par (partie, joueur), la requête externe récupère le
    ``score_cumule`` correspondant.
    """
    lignes = connexion.execute(
        "SELECT a.id_partie, a.index_joueur, a.score_cumule "
        "FROM actions a "
        "JOIN (SELECT id_partie, index_joueur, MAX(indice) AS max_indice "
        "      FROM actions GROUP BY id_partie, index_joueur) m "
        "  ON a.id_partie = m.id_partie "
        " AND a.index_joueur = m.index_joueur "
        " AND a.indice = m.max_indice"
    ).fetchall()
    scores: dict[int, dict[int, int]] = {}
    for ligne in lignes:
        scores.setdefault(ligne["id_partie"], {})[ligne["index_joueur"]] = (
            ligne["score_cumule"]
        )
    return scores


def lister_parties(chemin: _TypeChemin = CHEMIN_DEFAUT) -> list[ResumePartie]:
    """Résumé de chaque partie, triées par date de mise à jour décroissante.

    Chaque résumé porte ``scores_actuels`` : le score courant de chaque joueur
    (dans l'ordre de ``joueurs``), déduit du dernier ``score_cumule`` de la
    table ``actions`` sans rejouer la partie (issue #76).
    """
    with _connexion(chemin) as connexion:
        lignes = connexion.execute(
            "SELECT id, statut, graine, date_creation, date_maj, joueurs, "
            "scores_finaux, gagnants, mode_belgicisme FROM parties "
            "ORDER BY date_maj DESC, id DESC"
        ).fetchall()
        scores_par_partie = _scores_actuels_par_partie(connexion)
    resumes: list[ResumePartie] = []
    for ligne in lignes:
        scores = ligne["scores_finaux"]
        gagnants = ligne["gagnants"]
        joueurs = _joueurs_depuis_json(ligne["joueurs"])
        scores_joueurs = scores_par_partie.get(ligne["id"], {})
        scores_actuels = [scores_joueurs.get(i, 0) for i in range(len(joueurs))]
        resumes.append(
            ResumePartie(
                id=ligne["id"],
                statut=ligne["statut"],
                graine=ligne["graine"],
                date_creation=ligne["date_creation"],
                date_maj=ligne["date_maj"],
                joueurs=joueurs,
                scores_finaux=None if scores is None else json.loads(scores),
                gagnants=None if gagnants is None else json.loads(gagnants),
                scores_actuels=scores_actuels,
                mode_belgicisme=bool(ligne["mode_belgicisme"]),
            )
        )
    return resumes


def niveaux_ia_stockes(
    id_partie: int, chemin: _TypeChemin = CHEMIN_DEFAUT
) -> list[Niveau]:
    """Niveaux des IA de la partie stockée ``id_partie``, sans la reconstruire.

    Lit directement la configuration JSON des joueurs (colonne
    ``parties.joueurs``), sans rejouer les actions ni instancier de
    :class:`Partie`. Sert à l'appelant (``ui.accueil.ApiAccueil.reprendre``,
    issue #369 lot C) à savoir quels paliers de vocabulaire IA charger
    **avant** d'appeler :func:`reprendre_partie` : les niveaux d'une partie
    reprise doivent venir de la partie **stockée**, pas de la configuration
    courante de l'accueil (une IA « Expert » restée en base doit continuer à
    jouer Expert même si l'accueil affiche autre chose entre-temps).

    :raises KeyError: si aucune partie ne porte cet identifiant.
    """
    with _connexion(chemin) as connexion:
        ligne = connexion.execute(
            "SELECT joueurs FROM parties WHERE id = ?", (id_partie,)
        ).fetchone()
    if ligne is None:
        raise KeyError(f"Aucune partie d'identifiant {id_partie}.")
    configs = _joueurs_depuis_json(ligne["joueurs"])
    return [
        Niveau[donnees["niveau"]]
        for donnees in configs
        if donnees.get("niveau") is not None
    ]


def reprendre_partie(
    id_partie: int,
    dictionnaire: DictionnaireMots,
    chemin: _TypeChemin = CHEMIN_DEFAUT,
    *,
    dictionnaires_ia: dict[Niveau, DictionnaireMots] | None = None,
) -> Partie:
    """Reconstruit la :class:`Partie` ``id_partie`` en rejouant ses actions.

    Recrée les joueurs et le sac (même graine) depuis la table ``parties``, puis
    rejoue **dans l'ordre** chaque action de la table ``actions`` en appelant la
    méthode correspondante du moteur (``jouer_coup`` / ``passer`` / ``echanger``).
    Comme le déroulement est déterministe, la partie renvoyée est dans le même
    état exact (plateau, chevalets, sac, score, joueur courant) qu'au moment où
    la dernière action a été jouée — prête à continuer.

    ``dictionnaire`` doit être le même (ou en contenir les mots) que celui de la
    partie d'origine, sans quoi le rejeu d'un coup échouerait à la validation.

    ``dictionnaires_ia`` (issues #206, #369 lot C) associe à chaque
    :class:`~scrabble.moteur.ia.Niveau` présent son Trie restreint, transmis tel
    quel à la :class:`Partie` reconstruite pour que chaque IA d'une partie
    **reprise** continue de jouer dans son vocabulaire propre. ``None`` (défaut)
    = toutes les IA sur le dictionnaire complet. Voir :func:`niveaux_ia_stockes`
    pour connaître, avant l'appel, les niveaux à couvrir dans ce mapping (les
    niveaux viennent de la partie stockée, pas de la config courante). Le rejeu
    des actions passe toujours par ``valider_coup`` sur ``dictionnaire``
    complet : il n'est donc pas affecté par ce paramètre.

    :raises KeyError: si aucune partie ne porte cet identifiant.
    """
    with _connexion(chemin) as connexion:
        ligne = connexion.execute(
            "SELECT graine, joueurs FROM parties WHERE id = ?", (id_partie,)
        ).fetchone()
        if ligne is None:
            raise KeyError(f"Aucune partie d'identifiant {id_partie}.")
        actions = connexion.execute(
            "SELECT type_action, coup, jetons_echanges FROM actions "
            "WHERE id_partie = ? ORDER BY indice ASC",
            (id_partie,),
        ).fetchall()

    joueurs = _reconstruire_joueurs(_joueurs_depuis_json(ligne["joueurs"]))
    partie = Partie(
        joueurs,
        dictionnaire,
        graine=ligne["graine"],
        dictionnaires_ia=dictionnaires_ia,
    )

    for action in actions:
        type_action = action["type_action"]
        if type_action == ACTION_COUP:
            partie.jouer_coup(coup_depuis_json(action["coup"]))
        elif type_action == ACTION_PASSE:
            partie.passer()
        elif type_action == ACTION_ECHANGE:
            partie.echanger(json.loads(action["jetons_echanges"]))
        else:  # pragma: no cover - garde-fou contre une base corrompue
            raise ValueError(
                f"Type d'action inconnu dans la base : {type_action!r}."
            )
    return partie


def _reconstruire_joueurs(config: list[dict]) -> list[Joueur]:
    """Recrée les :class:`Joueur` (vides) depuis la configuration sérialisée.

    L'ordre est préservé : c'est l'ordre de jeu, indispensable pour que le rejeu
    distribue les tirages initiaux comme dans la partie d'origine.
    """
    joueurs: list[Joueur] = []
    for donnees in config:
        niveau = donnees.get("niveau")
        joueurs.append(
            Joueur(
                nom=donnees["nom"],
                humain=bool(donnees["humain"]),
                niveau=None if niveau is None else Niveau[niveau],
                # ``.get(..., "")`` : rétro-compatible avec une partie
                # sauvegardée avant l'issue #438 (lot A), dont le JSON ne
                # porte pas cette clé.
                personnage=donnees.get("personnage", ""),
                # ``.get(..., False)`` : rétro-compatible avec une partie
                # sauvegardée avant l'issue #440 (lot D), dont le JSON ne
                # porte pas cette clé — pas de révélation en fin de partie
                # pour un personnage qui n'a jamais pu être tiré au hasard.
                personnage_aleatoire=bool(donnees.get("personnage_aleatoire", False)),
            )
        )
    return joueurs


# --------------------------------------------------------------------------- #
# Lecture seule pour le script de relecture (issue #445)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ActionJournalisee:
    """Une ligne de la table ``actions``, telle que stockée (issue #445).

    Destinée au script de relecture (``scripts/relire_journal_ia.py``) : pas
    de rejeu de partie, lecture directe des colonnes. ``journal_ia`` vaut
    ``None`` pour une action humaine, ou pour une partie enregistrée avant
    cette fonctionnalité (voir :func:`_journal_ia_depuis_json`).
    """

    indice: int
    index_joueur: int
    nom_joueur: str
    action: str
    coup: Coup | None
    detail: DetailScore | None
    jetons_echanges: list[str]
    journal_ia: JournalDecisionIA | None


@dataclass(frozen=True)
class ConfigurationPartie:
    """En-tête d'une partie stockée : graine et configuration des joueurs.

    ``joueurs`` reprend le format de :func:`_joueurs_depuis_json` (``nom``,
    ``humain``, ``niveau``, ``personnage``, ``personnage_aleatoire``).
    """

    graine: int
    joueurs: list[dict]


def _connexion_lecture_seule(chemin: _TypeChemin) -> sqlite3.Connection:
    """Ouvre ``chemin`` en lecture seule, sans jamais créer ni migrer le schéma.

    Contrairement à :func:`_connexion` (utilisée par le jeu lui-même), cette
    fonction ne doit **jamais** écrire sur disque : le script de relecture
    (issue #445) n'a besoin d'aucune garantie d'écriture, et ouvrir en lecture
    seule permet de consulter une base pendant qu'une partie y est encore
    suivie par le jeu, sans risque de corruption ni de verrou concurrent.

    :raises FileNotFoundError: si ``chemin`` n'existe pas.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"Base introuvable : {chemin}")
    connexion = sqlite3.connect(f"file:{chemin.resolve().as_posix()}?mode=ro", uri=True)
    connexion.row_factory = sqlite3.Row
    return connexion


def lire_configuration_partie(
    id_partie: int, chemin: _TypeChemin = CHEMIN_DEFAUT
) -> ConfigurationPartie:
    """Lit, en lecture seule, la graine et la configuration des joueurs d'une partie.

    :raises KeyError: si aucune partie ne porte cet identifiant.
    """
    connexion = _connexion_lecture_seule(chemin)
    try:
        ligne = connexion.execute(
            "SELECT graine, joueurs FROM parties WHERE id = ?", (id_partie,)
        ).fetchone()
    finally:
        connexion.close()
    if ligne is None:
        raise KeyError(f"Aucune partie d'identifiant {id_partie}.")
    return ConfigurationPartie(
        graine=ligne["graine"],
        joueurs=_joueurs_depuis_json(ligne["joueurs"]),
    )


def lire_actions_journalisees(
    id_partie: int, chemin: _TypeChemin = CHEMIN_DEFAUT
) -> list[ActionJournalisee]:
    """Lit, en lecture seule, toutes les actions d'une partie, journal inclus.

    Aucun rejeu : chaque colonne stockée est simplement décodée, dans l'ordre
    chronologique (``indice`` croissant). Destinée au script de relecture
    (``scripts/relire_journal_ia.py``, issue #445).

    Fonctionne aussi sur une base **jamais rouverte en écriture** depuis
    l'ajout de la colonne ``journal_ia`` (issue #445) : contrairement à
    :func:`_connexion` (toujours utilisée par le jeu, qui migre le schéma à
    chaque ouverture), cette fonction ouvre en lecture seule et ne migre
    jamais rien — elle vérifie donc elle-même si la colonne existe et s'en
    passe sinon (``journal_ia`` vaudra ``None`` pour toutes les actions,
    comme pour une vieille partie jamais journalisée).

    :raises KeyError: si aucune partie ne porte cet identifiant.
    """
    connexion = _connexion_lecture_seule(chemin)
    try:
        if connexion.execute(
            "SELECT 1 FROM parties WHERE id = ?", (id_partie,)
        ).fetchone() is None:
            raise KeyError(f"Aucune partie d'identifiant {id_partie}.")
        colonnes = [
            row[1] for row in connexion.execute("PRAGMA table_info(actions)").fetchall()
        ]
        colonne_journal = "journal_ia" if "journal_ia" in colonnes else "NULL AS journal_ia"
        lignes = connexion.execute(
            "SELECT indice, index_joueur, nom_joueur, type_action, coup, "
            f"jetons_echanges, detail, {colonne_journal} FROM actions "
            "WHERE id_partie = ? ORDER BY indice ASC",
            (id_partie,),
        ).fetchall()
    finally:
        connexion.close()
    return [
        ActionJournalisee(
            indice=ligne["indice"],
            index_joueur=ligne["index_joueur"],
            nom_joueur=ligne["nom_joueur"],
            action=ligne["type_action"],
            coup=coup_depuis_json(ligne["coup"]) if ligne["coup"] else None,
            detail=_detail_depuis_json(ligne["detail"]) if ligne["detail"] else None,
            jetons_echanges=(
                json.loads(ligne["jetons_echanges"]) if ligne["jetons_echanges"] else []
            ),
            journal_ia=_journal_ia_depuis_json(ligne["journal_ia"]),
        )
        for ligne in lignes
    ]
