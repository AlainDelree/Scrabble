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
  lancé sur ``127.0.0.1`` à un port éphémère, arrêté en fin de test ;
- le verrouillage du dictionnaire (issue #479, étendu à ``poser_mot`` par
  l'issue #483) : fonctions de gestion des mots interdites, masquage de
  l'onglet Dictionnaire, lettres posées/vérifiées limitées au chevalet réel,
  limites de fréquence (``verifier_coup``/``verifier_mot``/``poser_mot``) et
  leur allongement de pause, absence d'arguments dans le journal.

Aucun de ces tests n'a besoin du VRAI dictionnaire (``data/dictionnaire/``) :
les méthodes exercées (``obtenir_etat``, servir une page statique) ne le
sollicitent pas, et les tests de partie (issue #479) chargent un
:class:`~scrabble.dictionnaire.dictionnaire.Trie` minimal construit en
mémoire (``Trie.depuis_iterable``) plutôt que les fichiers du dépôt.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import pytest

import scrabble.config as _config
import scrabble.journal as journal
import scrabble.persistance.stockage as _stockage
import scrabble.reglages as _reglages
from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.partie import Joueur, Partie
from scrabble.serveur.donnees import _repointer_defaut, isoler_donnees_utilisateur
from scrabble.serveur.httpd import (
    _CIBLES_NAVIGATION,
    ServeurScrabble,
    _resoudre_chemin_statique,
    _script_pont,
)
from scrabble.serveur.pont import (
    EVENEMENT_SSE_OUVERTURE,
    FenetrePont,
    GestionnaireDiffusion,
    fonctions_exposees,
    script_rattrapage,
    style_masquage_dictionnaire,
)
from scrabble.serveur.securite import (
    FONCTIONS_DICTIONNAIRE_INTERDITES,
    LIMITES_FREQUENCE,
    MESSAGE_CHEVALET_INVALIDE,
    MESSAGE_FONCTION_INTERDITE,
    MESSAGE_LIMITE_FREQUENCE,
    PALIERS_BLOCAGE_SECONDES,
    LimiteurFrequence,
    chevalet_du_joueur_courant,
)
from scrabble.ui.accueil import ApiAccueil
from scrabble.ui.application import DOSSIER_WEB, VUE_ACCUEIL, VUE_JEU, ApiRouteur
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


# -------------------------------------------------------------------------- #
# Rattrapage automatique portrait (issue #477, point 5)
# -------------------------------------------------------------------------- #


def test_script_pont_declenche_l_evenement_sse_ouverture_a_l_ouverture():
    """``source.onopen`` doit déclencher l'évènement dont dépend le rattrapage
    automatique (:func:`script_rattrapage`) — à l'ouverture initiale ET à
    chaque reconnexion automatique du navigateur après une coupure (même
    callback native ``EventSource.onopen``)."""
    script = _script_pont(["obtenir_etat"])
    assert "source.onopen" in script
    assert f'new Event("{EVENEMENT_SSE_OUVERTURE}")' in script


def test_script_rattrapage_ecoute_visibilite_et_reouverture_sse():
    script = script_rattrapage()
    assert "visibilitychange" in script
    assert EVENEMENT_SSE_OUVERTURE in script
    assert "obtenir_etat_plateau" in script
    assert "obtenir_etat_chevalet" in script
    assert "appliquerEtatPlateau" in script
    assert "appliquerEtatChevalet" in script


def test_serveur_sert_jeu_html_avec_le_script_de_rattrapage(serveur_test):
    with urllib.request.urlopen(_url(serveur_test, "/jeu.html")) as reponse:
        corps = reponse.read().decode("utf-8")
    assert EVENEMENT_SSE_OUVERTURE in corps
    assert "visibilitychange" in corps


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
def serveur_test(donnees_isolees, monkeypatch):
    """``donnees_isolees`` ne redirige que config/parties/journal (portée
    volontaire de l'issue #475, voir ``scrabble.serveur.donnees``) : le
    dictionnaire lui-même en est délibérément exclu. Mais
    ``test_serveur_diffuse_l_etat_via_sse`` (seul test d'ici à passer par un
    vrai ``ApiAccueil.lancer_partie()`` plutôt qu'une injection d'état
    directe) atteindrait sinon ``obtenir_trie``/``obtenir_trie_ia`` à leurs
    chemins par défaut réels, écrivant un cache dans le vrai ``cache/
    dictionnaire/`` du dépôt (issue #491) — un Trie factice en mémoire,
    comme partout ailleurs dans la suite, l'évite sans toucher à ce test."""
    monkeypatch.setattr(
        "scrabble.ui.accueil.obtenir_trie",
        lambda source="ods", **_: Trie.depuis_iterable(["ABC"]),
    )
    monkeypatch.setattr(
        "scrabble.ui.accueil.obtenir_trie_ia",
        lambda source="ods", **_: Trie.depuis_iterable(["ABC"]),
    )
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


# -------------------------------------------------------------------------- #
# Verrouillage du dictionnaire (issue #479)
# -------------------------------------------------------------------------- #
# Utilitaires communs aux points 1, 3, 4 et 5 ci-dessous.


def _requete_api(serveur: ServeurScrabble, fonction: str, *args, **kwargs):
    """Appel HTTP brut vers ``/api/<fonction>`` — renvoie ``(statut, corps)``.

    Contrairement à ``urllib.request.urlopen`` seul, ne lève JAMAIS : un
    statut non-2xx est simplement renvoyé tel quel (comme ``statut``), pour
    pouvoir vérifier aussi bien un succès qu'un refus contrôlé sans
    ``pytest.raises`` à chaque appel.
    """
    corps_requete: dict[str, Any] = {"args": list(args)}
    if kwargs:
        corps_requete["kwargs"] = kwargs
    requete = urllib.request.Request(
        _url(serveur, f"/__scrabble__/api/{fonction}"),
        data=json.dumps(corps_requete).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete) as reponse:
            return reponse.status, json.loads(reponse.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _charger_partie_test(
    serveur: ServeurScrabble, chevalet: tuple[str, ...]
) -> Partie:
    """Charge une partie à 1 joueur humain, chevalet FORCÉ, en vue Jeu.

    Injection d'état directe (comme l'issue #477) plutôt qu'un vrai
    ``lancer_partie`` : un dictionnaire minimal construit en mémoire
    (:class:`~scrabble.dictionnaire.dictionnaire.Trie.depuis_iterable`) évite
    toute dépendance au vrai ``data/dictionnaire/`` (absent par défaut dans un
    clone isolé) et un chevalet connu rend les tests de contrôle « lettre hors
    chevalet » déterministes, sans dépendre d'un tirage aléatoire.
    """
    joueur = Joueur("Testeur", humain=True)
    partie = Partie([joueur], Trie.depuis_iterable(["ABC"]))
    partie.joueurs[0].chevalet = list(chevalet)
    serveur.routeur.charger_jeu(partie, 1)
    serveur.routeur.activer_vue(VUE_JEU)
    return partie


# -- Point 1 — fonctions de gestion des mots interdites -------------------- #


@pytest.mark.parametrize("nom_fonction", sorted(FONCTIONS_DICTIONNAIRE_INTERDITES))
def test_serveur_refuse_les_fonctions_de_gestion_du_dictionnaire(
    serveur_test, nom_fonction
):
    statut, corps = _requete_api(serveur_test, nom_fonction, "xxx")
    assert statut == 403
    assert corps == {"erreur": MESSAGE_FONCTION_INTERDITE}


def test_fonctions_exposees_exclut_la_gestion_du_dictionnaire():
    """Ces fonctions sortent de la liste des fonctions appelables (point 1) :
    absentes de ``fonctions_exposees``, donc jamais dans ``FONCTIONS`` côté
    script-pont — ``typeof api.ajouter_mot`` reste ``'undefined'``, comme une
    fonction qui n'existe pas (même comportement que pywebview réel)."""
    routeur = ApiRouteur()
    fonctions = fonctions_exposees(routeur)
    for nom in FONCTIONS_DICTIONNAIRE_INTERDITES:
        assert nom not in fonctions


def test_verifier_mot_n_est_pas_dans_les_fonctions_interdites():
    """``verifier_mot`` reste une fonction de jeu normale (point 4, pas 1)."""
    assert "verifier_mot" not in FONCTIONS_DICTIONNAIRE_INTERDITES


# -- Point 2 — masquage de l'onglet Dictionnaire des réglages -------------- #


def test_style_masquage_dictionnaire_cible_les_bons_identifiants():
    style = style_masquage_dictionnaire()
    assert "#onglet-dictionnaire" in style
    assert "#panneau-dictionnaire" in style
    assert "display: none" in style


def test_serveur_sert_accueil_html_avec_le_masquage_dictionnaire(serveur_test):
    with urllib.request.urlopen(_url(serveur_test, "/accueil.html")) as reponse:
        corps = reponse.read().decode("utf-8")
    assert "#onglet-dictionnaire" in corps
    assert "#panneau-dictionnaire" in corps


def test_serveur_sert_jeu_html_sans_toucher_au_panneau_de_verification(serveur_test):
    """Le panneau « Tapez un mot à tester » (identifiants distincts de ceux
    masqués ci-dessus) reste intact sur l'écran de jeu : seul l'onglet
    Dictionnaire des réglages (accueil) est masqué."""
    with urllib.request.urlopen(_url(serveur_test, "/jeu.html")) as reponse:
        corps = reponse.read().decode("utf-8")
    assert "champ-verif" in corps
    assert "btn-verifier" in corps


# -- Point 3 — lettres posées/vérifiées limitées au chevalet --------------- #


def test_chevalet_du_joueur_courant_lit_le_chevalet_reel(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    assert chevalet_du_joueur_courant(serveur_test.fonctions) == [
        "A", "B", "C", "D", "E", "F", "G",
    ]


def test_chevalet_du_joueur_courant_renvoie_none_sans_partie_chargee(serveur_test):
    assert chevalet_du_joueur_courant(serveur_test.fonctions) is None


def test_serveur_laisse_passer_le_mode_clic_plateau(serveur_test):
    """Mode « clic plateau » (``ligne``/``colonne`` seuls) : la lettre est déjà
    résolue depuis le chevalet réel côté ``scrabble.ui`` — rien à contrôler de
    plus ici, le déroulé honnête n'est jamais refusé."""
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(serveur_test, "selectionner_lettre", 0)
    assert statut == 200
    assert corps["resultat"]["succes"] is True
    statut, corps = _requete_api(serveur_test, "poser_lettre_en_attente", 7, 7)
    assert statut == 200
    assert corps["resultat"] == {"succes": True}


def test_serveur_laisse_passer_une_lettre_reellement_du_chevalet(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test, "poser_lettre_en_attente", 7, 7, "A", False, 1, 0
    )
    assert statut == 200
    assert corps["resultat"] == {"succes": True}


def test_serveur_refuse_une_lettre_hors_chevalet_en_finalisation(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test, "poser_lettre_en_attente", 7, 7, "Z", False, 10, 0
    )
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_CHEVALET_INVALIDE}


def test_serveur_accepte_un_joker_reellement_du_chevalet(serveur_test):
    _charger_partie_test(serveur_test, ("*", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test, "poser_lettre_en_attente", 7, 7, "X", True, 0, 0
    )
    assert statut == 200
    assert corps["resultat"] == {"succes": True}


def test_serveur_refuse_un_joker_sans_joker_au_chevalet(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test, "poser_lettre_en_attente", 7, 7, "X", True, 0, 0
    )
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_CHEVALET_INVALIDE}


def test_serveur_refuse_verifier_coup_avec_placements_hors_chevalet(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test,
        "verifier_coup",
        [{"ligne": 7, "colonne": 7, "lettre": "Z", "joker": False}],
    )
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_CHEVALET_INVALIDE}


def test_serveur_refuse_poser_mot_avec_placements_hors_chevalet(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test,
        "poser_mot",
        [{"ligne": 7, "colonne": 7, "lettre": "Z", "joker": False}],
    )
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_CHEVALET_INVALIDE}


def test_serveur_laisse_passer_verifier_coup_avec_placements_du_chevalet(serveur_test):
    """Une lettre réellement du chevalet n'est jamais bloquée par CE contrôle :
    si l'appel échoue malgré tout, c'est pour une autre raison (ici : un mot
    d'une seule lettre n'est pas un placement valide), jamais le message de
    chevalet invalide."""
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    statut, corps = _requete_api(
        serveur_test,
        "verifier_coup",
        [{"ligne": 7, "colonne": 7, "lettre": "A", "joker": False}],
    )
    assert statut == 200
    assert corps["resultat"].get("erreur") != MESSAGE_CHEVALET_INVALIDE


# -- Point 4 — limites de fréquence ----------------------------------------- #


def test_limiteur_frequence_refuse_au_dela_de_la_limite_minute():
    limiteur = LimiteurFrequence(max_par_minute=3, max_par_jour=1000)
    t0 = 1_000_000.0
    assert limiteur.autoriser("1.2.3.4", t0)
    assert limiteur.autoriser("1.2.3.4", t0 + 1)
    assert limiteur.autoriser("1.2.3.4", t0 + 2)
    assert not limiteur.autoriser("1.2.3.4", t0 + 3)


def test_limiteur_frequence_refuse_au_dela_de_la_limite_jour():
    limiteur = LimiteurFrequence(max_par_minute=1000, max_par_jour=2)
    t0 = 1_000_000.0
    # Espacés de plus d'une minute pour ne jamais aussi déclencher la limite/minute.
    assert limiteur.autoriser("1.2.3.4", t0)
    assert limiteur.autoriser("1.2.3.4", t0 + 120)
    assert not limiteur.autoriser("1.2.3.4", t0 + 240)


def test_limiteur_frequence_distingue_les_adresses():
    limiteur = LimiteurFrequence(max_par_minute=1, max_par_jour=1000)
    t0 = 1_000_000.0
    assert limiteur.autoriser("1.2.3.4", t0)
    assert not limiteur.autoriser("1.2.3.4", t0 + 1)
    assert limiteur.autoriser("5.6.7.8", t0 + 1)


def test_limiteur_frequence_pause_s_allonge_si_le_client_insiste():
    limiteur = LimiteurFrequence(max_par_minute=1, max_par_jour=1000)
    t0 = 1_000_000.0
    assert limiteur.autoriser("1.2.3.4", t0)

    assert not limiteur.autoriser("1.2.3.4", t0 + 1)
    etat = limiteur._etats["1.2.3.4"]
    assert etat.blocage_jusqua - (t0 + 1) == PALIERS_BLOCAGE_SECONDES[0]

    # Insiste PENDANT le blocage : palier suivant, plus long.
    assert not limiteur.autoriser("1.2.3.4", t0 + 2)
    assert etat.blocage_jusqua - (t0 + 2) == PALIERS_BLOCAGE_SECONDES[1]

    assert not limiteur.autoriser("1.2.3.4", t0 + 3)
    assert etat.blocage_jusqua - (t0 + 3) == PALIERS_BLOCAGE_SECONDES[2]

    # Plafonné : un refus de plus ne dépasse pas le dernier palier.
    assert not limiteur.autoriser("1.2.3.4", t0 + 4)
    assert etat.blocage_jusqua - (t0 + 4) == PALIERS_BLOCAGE_SECONDES[-1]


def test_limiteur_frequence_reaccepte_apres_la_pause_et_reinitialise_l_escalade():
    limiteur = LimiteurFrequence(max_par_minute=1, max_par_jour=1000)
    t0 = 1_000_000.0
    assert limiteur.autoriser("1.2.3.4", t0)
    assert not limiteur.autoriser("1.2.3.4", t0 + 1)
    pause = PALIERS_BLOCAGE_SECONDES[0]
    assert limiteur.autoriser("1.2.3.4", t0 + 1 + pause + 1)
    assert limiteur._etats["1.2.3.4"].niveau_blocage == 0


def test_serveur_limite_la_frequence_de_verifier_mot(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    max_minute, _ = LIMITES_FREQUENCE["verifier_mot"]
    for _ in range(max_minute):
        statut, corps = _requete_api(serveur_test, "verifier_mot", "ABC")
        assert statut == 200
        assert corps["resultat"].get("erreur") != MESSAGE_LIMITE_FREQUENCE
    statut, corps = _requete_api(serveur_test, "verifier_mot", "ABC")
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_LIMITE_FREQUENCE}


def test_serveur_limite_la_frequence_de_verifier_coup(serveur_test):
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    max_minute, _ = LIMITES_FREQUENCE["verifier_coup"]
    for _ in range(max_minute):
        statut, corps = _requete_api(serveur_test, "verifier_coup")
        assert statut == 200
        assert corps["resultat"].get("erreur") != MESSAGE_LIMITE_FREQUENCE
    statut, corps = _requete_api(serveur_test, "verifier_coup")
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_LIMITE_FREQUENCE}


def test_serveur_limite_la_frequence_de_poser_mot(serveur_test):
    """Issue #483 : ``poser_mot`` est le même oracle accepté/refusé que
    ``verifier_coup`` — reprend donc exactement les mêmes plafonds, et chaque
    appel compte qu'il soit accepté ou refusé. Aucune lettre n'est posée via
    ``poser_lettre_en_attente`` ici : ``_en_attente`` reste vide, donc chaque
    appel est un refus « rien à jouer », sans jamais muter la partie — ce qui
    permet d'enchaîner les appels sans se soucier de l'état du plateau."""
    _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
    max_minute, _ = LIMITES_FREQUENCE["poser_mot"]
    for _ in range(max_minute):
        statut, corps = _requete_api(serveur_test, "poser_mot")
        assert statut == 200
        assert corps["resultat"].get("erreur") != MESSAGE_LIMITE_FREQUENCE
    statut, corps = _requete_api(serveur_test, "poser_mot")
    assert statut == 200
    assert corps["resultat"] == {"succes": False, "erreur": MESSAGE_LIMITE_FREQUENCE}


def test_poser_mot_et_verifier_coup_partagent_les_memes_plafonds(serveur_test):
    """Plafonds identiques, exigés explicitement par l'issue #483 (pas de
    seconde implémentation, mêmes limites que ``verifier_coup``)."""
    assert LIMITES_FREQUENCE["poser_mot"] == LIMITES_FREQUENCE["verifier_coup"]


# -- Point 5 — journal des abus, jamais les arguments ----------------------- #


def test_journal_abus_ne_contient_jamais_les_arguments(tmp_path, serveur_test):
    journal.demarrer_session(dossier=tmp_path)
    try:
        _requete_api(serveur_test, "rechercher_mot", "MOTSECRETINTERDIT")
        _charger_partie_test(serveur_test, ("A", "B", "C", "D", "E", "F", "G"))
        _requete_api(
            serveur_test, "poser_lettre_en_attente", 7, 7, "ZEBRECACHE", False, 10, 0
        )
        max_minute, _ = LIMITES_FREQUENCE["verifier_mot"]
        for _ in range(max_minute + 1):
            _requete_api(serveur_test, "verifier_mot", "AUTREMOTCACHE")
        # Lu AVANT la clôture : une session sans entrée de niveau « erreur »
        # (le cas ici — ``journal.info`` seulement) voit son fichier supprimé
        # par ``Journal.cloturer`` (politique de rétention, voir journal.py).
        contenu = journal.session_courante().chemin.read_text(encoding="utf-8")
    finally:
        journal.cloturer_session()
    assert "MOTSECRETINTERDIT" not in contenu
    assert "ZEBRECACHE" not in contenu
    assert "AUTREMOTCACHE" not in contenu
    assert "rechercher_mot" in contenu
    assert "poser_lettre_en_attente" in contenu
    assert "verifier_mot" in contenu
