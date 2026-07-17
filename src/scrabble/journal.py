"""Journal de diagnostic à rétention conditionnelle.

Objectif
--------
Aider à comprendre les bugs rencontrés par l'utilisatrice principale (non
technique) *sans qu'elle ait à décrire ce qui s'est passé*. Le délai entre un
bug et sa remontée peut être long (plusieurs jours) : on écrit donc chaque
entrée **immédiatement sur disque** (flush + ``fsync``, aucun tampon qui
retarderait l'écriture en cas de plantage), et on évite d'accumuler des
fichiers inutiles.

Principe de rétention
---------------------
Une **session** = un lancement du programme jusqu'à sa fermeture. Chaque
session écrit son propre fichier ``session-<horodatage>.log`` dans ``logs/``.

* À la **fermeture propre** (:meth:`Journal.cloturer`) : si aucune entrée de
  niveau *erreur* n'a été écrite, le fichier est **supprimé** ; sinon il est
  **conservé** et un résumé « Bugs connus, du plus fréquent au moins
  fréquent » lui est préfixé (lu depuis :data:`index_erreurs.json`).
* En cas de **plantage brutal** (``cloturer`` jamais appelé) : le fichier reste
  simplement sur disque — c'est justement le cas le plus utile à conserver.
  Aucun nettoyage a posteriori des fichiers orphelins n'est fait ici.

Index de fréquence
------------------
À chaque erreur journalisée, on calcule une **signature** stable (type
d'exception + fichier:fonction d'origine, sans les détails variables comme un
nom de joueur) et on incrémente un compteur dans ``logs/index_erreurs.json``,
avec la date de dernière occurrence. Ce compteur survit aux sessions : il rend
les bugs récurrents immédiatement visibles en tête des fichiers conservés.

API
---
Deux niveaux d'usage :

* la classe :class:`Journal` (une instance = une session), pratique à tester en
  pointant vers un dossier temporaire ;
* des fonctions module (:func:`demarrer_session`, :func:`info`, :func:`erreur`,
  :func:`cloturer_session`) qui pilotent une **session courante** unique, pour
  un usage simple depuis le reste du programme.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
import traceback
from pathlib import Path
from types import TracebackType
from typing import Any

from scrabble.config import RACINE_PROJET

#: Dossier des journaux, à côté de ``data/`` et gitignoré comme lui.
DOSSIER_LOGS = RACINE_PROJET / "logs"

#: Nom de l'index de fréquence des erreurs (dans le dossier des journaux).
NOM_INDEX = "index_erreurs.json"

#: Niveaux d'entrée reconnus. Seul ``ERREUR`` déclenche la conservation.
NIVEAU_INFO = "INFO"
NIVEAU_ERREUR = "ERREUR"

_TypeChemin = os.PathLike[str] | str


def _maintenant() -> datetime.datetime:
    """Horodatage local courant (heure lisible pour la relecture humaine)."""
    return datetime.datetime.now()


def _horodatage_iso() -> str:
    """Horodatage ISO 8601 à la seconde, pour les lignes et l'index."""
    return _maintenant().replace(microsecond=0).isoformat(sep=" ")


class Journal:
    """Journal d'une session : un fichier, écriture immédiate, rétention.

    L'instanciation crée le dossier des journaux au besoin et ouvre en écriture
    le fichier de la session (nommé d'après l'horodatage de lancement). Les
    entrées sont écrites au fil de l'eau ; c'est :meth:`cloturer` qui décide de
    supprimer ou de conserver le fichier.
    """

    def __init__(
        self,
        dossier: _TypeChemin = DOSSIER_LOGS,
        *,
        chemin_index: _TypeChemin | None = None,
    ) -> None:
        self.dossier = Path(dossier)
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.chemin_index = (
            Path(chemin_index) if chemin_index is not None else self.dossier / NOM_INDEX
        )

        lancement = _maintenant()
        # Microsecondes + PID : deux sessions lancées dans la même seconde (cas
        # des tests, notamment) n'écrasent jamais le fichier l'une de l'autre.
        nom = f"session-{lancement:%Y%m%d-%H%M%S-%f}-{os.getpid()}.log"
        self.chemin = self.dossier / nom
        self._fichier = open(self.chemin, "a", encoding="utf-8")
        self._nb_erreurs = 0
        self._clos = False

        self.info(f"Session ouverte : {lancement.replace(microsecond=0).isoformat(sep=' ')}")

    # -- Écriture d'entrées ------------------------------------------------

    def info(self, message: str) -> None:
        """Journalise une action normale (niveau info)."""
        self._ecrire(NIVEAU_INFO, message)

    def erreur(self, message: str, exc: BaseException | None = None) -> None:
        """Journalise un problème (niveau erreur) et met à jour l'index.

        Si ``exc`` est fourni, sa trace complète est jointe à l'entrée et la
        signature est calculée sur le dernier cadre de sa pile d'appels. Sinon
        la signature est calculée sur l'emplacement d'appel de cette méthode.
        """
        detail = message
        if exc is not None:
            trace = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ).rstrip()
            detail = f"{message}\n{trace}"
        self._ecrire(NIVEAU_ERREUR, detail)
        self._nb_erreurs += 1
        self._incrementer_index(_signature(exc))

    def _ecrire(self, niveau: str, message: str) -> None:
        """Écrit une ligne horodatée et la force **immédiatement** sur disque."""
        if self._clos:
            raise RuntimeError("Journal déjà clôturé : plus aucune écriture possible.")
        ligne = f"{_horodatage_iso()} [{niveau}] {message}\n"
        self._fichier.write(ligne)
        self._fichier.flush()
        os.fsync(self._fichier.fileno())

    # -- Index de fréquence des erreurs ------------------------------------

    def _incrementer_index(self, signature: str) -> None:
        """Incrémente le compteur de ``signature`` dans l'index (persistant)."""
        index = _lire_index(self.chemin_index)
        entree = index.get(signature)
        if not isinstance(entree, dict):
            entree = {"occurrences": 0, "derniere_occurrence": ""}
        entree["occurrences"] = int(entree.get("occurrences", 0)) + 1
        entree["derniere_occurrence"] = _horodatage_iso()
        index[signature] = entree
        _ecrire_index_atomique(self.chemin_index, index)

    # -- Clôture -----------------------------------------------------------

    @property
    def nb_erreurs(self) -> int:
        """Nombre d'entrées d'erreur journalisées durant la session."""
        return self._nb_erreurs

    def cloturer(self) -> None:
        """Ferme proprement la session : supprime ou conserve le fichier.

        Idempotente : un second appel n'a aucun effet. Sans aucune erreur
        journalisée, le fichier est supprimé. Avec au moins une erreur, il est
        conservé et un résumé de fréquence lui est préfixé.
        """
        if self._clos:
            return
        self.info("Session fermée proprement.")
        self._clos = True
        self._fichier.close()

        if self._nb_erreurs == 0:
            # Session sans problème : rien à conserver.
            try:
                self.chemin.unlink()
            except FileNotFoundError:
                pass
            return

        self._prefixer_resume()

    def _prefixer_resume(self) -> None:
        """Réécrit le fichier conservé avec le résumé de fréquence en tête."""
        corps = self.chemin.read_text(encoding="utf-8")
        resume = _construire_resume(_lire_index(self.chemin_index))
        self.chemin.write_text(resume + corps, encoding="utf-8")

    # -- Confort : usage en gestionnaire de contexte -----------------------

    def __enter__(self) -> "Journal":
        return self

    def __exit__(
        self,
        type_exc: type[BaseException] | None,
        valeur_exc: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        # Une exception qui traverse le bloc est journalisée avant clôture.
        if valeur_exc is not None:
            self.erreur("Exception non rattrapée en fin de session.", valeur_exc)
        self.cloturer()


def _signature(exc: BaseException | None) -> str:
    """Signature stable d'une erreur : ``Type @ fichier:fonction``.

    On ne garde que le nom de base du fichier et la fonction d'origine — aucun
    détail variable (nom de joueur, valeur en jeu) — pour que des occurrences
    du même bug se cumulent sous la même signature.
    """
    if exc is not None and exc.__traceback__ is not None:
        # Dernier cadre de la pile : là où l'exception a réellement surgi.
        dernier = traceback.extract_tb(exc.__traceback__)[-1]
        origine = f"{os.path.basename(dernier.filename)}:{dernier.name}"
        return f"{type(exc).__name__} @ {origine}"

    type_nom = type(exc).__name__ if exc is not None else "Erreur"
    # Sans trace exploitable, on remonte à l'appelant de Journal.erreur.
    for cadre in traceback.extract_stack()[::-1]:
        base = os.path.basename(cadre.filename)
        if base != "journal.py":
            return f"{type_nom} @ {base}:{cadre.name}"
    return f"{type_nom} @ inconnu"


def _lire_index(chemin: _TypeChemin) -> dict[str, Any]:
    """Lit l'index de fréquence, ou renvoie un dict vide si absent/corrompu."""
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            contenu = json.load(fichier)
    except (FileNotFoundError, IsADirectoryError, json.JSONDecodeError, OSError, ValueError):
        return {}
    return contenu if isinstance(contenu, dict) else {}


def _ecrire_index_atomique(chemin: _TypeChemin, index: dict[str, Any]) -> None:
    """Écrit l'index de façon atomique (jamais de fichier à moitié écrit)."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur, chemin_tmp = tempfile.mkstemp(
        dir=str(chemin.parent), prefix=".index-", suffix=".tmp"
    )
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
            json.dump(index, fichier, ensure_ascii=False, indent=2, sort_keys=True)
            fichier.write("\n")
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(chemin_tmp, chemin)
    except BaseException:
        try:
            os.unlink(chemin_tmp)
        except OSError:
            pass
        raise


def _construire_resume(index: dict[str, Any]) -> str:
    """Construit l'en-tête « Bugs connus », trié par fréquence décroissante."""
    lignes = ["===== Bugs connus, du plus fréquent au moins fréquent ====="]

    def cle_tri(item: tuple[str, Any]) -> tuple[int, str]:
        signature, data = item
        occ = int(data.get("occurrences", 0)) if isinstance(data, dict) else 0
        # Fréquence décroissante ; à égalité, ordre alphabétique stable.
        return (-occ, signature)

    entrees = sorted(index.items(), key=cle_tri)
    if not entrees:
        lignes.append("  (aucune erreur enregistrée dans l'index)")
    for signature, data in entrees:
        data = data if isinstance(data, dict) else {}
        occ = int(data.get("occurrences", 0))
        derniere = data.get("derniere_occurrence", "?") or "?"
        lignes.append(f"  {occ}× — {signature} — dernière : {derniere}")

    lignes.append("=" * 58)
    lignes.append("")
    lignes.append("")
    return "\n".join(lignes)


# --------------------------------------------------------------------------
# Session courante : API module simple pour le reste du programme.
# --------------------------------------------------------------------------

_session_courante: Journal | None = None


def demarrer_session(
    dossier: _TypeChemin = DOSSIER_LOGS,
    *,
    chemin_index: _TypeChemin | None = None,
) -> Journal:
    """Ouvre une nouvelle session courante (remplace l'éventuelle précédente)."""
    global _session_courante
    _session_courante = Journal(dossier, chemin_index=chemin_index)
    return _session_courante


def session_courante() -> Journal | None:
    """Renvoie la session courante, ou ``None`` si aucune n'est ouverte."""
    return _session_courante


def info(message: str) -> None:
    """Journalise une entrée info sur la session courante (sinon sans effet)."""
    if _session_courante is not None:
        _session_courante.info(message)


def erreur(message: str, exc: BaseException | None = None) -> None:
    """Journalise une erreur sur la session courante (sinon sans effet)."""
    if _session_courante is not None:
        _session_courante.erreur(message, exc)


def cloturer_session() -> None:
    """Clôture proprement la session courante, s'il y en a une."""
    global _session_courante
    if _session_courante is not None:
        _session_courante.cloturer()
        _session_courante = None
