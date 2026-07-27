"""Vérification issue #296 (suite #295) sous WebKitGTK : panneau blanc
France pleine hauteur, tuiles titre/sous-titre dans les deux modes,
disparition des étiquettes "France"/"Belgique" sous les cercles-drapeaux,
et nouveau titre de section "Parties en cours".

Repris de verif_belgicisme_292_webkitgtk.py (même mock d'API, même mécanique
de capture via webkit_web_view_get_snapshot). cf. bug #295 : toujours passer
un chemin de sortie ABSOLU en argument, sinon les captures atterrissent dans
le répertoire courant du process plutôt que dans SORTIE.

Usage : /usr/bin/python3 verif_296_webkitgtk.py <dossier_sortie_absolu>
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

MOCK_JS_VIDE = """
window.pywebview = { platform: 'test' };
window.__appelsMode = [];
setTimeout(() => {
  window.pywebview.api = {
    obtenir_etat: async () => ({
      joueurs: [],
      nb_humains: 0, nb_ordinateurs: 0, nb_total: 0,
      peut_ajouter_humain: true, peut_ajouter_ordinateur: true, peut_lancer: false,
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

MOCK_JS_REMPLI = """
window.pywebview = { platform: 'test' };
window.__appelsMode = [];
setTimeout(() => {
  window.pywebview.api = {
    obtenir_etat: async () => ({
      joueurs: [
        {nom:'Alain', humain:true, niveau:null},
        {nom:'Béatrice', humain:true, niveau:null},
        {nom:'Ordinateur 1', humain:false, niveau:'avance'},
        {nom:'Ordinateur 2', humain:false, niveau:'expert'},
      ],
      nb_humains: 2, nb_ordinateurs: 2, nb_total: 4,
      peut_ajouter_humain: false, peut_ajouter_ordinateur: false, peut_lancer: true,
      mode_belgicisme: false,
    }),
    obtenir_niveaux: async () => ['Débutant','Facile','Intermédiaire','Expert'],
    lister_parties_en_cours: async () => [
      {
        id: 1,
        date_maj: '2026-07-20T14:32:00',
        terminee: false,
        joueurs: [{nom:'Alain', score: 84}, {nom:'Béatrice', score: 91}],
      },
      {
        id: 2,
        date_maj: '2026-07-18T09:05:00',
        terminee: true,
        joueurs: [{nom:'Alain', score: 312}, {nom:'Ordinateur 1', score: 289}],
      },
    ],
    obtenir_prenom_principal: async () => 'Alain',
    definir_mode_belgicisme: async (actif) => {
      window.__appelsMode.push(actif);
      return { succes: true, mode_belgicisme: actif };
    },
  };
  window.dispatchEvent(new Event('pywebviewready'));
}, 100);
"""


def construire_mock(mock_js, nom_tmp):
    css = (WEB / "accueil.css").read_text()
    css = css.replace("url(images/", f"url(file://{WEB / 'images'}/")
    js = (WEB / "accueil.js").read_text()
    html = (WEB / "accueil.html").read_text()
    html = html.replace(
        '<link rel="stylesheet" href="accueil.css">', f"<style>{css}</style>"
    )
    html = html.replace(
        '<script src="accueil.js"></script>',
        f"<script>{mock_js}</script><script>{js}</script>",
    )
    chemin = SORTIE / nom_tmp
    chemin.write_text(html)
    return chemin


def capturer(url, largeur, hauteur, sortie_png, sequence_clics):
    win = Gtk.Window()
    win.set_default_size(largeur, hauteur)
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
        if minuterie["id"] is not None:
            GLib.source_remove(minuterie["id"])
            minuterie["id"] = None
        Gtk.main_quit()

    minuterie = {"id": None}
    webview.connect("load-changed", apres_chargement)
    webview.load_uri("file://" + url)
    minuterie["id"] = GLib.timeout_add(15000, Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    largeurs = [700, 1280]

    mock_vide = construire_mock(MOCK_JS_VIDE, "_i296_mock_vide_tmp.html")
    url_vide = str(mock_vide)

    print("Capture France 700x800 (vide)...")
    capturer(url_vide, 700, 800,
             SORTIE / "i296_france_vide_700x800.png", [])

    print("Capture Belgique 700x800 (vide)...")
    capturer(url_vide, 700, 800,
             SORTIE / "i296_belgique_vide_700x800.png", ["#drapeau-belgique"])

    mock_vide.unlink()

    mock_rempli = construire_mock(MOCK_JS_REMPLI, "_i296_mock_rempli_tmp.html")
    url_rempli = str(mock_rempli)

    for largeur in largeurs:
        print(f"Capture France {largeur}x800 (rempli)...")
        capturer(url_rempli, largeur, 800,
                 SORTIE / f"i296_france_rempli_{largeur}x800.png", [])

        print(f"Capture Belgique {largeur}x800 (rempli)...")
        capturer(url_rempli, largeur, 800,
                 SORTIE / f"i296_belgique_rempli_{largeur}x800.png",
                 ["#drapeau-belgique"])

    mock_rempli.unlink()

    print("Captures écrites dans", SORTIE)
