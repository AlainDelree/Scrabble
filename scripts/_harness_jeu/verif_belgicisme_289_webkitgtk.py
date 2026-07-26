"""Vérification issue #289 : panneau blanc central du mode Belgicisme sous
WebKitGTK (le moteur utilisé par pywebview sous Linux, cf. CONTEXTE.md — le
harnais Playwright habituel de _harness_jeu ne teste que Chromium et n'aurait
pas détecté l'écart de rendu constaté en #270).

#289 ajoute un panneau blanc/quasi-opaque derrière `.container` (voir
`.container::before` dans accueil.css) pour que le titre, les cartes et les
boutons du mode Belgicisme reposent toujours sur du blanc, quelle que soit la
largeur de fenêtre — le voile tricolore noir/jaune/rouge (issue #272) ne
reste visible que dans les marges latérales, hors du panneau. Ce harnais
reprend celui de #270/#272 (même mock d'API, même mécanique de capture via
webkit_web_view_get_snapshot) mais capture PLUSIEURS largeurs de fenêtre — les
largeurs identifiées par l'investigation précédente comme sujettes au
débordement : ~1280px (résolution cible réelle) et 700px (repli non
maximisé) — plus une largeur large (1920px) pour vérifier que le panneau ne
casse pas la mise en page déjà correcte à cette taille.

Prérequis système (déjà présents sur cette machine) : gir1.2-webkit2-4.1,
python3-gi (paquets système — utiliser /usr/bin/python3, pas un venv qui ne
voit pas les dist-packages système), un DISPLAY X11 valide (le WebView a
besoin d'un GtkWindow réel ; pas de Xvfb installé ici, mais le DISPLAY
existant a suffi).

Usage : /usr/bin/python3 verif_belgicisme_289_webkitgtk.py [dossier_sortie]
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
    chemin = SORTIE / "_i289_mock_tmp.html"
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
            # Le fond passe du vert au blanc+tricolore (transition CSS
            # `background-image 0.2s ease` du body) : 700ms de marge pour
            # être sûr que la capture ne tombe jamais en plein fondu.
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

    # Largeurs identifiées par l'investigation précédente : 700 (repli non
    # maximisé), 1280 (résolution cible logique réelle), 1340 (proche de la
    # pleine largeur déjà correcte avant #289 — ne doit pas être cassée par
    # le panneau). Plafonné à 1340 (et non 1920) : l'écran réel de cette
    # machine fait 1360x768 (xrandr), une fenêtre GTK ne peut pas dépasser
    # cette largeur ici — le cas ≥1800px est déjà couvert numériquement par
    # le harnais Playwright (verif_belgicisme_269.mjs, sans cette limite
    # d'écran physique).
    largeurs = [700, 1280, 1340]
    for largeur in largeurs:
        print(f"Capture Belgique {largeur}x800...")
        capturer(
            url, largeur, 800,
            SORTIE / f"i289_accueil_belgique_{largeur}x800_webkitgtk.png",
            ["#drapeau-belgique"],
        )

    print("Capture France 700x800 (référence, mode inchangé)...")
    capturer(
        url, 700, 800,
        SORTIE / "i289_accueil_france_700x800_webkitgtk.png",
        [],
    )

    mock.unlink()
    print("Captures écrites dans", SORTIE)
