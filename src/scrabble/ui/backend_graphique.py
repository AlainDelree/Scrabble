"""Sélection du backend graphique GTK avant l'initialisation de pywebview.

Cause racine de l'issue #93 (suite des issues #91/#92)
------------------------------------------------------
Le repositionnement, le drag applicatif et le maintien « au-dessus » (``on_top``)
de la fenêtre **chevalet** échouaient tous par la même cause, enfin prouvée par
les traces de journalisation : la machine tourne sous **GNOME/Wayland**, et le
backend GTK de pywebview s'y exécute comme **client Wayland natif**.

Or le protocole Wayland interdit **par conception** à une application de
connaître ou de fixer la position absolue de ses propres fenêtres. Concrètement,
sous ``GdkWaylandDisplay`` :

* ``Gtk.Window.move(x, y)`` (donc ``pywebview.Window.move``) est **silencieusement
  ignoré** : la fenêtre reste là où le compositeur l'a placée ;
* ``Gtk.Window.get_position()`` (donc ``window.x`` / ``window.y``) renvoie une
  valeur factice, typiquement **(0, 0)** — d'où la position lue toujours nulle
  après ``move`` (issue #92) et le calcul de drag relatif faussé (point de départ
  toujours (0, 0)) ;
* ``set_keep_above`` (l'indicateur ``on_top``) n'est pas honoré par Mutter pour
  un client Wayland (« always on top » applicatif volontairement ignoré).

Ce n'est **pas** une limitation propre aux fenêtres ``frameless`` : elle touche
toutes les fenêtres sous Wayland. ``frameless`` était une fausse piste.

Contournement racine retenu — sans dépendance externe
-----------------------------------------------------
Forcer ``GDK_BACKEND=x11`` **avant** que GTK n'ouvre son display fait tourner
toute l'application via **XWayland** (le serveur X de compatibilité, présent dès
qu'un ``DISPLAY`` est exporté — cas par défaut sur GNOME/Wayland). Sous XWayland,
le client est un client X11 classique : ``move()``, ``get_position()`` et
``set_keep_above`` fonctionnent de nouveau. Vérifié en isolation :

    GDK_BACKEND=x11  ->  Gtk.Window.move(520, 640)  ->  get_position() == (520, 640)

alors que sous Wayland natif le même appel donnait ``(26, 23)``.

``wmctrl`` / ``xdotool`` ne sont **pas** une alternative viable : ce sont des
outils X11 qui ne « voient » pas les surfaces Wayland natives. Une fois le
backend basculé sur XWayland, ils redeviendraient utilisables, mais le
basculement seul suffit et évite toute dépendance.

Prudence
--------
* On n'agit que sous Linux et uniquement si la session est Wayland.
* Un ``GDK_BACKEND`` déjà fixé explicitement (choix de l'utilisateur/CI) est
  respecté et jamais écrasé.
* Sans ``DISPLAY`` (XWayland indisponible), on ne bascule pas : mieux vaut une
  position non honorée qu'une fenêtre qui ne s'ouvre pas du tout.

La bascule doit intervenir **avant le premier ``webview.start()``** du processus
(c'est à ce moment que GTK ouvre son display) : elle est donc appelée en tête des
points de lancement (:func:`scrabble.ui.accueil.lancer_accueil` et
:func:`scrabble.ui.jeu.lancer_jeu`).
"""

from __future__ import annotations

import os
import platform

from scrabble import journal


def configurer_backend_graphique(environ: dict | None = None) -> str | None:
    """Bascule GTK sur X11 (XWayland) sous une session Wayland, si pertinent.

    Modifie ``environ`` (par défaut ``os.environ``) en y posant
    ``GDK_BACKEND=x11`` lorsque toutes les conditions sont réunies. Journalise la
    décision prise. Renvoie la valeur effectivement affectée à ``GDK_BACKEND``
    (``"x11"``) si la bascule a eu lieu, sinon ``None`` — utile pour les tests.

    Idempotente et sans effet de bord hors du cas Linux/Wayland/XWayland ; sûre à
    appeler plusieurs fois (chaque point de lancement l'invoque par sécurité).
    """
    env = os.environ if environ is None else environ

    if platform.system() != "Linux":
        return None

    backend_existant = env.get("GDK_BACKEND")
    if backend_existant:
        journal.info(
            "Backend graphique : GDK_BACKEND déjà fixé "
            f"({backend_existant!r}) — choix explicite respecté, aucune bascule."
        )
        return None

    session_wayland = (
        env.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        or bool(env.get("WAYLAND_DISPLAY"))
    )
    if not session_wayland:
        return None

    if not env.get("DISPLAY"):
        journal.info(
            "Backend graphique : session Wayland mais XWayland indisponible "
            "(DISPLAY absent) — backend GTK inchangé ; move()/on_top resteront "
            "non fiables (limitation Wayland, issue #93)."
        )
        return None

    env["GDK_BACKEND"] = "x11"
    journal.info(
        "Backend graphique : session Wayland détectée — GDK_BACKEND=x11 forcé "
        "(bascule sur XWayland) pour rétablir move()/window.x/window.y et on_top "
        "de la fenêtre chevalet (cause racine issue #93)."
    )
    return "x11"
