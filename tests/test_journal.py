"""Tests du journal de diagnostic à rétention conditionnelle.

Couvre le contrat de ``scrabble.journal`` :

* écriture d'entrées info/erreur, présentes et horodatées dans le fichier ;
* écriture **immédiate** sur disque (lisible avant la clôture) ;
* clôture d'une session **sans erreur** : le fichier est supprimé ;
* clôture d'une session **avec erreur(s)** : le fichier est conservé et un
  résumé de fréquence « Bugs connus » lui est préfixé, exact et trié ;
* incrémentation de l'index sur plusieurs sessions successives : signatures
  identiques cumulées, signatures différentes comptées séparément ;
* API module (session courante) et robustesse (crash = fichier conservé).

Chaque test travaille dans un dossier temporaire (``tmp_path``) : le dossier
``logs/`` réel n'est jamais touché.
"""

from __future__ import annotations

import json

import pytest

from scrabble import journal
from scrabble.journal import Journal, NIVEAU_ERREUR, NIVEAU_INFO


def _lire(j: Journal) -> str:
    """Contenu courant du fichier de session (avant clôture)."""
    return j.chemin.read_text(encoding="utf-8")


def _lever(exc: Exception) -> None:
    """Lève ``exc`` pour lui donner une trace exploitable (origine stable)."""
    raise exc


# --------------------------------------------------------------------------
# Écriture d'entrées
# --------------------------------------------------------------------------


def test_ecriture_info_et_erreur(tmp_path):
    """info() et erreur() écrivent des lignes horodatées aux bons niveaux."""
    j = Journal(tmp_path)

    j.info("action normale")
    j.erreur("un souci")

    contenu = _lire(j)
    assert f"[{NIVEAU_INFO}] action normale" in contenu
    assert f"[{NIVEAU_ERREUR}] un souci" in contenu
    assert j.nb_erreurs == 1


def test_ecriture_immediate_sur_disque(tmp_path):
    """Chaque entrée est lisible sur disque sans attendre la clôture."""
    j = Journal(tmp_path)
    j.info("visible tout de suite")
    # Aucune clôture, aucun flush explicite du test : le module doit avoir déjà
    # forcé l'écriture (flush + fsync).
    assert "visible tout de suite" in j.chemin.read_text(encoding="utf-8")


def test_erreur_avec_exception_joint_la_trace(tmp_path):
    """Passer une exception joint sa trace complète à l'entrée."""
    j = Journal(tmp_path)
    try:
        _lever(ValueError("boom"))
    except ValueError as exc:
        j.erreur("échec du calcul", exc)

    contenu = _lire(j)
    assert "échec du calcul" in contenu
    assert "ValueError: boom" in contenu
    assert "Traceback" in contenu


# --------------------------------------------------------------------------
# Rétention conditionnelle à la clôture
# --------------------------------------------------------------------------


def test_cloture_sans_erreur_supprime_le_fichier(tmp_path):
    """Session sans erreur : le fichier est supprimé à la clôture propre."""
    j = Journal(tmp_path)
    j.info("rien d'anormal")
    chemin = j.chemin
    assert chemin.exists()

    j.cloturer()

    assert not chemin.exists()


def test_cloture_avec_erreur_conserve_le_fichier(tmp_path):
    """Session avec erreur : le fichier est conservé à la clôture."""
    j = Journal(tmp_path)
    j.info("début")
    j.erreur("plantage")
    chemin = j.chemin

    j.cloturer()

    assert chemin.exists()
    contenu = chemin.read_text(encoding="utf-8")
    assert "plantage" in contenu


def test_cloture_idempotente(tmp_path):
    """Un second appel à cloturer() n'a aucun effet (pas d'erreur)."""
    j = Journal(tmp_path)
    j.info("ok")
    j.cloturer()
    j.cloturer()  # ne doit rien casser
    assert not j.chemin.exists()


def test_ecriture_apres_cloture_interdite(tmp_path):
    """Écrire après clôture est une erreur de programmation signalée."""
    j = Journal(tmp_path)
    j.erreur("boom")
    j.cloturer()
    with pytest.raises(RuntimeError):
        j.info("trop tard")


# --------------------------------------------------------------------------
# Résumé de fréquence en tête du fichier conservé
# --------------------------------------------------------------------------


def test_resume_frequence_en_tete(tmp_path):
    """Le fichier conservé commence par le résumé « Bugs connus » trié."""
    j = Journal(tmp_path)
    # Deux fois la même signature, une fois une autre.
    for _ in range(2):
        try:
            _lever(ValueError("x"))
        except ValueError as exc:
            j.erreur("erreur A", exc)
    try:
        _lever(KeyError("y"))
    except KeyError as exc:
        j.erreur("erreur B", exc)
    j.cloturer()

    contenu = j.chemin.read_text(encoding="utf-8")
    entete = contenu.split("\n", 1)[0]
    assert "Bugs connus, du plus fréquent au moins fréquent" in entete

    # La signature la plus fréquente (ValueError, 2×) apparaît avant l'autre.
    pos_value = contenu.index("ValueError")
    pos_key = contenu.index("KeyError")
    assert pos_value < pos_key
    assert "2× — ValueError" in contenu
    assert "1× — KeyError" in contenu
    # Le résumé précède bien le corps du journal (les entrées elles-mêmes).
    assert pos_value < contenu.index("[ERREUR]")


def test_resume_reflete_index_cumule_entre_sessions(tmp_path):
    """Le résumé s'appuie sur l'index cumulé, pas sur la seule session."""
    # Session 1 : une ValueError.
    j1 = Journal(tmp_path)
    try:
        _lever(ValueError("s1"))
    except ValueError as exc:
        j1.erreur("A", exc)
    j1.cloturer()

    # Session 2 : une seule KeyError, mais le résumé doit rappeler la
    # ValueError connue de la session précédente (index cumulé).
    j2 = Journal(tmp_path)
    try:
        _lever(KeyError("s2"))
    except KeyError as exc:
        j2.erreur("B", exc)
    j2.cloturer()

    contenu = j2.chemin.read_text(encoding="utf-8")
    assert "ValueError" in contenu
    assert "KeyError" in contenu


# --------------------------------------------------------------------------
# Index de fréquence sur plusieurs sessions
# --------------------------------------------------------------------------


def _index(tmp_path) -> dict:
    return json.loads((tmp_path / journal.NOM_INDEX).read_text(encoding="utf-8"))


def test_index_cumule_signatures_identiques(tmp_path):
    """Une même signature d'erreur se cumule au fil des sessions."""
    for _ in range(3):
        j = Journal(tmp_path)
        try:
            _lever(ValueError("meme origine"))
        except ValueError as exc:
            j.erreur("répété", exc)
        j.cloturer()

    index = _index(tmp_path)
    # Une seule signature, comptée 3 fois.
    assert len(index) == 1
    (unique,) = index.values()
    assert unique["occurrences"] == 3
    assert unique["derniere_occurrence"]  # date renseignée


def test_index_separe_signatures_differentes(tmp_path):
    """Des origines/types différents produisent des signatures distinctes."""
    j = Journal(tmp_path)
    try:
        _lever(ValueError("a"))
    except ValueError as exc:
        j.erreur("A", exc)
    try:
        _lever(KeyError("b"))
    except KeyError as exc:
        j.erreur("B", exc)
    j.cloturer()

    index = _index(tmp_path)
    assert len(index) == 2
    assert all(entree["occurrences"] == 1 for entree in index.values())
    # Les deux types d'exception apparaissent dans les signatures (clés).
    signatures = " ".join(index.keys())
    assert "ValueError" in signatures
    assert "KeyError" in signatures


def test_erreur_sans_exception_a_une_signature(tmp_path):
    """erreur() sans exception reste comptabilisée (signature d'appelant)."""
    j = Journal(tmp_path)
    j.erreur("problème sans exception")
    j.cloturer()

    index = _index(tmp_path)
    assert len(index) == 1
    (entree,) = index.values()
    assert entree["occurrences"] == 1


# --------------------------------------------------------------------------
# API module (session courante) et robustesse au crash
# --------------------------------------------------------------------------


def test_api_module_session_courante(tmp_path):
    """demarrer_session/info/erreur/cloturer_session pilotent une session."""
    j = journal.demarrer_session(tmp_path)
    assert journal.session_courante() is j
    journal.info("via module")
    journal.erreur("souci via module")
    chemin = j.chemin
    journal.cloturer_session()

    assert journal.session_courante() is None
    assert chemin.exists()  # conservé car une erreur a été journalisée
    assert "via module" in chemin.read_text(encoding="utf-8")


def test_api_module_sans_session_ne_plante_pas(tmp_path):
    """info()/erreur() sans session courante sont sans effet (pas d'erreur)."""
    journal.cloturer_session()  # s'assure qu'aucune session ne traîne
    journal.info("ignoré")
    journal.erreur("ignoré")
    # Aucun fichier ni index créé dans le dossier temporaire.
    assert not any(tmp_path.iterdir())


def test_crash_conserve_le_fichier(tmp_path):
    """Sans clôture (crash), le fichier reste sur disque, intact."""
    j = Journal(tmp_path)
    j.info("juste avant le crash")
    # On ne clôture pas : simulation d'un plantage brutal.
    contenu = j.chemin.read_text(encoding="utf-8")
    assert "juste avant le crash" in contenu
    assert j.chemin.exists()


def test_contextmanager_journalise_exception_et_conserve(tmp_path):
    """En gestionnaire de contexte, une exception est journalisée et conservée."""
    with pytest.raises(RuntimeError):
        with Journal(tmp_path) as j:
            chemin = j.chemin
            raise RuntimeError("échec dans le bloc")

    assert chemin.exists()
    contenu = chemin.read_text(encoding="utf-8")
    assert "RuntimeError" in contenu
