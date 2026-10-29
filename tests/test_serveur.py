"""Tests du prototype de serveur local (issue #475), sans fenêtre ni réseau externe.

Couvre :
- l'isolation des données utilisateur (:mod:`scrabble.serveur.donnees`) :
  ``config.json``/``parties.db`` redirigés vers un dossier temporaire, jamais
  celui du dépôt ;
- la protection du dossier statique (:func:`scrabble.serveur.httpd.
  _resoudre_chemin_statique`) contre toute sortie de ``ui/web/`` ;
- le filtre des fonctions exposées au navigateur (:func:`scrabble.serveur.
  pont.fonctions_exposees`) : public/appelable seulement, ``set_window``
  explicitement exclu ;
- un aller-retour HTTP complet (statique + appel d'API) sur un serveur réel,
  lancé sur ``127.0.0.1`` à un port éphémère, arrêté en fin de test.

Aucun de ces tests n'a besoin du dictionnaire (``data/dictionnaire/``) : les
méthodes exercées (``obtenir_etat``, servir une page statique) ne le
sollicitent pas.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import scrabble.config as _config
import scrabble.persistance.stockage as _stockage
import scrabble.reglages as _reglages
from scrabble.serveur.donnees import _repointer_defaut, isoler_donnees_utilisateur
from scrabble.serveur.httpd import (
    _CIBLES_NAVIGATION,
    ServeurScrabble,
    _resoudre_chemin_statique,
    _script_pont,
)
from scrabble.serveur.pont import FenetrePont, GestionnaireDiffusion, fonctions_exposees
from scrabble.ui.accueil import ApiAccueil
from scrabble.ui.application import DOSSIER_WEB, VUE_ACCUEIL, ApiRouteur
from scrabble.ui.jeu import ApiJeu

_FONCTIONS_STOCKAGE = (
    "demarrer_suivi",
    "enregistrer_action",
    "finaliser_partie",
    "supprimer_partie",
    "lister_parties",
    "niveaux_ia_stockes",
    "reprendre_partie",
    "lire_configuration_partie",
    "lire_actions_journalisees",
)
_FONCTIONS_CONFIG = ("charger_config", "sauvegarder_config")
_FONCTIONS_REGLAGES = ("lister_reglages", "lire_reglage", "modifier_reglage")


@pytest.fixture
def donnees_isolees(tmp_path):
    """Isole config/parties vers ``tmp_path`` pour la durée du test, puis restaure.

    Nécessaire car :func:`isoler_donnees_utilisateur` modifie des valeurs par
    défaut de fonctions PARTAGÉES par tout le processus pytest (cf. docstring
    de ``scrabble.serveur.donnees``) : sans restauration, un test ultérieur du
    même run (ex. ``test_application.py``, qui lit délibérément le
    ``config.json`` réel du poste) verrait un chemin différent.
    """
    chemin_config_origine = _config.CHEMIN_CONFIG
    chemin_base_origine = _stockage.CHEMIN_DEFAUT

    chemins = isoler_donnees_utilisateur(tmp_path)
    yield chemins

    chemin_config_tmp = _config.CHEMIN_CONFIG
    chemin_base_tmp = _stockage.CHEMIN_DEFAUT
    for nom in _FONCTIONS_CONFIG:
        _repointer_defaut(getattr(_config, nom), chemin_config_tmp, chemin_config_origine)
    for nom in _FONCTIONS_REGLAGES:
        _repointer_defaut(getattr(_reglages, nom), chemin_config_tmp, chemin_config_origine)
    _config.CHEMIN_CONFIG = chemin_config_origine
    for nom in _FONCTIONS_STOCKAGE:
        _repointer_defaut(getattr(_stockage, nom), chemin_base_tmp, chemin_base_origine)
    _stockage.CHEMIN_DEFAUT = chemin_base_origine


# -------------------------------------------------------------------------- #
# Isolation des données utilisateur
# -------------------------------------------------------------------------- #


def test_isolation_redirige_config_et_base(tmp_path, donnees_isolees):
    chemins = donnees_isolees
    assert chemins["config"] == tmp_path / "config.json"
    assert chemins["base_parties"] == tmp_path / "data" / "parties.db"
    assert _config.charger_config.__defaults__[0] == tmp_path / "config.json"
    assert _stockage.demarrer_suivi.__defaults__[0] == tmp_path / "data" / "parties.db"


def test_isolation_ecrit_bien_dans_le_dossier_isole(tmp_path, donnees_isolees):
    valeur = _reglages.modifier_reglage("prenom_principal", "Test475")
    assert valeur == "Test475"
    assert (tmp_path / "config.json").exists()


# -------------------------------------------------------------------------- #
# Protection du dossier statique
# -------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "chemin_requete",
    [
        "/../config.py",
        "/../../config.py",
        "/..%2fconfig.py",
        "/%2e%2e/config.py",
        "/accueil.html/../../config.py",
        "/avatars/..%2f..%2fconfig.py",
    ],
)
def test_protection_chemin_statique_refuse_la_sortie(chemin_requete):
    assert _resoudre_chemin_statique(DOSSIER_WEB, chemin_requete) is None


def test_protection_chemin_statique_sert_un_fichier_reel():
    resultat = _resoudre_chemin_statique(DOSSIER_WEB, "/accueil.html")
    assert resultat is not None
    assert resultat.is_relative_to(DOSSIER_WEB.resolve())


def test_protection_chemin_statique_racine_sert_accueil():
    assert _resoudre_chemin_statique(DOSSIER_WEB, "/") == (DOSSIER_WEB / "accueil.html").resolve()


def test_protection_chemin_statique_fichier_absent():
    assert _resoudre_chemin_statique(DOSSIER_WEB, "/ce_fichier_n_existe_pas.html") is None


# -------------------------------------------------------------------------- #
# Filtre des fonctions exposées
# -------------------------------------------------------------------------- #


def test_script_pont_navigue_sur_succes_des_fonctions_de_controle():
    """Le script généré doit rediriger le navigateur après les 4 méthodes de
    contrôle qui naviguent en pywebview (point 6) — vérifié ici au niveau du
    texte généré (voir aussi la vérification Playwright manuelle, hors suite
    pytest, documentée dans le rapport de l'issue #475)."""
    script = _script_pont(["demarrer_jeu", "obtenir_etat", "retourner_accueil"])
    assert json.dumps(_CIBLES_NAVIGATION) in script


def test_fonctions_exposees_exclut_set_window_et_les_prives():
    routeur = ApiRouteur()
    fonctions = fonctions_exposees(routeur)
    assert "set_window" not in fonctions
    assert all(not nom.startswith("_") for nom in fonctions)
    assert "demarrer_jeu" in fonctions
    assert "obtenir_etat" in fonctions


# -------------------------------------------------------------------------- #
# Serveur réel (aller-retour HTTP, pas de dictionnaire requis)
# -------------------------------------------------------------------------- #


@pytest.fixture
def serveur_test(donnees_isolees):
    chemins = donnees_isolees
    diffusion = GestionnaireDiffusion()
    pont = FenetrePont(diffusion)
    api_jeu = ApiJeu(chemin_persistance=chemins["base_parties"])
    api_jeu.set_window(pont)
    routeur = ApiRouteur(api_accueil=ApiAccueil(), api_jeu=api_jeu, vue_active=VUE_ACCUEIL)
    routeur.initialiser_joueur_humain()

    serveur = ServeurScrabble(("127.0.0.1", 0), DOSSIER_WEB, routeur, pont, diffusion)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        yield serveur
    finally:
        serveur.shutdown()
        serveur.server_close()
        fil.join(timeout=5)


def _url(serveur: ServeurScrabble, chemin: str) -> str:
    port = serveur.server_address[1]
    return f"http://127.0.0.1:{port}{chemin}"


def test_serveur_sert_accueil_html_avec_le_script_pont(serveur_test):
    with urllib.request.urlopen(_url(serveur_test, "/")) as reponse:
        corps = reponse.read().decode("utf-8")
    assert "pywebviewready" in corps
    assert "/__scrabble__/api/" in corps


def test_serveur_refuse_la_sortie_de_ui_web_en_http(serveur_test):
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(_url(serveur_test, "/../config.py"))
    assert exc.value.code == 404


def test_serveur_refuse_lacces_aux_donnees_privees(serveur_test):
    for cible in ("/../config.json", "/../data/parties.db", "/../logs/"):
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(_url(serveur_test, cible))
        assert exc.value.code == 404


def test_serveur_refuse_set_window_en_api(serveur_test):
    requete = urllib.request.Request(
        _url(serveur_test, "/__scrabble__/api/set_window"),
        data=json.dumps({"args": []}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(requete)
    assert exc.value.code == 404


def test_serveur_refuse_fonction_privee_en_api(serveur_test):
    requete = urllib.request.Request(
        _url(serveur_test, "/__scrabble__/api/__class__"),
        data=json.dumps({"args": []}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(requete)
    assert exc.value.code == 404


def test_serveur_aller_retour_api_simple(serveur_test):
    requete = urllib.request.Request(
        _url(serveur_test, "/__scrabble__/api/obtenir_etat"),
        data=json.dumps({"args": []}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(requete) as reponse:
        donnees = json.loads(reponse.read())
    assert "resultat" in donnees
    assert "nb_humains" in donnees["resultat"]


def test_serveur_diffuse_l_etat_via_sse(serveur_test):
    """``ApiJeu._diffuser`` (point 6) doit atteindre le navigateur via SSE.

    Sans fenêtre pywebview, ``_window_plateau`` est le :class:`FenetrePont` du
    test ; cette diffusion (``evaluate_js`` → SSE) est la seule façon dont
    l'état du plateau/chevalet atteint le navigateur après une mutation
    (``poser_mot``, ``passer``...) — les valeurs de retour des appels d'API ne
    portent, elles, que des messages transitoires (cf. docstring de module de
    ``scrabble.serveur.pont``).
    """
    port = serveur_test.server_address[1]
    messages: list[dict] = []

    def ecouter():
        connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connexion.request("GET", "/__scrabble__/evenements")
        reponse = connexion.getresponse()
        tampon = b""
        fin = time.time() + 5
        while time.time() < fin and len(messages) < 2:
            octet = reponse.read(1)
            if not octet:
                break
            tampon += octet
            if tampon.endswith(b"\n\n"):
                texte = tampon.decode("utf-8").strip()
                tampon = b""
                if texte.startswith("data: "):
                    messages.append(json.loads(texte[len("data: "):]))
        connexion.close()

    fil = threading.Thread(target=ecouter, daemon=True)
    fil.start()
    time.sleep(0.2)  # laisse l'abonnement SSE s'établir avant de déclencher la diffusion

    def _appel(fonction, *args):
        requete = urllib.request.Request(
            _url(serveur_test, f"/__scrabble__/api/{fonction}"),
            data=json.dumps({"args": list(args)}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(requete) as reponse:
            return json.loads(reponse.read()).get("resultat")

    _appel("ajouter_humain", "Testeur")
    _appel("ajouter_ordinateur", "Facile")
    _appel("lancer_partie")
    _appel("demarrer_jeu")

    fil.join(timeout=5)
    fonctions_recues = {m.get("fonction") for m in messages}
    assert fonctions_recues == {"appliquerEtatPlateau", "appliquerEtatChevalet"}
