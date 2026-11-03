"""Tests de la validation des chemins du flag Actualise (issue #484).

Couvre :

* un chemin légitime (fichier existant, extension autorisée, dans le dossier
  d'Actualise) est accepté ;
* un chemin hors du dossier d'Actualise (y compris via ``..``) est refusé ;
* un chemin dont l'extension n'est pas ``.bat``/``.exe`` est refusé ;
* un chemin inexistant est refusé.

Ces tests portent uniquement sur :func:`chemin_actualise_valide` — aucun
``subprocess.Popen`` n'est exercé.
"""

from __future__ import annotations

from pathlib import Path

from scrabble import actualise


def _dossier_actualise(tmp_path: Path, monkeypatch) -> Path:
    dossier = tmp_path / "Actualise"
    dossier.mkdir()
    monkeypatch.setattr(actualise, "DOSSIER_ACTUALISE", dossier)
    return dossier


def test_chemin_autorise_accepte(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    script = dossier / "maj.bat"
    script.write_text("rem maj", encoding="utf-8")

    assert actualise.chemin_actualise_valide(str(script)) == script


def test_chemin_hors_dossier_refuse(tmp_path, monkeypatch):
    _dossier_actualise(tmp_path, monkeypatch)
    ailleurs = tmp_path / "ailleurs.bat"
    ailleurs.write_text("rem", encoding="utf-8")

    assert actualise.chemin_actualise_valide(str(ailleurs)) is None


def test_chemin_hors_dossier_via_double_point_refuse(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    evasion = tmp_path / "evasion.bat"
    evasion.write_text("rem", encoding="utf-8")

    chemin = str(dossier / ".." / "evasion.bat")

    assert actualise.chemin_actualise_valide(chemin) is None


def test_extension_refusee(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    pas_un_script = dossier / "notes.txt"
    pas_un_script.write_text("rien à voir", encoding="utf-8")

    assert actualise.chemin_actualise_valide(str(pas_un_script)) is None


def test_chemin_inexistant_refuse(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    absent = dossier / "fantome.exe"

    assert actualise.chemin_actualise_valide(str(absent)) is None


def test_chemin_vide_ou_absent_refuse(tmp_path, monkeypatch):
    _dossier_actualise(tmp_path, monkeypatch)

    assert actualise.chemin_actualise_valide(None) is None
    assert actualise.chemin_actualise_valide("") is None


def test_dossier_valide_mais_pas_un_fichier_refuse(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    sous_dossier = dossier / "sous_dossier.bat"
    sous_dossier.mkdir()

    assert actualise.chemin_actualise_valide(str(sous_dossier)) is None


# --------------------------------------------------------------------------
# traiter_flag_actualise : aucun processus réel n'est lancé dans ces tests
# (subprocess.Popen est remplacé par un espion).
# --------------------------------------------------------------------------


class _EspionPopen:
    def __init__(self) -> None:
        self.appels: list[list[str]] = []

    def __call__(self, commande, *args, **kwargs):
        self.appels.append(commande)


def _preparer_executable(tmp_path: Path, monkeypatch) -> Path:
    executable = tmp_path / "Scrabble.exe"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(actualise.sys, "executable", str(executable))
    # Évite qu'un refus journalisé n'ouvre une vraie session (fichier sous
    # ``logs/``) : seul l'appel est vérifié, pas l'écriture sur disque
    # (déjà couverte par ``tests/test_journal.py``).
    monkeypatch.setattr(actualise.journal, "session_courante", lambda: object())
    monkeypatch.setattr(actualise.journal, "demarrer_session", lambda *a, **k: None)
    return executable


def test_traiter_flag_absent_ne_lance_rien(tmp_path, monkeypatch):
    _dossier_actualise(tmp_path, monkeypatch)
    _preparer_executable(tmp_path, monkeypatch)
    espion = _EspionPopen()
    monkeypatch.setattr(actualise.subprocess, "Popen", espion)

    actualise.traiter_flag_actualise("demarrage")

    assert espion.appels == []


def test_traiter_flag_chemin_invalide_ne_lance_rien(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    executable = _preparer_executable(tmp_path, monkeypatch)
    ui = dossier / "ui.exe"
    ui.write_text("", encoding="utf-8")
    hors_dossier = tmp_path / "evil.bat"
    hors_dossier.write_text("rem", encoding="utf-8")
    flag = executable.parent / "actualise_update.flag"
    flag.write_text(
        '{"bat": "' + str(hors_dossier).replace("\\", "\\\\")
        + '", "actualise_ui": "' + str(ui).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    espion = _EspionPopen()
    monkeypatch.setattr(actualise.subprocess, "Popen", espion)

    actualise.traiter_flag_actualise("demarrage")

    assert espion.appels == []


def test_traiter_flag_legitime_lance_le_processus_attendu(tmp_path, monkeypatch):
    dossier = _dossier_actualise(tmp_path, monkeypatch)
    executable = _preparer_executable(tmp_path, monkeypatch)
    bat = dossier / "maj.bat"
    bat.write_text("rem", encoding="utf-8")
    flag = executable.parent / "actualise_update.flag"
    flag.write_text(
        '{"bat": "' + str(bat).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    espion = _EspionPopen()
    monkeypatch.setattr(actualise.subprocess, "Popen", espion)

    actualise.traiter_flag_actualise("fermeture")

    assert espion.appels == [[str(bat)]]
    assert not flag.exists()
