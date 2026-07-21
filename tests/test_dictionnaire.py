"""Tests du module dictionnaire (``scrabble.dictionnaire.dictionnaire``).

Ces tests n'utilisent **jamais** les vrais fichiers ODS/Hunspell : ils
construisent de petits dictionnaires factices dans des fichiers temporaires
(``tmp_path``). Le dépliage Hunspell réel (via ``spylls``) n'est donc pas
exercé ici — seule la chaîne de construction (union/soustraction, Trie, cache)
et la normalisation sont testées de façon déterministe et rapide.
"""

from __future__ import annotations

import json
import os
import time

import pytest

import scrabble.dictionnaire.dictionnaire as d
from scrabble.dictionnaire.dictionnaire import (
    CHEMINS_MODIFS,
    Dictionnaire,
    Trie,
    assurer_fichiers_modifs,
    charger_definitions,
    charger_ods,
    chemins_modifs,
    construire_ensemble_mots,
    construire_trie,
    definition_mot,
    desaccentuer,
    est_mot_scrabble,
    lire_liste_mots,
    marquer_classique,
    modifier_appartenance,
    mot_existe_dans_une_source,
    normaliser_mot,
    obtenir_trie,
    rechercher_statut,
    statut_classique,
    statut_source,
)


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

def test_normalisation_majuscules_et_espaces():
    """Passage en MAJUSCULES et suppression des espaces superflus."""
    assert normaliser_mot("  chat  ") == "CHAT"
    assert normaliser_mot("Chien") == "CHIEN"


def test_normalisation_conserve_les_accents():
    """Le Scrabble francophone distingue les mots accentués : on les garde."""
    assert normaliser_mot("élève") == "ÉLÈVE"
    assert normaliser_mot("ELEVE") != normaliser_mot("élève")


def test_normalisation_chaine_vide():
    """Une ligne ne contenant que des espaces se normalise en chaîne vide."""
    assert normaliser_mot("   ") == ""
    assert normaliser_mot("\n") == ""


def test_normalisation_nfc():
    """Formes précomposée et combinante d'un accent sont unifiées (NFC)."""
    precompose = "É"          # U+00C9
    combinant = "É"     # E + accent aigu combinant
    assert normaliser_mot(precompose) == normaliser_mot(combinant)


# --------------------------------------------------------------------------- #
# Filtre alphabétique du dépliage Hunspell (issue #7, suite de #4)
# --------------------------------------------------------------------------- #

def test_est_mot_scrabble_accepte_les_formes_alphabetiques():
    """Un mot fait uniquement de lettres jouables (accents inclus) passe."""
    assert est_mot_scrabble("MANGEONS")
    assert est_mot_scrabble("BELLES")
    assert est_mot_scrabble("ÉLÈVE")       # voyelles accentuées usuelles
    assert est_mot_scrabble("CŒUR")        # ligature Œ
    assert est_mot_scrabble("NÆVUS")       # ligature Æ
    assert est_mot_scrabble("FRANÇAIS")    # cédille


def test_est_mot_scrabble_rejette_apostrophes_traits_union_chiffres():
    """Les formes bruitées du dépliage Hunspell sont écartées."""
    assert not est_mot_scrabble("QU'IL")        # élision avec apostrophe
    assert not est_mot_scrabble("QU’IL")        # apostrophe typographique
    assert not est_mot_scrabble("ARC-EN-CIEL")  # trait d'union
    assert not est_mot_scrabble("H2O")          # chiffre
    assert not est_mot_scrabble("2E")           # ordinal
    assert not est_mot_scrabble("ΑΛΦΑ")         # lettres grecques
    assert not est_mot_scrabble("CAÑON")        # lettre étrangère (ñ)
    assert not est_mot_scrabble("")             # chaîne vide
    assert not est_mot_scrabble("MOT SUIVI")    # espace interne


def test_est_mot_scrabble_ne_garde_que_la_forme_alphabetique():
    """Sur un lot mêlé, seule la forme purement alphabétique/accentuée passe."""
    candidats = ["ÉLÈVE", "QU'IL", "ARC-EN-CIEL", "H2O", "CŒUR"]
    conserves = [mot for mot in candidats if est_mot_scrabble(mot)]

    assert conserves == ["ÉLÈVE", "CŒUR"]


# --------------------------------------------------------------------------- #
# Lecture des listes de mots (un mot par ligne)
# --------------------------------------------------------------------------- #

def _ecrire_liste(chemin, mots):
    chemin.write_text("\n".join(mots) + "\n", encoding="utf-8")


def test_lire_liste_mots_normalise_et_ignore_les_vides(tmp_path):
    """Casse normalisée, lignes vides ignorées, doublons dédupliqués."""
    fichier = tmp_path / "liste.txt"
    fichier.write_text("chat\n\nCHAT\n  chien  \n\n", encoding="utf-8")

    mots = lire_liste_mots(fichier)

    assert mots == {"CHAT", "CHIEN"}


def test_lire_liste_mots_fichier_absent(tmp_path):
    """Un fichier inexistant donne un ensemble vide, sans erreur."""
    assert lire_liste_mots(tmp_path / "absent.txt") == set()


def test_charger_ods_lit_un_mot_par_ligne(tmp_path):
    """``charger_ods`` lit une liste ODS factice normalisée."""
    fichier = tmp_path / "ods.txt"
    _ecrire_liste(fichier, ["chat", "chien", "OISEAU"])

    assert charger_ods(fichier) == {"CHAT", "CHIEN", "OISEAU"}


def test_chemins_modifs_par_source(tmp_path):
    """Chaque source a sa propre paire de fichiers d'ajouts/retraits (issue #110)."""
    ajoutes_ods, retires_ods = chemins_modifs("ods")
    ajoutes_hun, retires_hun = chemins_modifs("hunspell")

    assert ajoutes_ods.name == "mots_ajoutes_ods.txt"
    assert retires_ods.name == "mots_retires_ods.txt"
    assert ajoutes_hun.name == "mots_ajoutes_hunspell.txt"
    assert retires_hun.name == "mots_retires_hunspell.txt"
    # Les deux sources pointent vers des fichiers distincts (pas de partage).
    assert {ajoutes_ods, retires_ods}.isdisjoint({ajoutes_hun, retires_hun})


def test_chemins_modifs_source_inconnue_retombe_sur_ods():
    """Une source inattendue retombe sur la paire ODS (robustesse)."""
    assert chemins_modifs("valeur_bidon") == CHEMINS_MODIFS["ods"]


def test_construire_trie_utilise_les_fichiers_de_la_source(tmp_path, monkeypatch):
    """Sans chemins explicites, ``construire_trie`` prend la paire de la source.

    On détourne ``CHEMINS_MODIFS`` vers des fichiers temporaires pour vérifier
    que l'ajout propre à ODS est bien appliqué, sans toucher aux vrais fichiers.
    """
    import scrabble.dictionnaire.dictionnaire as d

    chemin_ods = tmp_path / "ods.txt"
    _ecrire_liste(chemin_ods, ["chat"])
    ajoutes_ods = tmp_path / "mots_ajoutes_ods.txt"
    _ecrire_liste(ajoutes_ods, ["oiseau"])
    retires_ods = tmp_path / "mots_retires_ods.txt"
    _ecrire_liste(retires_ods, [""])
    monkeypatch.setitem(d.CHEMINS_MODIFS, "ods", (ajoutes_ods, retires_ods))

    trie = construire_trie(source="ods", chemin_ods=chemin_ods)

    assert "CHAT" in trie
    assert "OISEAU" in trie           # provient de la paire ODS résolue par défaut


def test_assurer_fichiers_modifs_cree_les_fichiers_vides(tmp_path):
    """Les fichiers d'ajouts/retraits sont créés vides s'ils manquent."""
    ajoutes = tmp_path / "sous" / "mots_ajoutes.txt"
    retires = tmp_path / "sous" / "mots_retires.txt"

    assurer_fichiers_modifs(ajoutes, retires)

    assert ajoutes.exists() and ajoutes.read_text(encoding="utf-8") == ""
    assert retires.exists() and retires.read_text(encoding="utf-8") == ""


# --------------------------------------------------------------------------- #
# Union / soustraction
# --------------------------------------------------------------------------- #

def test_construire_ensemble_union_puis_soustraction():
    """(source ∪ ajoutes) − retires, dans cet ordre."""
    source = {"CHAT", "CHIEN"}
    ajoutes = {"OISEAU", "CHAT"}      # CHAT déjà présent : union idempotente
    retires = {"CHIEN"}

    resultat = construire_ensemble_mots(source, ajoutes, retires)

    assert resultat == {"CHAT", "OISEAU"}


def test_soustraction_prioritaire_sur_ajout():
    """Un mot à la fois ajouté et retiré est absent (retrait prioritaire)."""
    resultat = construire_ensemble_mots({"CHAT"}, {"OISEAU"}, {"OISEAU"})

    assert resultat == {"CHAT"}


def test_retrait_d_un_mot_source():
    """Un mot de la source figurant dans les retraits disparaît."""
    resultat = construire_ensemble_mots({"CHAT", "CHIEN"}, set(), {"CHAT"})

    assert resultat == {"CHIEN"}


# --------------------------------------------------------------------------- #
# Trie
# --------------------------------------------------------------------------- #

def test_trie_contient_et_taille():
    """Insertion, appartenance et comptage sans doublon."""
    trie = Trie.depuis_iterable(["CHAT", "CHIEN", "CHAT"])

    assert "CHAT" in trie
    assert "CHIEN" in trie
    assert "CHA" not in trie          # préfixe non terminal
    assert "CHATS" not in trie        # dépasse un mot existant
    assert len(trie) == 2


def test_trie_mot_vide_ignore():
    """Insérer une chaîne vide n'ajoute rien."""
    trie = Trie()
    trie.inserer("")

    assert len(trie) == 0
    assert "" not in trie


def test_dictionnaire_mot_valide_normalise_l_entree():
    """``mot_valide`` normalise l'entrée avant de consulter le Trie."""
    dico = Dictionnaire(Trie.depuis_iterable(["CHAT", "ÉLÈVE"]))

    assert dico.mot_valide("chat")
    assert dico.mot_valide("  Chat ")
    assert dico.mot_valide("élève")
    assert not dico.mot_valide("eleve")   # accents distincts
    assert not dico.mot_valide("zzz")


# --------------------------------------------------------------------------- #
# Construction complète (source ODS factice) + validation
# --------------------------------------------------------------------------- #

def _preparer_dico(tmp_path, source_mots, ajoutes=(), retires=()):
    """Crée les fichiers ODS/ajouts/retraits factices et renvoie les chemins."""
    chemin_ods = tmp_path / "ods.txt"
    _ecrire_liste(chemin_ods, source_mots)
    chemin_ajoutes = tmp_path / "mots_ajoutes.txt"
    _ecrire_liste(chemin_ajoutes, ajoutes or [""])
    chemin_retires = tmp_path / "mots_retires.txt"
    _ecrire_liste(chemin_retires, retires or [""])
    return chemin_ods, chemin_ajoutes, chemin_retires


def test_construire_trie_bout_en_bout(tmp_path):
    """Chaîne complète en source ODS : union/soustraction + normalisation."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path,
        source_mots=["chat", "chien", "poisson"],
        ajoutes=["oiseau"],
        retires=["chien"],
    )

    trie = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
    )

    assert "CHAT" in trie
    assert "OISEAU" in trie           # ajouté
    assert "CHIEN" not in trie        # retiré
    assert len(trie) == 3             # CHAT, POISSON, OISEAU


def test_source_inconnue_retombe_sur_ods(tmp_path):
    """Une source inattendue retombe sur l'ODS (robustesse)."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )

    trie = construire_trie(
        source="valeur_bidon",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
    )

    assert "CHAT" in trie


# --------------------------------------------------------------------------- #
# Définitions (index mot → liste de définitions), issue #15
# --------------------------------------------------------------------------- #

def test_charger_definitions_fichier_present(tmp_path):
    """Un fichier ``definitions.json`` présent est lu et renvoyé tel quel."""
    fichier = tmp_path / "definitions.json"
    fichier.write_text(
        json.dumps({"CHAT": ["Petit félin domestique."]}, ensure_ascii=False),
        encoding="utf-8",
    )

    definitions = charger_definitions(fichier)

    assert definitions == {"CHAT": ["Petit félin domestique."]}


def test_charger_definitions_fichier_absent(tmp_path):
    """Fichier absent : dict vide, sans erreur (le jeu reste jouable)."""
    assert charger_definitions(tmp_path / "absent.json") == {}


def test_charger_definitions_mot_avec_plusieurs_definitions(tmp_path):
    """Un mot homographe porte plusieurs définitions fusionnées en liste."""
    fichier = tmp_path / "definitions.json"
    fichier.write_text(
        json.dumps(
            {"LIRE": ["Interpréter un texte écrit.", "Ancienne monnaie italienne."]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    definitions = charger_definitions(fichier)

    assert definitions["LIRE"] == [
        "Interpréter un texte écrit.",
        "Ancienne monnaie italienne.",
    ]


def test_charger_definitions_mot_ascii_sans_accent(tmp_path):
    """Une clé ODS8 purement ASCII (ex. ``ELEVE``) est lue telle quelle.

    Depuis l'issue #18, le matching est désaccentué mais la CLÉ stockée reste
    le mot ODS8 (ASCII) : ``definitions.json`` contient donc des entrées comme
    ``ELEVE`` (sans accent), dont la définition provient du lemme accentué
    ``ÉLÈVE``. L'interface reste un simple dict mot → liste de définitions.
    """
    fichier = tmp_path / "definitions.json"
    fichier.write_text(
        json.dumps(
            {"ELEVE": ["Personne qui reçoit un enseignement.", "Nourri, engraissé."]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    definitions = charger_definitions(fichier)

    assert definitions["ELEVE"] == [
        "Personne qui reçoit un enseignement.",
        "Nourri, engraissé.",
    ]


def test_charger_definitions_json_invalide(tmp_path):
    """Un JSON illisible retombe sur un dict vide plutôt que de planter."""
    fichier = tmp_path / "definitions.json"
    fichier.write_text("{ ceci n'est pas du json", encoding="utf-8")

    assert charger_definitions(fichier) == {}


# --------------------------------------------------------------------------- #
# Cache disque : reconstruction et invalidation
# --------------------------------------------------------------------------- #

def test_cache_ecrit_et_relu(tmp_path):
    """Le premier appel écrit le cache, le second le relit tel quel."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat", "chien"]
    )
    chemin_cache = tmp_path / "trie_cache.pkl"

    kwargs = dict(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        chemin_cache=chemin_cache,
    )

    trie1 = obtenir_trie(**kwargs)
    assert chemin_cache.exists()
    mtime_cache = chemin_cache.stat().st_mtime_ns

    trie2 = obtenir_trie(**kwargs)
    # Cache non périmé : pas de réécriture (mtime inchangé).
    assert chemin_cache.stat().st_mtime_ns == mtime_cache
    assert "CHAT" in trie1 and "CHAT" in trie2


def test_cache_invalide_si_source_modifiee(tmp_path):
    """Modifier un fichier source après le cache force une reconstruction."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    chemin_cache = tmp_path / "trie_cache.pkl"
    kwargs = dict(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        chemin_cache=chemin_cache,
    )

    trie1 = obtenir_trie(**kwargs)
    assert "OISEAU" not in trie1

    # On modifie la source ET on rend son mtime postérieur au cache, sans
    # dépendre de la résolution d'horloge (mtime forcé à cache + 10 s).
    _ecrire_liste(chemin_ods, ["chat", "oiseau"])
    futur = chemin_cache.stat().st_mtime + 10
    os.utime(chemin_ods, (futur, futur))

    trie2 = obtenir_trie(**kwargs)

    assert "OISEAU" in trie2           # cache invalidé, dictionnaire reconstruit


def test_cache_invalide_si_source_configuree_change(tmp_path):
    """Changer la source (ods → hunspell) invalide le cache existant."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    # Fichiers hunspell factices : jamais lus car le cache doit d'abord être
    # jugé invalide sur le seul critère « source différente ». Pour éviter tout
    # dépliage réel, on garde source="ods" au 1er appel puis on vérifie que
    # _cache_valide rejette une source distincte via l'en-tête.
    chemin_cache = tmp_path / "trie_cache.pkl"
    obtenir_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        chemin_cache=chemin_cache,
    )

    from scrabble.dictionnaire.dictionnaire import _cache_valide, _sources_pertinentes

    sources_ods = _sources_pertinentes(
        "ods", chemin_ods, tmp_path / "base", chemin_ajoutes, chemin_retires
    )
    assert _cache_valide(chemin_cache, "ods", sources_ods) is True
    # Même cache, source demandée différente → invalide.
    assert _cache_valide(chemin_cache, "hunspell", sources_ods) is False


# --------------------------------------------------------------------------- #
# Désaccentuation + définitions (issue #111, onglet Dictionnaire)
# --------------------------------------------------------------------------- #

def test_desaccentuer_accents_et_ligatures():
    """Reproduit la graphie ASCII des clés de definitions.json (issue #111)."""
    assert desaccentuer("ÉLÈVE") == "ELEVE"
    assert desaccentuer("CŒUR") == "COEUR"
    assert desaccentuer("EX ÆQUO".replace(" ", "")) == "EXAEQUO"
    assert desaccentuer("CHAT") == "CHAT"


def test_definition_mot_desaccentue_la_requete(tmp_path):
    """Un mot accentué retrouve sa définition indexée en ASCII désaccentué."""
    fichier = tmp_path / "definitions.json"
    fichier.write_text(
        json.dumps({"ELEVE": ["Personne qui reçoit un enseignement."]}),
        encoding="utf-8",
    )
    assert definition_mot("élève", fichier) == [
        "Personne qui reçoit un enseignement."
    ]


def test_definition_mot_absent_renvoie_none(tmp_path):
    """Un mot hors index (ou fichier absent) renvoie None, pas d'erreur."""
    fichier = tmp_path / "definitions.json"
    fichier.write_text(json.dumps({"CHAT": ["Félin."]}), encoding="utf-8")
    assert definition_mot("CHIEN", fichier) is None
    assert definition_mot("CHAT", tmp_path / "absent.json") is None
    assert definition_mot("", fichier) is None


# --------------------------------------------------------------------------- #
# Statut par source + personnalisation manuelle (issue #111)
# --------------------------------------------------------------------------- #

def _preparer_source_modifs(tmp_path, monkeypatch, mots_source, ajoutes=(), retires=()):
    """Prépare une source ODS et sa paire de fichiers de modif dans tmp_path."""
    chemin_ods = tmp_path / "ods.txt"
    chemin_ods.write_text("\n".join(mots_source) + "\n", encoding="utf-8")
    ajoutes_p = tmp_path / "mots_ajoutes_ods.txt"
    retires_p = tmp_path / "mots_retires_ods.txt"
    ajoutes_p.write_text("\n".join(ajoutes), encoding="utf-8")
    retires_p.write_text("\n".join(retires), encoding="utf-8")
    monkeypatch.setitem(d.CHEMINS_MODIFS, "ods", (ajoutes_p, retires_p))
    return chemin_ods


def test_statut_source_present_dorigine(tmp_path, monkeypatch):
    """Un mot brut de l'ODS est présent, sans personnalisation manuelle."""
    chemin_ods = _preparer_source_modifs(tmp_path, monkeypatch, ["CHAT", "CHIEN"])
    statut = statut_source("CHAT", "ods", chemin_ods=chemin_ods)
    assert statut["present_brut"] is True
    assert statut["present"] is True
    assert statut["ajout_manuel"] is False
    assert statut["retrait_manuel"] is False
    assert statut["indisponible"] is False


def test_statut_source_ajout_manuel(tmp_path, monkeypatch):
    """Un mot absent de l'ODS mais ajouté manuellement devient présent."""
    chemin_ods = _preparer_source_modifs(
        tmp_path, monkeypatch, ["CHAT"], ajoutes=["ZORGLUB"]
    )
    statut = statut_source("ZORGLUB", "ods", chemin_ods=chemin_ods)
    assert statut["present_brut"] is False
    assert statut["ajout_manuel"] is True
    assert statut["present"] is True


def test_statut_source_retrait_manuel(tmp_path, monkeypatch):
    """Un mot brut de l'ODS retiré manuellement devient absent."""
    chemin_ods = _preparer_source_modifs(
        tmp_path, monkeypatch, ["CHAT"], retires=["CHAT"]
    )
    statut = statut_source("CHAT", "ods", chemin_ods=chemin_ods)
    assert statut["present_brut"] is True
    assert statut["retrait_manuel"] is True
    assert statut["present"] is False


def test_statut_source_hunspell_indisponible(tmp_path, monkeypatch):
    """Une source Hunspell introuvable est signalée indisponible sans planter."""
    monkeypatch.setitem(
        d.CHEMINS_MODIFS,
        "hunspell",
        (tmp_path / "aj.txt", tmp_path / "re.txt"),
    )
    statut = statut_source(
        "CHAT", "hunspell", base_hunspell=tmp_path / "inexistant"
    )
    assert statut["indisponible"] is True
    assert statut["present"] is False


def test_modifier_appartenance_ajout_puis_retrait(tmp_path, monkeypatch):
    """Ajouter écrit dans ajoutes et purge retires ; retirer fait l'inverse."""
    ajoutes_p = tmp_path / "mots_ajoutes_ods.txt"
    retires_p = tmp_path / "mots_retires_ods.txt"
    monkeypatch.setitem(d.CHEMINS_MODIFS, "ods", (ajoutes_p, retires_p))

    modifier_appartenance("chien", "ods", present=True)
    assert "CHIEN" in lire_liste_mots(ajoutes_p)
    assert "CHIEN" not in lire_liste_mots(retires_p)

    # Retirer le même mot : il quitte ajoutes et entre dans retires.
    modifier_appartenance("chien", "ods", present=False)
    assert "CHIEN" not in lire_liste_mots(ajoutes_p)
    assert "CHIEN" in lire_liste_mots(retires_p)


def test_modifier_appartenance_mot_invalide(tmp_path, monkeypatch):
    """Un mot non jouable au Scrabble est rejeté par une ValueError."""
    monkeypatch.setitem(
        d.CHEMINS_MODIFS, "ods", (tmp_path / "a.txt", tmp_path / "r.txt")
    )
    with pytest.raises(ValueError):
        modifier_appartenance("ch1en", "ods", present=True)
    with pytest.raises(ValueError):
        modifier_appartenance("", "ods", present=True)


def test_modifier_appartenance_source_inconnue():
    """Une source inconnue est rejetée."""
    with pytest.raises(ValueError):
        modifier_appartenance("CHAT", "klingon", present=True)


def test_rechercher_statut_assemble_sources_et_definition(tmp_path, monkeypatch):
    """rechercher_statut agrège le statut des deux sources + la définition."""
    chemin_ods = _preparer_source_modifs(tmp_path, monkeypatch, ["CHAT"])
    monkeypatch.setitem(
        d.CHEMINS_MODIFS, "hunspell", (tmp_path / "ha.txt", tmp_path / "hr.txt")
    )
    definitions = tmp_path / "definitions.json"
    definitions.write_text(json.dumps({"CHAT": ["Félin."]}), encoding="utf-8")
    _preparer_classiques(tmp_path, monkeypatch, ajoutes=["CHAT"])

    resultat = rechercher_statut(
        "chat",
        chemin_ods=chemin_ods,
        base_hunspell=tmp_path / "inexistant",
        chemin_definitions=definitions,
    )
    assert resultat["mot"] == "CHAT"
    assert resultat["valide_saisie"] is True
    assert set(resultat["sources"]) == {"ods", "hunspell"}
    assert resultat["sources"]["ods"]["present"] is True
    assert resultat["sources"]["hunspell"]["indisponible"] is True
    assert resultat["classique"]["classique"] is True
    assert resultat["definition"] == ["Félin."]


# --------------------------------------------------------------------------- #
# Statut « classique du jeu » (issue #204)
# --------------------------------------------------------------------------- #

def _preparer_classiques(tmp_path, monkeypatch, ajoutes=(), retires=()):
    """Prépare la paire classiques_ajoutes/retires dans tmp_path et la branche."""
    ajoutes_p = tmp_path / "classiques_ajoutes.txt"
    retires_p = tmp_path / "classiques_retires.txt"
    ajoutes_p.write_text("\n".join(ajoutes), encoding="utf-8")
    retires_p.write_text("\n".join(retires), encoding="utf-8")
    monkeypatch.setattr(d, "CHEMINS_CLASSIQUES", (ajoutes_p, retires_p))
    return ajoutes_p, retires_p


def test_statut_classique_marque(tmp_path, monkeypatch):
    """Un mot présent dans classiques_ajoutes est signalé classique."""
    _preparer_classiques(tmp_path, monkeypatch, ajoutes=["WU"])
    statut = statut_classique("WU")
    assert statut["ajout_manuel"] is True
    assert statut["retrait_manuel"] is False
    assert statut["classique"] is True


def test_statut_classique_non_marque(tmp_path, monkeypatch):
    """Un mot absent de la liste n'est pas classique."""
    _preparer_classiques(tmp_path, monkeypatch)
    assert statut_classique("CHAT")["classique"] is False


def test_statut_classique_retrait_prioritaire(tmp_path, monkeypatch):
    """Un retrait l'emporte sur un ajout (comme les sources)."""
    _preparer_classiques(tmp_path, monkeypatch, ajoutes=["WU"], retires=["WU"])
    assert statut_classique("WU")["classique"] is False


def test_mot_existe_dans_une_source_ods(tmp_path):
    """Présent dans l'ODS (une seule source suffit) → True."""
    chemin_ods = tmp_path / "ods.txt"
    chemin_ods.write_text("WU\nSIX\n", encoding="utf-8")
    assert mot_existe_dans_une_source(
        "WU", chemin_ods=chemin_ods, base_hunspell=tmp_path / "inexistant"
    ) is True


def test_mot_existe_dans_une_source_absent_partout(tmp_path):
    """Absent de l'ODS et Hunspell indisponible → False."""
    chemin_ods = tmp_path / "ods.txt"
    chemin_ods.write_text("SIX\n", encoding="utf-8")
    assert mot_existe_dans_une_source(
        "ZORGLUB", chemin_ods=chemin_ods, base_hunspell=tmp_path / "inexistant"
    ) is False


def test_marquer_classique_accepte_mot_present(tmp_path, monkeypatch):
    """Marquer un mot présent dans une source écrit dans ajoutes."""
    ajoutes_p, retires_p = _preparer_classiques(tmp_path, monkeypatch)
    chemin_ods = tmp_path / "ods.txt"
    chemin_ods.write_text("WU\n", encoding="utf-8")

    norme = marquer_classique(
        "wu", present=True, chemin_ods=chemin_ods, base_hunspell=tmp_path / "no"
    )
    assert norme == "WU"
    assert "WU" in lire_liste_mots(ajoutes_p)
    assert "WU" not in lire_liste_mots(retires_p)


def test_marquer_classique_refuse_mot_absent_des_deux_sources(tmp_path, monkeypatch):
    """Un mot inexistant dans les deux sources est refusé, sans écrire."""
    ajoutes_p, retires_p = _preparer_classiques(tmp_path, monkeypatch)
    chemin_ods = tmp_path / "ods.txt"
    chemin_ods.write_text("WU\n", encoding="utf-8")

    with pytest.raises(ValueError):
        marquer_classique(
            "zorglub", present=True,
            chemin_ods=chemin_ods, base_hunspell=tmp_path / "no",
        )
    # Aucune écriture : le fichier reste vide.
    assert lire_liste_mots(ajoutes_p) == set()


def test_marquer_classique_mot_invalide(tmp_path, monkeypatch):
    """Un mot non jouable (chiffres) est rejeté avant toute vérification."""
    _preparer_classiques(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        marquer_classique("w1", present=True)


def test_marquer_classique_demarquage_sans_verif_source(tmp_path, monkeypatch):
    """Le démarquage (present=False) ne vérifie pas l'existence en source."""
    ajoutes_p, retires_p = _preparer_classiques(
        tmp_path, monkeypatch, ajoutes=["WU"]
    )
    chemin_ods = tmp_path / "ods.txt"
    chemin_ods.write_text("AUTRE\n", encoding="utf-8")

    marquer_classique(
        "wu", present=False, chemin_ods=chemin_ods, base_hunspell=tmp_path / "no"
    )
    assert "WU" not in lire_liste_mots(ajoutes_p)
    assert "WU" in lire_liste_mots(retires_p)


def test_marquer_classique_round_trip(tmp_path, monkeypatch):
    """Recherche → marquage → nouvelle recherche confirme le statut (issue #204)."""
    chemin_ods = _preparer_source_modifs(tmp_path, monkeypatch, ["WU"])
    monkeypatch.setitem(
        d.CHEMINS_MODIFS, "hunspell", (tmp_path / "ha.txt", tmp_path / "hr.txt")
    )
    _preparer_classiques(tmp_path, monkeypatch)

    avant = rechercher_statut(
        "wu", chemin_ods=chemin_ods, base_hunspell=tmp_path / "no",
        chemin_definitions=tmp_path / "defs.json",
    )
    assert avant["classique"]["classique"] is False

    marquer_classique(
        "wu", present=True, chemin_ods=chemin_ods, base_hunspell=tmp_path / "no"
    )

    apres = rechercher_statut(
        "wu", chemin_ods=chemin_ods, base_hunspell=tmp_path / "no",
        chemin_definitions=tmp_path / "defs.json",
    )
    assert apres["classique"]["classique"] is True
