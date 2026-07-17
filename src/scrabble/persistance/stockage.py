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

from scrabble.config import RACINE_PROJET
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import (
    ACTION_COUP,
    ACTION_ECHANGE,
    ACTION_PASSE,
    EntreeHistorique,
    Joueur,
    Partie,
)
from scrabble.moteur.plateau_partie import Coup, Direction, Tuile
from scrabble.moteur.score import DetailMot, DetailScore
from scrabble.moteur.validation import DictionnaireMots
from scrabble.regles.plateau import TypeCase

#: Emplacement par défaut de la base (dans ``data/``, gitignoré).
CHEMIN_DEFAUT = RACINE_PROJET / "data" / "parties.db"

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

    ``joueurs`` liste des dictionnaires ``{"nom", "humain", "niveau"}`` (niveau
    ``None`` pour un humain). ``scores_finaux`` et ``gagnants`` valent ``None``
    tant que la partie n'est pas terminée.
    """

    id: int
    statut: str
    graine: int
    date_creation: str
    date_maj: str
    joueurs: list[dict]
    scores_finaux: list[int] | None = None
    gagnants: list[str] | None = None

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


def _joueurs_vers_json(joueurs: list[Joueur]) -> str:
    return json.dumps(
        [
            {
                "nom": j.nom,
                "humain": j.humain,
                "niveau": None if j.niveau is None else j.niveau.name,
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
            FOREIGN KEY (id_partie) REFERENCES parties(id),
            UNIQUE (id_partie, indice)
        );

        CREATE INDEX IF NOT EXISTS idx_actions_partie
            ON actions (id_partie, indice);
        """
    )
    connexion.commit()


def _maintenant() -> str:
    """Horodatage ISO 8601 en UTC (colonnes de dates)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Fonctions principales
# --------------------------------------------------------------------------- #

def demarrer_suivi(partie: Partie, chemin: _TypeChemin = CHEMIN_DEFAUT) -> int:
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
            "(graine, date_creation, date_maj, joueurs, statut) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                partie.graine,
                horodatage,
                horodatage,
                _joueurs_vers_json(partie.joueurs),
                STATUT_EN_COURS,
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
    with _connexion(chemin) as connexion:
        (indice_suivant,) = connexion.execute(
            "SELECT COUNT(*) FROM actions WHERE id_partie = ?", (id_partie,)
        ).fetchone()
        connexion.execute(
            "INSERT INTO actions "
            "(id_partie, indice, index_joueur, nom_joueur, type_action, coup, "
            " jetons_echanges, detail, lettres_echangees, score_cumule) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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


def lister_parties(chemin: _TypeChemin = CHEMIN_DEFAUT) -> list[ResumePartie]:
    """Résumé de chaque partie, triées par date de mise à jour décroissante."""
    with _connexion(chemin) as connexion:
        lignes = connexion.execute(
            "SELECT id, statut, graine, date_creation, date_maj, joueurs, "
            "scores_finaux, gagnants FROM parties ORDER BY date_maj DESC, id DESC"
        ).fetchall()
    resumes: list[ResumePartie] = []
    for ligne in lignes:
        scores = ligne["scores_finaux"]
        gagnants = ligne["gagnants"]
        resumes.append(
            ResumePartie(
                id=ligne["id"],
                statut=ligne["statut"],
                graine=ligne["graine"],
                date_creation=ligne["date_creation"],
                date_maj=ligne["date_maj"],
                joueurs=_joueurs_depuis_json(ligne["joueurs"]),
                scores_finaux=None if scores is None else json.loads(scores),
                gagnants=None if gagnants is None else json.loads(gagnants),
            )
        )
    return resumes


def reprendre_partie(
    id_partie: int,
    dictionnaire: DictionnaireMots,
    chemin: _TypeChemin = CHEMIN_DEFAUT,
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
    partie = Partie(joueurs, dictionnaire, graine=ligne["graine"])

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
            )
        )
    return joueurs
