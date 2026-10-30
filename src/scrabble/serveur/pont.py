"""Pont API navigateur ↔ ``ApiRouteur`` (issue #475).

Deux mécaniques distinctes relient le navigateur au routeur d'API existant
(``scrabble.ui.application.ApiRouteur``), toutes deux sans rien changer à
``scrabble/ui/`` :

1. **Appels** ``window.pywebview.api.<fonction>(...)`` : le script navigateur
   (généré par :func:`script_pont`) les transforme en requêtes HTTP ``POST``
   ``/__scrabble__/api/<fonction>`` ; le serveur HTTP (``scrabble.serveur.
   httpd``) les relaie vers :func:`fonctions_exposees`.

2. **Diffusions** ``ApiJeu._diffuser()`` → ``window.appliquerEtatPlateau``/
   ``appliquerEtatChevalet`` (issue #90) : en pywebview, ``ApiJeu._pousser``
   appelle ``self._window_plateau.evaluate_js(script)`` directement sur la
   fenêtre native. Ici, :class:`FenetrePont` tient lieu de
   ``self._window_plateau`` : sa seule méthode, :meth:`FenetrePont.
   evaluate_js`, décode le script généré par ``_pousser`` (toujours de la
   forme ``window.FN && window.FN(JSON)``, voir ``api_diffusion.py``) et
   republie ``(FN, JSON)`` via :class:`GestionnaireDiffusion` vers tous les
   navigateurs connectés en« Server-Sent Events » (SSE, ``/__scrabble__/
   evenements``). Aucun ``eval`` côté navigateur : le script relayé n'est
   jamais exécuté tel quel, seul le nom de fonction (restreint à une liste
   connue) et son argument JSON sont transmis.

   ``FenetrePont`` n'implémente **que** ``evaluate_js`` : ``_maximiser_
   plateau``/``_attendre_fenetre_affichee`` (``scrabble.ui.jeu``) accèdent à
   leurs attributs de fenêtre (``events``, ``maximize``, ``resize``...) via
   ``getattr(..., None)`` et tolèrent explicitement leur absence (« robuste
   aux fenêtres factices des tests », cf. leurs docstrings) : aucune
   adaptation de ces fonctions n'est nécessaire.

Fonctions atteignables depuis le navigateur (point 4 de l'issue #475) :
seules les méthodes **publiques** (sans ``_`` initial) et **appelables** du
routeur, à l'exclusion de :data:`_FONCTIONS_INTERDITES` (méthodes de
plomberie interne, jamais appelées par ``accueil.js``/``jeu.js`` — en
particulier ``set_window``, dont un appel depuis le navigateur avec un objet
JSON quelconque casserait l'invariant « pas de fenêtre » dont dépend la
navigation côté serveur, cf. :mod:`scrabble.serveur.httpd`).
"""

from __future__ import annotations

import json
import queue
import re
import threading
from typing import Any, Callable

# Méthodes de contrôle du routeur jamais appelées par le JS existant
# (``accueil.js``/``jeu.js``) : exclues par prudence du pont, même si elles
# sont publiques. Cf. ``ApiRouteur._CONTROLE`` (scrabble.ui.application) pour
# la liste des méthodes de contrôle *routées* ; ``set_window`` n'en fait même
# pas partie (ce n'est pas une route, c'est de la plomberie de démarrage).
_FONCTIONS_INTERDITES = frozenset({"set_window"})

# Forme exacte produite par ``MixinDiffusion._pousser`` (api_diffusion.py) :
# ``f"window.{fonction} && window.{fonction}({json.dumps(charge, ...)})"``.
_MOTIF_SCRIPT_DIFFUSION = re.compile(
    r"^window\.(?P<fonction>\w+) && window\.\1\((?P<charge>.*)\)$", re.DOTALL
)

# Les deux seules fonctions que ``_diffuser`` pousse réellement (issue #90/#187).
# Toute autre correspondance du motif ci-dessus est ignorée par prudence.
_FONCTIONS_DIFFUSION_CONNUES = frozenset({"appliquerEtatPlateau", "appliquerEtatChevalet"})


def fonctions_exposees(routeur: Any) -> dict[str, Callable[..., Any]]:
    """Dictionnaire ``{nom: méthode}`` des fonctions publiques appelables du routeur.

    Même filtre que celui que pywebview applique lui-même via ``dir()``
    (cf. ``ApiRouteur._installer_routes``) : pas de nom commençant par ``_``,
    valeur appelable — moins :data:`_FONCTIONS_INTERDITES`.
    """
    fonctions: dict[str, Callable[..., Any]] = {}
    for nom in dir(routeur):
        if nom.startswith("_") or nom in _FONCTIONS_INTERDITES:
            continue
        valeur = getattr(routeur, nom, None)
        if callable(valeur):
            fonctions[nom] = valeur
    return fonctions


class GestionnaireDiffusion:
    """Registre des navigateurs connectés (SSE) + diffusion des messages poussés.

    Un navigateur par file d'attente (``queue.Queue``) ; :meth:`publier` les
    alimente toutes. Pensé pour UN seul joueur (point 5 de l'issue #475) : si
    un second navigateur se connecte, il reçoit sa propre file et les MÊMES
    diffusions que le premier (état de partie partagé, pas de session par
    joueur) — documenté, non résolu ici.
    """

    def __init__(self) -> None:
        self._verrou = threading.Lock()
        self._files: list[queue.Queue] = []

    def abonner(self) -> queue.Queue:
        file: queue.Queue = queue.Queue()
        with self._verrou:
            self._files.append(file)
        return file

    def desabonner(self, file: queue.Queue) -> None:
        with self._verrou:
            if file in self._files:
                self._files.remove(file)

    def publier(self, fonction: str, charge: Any) -> None:
        message = json.dumps({"fonction": fonction, "charge": charge}, ensure_ascii=False)
        with self._verrou:
            cibles = list(self._files)
        for file in cibles:
            file.put(message)


class FenetrePont:
    """Remplace ``webview.Window`` côté serveur pour ``ApiJeu._window_plateau``.

    Seule ``evaluate_js`` est implémentée (voir docstring de module) : décode
    le script de diffusion et republie ``(fonction, charge)`` sur
    ``diffusion``. Toute correspondance hors de :data:`_FONCTIONS_DIFFUSION_
    CONNUES`, ou tout script qui ne respecte pas le motif attendu, est
    ignorée sans lever d'exception (même contrat de robustesse que
    ``MixinDiffusion._pousser``, qui encadre déjà chaque appel réel de
    ``try/except``).
    """

    def __init__(self, diffusion: GestionnaireDiffusion) -> None:
        self._diffusion = diffusion

    def evaluate_js(self, script: str) -> None:
        correspondance = _MOTIF_SCRIPT_DIFFUSION.match(script)
        if correspondance is None:
            return
        fonction = correspondance.group("fonction")
        if fonction not in _FONCTIONS_DIFFUSION_CONNUES:
            return
        charge = json.loads(correspondance.group("charge"))
        self._diffusion.publier(fonction, charge)


#: Évènement DOM que ``httpd._script_pont`` déclenche sur ``EventSource.onopen``
#: (connexion initiale ET reconnexions automatiques du navigateur) — seul
#: moyen, pour :func:`script_rattrapage` ci-dessous, de savoir que le flux SSE
#: vient de (re)s'ouvrir sans dupliquer une seconde connexion SSE. Nom PUBLIC
#: (pas de ``_``) : ``httpd._script_pont`` l'importe pour déclencher le même
#: évènement, voir ce module.
EVENEMENT_SSE_OUVERTURE = "scrabble:sse-ouverture"


def script_rattrapage() -> str:
    """Script de rattrapage automatique après un décrochage (issue #477, point 5).

    Remplace, en portrait (téléphone, voir le bouton masqué à ≤480px dans
    ``jeu.css``), l'ancien bouton « ↻ Resynchroniser » (``btn-rafraichir``,
    ``jeu.js``) : sur l'application de bureau (pywebview), Alain n'en a jamais
    eu besoin — mais sur téléphone, l'affichage peut rater une diffusion SSE
    pendant une mise en veille de l'écran ou une coupure de connexion
    momentanée pendant que l'ordinateur joue son coup. Ce script recrée
    exactement l'effet du bouton (``obtenir_etat_plateau``/
    ``obtenir_etat_chevalet`` puis ``appliquerEtatPlateau``/
    ``appliquerEtatChevalet`` — mêmes fonctions que ``rafraichir()`` dans
    jeu.js, jamais modifié) à deux déclencheurs :

    - ``visibilitychange`` quand la page redevient visible (réveil du
      téléphone, retour d'un changement d'onglet) ;
    - :data:`EVENEMENT_SSE_OUVERTURE`, déclenché par le script-pont
      (``scrabble.serveur.httpd._script_pont``) à chaque ouverture de la
      connexion SSE — la première ET, grâce à la reconnexion automatique
      native d'``EventSource``, toute reconnexion après une coupure.

    Injecté dans TOUTES les pages HTML servies (comme ``_script_pont``), donc
    aussi sur ``accueil.html`` : les deux gardes ``typeof ... === 'function'``
    rendent l'appel silencieux là où ``jeu.js`` n'a rien posé sur ``window``
    (``appliquerEtatPlateau``/``appliquerEtatChevalet`` n'existent que sur
    ``jeu.html``). Sans aucun effet sur l'application de bureau : ce script
    n'existe que dans les pages servies par CE serveur HTTP, jamais chargé par
    pywebview.
    """
    return f"""
<script>
(function() {{
    "use strict";
    function rattraper() {{
        if (!window.pywebview || !window.pywebview.api) {{ return; }}
        var api = window.pywebview.api;
        if (typeof api.obtenir_etat_plateau === "function"
                && typeof window.appliquerEtatPlateau === "function") {{
            api.obtenir_etat_plateau().then(function(etat) {{
                window.appliquerEtatPlateau(etat);
            }}).catch(function() {{}});
        }}
        if (typeof api.obtenir_etat_chevalet === "function"
                && typeof window.appliquerEtatChevalet === "function") {{
            api.obtenir_etat_chevalet().then(function(etat) {{
                window.appliquerEtatChevalet(etat);
            }}).catch(function() {{}});
        }}
    }}
    document.addEventListener("visibilitychange", function() {{
        if (document.visibilityState === "visible") {{ rattraper(); }}
    }});
    window.addEventListener("{EVENEMENT_SSE_OUVERTURE}", rattraper);
}})();
</script>
""".strip()
