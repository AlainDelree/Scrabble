"""Vérification issues #270/#271 : rendu réel du mode Belgicisme sous
WebKitGTK (le moteur utilisé par pywebview sous Linux, cf. CONTEXTE.md — le
harnais Playwright habituel de _harness_jeu ne teste que Chromium et n'aurait
pas détecté l'écart de rendu constaté en #270).

#271 remplace le bandeau opaque 6px de #270 par un fond blanc + voile
tricolore translucide sur toute la surface, avec plaques de fond blanches
ciblées derrière le titre/sous-titre/légendes des drapeaux (texte noir).
Ce harnais (créé en #270) est réutilisé tel quel : il ne fait qu'une
capture générique de l'écran, sans assertion sur le rendu précis.

Charge accueil.html/css/js (avec la même API pywebview mockée que
verif_belgicisme_269.mjs) dans un vrai WebKit2.WebView, bascule France <->
Belgique plusieurs fois et capture un screenshot du rendu final via
webkit_web_view_get_snapshot (pas un screenshot X11 : un rendu direct de la
page, indépendant du gestionnaire de fenêtres).

Prérequis système (déjà présents sur cette machine) : gir1.2-webkit2-4.1,
python3-gi (paquets système — utiliser /usr/bin/python3, pas un venv qui ne
voit pas les dist-packages système), un DISPLAY X11 valide (le WebView a
besoin d'un GtkWindow réel ; pas de Xvfb installé ici, mais le DISPLAY
existant a suffi).

Usage : /usr/bin/python3 verif_belgicisme_270_webkitgtk.py [dossier_sortie]
"""
import pathlib
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk, WebKit2  # noqa: E402

ICI = pathlib.Path(__file__).resolve().parent
WEB = ICI.parent.parent / "src" / "scrabble" / "ui" / "web"
SORTIE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ICI

MOCK_JS = """
window.pywebview = { platform: 'test' };
window.__appelsMode = [];
setTimeout(() => {
  window.pywebview.api = {
    obtenir_etat: async () => ({
      joueurs: [{nom:'Alain', humain:true, niveau:null}],
      nb_humains: 1, nb_ordinateurs: 0, nb_total: 1,
      peut_ajouter_humain: true, peut_ajouter_ordinateur: true, peut_lancer: true,
      mode_belgicisme: false,
    }),
    obtenir_niveaux: async () => ['Débutant','Facile','Intermédiaire','Expert'],
    lister_parties_en_cours: async () => [],
    obtenir_prenom_principal: async () => 'Alain',
    definir_mode_belgicisme: async (actif) => {
      window.__appelsMode.push(actif);
      return { succes: true, mode_belgicisme: actif };
    },
  };
  window.dispatchEvent(new Event('pywebviewready'));
}, 100);
"""


def construire_mock():
    css = (WEB / "accueil.css").read_text()
    js = (WEB / "accueil.js").read_text()
    html = (WEB / "accueil.html").read_text()
    html = html.replace(
        '<link rel="stylesheet" href="accueil.css">', f"<style>{css}</style>"
    )
    html = html.replace(
        '<script src="accueil.js"></script>',
        f"<script>{MOCK_JS}</script><script>{js}</script>",
    )
    chemin = SORTIE / "_i270_mock_tmp.html"
    chemin.write_text(html)
    return chemin


def capturer(url, sortie_png, sequence_clics):
    win = Gtk.Window()
    win.set_default_size(900, 700)
    webview = WebKit2.WebView()
    win.add(webview)
    win.show_all()

    etape = {"i": 0}

    def apres_chargement(view, event):
        if event == WebKit2.LoadEvent.FINISHED and etape["i"] == 0:
            etape["i"] = 1
            GLib.timeout_add(400, lambda: jouer_sequence(0))

    def jouer_sequence(i):
        if i >= len(sequence_clics):
            # #271 : le fond passe désormais du vert au blanc+tricolore (au
            # lieu de deux verts proches en #270), un contraste bien plus
            # marqué pour la transition CSS `background-image 0.2s ease` du
            # body — 700ms de marge (au lieu de 300ms) pour être sûr que la
            # capture ne tombe jamais en plein milieu du fondu et ne soit
            # prise pour un résidu visuel.
            GLib.timeout_add(700, prendre_snapshot)
            return False
        webview.run_javascript(
            f"document.querySelector('{sequence_clics[i]}').click();",
            None, None, None,
        )
        GLib.timeout_add(250, lambda: jouer_sequence(i + 1))
        return False

    def prendre_snapshot():
        webview.get_snapshot(
            WebKit2.SnapshotRegion.FULL_DOCUMENT,
            WebKit2.SnapshotOptions.NONE,
            None, snapshot_pret, None,
        )
        return False

    def snapshot_pret(view, result, data):
        surface = webview.get_snapshot_finish(result)
        surface.write_to_png(str(sortie_png))
        win.destroy()
        Gtk.main_quit()

    webview.connect("load-changed", apres_chargement)
    webview.load_uri("file://" + url)
    GLib.timeout_add(15000, Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    mock = construire_mock()
    url = str(mock)

    print("Capture France (défaut)...")
    capturer(url, SORTIE / "i271_accueil_france_webkitgtk.png", [])

    print("Capture Belgique (après 5 bascules France/Belgique)...")
    capturer(
        url,
        SORTIE / "i271_accueil_belgique_webkitgtk.png",
        [
            "#drapeau-belgique", "#drapeau-france", "#drapeau-belgique",
            "#drapeau-france", "#drapeau-belgique",
        ],
    )

    print("Capture retour France (après la bascule Belgique, résidu ?)...")
    capturer(
        url,
        SORTIE / "i271_accueil_retour_france_webkitgtk.png",
        ["#drapeau-belgique", "#drapeau-france"],
    )

    mock.unlink()
    print("Captures écrites dans", SORTIE)
