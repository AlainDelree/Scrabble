"""Tests du script de croisement ODS8 × Lexique 3 (``scripts/generer_mots_courants.py``, issue #205).

Comme ``test_dictionnaire``, ces tests n'utilisent **jamais** le vrai fichier
``Lexique383.tsv`` (~25 Mo) : ils fabriquent un mini-Lexique et un mini-ODS8 dans
des fichiers temporaires. On vérifie surtout les trois points sensibles de
l'issue : tolérance à l'absence du fichier, cohérence du croisement/seuil, et
appariement des formes accentuées de Lexique avec l'ODS8 **désaccentué**.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Le script vit dans ``scripts/`` (hors du paquet ``scrabble``, hors pythonpath) :
# on le charge par son chemin, comme le ferait un lancement en ligne de commande.
_CHEMIN_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "generer_mots_courants.py"
)
_spec = importlib.util.spec_from_file_location("generer_mots_courants", _CHEMIN_SCRIPT)
gmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gmc)


# En-tête minimal reproduisant l'ordre réel des colonnes utiles de Lexique383.
_ENTETE = "ortho\tphon\tfreqfilms2\tfreqlivres\n"


def _ecrire_lexique(chemin: Path, lignes: list[tuple[str, float, float]]) -> None:
    """Écrit un mini-Lexique ``ortho / freqfilms2 / freqlivres`` (avec en-tête)."""
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(_ENTETE)
        for ortho, freqfilms2, freqlivres in lignes:
            f.write(f"{ortho}\tXXX\t{freqfilms2}\t{freqlivres}\n")


# --------------------------------------------------------------------------- #
# Tolérance à l'absence du fichier (point 4)
# --------------------------------------------------------------------------- #

def test_lire_frequences_fichier_absent_leve_filenotfound(tmp_path):
    """La lecture d'un Lexique inexistant lève ``FileNotFoundError`` (pas un plantage muet)."""
    with pytest.raises(FileNotFoundError):
        gmc.lire_frequences_lexique(tmp_path / "pas_la.tsv")


def test_main_fichier_absent_retourne_code_erreur(tmp_path, monkeypatch, capsys):
    """``main`` sur un Lexique absent renvoie un code non nul et un message clair, sans exception."""
    # ODS8 factice non vide pour dépasser le contrôle ODS et atteindre celui de Lexique.
    monkeypatch.setattr(gmc, "charger_ods", lambda: {"MOT"})
    code = gmc.main(["--lexique", str(tmp_path / "absent.tsv"), "--dry-run"])
    assert code == 1
    sortie = capsys.readouterr()
    assert "introuvable" in sortie.err
    assert "lexique.org" in sortie.err


# --------------------------------------------------------------------------- #
# Croisement et seuil (points 2 et 3)
# --------------------------------------------------------------------------- #

def test_selection_applique_seuil_et_intersection(tmp_path):
    """Seuls les mots ODS présents dans Lexique **et** au-dessus du seuil sont retenus."""
    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(
        lexique,
        [
            ("maison", 50.0, 40.0),   # courant
            ("brouette", 3.0, 2.0),   # au-dessus du seuil 1
            ("gnognote", 0.2, 0.1),   # sous le seuil
            ("bidule", 5.0, 5.0),     # présent dans Lexique mais absent de l'ODS
        ],
    )
    freq = gmc.lire_frequences_lexique(lexique)
    ods = {"MAISON", "BROUETTE", "GNOGNOTE", "ZYTHUM"}  # ZYTHUM absent de Lexique

    courants = gmc.selectionner_mots_courants(freq, ods, seuil=1.0, corpus="union")
    assert courants == {"MAISON", "BROUETTE"}
    # GNOGNOTE : sous le seuil ; ZYTHUM : hors Lexique ; BIDULE : hors ODS.
    assert "GNOGNOTE" not in courants
    assert "ZYTHUM" not in courants
    assert "BIDULE" not in courants


def test_corpus_livres_vs_films(tmp_path):
    """Le choix du corpus change la sélection (mot fréquent à l'oral mais rare à l'écrit)."""
    lexique = tmp_path / "lex.tsv"
    # « ouais » : très fréquent en sous-titres, quasi nul en livres.
    _ecrire_lexique(lexique, [("ouais", 80.0, 0.3)])
    freq = gmc.lire_frequences_lexique(lexique)
    ods = {"OUAIS"}

    assert gmc.selectionner_mots_courants(freq, ods, 1.0, "films") == {"OUAIS"}
    assert gmc.selectionner_mots_courants(freq, ods, 1.0, "livres") == set()
    assert gmc.selectionner_mots_courants(freq, ods, 1.0, "union") == {"OUAIS"}


def test_homographes_retiennent_la_frequence_max(tmp_path):
    """Deux lignes de même ortho : on garde la fréquence maximale."""
    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(
        lexique,
        [("est", 10.0, 0.5), ("est", 300.0, 200.0)],  # « est » (point card.) vs verbe
    )
    freq = gmc.lire_frequences_lexique(lexique)
    assert freq["EST"] == (200.0, 300.0)  # (max freqlivres, max freqfilms2)


# --------------------------------------------------------------------------- #
# Normalisation accents : LE point 4 (ODS8 sans accents, Lexique accentué)
# --------------------------------------------------------------------------- #

def test_formes_accentuees_lexique_apparient_ods_desaccentue(tmp_path):
    """Les formes accentuées de Lexique doivent matcher l'ODS8 stocké sans accents.

    C'est le piège central de l'issue : sans désaccentuation, ``élève`` (Lexique)
    ne s'apparierait pas à ``ELEVE`` (ODS8), perdant des dizaines de milliers de
    correspondances.
    """
    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(
        lexique,
        [
            ("élève", 30.0, 25.0),
            ("abbé", 5.0, 8.0),
            ("abcès", 2.0, 3.0),
            ("Noël", 40.0, 20.0),
        ],
    )
    freq = gmc.lire_frequences_lexique(lexique)
    # Les clés sont désaccentuées comme l'ODS8.
    assert "ELEVE" in freq
    assert "ABBE" in freq
    assert "ABCES" in freq
    assert "NOEL" in freq

    ods = {"ELEVE", "ABBE", "ABCES", "NOEL"}
    courants = gmc.selectionner_mots_courants(freq, ods, 1.0, "union")
    assert courants == ods  # tous appariés, aucune perte


def test_deux_formes_lexique_fondues_par_desaccentuation(tmp_path):
    """``côté`` et ``cote`` fondent sur ``COTE`` : on garde la fréquence max des deux."""
    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(lexique, [("côté", 100.0, 90.0), ("cote", 4.0, 3.0)])
    freq = gmc.lire_frequences_lexique(lexique)
    assert set(freq) == {"COTE"}
    assert freq["COTE"] == (90.0, 100.0)


# --------------------------------------------------------------------------- #
# Mesure de couverture et sortie fichier
# --------------------------------------------------------------------------- #

def test_mesure_couverture_intersection_et_balayage(tmp_path):
    """La couverture rapporte l'intersection brute et un balayage de seuils."""
    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(
        lexique,
        [("maison", 50.0, 40.0), ("rare", 0.6, 0.6), ("absent", 100.0, 100.0)],
    )
    freq = gmc.lire_frequences_lexique(lexique)
    ods = {"MAISON", "RARE", "INCONNU"}  # INCONNU hors Lexique

    stats = gmc.mesurer_couverture(freq, ods, "union")
    assert stats["total_ods"] == 3
    assert stats["intersection_brute"] == 2  # MAISON + RARE (ABSENT hors ODS)
    balayage = dict(stats["balayage"])
    assert balayage[0.5] == 2   # MAISON + RARE
    assert balayage[1.0] == 1   # MAISON seul (RARE sous 1.0)


# --------------------------------------------------------------------------- #
# Palier « expert » : seuil 0 == intersection brute (issue #366, lot A)
# --------------------------------------------------------------------------- #

def test_selection_seuil_zero_egale_intersection_brute(tmp_path):
    """``selectionner_mots_courants(..., seuil=0.0)`` rend l'intersection brute.

    Y compris pour une forme à fréquence mesurée nulle dans les deux corpus :
    la comparaison est large (``>=``), pas stricte, donc rien n'est exclu à
    tort — c'est cette propriété que le palier Expert exploite (voir le
    docstring du script).
    """
    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(
        lexique,
        [
            ("maison", 50.0, 40.0),
            ("rare", 0.1, 0.05),
            ("jamaisvu", 0.0, 0.0),  # présent dans Lexique, fréquence nulle partout
        ],
    )
    freq = gmc.lire_frequences_lexique(lexique)
    ods = {"MAISON", "RARE", "JAMAISVU", "HORSLEXIQUE"}

    stats = gmc.mesurer_couverture(freq, ods, "union")
    au_seuil_zero = gmc.selectionner_mots_courants(freq, ods, seuil=0.0, corpus="union")

    assert len(au_seuil_zero) == stats["intersection_brute"]
    assert au_seuil_zero == {"MAISON", "RARE", "JAMAISVU"}
    assert "HORSLEXIQUE" not in au_seuil_zero


# --------------------------------------------------------------------------- #
# Mode --tous : cinq paliers en une commande (issue #366, lot A)
# --------------------------------------------------------------------------- #

def test_ordre_et_seuils_paliers_couvrent_les_memes_cles():
    """``ORDRE_PALIERS``, ``SEUILS_PALIER`` et ``FICHIERS_VOCABULAIRE_PALIER``.

    doivent porter exactement les mêmes cinq paliers, sans quoi
    :func:`generer_tous_paliers` lèverait un ``KeyError`` à l'exécution.
    """
    assert set(gmc.ORDRE_PALIERS) == set(gmc.SEUILS_PALIER)
    assert set(gmc.ORDRE_PALIERS) == set(gmc.FICHIERS_VOCABULAIRE_PALIER)
    assert len(gmc.ORDRE_PALIERS) == 5


def test_generer_tous_paliers_ecrit_les_cinq_fichiers(tmp_path, monkeypatch):
    """``generer_tous_paliers`` écrit un fichier par palier, filtré à son seuil."""
    chemins = {palier: tmp_path / f"{palier}.txt" for palier in gmc.ORDRE_PALIERS}
    monkeypatch.setattr(gmc, "FICHIERS_VOCABULAIRE_PALIER", chemins)

    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(
        lexique,
        [
            ("tres", 10.0, 10.0),      # >= 3.0 : dans tous les paliers
            ("moyen", 1.5, 1.5),       # >= 1.0 mais < 2.0 : intermédiaire/avancé/expert
            ("faible", 0.6, 0.6),      # >= 0.5 mais < 1.0 : avancé/expert seuls
            ("nul", 0.0, 0.0),         # présent mais fréquence nulle : expert seul
        ],
    )
    freq = gmc.lire_frequences_lexique(lexique)
    ods = {"TRES", "MOYEN", "FAIBLE", "NUL"}

    resultats = gmc.generer_tous_paliers(freq, ods, corpus="union", dry_run=False)

    effectifs = dict(resultats)
    assert effectifs["debutant"] == 1     # TRES seul (seuil 3.0)
    assert effectifs["facile"] == 1       # TRES seul (seuil 2.0)
    assert effectifs["intermediaire"] == 2  # TRES + MOYEN (seuil 1.0)
    assert effectifs["avance"] == 3       # + FAIBLE (seuil 0.5)
    assert effectifs["expert"] == 4       # + NUL (seuil 0.0, intersection brute)

    for palier, chemin in chemins.items():
        assert chemin.exists()
        mots = set(chemin.read_text(encoding="utf-8").split())
        assert len(mots) == effectifs[palier]


def test_generer_tous_paliers_dry_run_ecrit_rien(tmp_path, monkeypatch):
    """``dry_run=True`` mesure sans écrire aucun des cinq fichiers."""
    chemins = {palier: tmp_path / f"{palier}.txt" for palier in gmc.ORDRE_PALIERS}
    monkeypatch.setattr(gmc, "FICHIERS_VOCABULAIRE_PALIER", chemins)

    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(lexique, [("maison", 50.0, 40.0)])
    freq = gmc.lire_frequences_lexique(lexique)

    gmc.generer_tous_paliers(freq, {"MAISON"}, corpus="union", dry_run=True)

    for chemin in chemins.values():
        assert not chemin.exists()


def test_main_tous_produit_le_recapitulatif(tmp_path, monkeypatch, capsys):
    """``main(["--tous"])`` génère les cinq fichiers et affiche un récapitulatif."""
    chemins = {palier: tmp_path / f"{palier}.txt" for palier in gmc.ORDRE_PALIERS}
    monkeypatch.setattr(gmc, "FICHIERS_VOCABULAIRE_PALIER", chemins)
    monkeypatch.setattr(gmc, "charger_ods", lambda: {"MAISON", "ZEBRE"})

    lexique = tmp_path / "lex.tsv"
    _ecrire_lexique(lexique, [("maison", 50.0, 40.0), ("zebre", 5.0, 4.0)])

    code = gmc.main(["--lexique", str(lexique), "--tous"])
    assert code == 0
    for chemin in chemins.values():
        assert chemin.exists()
    sortie = capsys.readouterr().out
    assert "Récapitulatif" in sortie
    for palier in gmc.ORDRE_PALIERS:
        assert palier in sortie


def test_main_tous_incompatible_avec_sortie_ou_seuil(tmp_path):
    """``--tous`` combiné à ``--sortie``/``--seuil`` est un usage rejeté (pas un plantage)."""
    with pytest.raises(SystemExit):
        gmc.main(["--tous", "--seuil", "2"])
    with pytest.raises(SystemExit):
        gmc.main(["--tous", "--sortie", str(tmp_path / "sortie.txt")])


def test_main_tous_fichier_lexique_absent_message_clair(tmp_path, monkeypatch, capsys):
    """``--tous`` sans ``Lexique383.tsv`` échoue proprement, comme le mode simple."""
    monkeypatch.setattr(gmc, "charger_ods", lambda: {"MOT"})
    code = gmc.main(["--lexique", str(tmp_path / "absent.tsv"), "--tous"])
    assert code == 1
    sortie = capsys.readouterr()
    assert "introuvable" in sortie.err


def test_main_ecrit_fichier_trie(tmp_path, monkeypatch, capsys):
    """``main`` produit un fichier « un mot par ligne » trié, relisible tel quel."""
    lexique = tmp_path / "lex.tsv"
    sortie = tmp_path / "mots_courants.txt"
    _ecrire_lexique(
        lexique, [("maison", 50.0, 40.0), ("zebre", 5.0, 4.0), ("rare", 0.1, 0.1)]
    )
    monkeypatch.setattr(gmc, "charger_ods", lambda: {"MAISON", "ZEBRE", "RARE"})

    code = gmc.main(
        ["--lexique", str(lexique), "--sortie", str(sortie), "--seuil", "1"]
    )
    assert code == 0
    lignes = sortie.read_text(encoding="utf-8").split()
    assert lignes == ["MAISON", "ZEBRE"]  # trié, RARE exclue
