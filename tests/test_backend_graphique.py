"""Tests de la sélection du backend graphique (issue #93).

Vérifie la bascule ``GDK_BACKEND=x11`` (XWayland) décidée par
:func:`scrabble.ui.backend_graphique.configurer_backend_graphique` selon
l'environnement, sans jamais dépendre de l'``os.environ`` réel ni du système
graphique de la machine de test (on injecte un ``environ`` factice et on
neutralise ``platform.system``).
"""

from __future__ import annotations

import scrabble.ui.backend_graphique as bg
from scrabble.ui.backend_graphique import configurer_backend_graphique


def _forcer_linux(monkeypatch) -> None:
    monkeypatch.setattr(bg.platform, "system", lambda: "Linux")


def test_bascule_x11_sous_wayland_avec_xwayland(monkeypatch):
    """Session Wayland + DISPLAY présent -> GDK_BACKEND=x11 posé."""
    _forcer_linux(monkeypatch)
    env: dict[str, str] = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}
    assert configurer_backend_graphique(env) == "x11"
    assert env["GDK_BACKEND"] == "x11"


def test_bascule_sur_wayland_display_seul(monkeypatch):
    """WAYLAND_DISPLAY (sans XDG_SESSION_TYPE) suffit à détecter Wayland."""
    _forcer_linux(monkeypatch)
    env = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
    assert configurer_backend_graphique(env) == "x11"
    assert env["GDK_BACKEND"] == "x11"


def test_pas_de_bascule_sans_display(monkeypatch):
    """Wayland mais XWayland indisponible (DISPLAY absent) : on ne touche à rien."""
    _forcer_linux(monkeypatch)
    env = {"XDG_SESSION_TYPE": "wayland"}
    assert configurer_backend_graphique(env) is None
    assert "GDK_BACKEND" not in env


def test_pas_de_bascule_hors_wayland(monkeypatch):
    """Session X11 native : positionnement déjà fonctionnel, aucune bascule."""
    _forcer_linux(monkeypatch)
    env = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
    assert configurer_backend_graphique(env) is None
    assert "GDK_BACKEND" not in env


def test_respecte_backend_explicite(monkeypatch):
    """Un GDK_BACKEND déjà fixé n'est jamais écrasé (choix explicite)."""
    _forcer_linux(monkeypatch)
    env = {
        "XDG_SESSION_TYPE": "wayland",
        "DISPLAY": ":0",
        "GDK_BACKEND": "wayland",
    }
    assert configurer_backend_graphique(env) is None
    assert env["GDK_BACKEND"] == "wayland"


def test_sans_effet_hors_linux(monkeypatch):
    """Hors Linux (macOS/Windows) : la fonction est inerte."""
    monkeypatch.setattr(bg.platform, "system", lambda: "Darwin")
    env = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}
    assert configurer_backend_graphique(env) is None
    assert "GDK_BACKEND" not in env


def test_idempotente(monkeypatch):
    """Deux appels successifs : le second respecte le backend posé au premier."""
    _forcer_linux(monkeypatch)
    env = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}
    assert configurer_backend_graphique(env) == "x11"
    # Deuxième appel : GDK_BACKEND=x11 est désormais « explicite » -> pas de doublon.
    assert configurer_backend_graphique(env) is None
    assert env["GDK_BACKEND"] == "x11"
