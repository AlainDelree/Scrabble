"""Tests du module dictionnaire (``scrabble.dictionnaire.dictionnaire``).

Ces tests n'utilisent **jamais** les vrais fichiers ODS/Hunspell : ils
construisent de petits dictionnaires factices dans des fichiers temporaires
(``tmp_path``). Le dépliage Hunspell réel (via ``spylls``) n'est donc pas
exercé ici — seule la chaîne de construction (union/soustraction, Trie, cache)
et la normalisation sont testées de façon déterministe et rapide.
"""

from __future__ import annotations

import csv
import json
import os
import pickle
import time

import pytest

import scrabble.dictionnaire.dictionnaire as d
from scrabble.dictionnaire.dictionnaire import (
    CHEMINS_MODIFS,
    Dictionnaire,
    Trie,
    assurer_fichiers_modifs,
    charger_belgicismes,
    charger_definitions,
    charger_definitions_belges,
    charger_ods,
    chemins_modifs,
    construire_ensemble_ia,
    construire_ensemble_mots,
    construire_trie,
    definition_mot,
    definitions_annotees,
    desaccentuer,
    ensemble_classiques,
    est_mot_scrabble,
    lire_liste_mots,
    marquer_classique,
    modifier_appartenance,
    mot_existe_dans_une_source,
    normaliser_mot,
    obtenir_trie,
    obtenir_trie_ia,
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
    """``mot_valide`` normalise PUIS désaccentue l'entrée avant de consulter le
    Trie (issue #281) : un Trie de validation contient toujours des entrées
    déjà désaccentuées (voir :func:`construire_trie`), donc « ELEVE » ici,
    reconnu qu'on tape « élève » ou « eleve » — accents ou non, même mot."""
    dico = Dictionnaire(Trie.depuis_iterable(["CHAT", "ELEVE"]))

    assert dico.mot_valide("chat")
    assert dico.mot_valide("  Chat ")
    assert dico.mot_valide("élève")
    assert dico.mot_valide("eleve")       # accents désormais indifférents
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


def test_definition_mot_jeune_jeune_circonflexe_meme_cle_desaccentuee(tmp_path):
    """« jeune » et « jeûne » partagent la clé désaccentuée JEUNE (issue #281).

    C'est le scénario de « collision » évoqué par Alain : les lettres du
    Scrabble n'ayant elles-mêmes aucun accent, les deux mots sont déjà un seul
    et même mot jouable — pas un bug à corriger. Le point à vérifier est que
    l'affichage combine bien les gloses des DEUX mots sous cette clé unique,
    sans que l'une masque l'autre. ``definition_mot``/``definitions_annotees``
    ne sont pas modifiées par cette issue : elles utilisaient déjà
    ``desaccentuer(normaliser_mot(mot))`` pour retrouver la clé, et le
    contenu de la clé (une simple liste) affiche déjà toutes les gloses
    à la suite — comportement confirmé ici, aucun correctif requis.
    """
    fichier = tmp_path / "definitions.json"
    fichier.write_text(
        json.dumps(
            {
                "JEUNE": [
                    "Qui est dans une phase au commencement de sa vie.",  # jeune
                    "Abstention totale d'aliments.",                     # jeûne
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    attendu = [
        "Qui est dans une phase au commencement de sa vie.",
        "Abstention totale d'aliments.",
    ]
    # Les deux graphies (avec et sans accent circonflexe) retrouvent la même
    # liste combinée : aucune des deux définitions n'est masquée par l'autre.
    assert definition_mot("jeûne", fichier) == attendu
    assert definition_mot("jeune", fichier) == attendu


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
# Belgicismes (mode Belgicisme), issue #274
# --------------------------------------------------------------------------- #

def _ecrire_csv_belgicismes(chemin, lignes):
    """Écrit un CSV belgicismes factice. ``lignes`` : liste de (mot, existe)."""
    with open(chemin, "w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(
            ["mot", "définition(s) belge(s)", "origine_wallonne", "existe_sens_standard"]
        )
        for mot, existe in lignes:
            ecrivain.writerow([mot, "Une définition.", "non", existe])


def test_charger_belgicismes_ne_retient_que_les_mots_sans_equivalent_standard(tmp_path):
    """Seuls les mots ``existe_sens_standard`` != "oui" (normalisé) sont chargés."""
    chemin = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(
        chemin,
        [
            ("sketter", "non"),
            ("abaisser", "oui"),
            ("abiye", " Non "),
            ("dringuelle", "NON"),
        ],
    )
    mots = charger_belgicismes(chemin)
    assert mots == {"SKETTER", "ABIYE", "DRINGUELLE"}
    assert "ABAISSER" not in mots


def test_charger_belgicismes_fichier_absent(tmp_path):
    """Fichier absent : ensemble vide, sans erreur (comme lire_liste_mots)."""
    assert charger_belgicismes(tmp_path / "absent.csv") == set()


def test_construire_trie_mode_belgicisme_ajoute_mot_belge(tmp_path):
    """Un mot belge (existe_sens_standard=non) est valide en mode Belgicisme et
    invalide en mode France (issue #274) — ex. « sketter », absent de l'ODS."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("sketter", "non")])

    trie_france = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        mode_belgicisme=False,
        chemin_belgicismes=chemin_belges,
    )
    trie_belgique = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        mode_belgicisme=True,
        chemin_belgicismes=chemin_belges,
    )

    assert "SKETTER" not in trie_france
    assert "SKETTER" in trie_belgique
    assert "CHAT" in trie_france and "CHAT" in trie_belgique


def test_construire_trie_mode_belgicisme_pas_de_doublon_mot_standard(tmp_path):
    """Un mot ``existe_sens_standard=oui`` n'est pas réinjecté par le chargement
    belge : il est déjà présent via la source standard, comportement inchangé."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["academique"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("academique", "oui")])

    trie = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        mode_belgicisme=True,
        chemin_belgicismes=chemin_belges,
    )

    assert "ACADEMIQUE" in trie
    assert len(trie) == 1  # un seul mot : pas de doublon via le CSV belge


def test_construire_trie_mode_belgicisme_mot_oui_absent_de_la_source_reste_absent(
    tmp_path,
):
    """Un mot ``oui`` absent de la source standard n'est pas ajouté via le CSV
    belge (seuls les mots ``!= oui`` sont chargés, voir :func:`charger_belgicismes`)."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("zorglub", "oui")])

    trie = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        mode_belgicisme=True,
        chemin_belgicismes=chemin_belges,
    )
    assert "ZORGLUB" not in trie


# --------------------------------------------------------------------------- #
# Désaccentuation cohérente insertion + recherche (issue #281)
# --------------------------------------------------------------------------- #

def test_construire_trie_ods_reconnait_les_mots_tapes_avec_accent(tmp_path):
    """L'ODS8 est stocké sans accent : un mot valide tapé AVEC accent (ex.
    « académique », « école », « été ») doit être reconnu, la comparaison
    d'appartenance étant elle aussi désaccentuée (:meth:`Dictionnaire.mot_valide`)."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["academique", "ecole", "ete"]
    )
    trie = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
    )
    dico = Dictionnaire(trie)

    assert dico.mot_valide("académique")
    assert dico.mot_valide("école")
    assert dico.mot_valide("été")
    # La forme sans accent reste bien sûr valide aussi (non-régression).
    assert dico.mot_valide("ACADEMIQUE")


def test_construire_trie_hunspell_mot_accentue_reste_valide(tmp_path, monkeypatch):
    """Non-régression : Hunspell contient légitimement des entrées accentuées
    (ex. « ACADÉMIQUE »). La désaccentuation à l'insertion et à la recherche
    étant symétrique, ce mot reste reconnu — tapé avec ou sans accent."""
    monkeypatch.setattr(
        d,
        "charger_source",
        lambda source, chemin_ods, base_hunspell: {"ACADÉMIQUE", "ÉCOLE"},
    )
    chemin_ajoutes = tmp_path / "mots_ajoutes.txt"
    chemin_ajoutes.touch()
    chemin_retires = tmp_path / "mots_retires.txt"
    chemin_retires.touch()

    trie = construire_trie(
        source="hunspell",
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
    )
    dico = Dictionnaire(trie)

    assert dico.mot_valide("académique")
    assert dico.mot_valide("ACADEMIQUE")
    assert dico.mot_valide("école")


def test_construire_trie_belgicisme_accentue_sans_equivalent_standard(tmp_path):
    """Un belgicisme accentué sans équivalent standard (ex. « agréation »,
    ``existe_sens_standard=non``) est valide en mode Belgicisme, reconnu qu'on
    le tape avec ou sans accent (issue #281)."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("agréation", "non")])

    trie = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        mode_belgicisme=True,
        chemin_belgicismes=chemin_belges,
    )
    dico = Dictionnaire(trie)

    assert dico.mot_valide("agréation")
    assert dico.mot_valide("AGREATION")


def test_obtenir_trie_cache_mode_defaut_false_comportement_inchange(tmp_path):
    """Non-régression (issue #274) : mode par défaut (``False``), le cache se
    comporte strictement comme avant cette issue (écrit puis relu sans
    reconstruction superflue)."""
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
    assert chemin_cache.exists()
    mtime_cache = chemin_cache.stat().st_mtime_ns

    trie2 = obtenir_trie(**kwargs)
    assert chemin_cache.stat().st_mtime_ns == mtime_cache  # non réécrit
    assert "CHAT" in trie1 and "CHAT" in trie2


def test_obtenir_trie_cache_invalide_si_mode_belgicisme_change(tmp_path):
    """Basculer le mode Belgicisme invalide le cache existant (en-tête ``belge``)."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("sketter", "non")])
    chemin_cache = tmp_path / "trie_cache.pkl"
    kwargs = dict(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        chemin_cache=chemin_cache,
        chemin_belgicismes=chemin_belges,
    )

    trie_france = obtenir_trie(mode_belgicisme=False, **kwargs)
    assert "SKETTER" not in trie_france

    trie_belgique = obtenir_trie(mode_belgicisme=True, **kwargs)
    assert "SKETTER" in trie_belgique

    # Rebasculer en France reconstruit aussi (le cache belge ne doit pas fuiter).
    trie_france_2 = obtenir_trie(mode_belgicisme=False, **kwargs)
    assert "SKETTER" not in trie_france_2


def test_obtenir_trie_cache_ancien_sans_champ_belge_reste_valide_en_mode_france(
    tmp_path,
):
    """Un cache écrit avant l'issue #274 (en-tête sans clé ``belge``) reste
    valide en mode France par défaut, sans reconstruction (repli
    ``entete.get("belge", False)``)."""
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=["chat"]
    )
    chemin_cache = tmp_path / "trie_cache.pkl"
    trie = construire_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
    )
    with open(chemin_cache, "wb") as fichier:
        pickle.dump({"version": d.VERSION_CACHE, "source": "ods"}, fichier)
        pickle.dump(trie, fichier)
    mtime_cache = chemin_cache.stat().st_mtime_ns

    trie_relu = obtenir_trie(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        chemin_cache=chemin_cache,
    )
    assert chemin_cache.stat().st_mtime_ns == mtime_cache  # pas régénéré
    assert "CHAT" in trie_relu


# --------------------------------------------------------------------------- #
# Définitions belges + fusion annotée (loupe), issue #276
# --------------------------------------------------------------------------- #

def _ecrire_csv_definitions_belges(chemin, lignes):
    """Écrit un CSV belgicismes factice avec définition personnalisée.

    ``lignes`` : liste de ``(mot, definition_brute, existe_sens_standard)``.
    """
    with open(chemin, "w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(
            ["mot", "définition(s) belge(s)", "origine_wallonne", "existe_sens_standard"]
        )
        for mot, definition, existe in lignes:
            ecrivain.writerow([mot, definition, "non", existe])


def test_charger_definitions_belges_ne_filtre_pas_existe_sens_standard(tmp_path):
    """Contrairement à charger_belgicismes, TOUTES les lignes sont chargées, y
    compris ``existe_sens_standard=oui`` (cas ``académique``, issue #276)."""
    chemin = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(
        chemin,
        [
            ("academique", "Universitaire. | Relatif à un retard toléré.", "oui"),
            ("sketter", "Casser, fatiguer.", "non"),
        ],
    )

    definitions = charger_definitions_belges(chemin)

    assert definitions["ACADEMIQUE"] == [
        "Universitaire.",
        "Relatif à un retard toléré.",
    ]
    assert definitions["SKETTER"] == ["Casser, fatiguer."]


def test_charger_definitions_belges_fichier_absent(tmp_path):
    """Fichier absent : dict vide, sans erreur (comme charger_definitions)."""
    assert charger_definitions_belges(tmp_path / "absent.csv") == {}


def test_definitions_annotees_mot_belge_sans_equivalent_standard(tmp_path):
    """« sketter » : aucune glose standard, toutes les gloses sont belges."""
    chemin_defs = tmp_path / "definitions.json"
    chemin_defs.write_text(json.dumps({}), encoding="utf-8")
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(chemin_belges, [("sketter", "Casser, fatiguer.", "non")])

    annotees = definitions_annotees("sketter", chemin_defs, chemin_belges)

    assert annotees == [{"texte": "Casser, fatiguer.", "origine": "belge"}]


def test_definitions_annotees_mot_avec_glose_belge_non_dupliquee(tmp_path):
    """Une glose standard suivie d'une glose belge non dupliquée (drapeau)."""
    chemin_defs = tmp_path / "definitions.json"
    chemin_defs.write_text(
        json.dumps({"CHAT": ["Petit félin domestique."]}), encoding="utf-8"
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(chemin_belges, [("chat", "Loquet de porte.", "non")])

    annotees = definitions_annotees("chat", chemin_defs, chemin_belges)

    assert annotees == [
        {"texte": "Petit félin domestique.", "origine": "standard"},
        {"texte": "Loquet de porte.", "origine": "belge"},
    ]


def test_definitions_annotees_academique_deduplique_sans_doublon(tmp_path):
    """Cas ``académique`` (issues #276/#278) : les deux gloses belges existent
    déjà mot pour mot dans le Wiktionnaire filtré — aucun doublon de texte,
    mais les gloses standards partagées portent ``aussi_belge`` pour que le
    drapeau reste visible."""
    chemin_defs = tmp_path / "definitions.json"
    chemin_defs.write_text(
        json.dumps(
            {
                "ACADEMIQUE": [
                    "Qui se rapporte aux académies.",
                    "Universitaire.",
                    "Relatif à un retard toléré.",
                ]
            }
        ),
        encoding="utf-8",
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(
        chemin_belges,
        [("academique", "Universitaire. | Relatif à un retard toléré.", "oui")],
    )

    annotees = definitions_annotees("academique", chemin_defs, chemin_belges)

    assert annotees == [
        {"texte": "Qui se rapporte aux académies.", "origine": "standard"},
        {"texte": "Universitaire.", "origine": "standard", "aussi_belge": True},
        {
            "texte": "Relatif à un retard toléré.",
            "origine": "standard",
            "aussi_belge": True,
        },
    ]
    assert all(glose["origine"] == "standard" for glose in annotees)


def test_definitions_annotees_dedup_insensible_casse_espaces_ponctuation(tmp_path):
    """La déduplication de texte ignore casse, espaces superflus et ponctuation
    finale (issue #278 : pas de doublon, mais le drapeau reste porté par la
    glose standard via ``aussi_belge``)."""
    chemin_defs = tmp_path / "definitions.json"
    chemin_defs.write_text(json.dumps({"MOT": ["Une   glose.  "]}), encoding="utf-8")
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(chemin_belges, [("mot", "une glose", "non")])

    annotees = definitions_annotees("mot", chemin_defs, chemin_belges)

    assert annotees == [
        {"texte": "Une   glose.  ", "origine": "standard", "aussi_belge": True}
    ]


def test_definitions_annotees_mot_sans_definition_belge_comportement_inchange(tmp_path):
    """Un mot sans entrée dans le CSV belge : uniquement les gloses standards,
    comportement strictement inchangé (mêmes gloses, simplement annotées)."""
    chemin_defs = tmp_path / "definitions.json"
    chemin_defs.write_text(
        json.dumps({"CHIEN": ["Mammifère domestique."]}), encoding="utf-8"
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(chemin_belges, [("sketter", "Casser, fatiguer.", "non")])

    annotees = definitions_annotees("chien", chemin_defs, chemin_belges)

    assert annotees == [{"texte": "Mammifère domestique.", "origine": "standard"}]


def test_definitions_annotees_mot_totalement_absent_renvoie_none(tmp_path):
    """Ni définition standard ni définition belge : None (comme definition_mot)."""
    chemin_defs = tmp_path / "definitions.json"
    chemin_defs.write_text(json.dumps({}), encoding="utf-8")
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_definitions_belges(chemin_belges, [("sketter", "Casser, fatiguer.", "non")])

    assert definitions_annotees("zorglub", chemin_defs, chemin_belges) is None


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


# --------------------------------------------------------------------------- #
# Trie restreint « vocabulaire humain » de l'IA (issue #206)
# --------------------------------------------------------------------------- #

def _preparer_ia(tmp_path, monkeypatch, *, source_mots, courants=None,
                 classiques_ajoutes=(), classiques_retires=()):
    """Prépare source ODS, mots_courants et classiques, tous branchés en tmp_path.

    ``courants=None`` ne crée **pas** le fichier ``mots_courants.txt`` (cas
    « absence » ), tandis qu'une liste (même vide) l'écrit. Renvoie les chemins
    (ods, ajoutes, retires, mots_courants).
    """
    chemin_ods, chemin_ajoutes, chemin_retires = _preparer_dico(
        tmp_path, source_mots=source_mots
    )
    chemin_courants = tmp_path / "mots_courants.txt"
    if courants is not None:
        _ecrire_liste(chemin_courants, courants or [""])
    _preparer_classiques(
        tmp_path, monkeypatch,
        ajoutes=classiques_ajoutes, retires=classiques_retires,
    )
    return chemin_ods, chemin_ajoutes, chemin_retires, chemin_courants


def _kwargs_ia(chemin_ods, chemin_ajoutes, chemin_retires, chemin_courants,
               chemin_cache):
    return dict(
        source="ods",
        chemin_ods=chemin_ods,
        chemin_ajoutes=chemin_ajoutes,
        chemin_retires=chemin_retires,
        chemin_mots_courants=chemin_courants,
        chemin_cache=chemin_cache,
    )


def test_ensemble_classiques_ajoutes_moins_retires(tmp_path, monkeypatch):
    """ensemble_classiques = classiques_ajoutes − classiques_retires."""
    _preparer_classiques(
        tmp_path, monkeypatch, ajoutes=["WU", "SIX", "ZOO"], retires=["ZOO"]
    )
    assert ensemble_classiques() == {"WU", "SIX"}


def test_construire_ensemble_ia_union_puis_intersection(tmp_path, monkeypatch):
    """(courants ∪ classiques) ∩ dico complet actif."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch,
        source_mots=["chat", "chien", "wu", "six", "poisson"],
        courants=["chat", "chien"],
        classiques_ajoutes=["WU", "SIX"],
    )
    ensemble = construire_ensemble_ia(
        chemin_ods=ods, chemin_ajoutes=aj, chemin_retires=re_,
        chemin_mots_courants=co,
    )
    assert ensemble == {"CHAT", "CHIEN", "WU", "SIX"}
    # « POISSON » est dans la source complète mais ni courant ni classique.
    assert "POISSON" not in ensemble


def test_construire_ensemble_ia_intersection_exclut_hors_source(tmp_path, monkeypatch):
    """Un mot courant/classique absent de la source active est exclu."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch,
        source_mots=["chat"],
        courants=["chat", "zorglub"],       # ZORGLUB absent de la source
        classiques_ajoutes=["WU"],          # WU absent de la source
    )
    ensemble = construire_ensemble_ia(
        chemin_ods=ods, chemin_ajoutes=aj, chemin_retires=re_,
        chemin_mots_courants=co,
    )
    assert ensemble == {"CHAT"}
    assert "ZORGLUB" not in ensemble and "WU" not in ensemble


def test_construire_ensemble_ia_pas_de_doublon_ni_biais(tmp_path, monkeypatch):
    """Un mot présent dans courants ET classiques n'est compté qu'une fois.

    Non-régression sur le point soulevé par Alain : l'union est un ``set`` ;
    « SIX » figurant dans les deux listes n'apparaît qu'une fois dans le Trie,
    et le Trie ne pondère jamais par fréquence (test existe/n'existe pas).
    """
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch,
        source_mots=["six", "chat"],
        courants=["six"],
        classiques_ajoutes=["SIX"],
    )
    ensemble = construire_ensemble_ia(
        chemin_ods=ods, chemin_ajoutes=aj, chemin_retires=re_,
        chemin_mots_courants=co,
    )
    # Un set : « SIX » y est une seule fois par construction.
    assert ensemble == {"SIX"}
    trie = Trie.depuis_iterable(ensemble)
    assert len(trie) == 1                    # aucune duplication dans le Trie
    assert "SIX" in trie


def test_construire_ensemble_ia_tolere_absence_mots_courants(tmp_path, monkeypatch):
    """Sans mots_courants.txt : repli sur les seuls classiques, sans planter."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch,
        source_mots=["wu", "chat"],
        courants=None,                       # fichier absent
        classiques_ajoutes=["WU"],
    )
    assert not co.exists()
    ensemble = construire_ensemble_ia(
        chemin_ods=ods, chemin_ajoutes=aj, chemin_retires=re_,
        chemin_mots_courants=co,
    )
    assert ensemble == {"WU"}                 # classiques seuls (∩ source)


def test_construire_ensemble_ia_retrait_source_exclut_ia(tmp_path, monkeypatch):
    """Un mot courant retiré de la source (mots_retires) sort aussi du Trie IA.

    Garantit l'invariant Trie IA ⊆ dictionnaire complet : l'IA ne peut pas
    générer un coup que valider_coup rejetterait.
    """
    ods, aj, re_, co = _preparer_ia(
        tmp_path, monkeypatch,
        source_mots=["chat", "chien"],
        courants=["chat", "chien"],
    )[:4]
    _ecrire_liste(re_, ["chien"])            # CHIEN retiré du dico complet
    ensemble = construire_ensemble_ia(
        chemin_ods=ods, chemin_ajoutes=aj, chemin_retires=re_,
        chemin_mots_courants=co,
    )
    assert ensemble == {"CHAT"}
    assert "CHIEN" not in ensemble


def test_obtenir_trie_ia_cache_ecrit_et_relu(tmp_path, monkeypatch):
    """Premier appel écrit le cache IA, le second le relit sans réécrire."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch, source_mots=["chat"], courants=["chat"]
    )
    cache = tmp_path / "trie_ia_cache.pkl"
    kwargs = _kwargs_ia(ods, aj, re_, co, cache)

    trie1 = obtenir_trie_ia(**kwargs)
    assert cache.exists() and "CHAT" in trie1
    mtime = cache.stat().st_mtime_ns

    trie2 = obtenir_trie_ia(**kwargs)
    assert cache.stat().st_mtime_ns == mtime     # non réécrit
    assert "CHAT" in trie2


def test_obtenir_trie_ia_cache_invalide_si_mots_courants_change(tmp_path, monkeypatch):
    """Modifier mots_courants.txt après le cache force une reconstruction."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch, source_mots=["chat", "chien"], courants=["chat"]
    )
    cache = tmp_path / "trie_ia_cache.pkl"
    kwargs = _kwargs_ia(ods, aj, re_, co, cache)

    trie1 = obtenir_trie_ia(**kwargs)
    assert "CHIEN" not in trie1

    _ecrire_liste(co, ["chat", "chien"])
    futur = cache.stat().st_mtime + 10
    os.utime(co, (futur, futur))

    trie2 = obtenir_trie_ia(**kwargs)
    assert "CHIEN" in trie2                       # cache invalidé


def test_obtenir_trie_ia_cache_invalide_si_classiques_change(tmp_path, monkeypatch):
    """Modifier classiques_ajoutes.txt après le cache force une reconstruction."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch, source_mots=["chat", "wu"], courants=["chat"]
    )
    cache = tmp_path / "trie_ia_cache.pkl"
    kwargs = _kwargs_ia(ods, aj, re_, co, cache)

    trie1 = obtenir_trie_ia(**kwargs)
    assert "WU" not in trie1

    classiques_ajoutes = d.chemins_classiques()[0]
    _ecrire_liste(classiques_ajoutes, ["WU"])
    futur = cache.stat().st_mtime + 10
    os.utime(classiques_ajoutes, (futur, futur))

    trie2 = obtenir_trie_ia(**kwargs)
    assert "WU" in trie2                          # cache invalidé


def test_construire_ensemble_ia_mode_belgicisme_hors_courants_reste_exclu(
    tmp_path, monkeypatch
):
    """Le ``complet`` interne inclut les belges actifs (sur-ensemble cohérent
    avec le Trie complet, issue #274), mais le Trie IA restreint ne les retient
    que s'ils sont aussi mots courants/classiques — sinon ils restent exclus."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch, source_mots=["chat"], courants=["chat"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("sketter", "non")])

    ensemble = construire_ensemble_ia(
        chemin_ods=ods,
        chemin_ajoutes=aj,
        chemin_retires=re_,
        chemin_mots_courants=co,
        mode_belgicisme=True,
        chemin_belgicismes=chemin_belges,
    )
    assert ensemble == {"CHAT"}
    assert "SKETTER" not in ensemble


def test_construire_ensemble_ia_mode_belgicisme_mot_courant_est_inclus(
    tmp_path, monkeypatch
):
    """Un mot belge aussi présent dans ``mots_courants.txt`` rejoint le Trie IA."""
    ods, aj, re_, co, *_ = _preparer_ia(
        tmp_path, monkeypatch, source_mots=["chat"], courants=["chat", "sketter"]
    )
    chemin_belges = tmp_path / "belgicismes.csv"
    _ecrire_csv_belgicismes(chemin_belges, [("sketter", "non")])

    ensemble = construire_ensemble_ia(
        chemin_ods=ods,
        chemin_ajoutes=aj,
        chemin_retires=re_,
        chemin_mots_courants=co,
        mode_belgicisme=True,
        chemin_belgicismes=chemin_belges,
    )
    assert ensemble == {"CHAT", "SKETTER"}
