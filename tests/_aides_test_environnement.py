"""Aides partagées pour détecter des conditions d'environnement de test (issue #464).

Un dossier de travail isolé (clone secondaire, sans les données manuellement
déposées dans ``data/dictionnaire/``) ne dispose pas des fichiers de
vocabulaire IA par palier. Les tests qui en dépendent réellement (pas
seulement via un ``Trie`` factice) doivent donc être ignorés proprement là où
la donnée manque, et continuer de s'exécuter normalement sur un poste complet
qui la possède.
"""

from scrabble.dictionnaire.dictionnaire import paliers_disponibles


def palier_vocabulaire_indisponible(nom_palier: str) -> bool:
    """Vrai si le fichier de vocabulaire du palier d'IA donné est absent du disque.

    Ne couvre pas les paliers « expert » et « champion_du_monde », toujours
    disponibles (voir :func:`~scrabble.dictionnaire.dictionnaire.paliers_disponibles`).
    """
    return not paliers_disponibles().get(nom_palier, False)
