"""Vérification issue #292 : fond drapeau en image + panneau blanc flottant
du mode Belgicisme sous WebKitGTK (le moteur utilisé par pywebview sous
Linux, cf. CONTEXTE.md — le harnais Playwright habituel de _harness_jeu ne
teste que Chromium et n'aurait pas détecté l'écart de rendu constaté en
#270).

#292 remplace le voile CSS en `linear-gradient` (#289-#291, bandes forcément
droites et figées) par une vraie photo de drapeau belge ondulé
(`images/drapeau-belge.jpg`) en `background-image`, repasse le panneau
(`.container::before`) à une opacité quasi opaque (0.95, l'image n'a plus
besoin de transparaître à travers le contenu) et corrige le chevauchement du
titre en tuiles avec le bouton réglages. Ce harnais reprend celui de #291
(même mock d'API, même mécanique de capture via
webkit_web_view_get_snapshot) aux mêmes largeurs, mais ajoute une variante
"contenu rempli" (plusieurs joueurs + plusieurs parties enregistrées) en
plus de la variante "contenu vide" (aucun joueur, aucune partie), pour
vérifier que le panneau s'arrête bien à la fin du contenu réel dans les deux
cas.

Prérequis système (déjà présents sur cette machine) : gir1.2-webkit2-4.1,
python3-gi (paquets système — utiliser /usr/bin/python3, pas un venv qui ne
voit pas les dist-packages système), un DISPLAY X11 valide (le WebView a
besoin d'un GtkWindow réel ; pas de Xvfb installé ici, mais le DISPLAY
existant a suffi).

Usage : /usr/bin/python3 verif_belgicisme_292_webkitgtk.py [dossier_sortie]
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

# Variante "vide" : aucun joueur, aucune partie enregistrée.
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

# Variante "rempli" : plusieurs joueurs autour de la table + plusieurs
# parties enregistrées (une en cours, une terminée), pour vérifier que le
# panneau grandit avec le contenu plutôt que de rester figé à une hauteur.
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
    # Le CSS est inliné dans un <style> d'un HTML temporaire écrit hors de
    # web/ (dans SORTIE) : le chemin relatif `url(images/...)` doit être
    # réécrit en chemin absolu file:// pour continuer à résoudre vers
    # web/images/, sinon l'image de fond ne se charge pas dans ce harnais
    # (bug spécifique au mock, sans rapport avec l'app réelle où accueil.css
    # et images/ restent voisins sous web/).
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
            # Le fond passe du vert à l'image drapeau (transition CSS
            # `background-image 0.2s ease` du body) : 700ms de marge pour
            # être sûr que la capture ne tombe jamais en plein fondu, et que
            # l'image (chargée en parallèle) a le temps de s'afficher.
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

    # Repli anti-blocage : sans lui, un chargement qui ne finit jamais (échec
    # WebKit, ex.) bloquerait indéfiniment. Sans l'annuler via
    # `GLib.source_remove` une fois la capture réussie (ci-dessus), ce
    # timeout restait planté dans le contexte GLib par défaut au-delà de la
    # fin du `Gtk.main()` courant et finissait par déclencher un
    # `Gtk.main_quit()` prématuré pendant l'appel `capturer()` SUIVANT
    # (partagent le même contexte GLib par défaut) — constaté : les deux
    # dernières captures de la série (700/1280/1340 x vide/rempli) restaient
    # silencieusement absentes, le script se terminant sans erreur.
    minuterie = {"id": None}
    webview.connect("load-changed", apres_chargement)
    webview.load_uri("file://" + url)
    minuterie["id"] = GLib.timeout_add(15000, Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    # Mêmes largeurs que #289/#290/#291 (700 repli, 1280 résolution cible,
    # 1340 proche pleine largeur — écran physique de cette machine limité à
    # 1360x768) pour comparaison directe avant/après #292.
    largeurs = [700, 1280, 1340]

    mock_vide = construire_mock(MOCK_JS_VIDE, "_i292_mock_vide_tmp.html")
    url_vide = str(mock_vide)
    for largeur in largeurs:
        print(f"Capture Belgique {largeur}x800 (contenu vide)...")
        capturer(
            url_vide, largeur, 800,
            SORTIE / f"i292_accueil_belgique_vide_{largeur}x800_webkitgtk.png",
            ["#drapeau-belgique"],
        )

    print("Capture France 700x800 (contenu vide, référence, mode inchangé)...")
    capturer(
        url_vide, 700, 800,
        SORTIE / "i292_accueil_france_vide_700x800_webkitgtk.png",
        [],
    )
    mock_vide.unlink()

    mock_rempli = construire_mock(MOCK_JS_REMPLI, "_i292_mock_rempli_tmp.html")
    url_rempli = str(mock_rempli)
    for largeur in largeurs:
        print(f"Capture Belgique {largeur}x800 (contenu rempli)...")
        capturer(
            url_rempli, largeur, 800,
            SORTIE / f"i292_accueil_belgique_rempli_{largeur}x800_webkitgtk.png",
            ["#drapeau-belgique"],
        )

    print("Capture France 700x800 (contenu rempli, référence, mode inchangé)...")
    capturer(
        url_rempli, 700, 800,
        SORTIE / "i292_accueil_france_rempli_700x800_webkitgtk.png",
        [],
    )
    mock_rempli.unlink()

    print("Captures écrites dans", SORTIE)
