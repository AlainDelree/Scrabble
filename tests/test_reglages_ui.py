"""Tests de l'API Python de la fenêtre de réglages (``scrabble.ui.reglages``).

On teste l'adaptateur ``ApiReglages`` (js_api) **sans lancer pywebview** : les
méthodes sont appelées directement, et les fonctions de domaine sous-jacentes
(``modifier_reglage`` de ``config``/``reglages``, ``rechercher_statut`` /
``modifier_appartenance`` du dictionnaire) sont remplacées par des doublures pour
ne toucher ni ``config.json`` ni les vrais fichiers du dictionnaire (le dépliage
Hunspell réel serait de toute façon trop coûteux ici).
"""

from __future__ import annotations

import scrabble.ui.reglages as r
from scrabble.ui.reglages import ApiReglages


# --------------------------------------------------------------------------- #
# Onglet Général
# --------------------------------------------------------------------------- #

def test_obtenir_reglages_generaux_structure():
    """Renvoie les valeurs courantes + les options des menus (thèmes/sources)."""
    api = ApiReglages()
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


def test_enregistrer_reglage_delegue_a_modifier_reglage(monkeypatch):
    """Un réglage valide passe par ``modifier_reglage`` et renvoie la valeur retenue."""
    appels = {}

    def faux_modifier(cle, valeur):
        appels[cle] = valeur
        return valeur

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiReglages().enregistrer_reglage("theme_plateau", "vert")

    assert res == {"succes": True, "valeur": "vert"}
    assert appels == {"theme_plateau": "vert"}


def test_enregistrer_reglage_source_invalide_refusee(monkeypatch):
    """Une source de dictionnaire inconnue est rejetée sans écriture."""
    def interdit(*args, **kwargs):  # pragma: no cover - ne doit pas être appelé
        raise AssertionError("modifier_reglage ne doit pas être appelé.")

    monkeypatch.setattr(r, "modifier_reglage", interdit)

    res = ApiReglages().enregistrer_reglage("source_dictionnaire", "klingon")

    assert res["succes"] is False
    assert "klingon" in res["erreur"]


def test_enregistrer_reglage_cle_inconnue(monkeypatch):
    """Une clé inconnue remonte proprement une erreur (KeyError → message)."""
    def faux_modifier(cle, valeur):
        raise KeyError(cle)

    monkeypatch.setattr(r, "modifier_reglage", faux_modifier)

    res = ApiReglages().enregistrer_reglage("cle_bidon", "x")

    assert res["succes"] is False


# --------------------------------------------------------------------------- #
# Onglet Dictionnaire
# --------------------------------------------------------------------------- #

def test_rechercher_mot_ajoute_le_drapeau_succes(monkeypatch):
    """Le statut renvoyé par le domaine est complété d'un ``succes`` True."""
    monkeypatch.setattr(
        r, "rechercher_statut", lambda mot: {"mot": "CHAT", "sources": {}}
    )

    res = ApiReglages().rechercher_mot("chat")

    assert res["succes"] is True
    assert res["mot"] == "CHAT"


def test_rechercher_mot_erreur_encapsulee(monkeypatch):
    """Une exception du domaine est encapsulée en ``{succes: False, erreur}``."""
    def boom(mot):
        raise RuntimeError("spylls manquant")

    monkeypatch.setattr(r, "rechercher_statut", boom)

    res = ApiReglages().rechercher_mot("chat")

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

    res = ApiReglages().ajouter_mot("chat", "ods")

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

    res = ApiReglages().retirer_mot("chat", "ods")

    assert res["succes"] is True
    assert appels["present"] is False


def test_modifier_mot_invalide_encapsule_valueerror(monkeypatch):
    """Un mot rejeté par le domaine (ValueError) donne ``{succes: False}``."""
    def faux_modifier(mot, source, present):
        raise ValueError("mot non jouable")

    monkeypatch.setattr(r, "modifier_appartenance", faux_modifier)

    res = ApiReglages().ajouter_mot("ch1en", "ods")

    assert res["succes"] is False
    assert "non jouable" in res["erreur"]


# --------------------------------------------------------------------------- #
# Fermeture
# --------------------------------------------------------------------------- #

def test_fermer_fenetre_sans_fenetre():
    """Sans fenêtre associée, la fermeture renvoie un échec explicite."""
    res = ApiReglages().fermer_fenetre()
    assert res["succes"] is False


def test_fermer_fenetre_appelle_destroy():
    """Avec une fenêtre, la fermeture appelle ``destroy`` et renvoie un succès."""
    class FausseFenetre:
        def __init__(self):
            self.detruite = False

        def destroy(self):
            self.detruite = True

    api = ApiReglages()
    fenetre = FausseFenetre()
    api.set_window(fenetre)

    res = api.fermer_fenetre()

    assert res == {"succes": True}
    assert fenetre.detruite is True
