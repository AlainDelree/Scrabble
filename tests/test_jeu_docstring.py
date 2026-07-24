"""Garde-fou : vérifie que la docstring de test_jeu.py liste exactement les fichiers test_jeu_*.py existants (issue #265)."""

import glob
import re


def test_docstring_liste_fichiers_coherente():
    import tests.test_jeu as module_jeu

    docstring = module_jeu.__doc__ or ""
    mentionnes = set(re.findall(r"(test_jeu_\w+\.py)", docstring))

    existants = {
        f.split("/")[-1]
        for f in glob.glob("tests/test_jeu_*.py")
        if not f.endswith("test_jeu_docstring.py")
    }

    manquants = existants - mentionnes
    fantomes = mentionnes - existants

    messages = []
    if manquants:
        messages.append(f"Fichiers existants absents de la docstring : {sorted(manquants)}")
    if fantomes:
        messages.append(f"Fichiers mentionnés dans la docstring mais inexistants : {sorted(fantomes)}")

    assert not messages, "\n".join(messages)
