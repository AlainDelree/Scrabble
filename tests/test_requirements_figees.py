"""Garde-fou : chaque dépendance de requirements.txt doit être figée à une
version exacte (``==``), issue #502.

Limite connue : ce test vérifie seulement l'écriture des lignes présentes
dans requirements.txt. Il ne lance ni pip ni aucun accès réseau, et ne peut
donc pas détecter qu'une dépendance transitive serait absente de la liste.
"""

from pathlib import Path

CHEMIN_REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


def _lignes_dependances(chemin):
    lignes = []
    for brute in chemin.read_text(encoding="utf-8").splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#"):
            continue
        lignes.append(ligne)
    return lignes


def test_chaque_dependance_est_figee_a_une_version_exacte():
    fautives = []
    for ligne in _lignes_dependances(CHEMIN_REQUIREMENTS):
        specification = ligne.split(";", 1)[0].strip()
        if "==" not in specification:
            fautives.append(ligne)
            continue
        nom, _, reste = specification.partition("==")
        if not nom.strip() or not reste.strip():
            fautives.append(ligne)
            continue
        for interdit in ("<", ">", ",", "!", "~", "*"):
            if interdit in reste:
                fautives.append(ligne)
                break

    assert not fautives, (
        "Lignes de requirements.txt non figées à une version exacte (==) : "
        f"{fautives}"
    )
