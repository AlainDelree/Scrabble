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


# ---------------------------------------------------------------------------
# Déploiement plein écran générique des fenêtres (issue #159)
# ---------------------------------------------------------------------------
# Toutes les fenêtres du jeu doivent s'ouvrir maximisées pour rester lisibles
# (plateau non minuscule, pas de scrollbars superflues). Or, comme l'a établi
# l'issue #95 pour le plateau, ``maximized=True`` à la création est un **no-op**
# sous XWayland/mutter (le ``Gtk.Window.maximize()`` émis avant/après mappage est
# silencieusement ignoré). Le contournement fiable — une fois la boucle GUI
# démarrée et la fenêtre affichée — est de forcer un ``resize`` + ``move`` sur la
# zone de travail réelle de l'écran. On expose ici ce mécanisme sous forme
# générique afin que l'accueil (« Nouvelle partie ») et les réglages (« fiche
# joueur ») bénéficient du même déploiement que le plateau, sans dupliquer la
# logique éprouvée. (La fenêtre plateau garde sa propre variante instrumentée
# dans ``jeu.py`` : elle est couverte par des tests dédiés à l'issue #95.)


def zone_travail_ecran() -> tuple[int, int, int, int] | None:
    """Zone de travail (x, y, largeur, hauteur) du moniteur principal — issue #159.

    Surface d'écran réellement **utilisable**, panneaux et barres système EXCLUS
    (EWMH ``_NET_WORKAREA``), lue via **GDK** — le même moteur que
    ``webview.screens``. Replis successifs si GDK est indisponible (tests, backend
    non-GTK) : géométrie plein écran de ``webview.screens[0]``, puis ``None``.

    Réplique volontaire de :func:`scrabble.ui.jeu._zone_travail_ecran` : voir la
    note d'en-tête (la variante du plateau reste sous tests #95).
    """
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or Gdk.Display.get_monitor(display, 0)
        wa = monitor.get_workarea()
        return int(wa.x), int(wa.y), int(wa.width), int(wa.height)
    except Exception as e:  # noqa: BLE001 - GDK indisponible : on tente un repli
        journal.info(
            f"Backend graphique : zone de travail GDK indisponible ({e!r}) — repli "
            "sur webview.screens."
        )
    try:
        import webview

        ecrans = webview.screens
        ecran = ecrans[0] if ecrans else None
        if ecran is not None:
            return int(ecran.x), int(ecran.y), int(ecran.width), int(ecran.height)
    except Exception as e:  # noqa: BLE001 - aucun écran interrogeable
        journal.info(
            f"Backend graphique : webview.screens illisible pour la zone de travail ({e!r})."
        )
    return None


def attendre_fenetre_affichee(
    window, nom: str = "fenêtre", timeout: float = 5.0
) -> None:
    """Attend l'événement ``shown`` de ``window`` (au plus ``timeout`` s) — issue #159.

    ``webview.Window.events.shown`` est signalé une fois la fenêtre affichée par le
    backend. On l'attend avant tout ``move``/``resize``/``maximize`` pour éviter une
    requête ignorée (fenêtre pas encore mappée sous WebKitGTK). Tolère l'absence
    d'attribut ``events`` (backends/fenêtres factices des tests) : dans ce cas on
    n'attend pas. Toute erreur est journalisée sans interrompre l'application.
    """
    evenements = getattr(window, "events", None)
    shown = getattr(evenements, "shown", None)
    attendre = getattr(shown, "wait", None)
    if attendre is None:
        journal.info(
            f"Backend graphique : événement 'shown' indisponible ({nom}) — "
            "poursuite immédiate."
        )
        return
    try:
        signale = attendre(timeout)
        journal.info(
            f"Backend graphique : attente de l'affichage de la fenêtre {nom} — "
            f"shown={signale!r}."
        )
    except Exception as e:  # noqa: BLE001 - une attente ratée ne bloque pas l'appli
        journal.erreur(
            f"Backend graphique : attente de l'affichage de la fenêtre {nom} impossible.",
            e,
        )


def deployer_fenetre_maximisee(window, nom: str = "fenêtre") -> None:
    """Déploie ``window`` sur toute la zone de travail utile — issue #159.

    À appeler **après** le démarrage de la boucle GUI (callback de
    ``webview.start`` en lancement autonome, ou fil dédié pour une fenêtre ouverte
    dans une boucle déjà démarrée) : c'est seulement une fois la fenêtre affichée
    que le déploiement est honoré sous XWayland. Enchaîne, chaque étape isolée et
    tolérante aux fenêtres factices des tests :

    1. attente de l'affichage (``shown``) ;
    2. dé-iconification (``restore``) au cas où la fenêtre s'ouvre réduite ;
    3. demande native ``maximize()`` — honorée par les WM coopératifs ;
    4. **force** ``resize`` + ``move`` sur la :func:`zone_travail_ecran`, honorés
       sous XWayland là où la maximisation seule est un no-op (cause racine #95).
    """
    attendre_fenetre_affichee(window, nom)

    restaurer = getattr(window, "restore", None)
    if callable(restaurer):
        try:
            restaurer()
        except Exception as e:  # noqa: BLE001 - une restauration ratée ne bloque pas l'appli
            journal.erreur(
                f"Backend graphique : dé-iconification de la fenêtre {nom} impossible.", e
            )
    maximiser = getattr(window, "maximize", None)
    if callable(maximiser):
        try:
            maximiser()
        except Exception as e:  # noqa: BLE001 - échec sans conséquence : le resize suit
            journal.erreur(
                f"Backend graphique : demande native de maximisation de {nom} impossible.",
                e,
            )

    zone = zone_travail_ecran()
    if zone is None:
        journal.info(
            f"Backend graphique : zone de travail inconnue — maximisation de {nom} "
            "limitée à la demande native (issue #159)."
        )
        return
    x, y, largeur, hauteur = zone
    redimensionner = getattr(window, "resize", None)
    deplacer = getattr(window, "move", None)
    try:
        if callable(redimensionner):
            redimensionner(largeur, hauteur)
        if callable(deplacer):
            deplacer(x, y)
        journal.info(
            f"Backend graphique : fenêtre {nom} déployée sur la zone de travail "
            f"{largeur}×{hauteur} en ({x}, {y}) — contournement XWayland (issue #159)."
        )
    except Exception as e:  # noqa: BLE001 - un déploiement raté ne bloque pas l'appli
        journal.erreur(
            f"Backend graphique : déploiement plein écran de la fenêtre {nom} impossible.",
            e,
        )
