"""Serveur HTTP du prototype (issue #475) — bibliothèque standard uniquement.

Sert les fichiers statiques de ``scrabble/ui/web/`` (plateau, CSS, avatars...)
et répond aux appels d'API du navigateur en les relayant vers l'``ApiRouteur``
existant (``scrabble.ui.application``). N'importe ni ``pywebview`` ni aucun
paquet tiers : uniquement ``http.server``/``socketserver`` de la bibliothèque
standard.

Trois familles de requêtes, toutes sous le préfixe réservé ``/__scrabble__/``
pour ne jamais entrer en collision avec un fichier de ``ui/web/`` :

* ``POST /__scrabble__/api/<fonction>`` — appel d'API (point 4) ;
* ``GET /__scrabble__/evenements`` — flux SSE des diffusions d'état (point 6) ;
* tout le reste en ``GET`` — fichier statique de ``ui/web/`` (point 3), avec
  injection du script-pont dans les pages HTML.

Avertissement de sécurité (point 2) : AUCUNE authentification. Prototype pour
un seul joueur de confiance sur un réseau local de confiance — jamais
Internet. Affiché au démarrage par :func:`scrabble.serveur.cli.main` ; voir
``CONTEXTE.md``.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from scrabble import journal
from scrabble.serveur.pont import (
    EVENEMENT_SSE_OUVERTURE,
    FenetrePont,
    GestionnaireDiffusion,
    fonctions_exposees,
    script_rattrapage,
)

#: Préfixe réservé aux endpoints du serveur — jamais un vrai fichier de ``ui/web/``.
PREFIXE_INTERNE = "/__scrabble__"

#: Pages HTML dans lesquelles le script-pont est injecté (point 4). Les autres
#: réponses (CSS/JS/SVG/PNG...) sont servies telles quelles, sans modification.
_BALISE_INJECTION = b"</head>"

#: Méthodes de contrôle du routeur qui naviguent en pywebview (``load_url``,
#: cf. ``scrabble.ui.application.ApiRouteur``) et que le pont doit donc
#: traduire en changement de page côté navigateur sur succès (point 6).
_CIBLES_NAVIGATION = {
    "demarrer_jeu": "jeu.html",
    "recommencer_jeu": "jeu.html",
    "retourner_accueil": "accueil.html",
    "annuler_tirage_accueil": "accueil.html",
}


def _script_pont(noms_fonctions: list[str]) -> str:
    """Génère le script navigateur qui recrée ``window.pywebview.api`` (point 4).

    Reproduit l'ordre d'apparition réel de pywebview, dont dépendent
    ``accueil.js``/``commun.js`` (cf. leurs commentaires sur l'issue #145) :
    ``window.pywebview`` existe D'ABORD (sans ``api``), PUIS ``window.
    pywebview.api`` est publié, PUIS l'évènement ``pywebviewready`` est émis.

    La liste ``noms_fonctions`` (calculée côté serveur à partir des méthodes
    publiques RÉELLES du routeur, cf. :func:`~scrabble.serveur.pont.
    fonctions_exposees`) est posée telle quelle : ``typeof api.xxx ===
    'function'`` se comporte donc exactement comme avec le vrai pont
    pywebview — seules les fonctions qui existent vraiment répondent
    ``'function'``, les autres restent ``'undefined'`` (contrairement à un
    ``Proxy`` qui répondrait ``'function'`` pour n'importe quel nom).

    Un deuxième bloc ouvre une connexion SSE vers ``/__scrabble__/evenements``
    et appelle ``window[fonction](charge)`` pour chaque message reçu — c'est
    le relais des diffusions poussées par ``ApiJeu._diffuser`` (voir
    ``scrabble.serveur.pont.FenetrePont``). Il déclenche aussi, sur
    ``EventSource.onopen`` (connexion initiale ET reconnexions automatiques du
    navigateur après une coupure), l'évènement DOM
    :data:`~scrabble.serveur.pont.EVENEMENT_SSE_OUVERTURE` : c'est le signal
    dont dépend le rattrapage automatique du téléphone (issue #477, point 5 —
    voir :func:`scrabble.serveur.pont.script_rattrapage`, injecté séparément
    par :meth:`GestionnaireRequetes._servir_statique`).

    Navigation (point 6) : ``demarrer_jeu``/``recommencer_jeu``/``retourner_
    accueil``/``annuler_tirage_accueil`` sont les méthodes de contrôle du
    routeur qui, en pywebview, naviguent elles-mêmes via ``window.load_url``
    (cf. ``scrabble.ui.application.ApiRouteur``). Sans fenêtre, le routeur
    saute cette navigation (branche déjà existante dans son code : ``if
    self._window is not None: ...``) et se contente de retourner ``{"succes":
    True}`` — ``accueil.js``/``jeu.js``, inchangés, ne font alors RIEN de plus
    de leur côté (ils supposent, comme en pywebview, que la navigation a déjà
    eu lieu côté Python). C'est donc ici, dans le pont, que la bascule
    ``window.location.href`` est déclenchée sur un succès de l'une de ces
    fonctions précises — ``_CIBLES_NAVIGATION`` — sans toucher à
    ``accueil.js``/``jeu.js``.
    """
    fonctions_json = json.dumps(sorted(noms_fonctions))
    cibles_navigation_json = json.dumps(_CIBLES_NAVIGATION)
    return f"""
<script>
(function() {{
    "use strict";
    var FONCTIONS = {fonctions_json};
    var CIBLES_NAVIGATION = {cibles_navigation_json};
    window.pywebview = window.pywebview || {{}};
    var api = {{}};
    FONCTIONS.forEach(function(nom) {{
        api[nom] = function() {{
            var args = Array.prototype.slice.call(arguments);
            return fetch("{PREFIXE_INTERNE}/api/" + encodeURIComponent(nom), {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{args: args}})
            }}).then(function(reponse) {{
                return reponse.json().then(function(donnees) {{
                    if (!reponse.ok || donnees.erreur !== undefined) {{
                        throw new Error(donnees.erreur || ("Erreur API (" + reponse.status + ")."));
                    }}
                    var cible = CIBLES_NAVIGATION[nom];
                    if (cible && donnees.resultat && donnees.resultat.succes) {{
                        window.location.href = cible;
                    }}
                    return donnees.resultat;
                }});
            }});
        }};
    }});
    window.pywebview.api = api;
    window.dispatchEvent(new Event("pywebviewready"));

    var source = new EventSource("{PREFIXE_INTERNE}/evenements");
    source.onmessage = function(evenement) {{
        var message = JSON.parse(evenement.data);
        var fn = window[message.fonction];
        if (typeof fn === "function") {{
            fn(message.charge);
        }}
    }};
    source.onopen = function() {{
        window.dispatchEvent(new Event("{EVENEMENT_SSE_OUVERTURE}"));
    }};
}})();
</script>
""".strip()


def _resoudre_chemin_statique(dossier_racine: Path, chemin_requete: str) -> Path | None:
    """Résout ``chemin_requete`` (``path`` de l'URL) sous ``dossier_racine``, ou ``None``.

    Protection contre toute sortie de ``dossier_racine`` (point 3) : remontées
    ``..``, chemins encodés (``%2e%2e``...), liens symboliques pointant
    ailleurs. On décode une seule fois le pourcentage-encodage (``unquote``,
    comme le ferait un navigateur), on retire la racine ``/`` initiale, on
    rejette tout chemin absolu résiduel ou segment ``..``, puis on résout
    (``resolve()``, qui suit les liens symboliques) et on vérifie que le
    résultat est bien *sous* la racine résolue (``is_relative_to``). Tout
    refus renvoie ``None`` → 404 côté appelant, jamais un détail d'erreur.
    """
    try:
        decode = urllib.parse.unquote(chemin_requete.split("?", 1)[0])
        relatif = decode.lstrip("/")
        if relatif == "":
            relatif = "accueil.html"
        segments = relatif.split("/")
        if any(segment in ("..", "") for segment in segments) or any(
            "\\" in segment for segment in segments
        ):
            return None
        racine_resolue = dossier_racine.resolve()
        candidat = (dossier_racine / Path(*segments)).resolve()
    except (ValueError, OSError):
        # Chemin invalide (octet nul, etc.) : refusé comme n'importe quelle
        # autre tentative de sortie du dossier (point 3) — jamais de trace.
        return None
    if not candidat.is_relative_to(racine_resolue):
        return None
    if not candidat.is_file():
        return None
    return candidat


class GestionnaireRequetes(BaseHTTPRequestHandler):
    """Un gestionnaire par connexion (``ThreadingHTTPServer``) — voir :class:`ServeurScrabble`.

    Toute la configuration (routeur, dossier web, fonctions exposées,
    diffusion) est portée par le serveur, accessible ici via ``self.server``
    (typé :class:`ServeurScrabble`) — cette classe de gestionnaire elle-même
    reste sans état propre, réutilisable telle quelle par
    ``ThreadingHTTPServer`` (un nouveau gestionnaire par connexion).
    """

    server: "ServeurScrabble"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ #
    # Journalisation (jamais les arguments ni les résultats des appels d'API,
    # exigence du point 3 — ils peuvent contenir des mots du dictionnaire).
    # ------------------------------------------------------------------ #

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature imposée
        journal.info(f"Serveur HTTP : {self.address_string()} — {format % args}")

    # ------------------------------------------------------------------ #
    # GET — fichiers statiques + flux SSE
    # ------------------------------------------------------------------ #

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par BaseHTTPRequestHandler
        chemin = urllib.parse.urlsplit(self.path).path
        if chemin == f"{PREFIXE_INTERNE}/evenements":
            self._servir_evenements()
            return
        if chemin.startswith(PREFIXE_INTERNE):
            self._repondre_json(404, {"erreur": "Introuvable."})
            return
        self._servir_statique(chemin)

    def _servir_statique(self, chemin_requete: str) -> None:
        fichier = _resoudre_chemin_statique(self.server.dossier_web, chemin_requete)
        if fichier is None:
            self._repondre_json(404, {"erreur": "Introuvable."})
            return
        contenu = fichier.read_bytes()
        type_mime, _ = mimetypes.guess_type(str(fichier))
        type_mime = type_mime or "application/octet-stream"
        if fichier.suffix == ".html":
            # Script-pont (point 4) + rattrapage automatique portrait (issue
            # #477, point 5 — scrabble.serveur.pont.script_rattrapage) : les
            # deux sont injectés ensemble, dans TOUTES les pages HTML, comme
            # le script-pont l'était déjà seul. Sans effet hors de ce
            # serveur : jamais chargé par l'application de bureau (pywebview).
            script = (
                _script_pont(sorted(self.server.fonctions.keys())) + script_rattrapage()
            ).encode("utf-8")
            if _BALISE_INJECTION in contenu:
                contenu = contenu.replace(_BALISE_INJECTION, script + _BALISE_INJECTION, 1)
            else:
                contenu = contenu + script
        self.send_response(200)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(contenu)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(contenu)

    def _servir_evenements(self) -> None:
        """Flux SSE (``text/event-stream``) des diffusions d'état (point 6).

        Une file par connexion, désabonnée proprement à la déconnexion du
        navigateur (``BrokenPipeError``/``ConnectionResetError`` — un seul
        joueur de confiance, pas de limite de connexions ici, cf. point 5).
        """
        file = self.server.diffusion.abonner()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            while True:
                try:
                    message = file.get(timeout=15.0)
                except Exception:  # noqa: BLE001 - file.Empty : keep-alive
                    message = None
                try:
                    if message is None:
                        self.wfile.write(b": keep-alive\n\n")
                    else:
                        self.wfile.write(f"data: {message}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            self.server.diffusion.desabonner(file)

    # ------------------------------------------------------------------ #
    # POST — appels d'API (point 4)
    # ------------------------------------------------------------------ #

    def do_POST(self) -> None:  # noqa: N802 - nom imposé par BaseHTTPRequestHandler
        chemin = urllib.parse.urlsplit(self.path).path
        prefixe_api = f"{PREFIXE_INTERNE}/api/"
        if not chemin.startswith(prefixe_api):
            self._repondre_json(404, {"erreur": "Introuvable."})
            return
        nom_fonction = urllib.parse.unquote(chemin[len(prefixe_api):])
        longueur = int(self.headers.get("Content-Length", "0") or "0")
        corps_brut = self.rfile.read(longueur) if longueur > 0 else b"{}"
        try:
            charge = json.loads(corps_brut.decode("utf-8")) if corps_brut else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._repondre_json(400, {"erreur": "Corps JSON invalide."})
            return
        if not isinstance(charge, dict):
            self._repondre_json(400, {"erreur": "Corps JSON invalide."})
            return
        args = charge.get("args", [])
        kwargs = charge.get("kwargs", {})
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            self._repondre_json(400, {"erreur": "« args »/« kwargs » invalides."})
            return

        # Seules les fonctions publiques du routeur, jamais un nom commençant
        # par « _ » ni un attribut quelconque (point 4 de l'issue #475) : le
        # filtre a déjà eu lieu une fois dans ``fonctions_exposees`` au
        # démarrage — on ne consulte ici QUE ce dictionnaire pré-filtré,
        # jamais ``getattr(routeur, nom_fonction)`` directement.
        methode = self.server.fonctions.get(nom_fonction)
        if methode is None:
            self._repondre_json(404, {"erreur": f"Fonction inconnue : « {nom_fonction} »."})
            return
        try:
            resultat = methode(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - erreur Python remontée au JS, comme pywebview
            journal.erreur(f"Serveur HTTP : échec de l'appel « {nom_fonction} ».", e)
            self._repondre_json(500, {"erreur": str(e)})
            return
        try:
            self._repondre_json(200, {"resultat": resultat})
        except TypeError as e:
            # Résultat non sérialisable en JSON (ex. objet Python interne) :
            # ne devrait pas arriver pour une méthode de l'API web, mais on
            # préfère une erreur propre à un plantage du fil de connexion.
            journal.erreur(
                f"Serveur HTTP : résultat non sérialisable pour « {nom_fonction} ».", e
            )
            self._repondre_json(500, {"erreur": "Résultat non sérialisable en JSON."})

    # ------------------------------------------------------------------ #
    # Utilitaire de réponse JSON
    # ------------------------------------------------------------------ #

    def _repondre_json(self, code: int, charge: dict[str, Any]) -> None:
        corps = json.dumps(charge, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


class ServeurScrabble(ThreadingHTTPServer):
    """``ThreadingHTTPServer`` porteur du routeur, du dossier web et de la diffusion.

    Un thread par connexion (hérité de ``ThreadingHTTPServer``) : nécessaire
    pour que le flux SSE (une connexion bloquée indéfiniment) ne gèle pas les
    appels d'API suivants.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        adresse: tuple[str, int],
        dossier_web: Path,
        routeur: Any,
        fenetre_pont: FenetrePont,
        diffusion: GestionnaireDiffusion,
    ) -> None:
        super().__init__(adresse, GestionnaireRequetes)
        self.dossier_web = dossier_web
        self.routeur = routeur
        self.fonctions: dict[str, Callable[..., Any]] = fonctions_exposees(routeur)
        self.fenetre_pont = fenetre_pont
        self.diffusion = diffusion

