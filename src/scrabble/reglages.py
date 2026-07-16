"""Utilitaire de consultation et de modification des réglages.

Petit outil en ligne de commande (et API Python testable) pour lire ou
changer les valeurs de ``config.json`` sans éditer le fichier à la main.
Il s'appuie entièrement sur ``scrabble.config`` : les valeurs écrites sont
donc normalisées et le fichier reste auto-réparant.

Exemples ::

    python -m scrabble.reglages                      # affiche tous les réglages
    python -m scrabble.reglages prenom_principal     # affiche une valeur
    python -m scrabble.reglages prenom_principal Marie   # modifie une valeur
    python -m scrabble.reglages prenom_principal ""      # efface la valeur
"""

from __future__ import annotations

import os
import sys
from typing import Any

from .config import (
    CHEMIN_CONFIG,
    CONFIG_DEFAUT,
    charger_config,
    sauvegarder_config,
)


def lister_reglages(chemin: os.PathLike[str] | str = CHEMIN_CONFIG) -> dict[str, Any]:
    """Retourne l'ensemble des réglages courants (normalisés)."""
    return charger_config(chemin)


def lire_reglage(cle: str, chemin: os.PathLike[str] | str = CHEMIN_CONFIG) -> Any:
    """Retourne la valeur courante de ``cle``.

    Lève ``KeyError`` si la clé n'est pas un réglage connu.
    """
    _verifier_cle(cle)
    return charger_config(chemin)[cle]


def modifier_reglage(
    cle: str, valeur: str, chemin: os.PathLike[str] | str = CHEMIN_CONFIG
) -> Any:
    """Écrit ``valeur`` pour le réglage ``cle`` et renvoie la valeur retenue.

    La valeur passe par la normalisation de ``scrabble.config`` : un champ
    contraint recevant une valeur invalide retombe sur son défaut, tandis
    qu'un champ en texte libre (ex. ``prenom_principal``) accepte le vide.
    Lève ``KeyError`` si la clé est inconnue et ``TypeError`` si la valeur
    n'est pas une chaîne.
    """
    _verifier_cle(cle)
    if not isinstance(valeur, str):
        raise TypeError(f"La valeur de « {cle} » doit être une chaîne de caractères.")
    config = charger_config(chemin)
    config[cle] = valeur
    sauvegarder_config(config, chemin)
    # On relit pour renvoyer la valeur réellement retenue après normalisation.
    return charger_config(chemin)[cle]


def _verifier_cle(cle: str) -> None:
    """Vérifie que ``cle`` fait partie des réglages connus."""
    if cle not in CONFIG_DEFAUT:
        connues = ", ".join(sorted(CONFIG_DEFAUT))
        raise KeyError(f"Réglage inconnu : « {cle} ». Réglages connus : {connues}.")


def _formater_reglages(config: dict[str, Any]) -> str:
    """Met en forme les réglages pour un affichage lisible."""
    largeur = max(len(cle) for cle in config)
    lignes = [f"{cle.ljust(largeur)} = {valeur!r}" for cle, valeur in sorted(config.items())]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande. Retourne un code de sortie."""
    args = list(sys.argv[1:] if argv is None else argv)

    # On relit la constante depuis le module (et non le défaut figé des
    # signatures) pour rester substituable dans les tests.
    chemin = CHEMIN_CONFIG

    if not args:
        print(_formater_reglages(lister_reglages(chemin)))
        return 0

    cle = args[0]
    try:
        if len(args) == 1:
            print(lire_reglage(cle, chemin))
        elif len(args) == 2:
            retenue = modifier_reglage(cle, args[1], chemin)
            print(f"{cle} = {retenue!r}")
        else:
            print("Usage : python -m scrabble.reglages [CLE [VALEUR]]", file=sys.stderr)
            return 2
    except (KeyError, TypeError) as erreur:
        # KeyError met le message entre guillemets : on l'affiche proprement.
        message = erreur.args[0] if erreur.args else str(erreur)
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
