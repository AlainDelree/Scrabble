"""Tests de l'API Réglages, désormais portée par l'accueil (``scrabble.ui.accueil``).

Depuis l'issue #169, les réglages ne sont plus une fenêtre pywebview autonome
(``ui/reglages.py`` supprimé) mais un panneau intégré à la fenêtre d'accueil :
les méthodes de l'ex-``ApiReglages`` ont été migrées telles quelles dans
``ApiAccueil``. On les teste ici **sans lancer pywebview** : les méthodes sont
appelées directement, et les fonctions de domaine sous-jacentes
(``modifier_reglage`` de ``config``/``reglages``, ``rechercher_statut`` /
``modifier_appartenance`` du dictionnaire) sont remplacées par des doublures pour
ne toucher ni ``config.json`` ni les vrais fichiers du dictionnaire (le dépliage
Hunspell réel serait de toute façon trop coûteux ici).
"""

from __future__ import annotations

import scrabble.ui.accueil as r
from scrabble.ui.accueil import ApiAccueil


# --------------------------------------------------------------------------- #
# Onglet Général
# --------------------------------------------------------------------------- #

def test_obtenir_reglages_generaux_structure():
    """Renvoie les valeurs courantes + les options des menus (thèmes/sources)."""
    api = ApiAccueil()
    data = api.obtenir_reglages_generaux()

    assert set(data) >= {
        "prenom_principal",
        "theme_plateau",
        "source_dictionnaire",
        "themes",
        "sources",
    }
    # Chaque option est un couple {valeur, libelle} exploitable tel quel par le JS.
    assert all({"valeur", "libelle"} <= set(o) for o in data["themes"])
    valeurs_sources = {o["valeur"] for o in data["sources"]}
    assert valeurs_sources == {"ods", "hunspell"}


def test_obtenir_reglages_generaux_expose_avatars():
    """La grille d'avatars (issue #143) est livrée avec l'avatar courant."""
    from scrabble.config import AVATARS_DISPONIBLES

    data = ApiAccueil().obtenir_reglages_generaux()

    assert "avatar_principal" in data
    # Chaque vignette est un couple {valeur, image} exploitable tel quel par le JS.
    assert all({"valeur", "image"} <= set(a) for a in data["avatars"])
    valeurs = [a["valeur"] for a in data["avatars"]]
    assert valeurs == list(AVATARS_DISPONIBLES)
    # Le chemin d'image pointe vers le SVG servi par la page web.
    assert data["avatars"][0]["image"] == f"avatars/{AVATARS_DISPONIBLES[0]}.svg"


def test_enregistrer_avatar_principal_delegue(monkeypatch):
    """Choisir un avatar passe par ``modifier_reglage`` (clé avatar_principal)."""
    appels = {}

    def faux_modifier(cle, valeur):
        appels[cle] = valeur
        return valeur

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiAccueil().enregistrer_reglage("avatar_principal", "avatar-07")

    assert res == {"succes": True, "valeur": "avatar-07"}
    assert appels == {"avatar_principal": "avatar-07"}


def test_enregistrer_reglage_delegue_a_modifier_reglage(monkeypatch):
    """Un réglage valide passe par ``modifier_reglage`` et renvoie la valeur retenue."""
    appels = {}

    def faux_modifier(cle, valeur):
        appels[cle] = valeur
        return valeur

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiAccueil().enregistrer_reglage("theme_plateau", "vert")

    assert res == {"succes": True, "valeur": "vert"}
    assert appels == {"theme_plateau": "vert"}


def test_enregistrer_reglage_booleen_transmis_tel_quel(monkeypatch):
    """Un réglage booléen (bonus_fin_partie) est transmis comme vrai booléen."""
    appels = {}

    def faux_modifier(cle, valeur):
        appels[cle] = valeur
        return valeur

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiAccueil().enregistrer_reglage("bonus_fin_partie", True)

    assert res == {"succes": True, "valeur": True}
    assert appels == {"bonus_fin_partie": True}


def test_obtenir_reglages_generaux_expose_bonus_fin_partie(monkeypatch):
    """La structure renvoyée expose bonus_fin_partie sous forme de booléen."""
    monkeypatch.setattr(r, "lire_reglage", lambda cle: True if cle == "bonus_fin_partie" else "")

    data = ApiAccueil().obtenir_reglages_generaux()

    assert data["bonus_fin_partie"] is True


def test_obtenir_reglages_generaux_expose_vocabulaire_humain(monkeypatch):
    """La structure expose vocabulaire_humain sous forme de booléen (issue #206)."""
    monkeypatch.setattr(
        r, "lire_reglage",
        lambda cle: True if cle == "vocabulaire_humain" else "",
    )

    data = ApiAccueil().obtenir_reglages_generaux()

    assert data["vocabulaire_humain"] is True


def test_obtenir_reglages_generaux_expose_type_echange(monkeypatch):
    """La structure expose type_echange + les options complet/partiel (issue #138)."""
    monkeypatch.setattr(
        r, "lire_reglage",
        lambda cle: "partiel" if cle == "type_echange" else "",
    )

    data = ApiAccueil().obtenir_reglages_generaux()

    assert data["type_echange"] == "partiel"
    valeurs = {o["valeur"] for o in data["types_echange"]}
    assert valeurs == {"complet", "partiel"}
    assert all({"valeur", "libelle"} <= set(o) for o in data["types_echange"])


def test_enregistrer_type_echange_delegue(monkeypatch):
    """type_echange (chaîne à choix fini) passe par modifier_reglage sans cas spécial."""
    appels = {}

    def faux_modifier(cle, valeur):
        appels[cle] = valeur
        return valeur

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiAccueil().enregistrer_reglage("type_echange", "partiel")

    assert res == {"succes": True, "valeur": "partiel"}
    assert appels == {"type_echange": "partiel"}


def test_enregistrer_reglage_source_invalide_refusee(monkeypatch):
    """Une source de dictionnaire inconnue est rejetée sans écriture."""
    def interdit(*args, **kwargs):  # pragma: no cover - ne doit pas être appelé
        raise AssertionError("modifier_reglage ne doit pas être appelé.")

    monkeypatch.setattr(r, "modifier_reglage", interdit)

    res = ApiAccueil().enregistrer_reglage("source_dictionnaire", "klingon")

    assert res["succes"] is False
    assert "klingon" in res["erreur"]


def test_enregistrer_reglage_cle_inconnue(monkeypatch):
    """Une clé inconnue remonte proprement une erreur (KeyError → message)."""
    def faux_modifier(cle, valeur):
        raise KeyError(cle)

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiAccueil().enregistrer_reglage("cle_bidon", "x")

    assert res["succes"] is False


# --------------------------------------------------------------------------- #
# Onglet Dictionnaire
# --------------------------------------------------------------------------- #

def test_rechercher_mot_ajoute_le_drapeau_succes(monkeypatch):
    """Le statut renvoyé par le domaine est complété d'un ``succes`` True."""
    monkeypatch.setattr(
        r, "rechercher_statut", lambda mot: {"mot": "CHAT", "sources": {}}
    )

    res = ApiAccueil().rechercher_mot("chat")

    assert res["succes"] is True
    assert res["mot"] == "CHAT"


def test_rechercher_mot_erreur_encapsulee(monkeypatch):
    """Une exception du domaine est encapsulée en ``{succes: False, erreur}``."""
    def boom(mot):
        raise RuntimeError("spylls manquant")

    monkeypatch.setattr(r, "rechercher_statut", boom)

    res = ApiAccueil().rechercher_mot("chat")

    assert res["succes"] is False
    assert "spylls" in res["erreur"]


def test_ajouter_mot_applique_et_rafraichit(monkeypatch):
    """Ajouter délègue à ``modifier_appartenance`` puis renvoie le statut à jour."""
    appels = {}

    def faux_modifier(mot, source, present):
        appels["args"] = (mot, source, present)
        return "CHAT"

    monkeypatch.setattr(r, "modifier_appartenance", faux_modifier)
    monkeypatch.setattr(
        r, "rechercher_statut", lambda mot: {"mot": mot, "sources": {}}
    )

    res = ApiAccueil().ajouter_mot("chat", "ods")

    assert res["succes"] is True
    assert appels["args"] == ("chat", "ods", True)


def test_retirer_mot_present_false(monkeypatch):
    """Retirer appelle ``modifier_appartenance`` avec ``present=False``."""
    appels = {}

    def faux_modifier(mot, source, present):
        appels["present"] = present
        return "CHAT"

    monkeypatch.setattr(r, "modifier_appartenance", faux_modifier)
    monkeypatch.setattr(
        r, "rechercher_statut", lambda mot: {"mot": mot, "sources": {}}
    )

    res = ApiAccueil().retirer_mot("chat", "ods")

    assert res["succes"] is True
    assert appels["present"] is False


def test_modifier_mot_invalide_encapsule_valueerror(monkeypatch):
    """Un mot rejeté par le domaine (ValueError) donne ``{succes: False}``."""
    def faux_modifier(mot, source, present):
        raise ValueError("mot non jouable")

    monkeypatch.setattr(r, "modifier_appartenance", faux_modifier)

    res = ApiAccueil().ajouter_mot("ch1en", "ods")

    assert res["succes"] is False
    assert "non jouable" in res["erreur"]


# --------------------------------------------------------------------------- #
# Statut « classique du jeu » (issue #204)
# --------------------------------------------------------------------------- #

def test_marquer_classique_mot_delegue_et_rafraichit(monkeypatch):
    """Marquer classique délègue à ``marquer_classique`` puis renvoie le statut."""
    appels = {}

    def faux_marquer(mot, present):
        appels["args"] = (mot, present)
        return "WU"

    monkeypatch.setattr(r, "marquer_classique", faux_marquer)
    monkeypatch.setattr(
        r, "rechercher_statut",
        lambda mot: {"mot": mot, "sources": {}, "classique": {"classique": True}},
    )

    res = ApiAccueil().marquer_classique_mot("wu", True)

    assert res["succes"] is True
    assert appels["args"] == ("wu", True)
    assert res["classique"]["classique"] is True


def test_marquer_classique_mot_refus_encapsule_valueerror(monkeypatch):
    """Un marquage refusé (mot absent des deux sources) donne succes False."""
    def faux_marquer(mot, present):
        raise ValueError("n'existe dans aucune source")

    monkeypatch.setattr(r, "marquer_classique", faux_marquer)

    res = ApiAccueil().marquer_classique_mot("zorglub", True)

    assert res["succes"] is False
    assert "aucune source" in res["erreur"]


# --------------------------------------------------------------------------- #
# Fermeture
# --------------------------------------------------------------------------- #

def test_fermer_fenetre_sans_fenetre():
    """Sans fenêtre associée, la fermeture renvoie un échec explicite."""
    res = ApiAccueil().fermer_fenetre()
    assert res["succes"] is False


def test_fermer_fenetre_appelle_destroy():
    """Avec une fenêtre, la fermeture appelle ``destroy`` et renvoie un succès."""
    class FausseFenetre:
        def __init__(self):
            self.detruite = False

        def destroy(self):
            self.detruite = True

    api = ApiAccueil()
    fenetre = FausseFenetre()
    api.set_window(fenetre)

    res = api.fermer_fenetre()

    assert res == {"succes": True}
    assert fenetre.detruite is True
