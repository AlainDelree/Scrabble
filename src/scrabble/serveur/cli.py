"""Point d'entrée du prototype de serveur local (issue #475).

Commande ::

    python -m scrabble.serveur [--reseau] [--port 8765] [--dossier-donnees CHEMIN]

Voir ``CONTEXTE.md`` pour le détail des options et l'avertissement de
sécurité. Aucune fenêtre n'est ouverte : ``ApiRouteur`` (routeur d'API
existant, ``scrabble.ui.application``) est utilisé directement, avec une
``ApiAccueil``/``ApiJeu`` comme pour l'application de bureau — seule la
fenêtre pywebview est remplacée par le serveur HTTP (:mod:`scrabble.serveur.
httpd`) et un pont de diffusion (:mod:`scrabble.serveur.pont`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: Port par défaut, délibérément différent de 8000 (point 2 de l'issue #475).
PORT_DEFAUT = 8765

#: Dossier de données utilisateur par défaut du serveur — distinct de celui de
#: l'application de bureau (point 7) : ``~/.local/share/scrabble-serveur`` sur
#: Linux. Jamais ``RACINE_DONNEES_UTILISATEUR`` (dépôt/installation).
DOSSIER_DONNEES_DEFAUT = Path.home() / ".local" / "share" / "scrabble-serveur"

_BANNIERE = """\
==============================================================================
 Scrabble — prototype de serveur local (issue #475)
 AUCUNE AUTHENTIFICATION. Réservé à un réseau local DE CONFIANCE.
 Ne JAMAIS exposer ce serveur sur Internet (pas de pare-feu, pas de compte,
 pas de chiffrement : quiconque atteint cette adresse joue la partie en cours).
 Adresse : http://{hote}:{port}/
==============================================================================
"""


def construire_argpars() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="python -m scrabble.serveur",
        description="Prototype de serveur local Scrabble (un seul joueur, issue #475).",
    )
    analyseur.add_argument(
        "--reseau",
        action="store_true",
        help=(
            "Écoute sur toutes les interfaces (0.0.0.0) pour être joignable "
            "depuis un téléphone sur le même réseau local. Par défaut : "
            "127.0.0.1 uniquement (cette machine)."
        ),
    )
    analyseur.add_argument(
        "--port",
        type=int,
        default=PORT_DEFAUT,
        help=f"Port d'écoute (défaut : {PORT_DEFAUT}).",
    )
    analyseur.add_argument(
        "--dossier-donnees",
        type=Path,
        default=DOSSIER_DONNEES_DEFAUT,
        help=(
            "Dossier de données utilisateur du serveur (config.json, "
            f"data/parties.db, logs/) — défaut : {DOSSIER_DONNEES_DEFAUT}."
        ),
    )
    return analyseur


def main(argv: list[str] | None = None) -> int:
    args = construire_argpars().parse_args(argv)

    # Isolation AVANT tout import de scrabble.ui/scrabble.dictionnaire : les
    # constantes de chemin de ces modules sont calculées à l'import (cf.
    # scrabble.serveur.donnees pour le détail et les limites de l'approche).
    from scrabble.serveur.donnees import isoler_donnees_utilisateur

    chemins = isoler_donnees_utilisateur(args.dossier_donnees)

    from scrabble import journal
    from scrabble.serveur.httpd import ServeurScrabble
    from scrabble.serveur.pont import FenetrePont, GestionnaireDiffusion
    from scrabble.ui.accueil import ApiAccueil
    from scrabble.ui.application import DOSSIER_WEB, ApiRouteur, VUE_ACCUEIL
    from scrabble.ui.jeu import ApiJeu

    journal.demarrer_session(dossier=chemins["logs"])

    diffusion = GestionnaireDiffusion()
    fenetre_pont = FenetrePont(diffusion)
    api_jeu = ApiJeu(chemin_persistance=chemins["base_parties"])
    api_jeu.set_window(fenetre_pont)
    routeur = ApiRouteur(api_accueil=ApiAccueil(), api_jeu=api_jeu, vue_active=VUE_ACCUEIL)
    # Pas de ``routeur.set_window(...)`` : la navigation Accueil↔Jeu est donc
    # laissée au navigateur (point 6 — cf. CONTEXTE.md et le rapport de
    # l'issue #475 pour le détail des méthodes concernées).
    # Routée dynamiquement par ``ApiRouteur`` (méthode publique d'``ApiAccueil``,
    # vue active = accueil) — même effet que l'accès privé fait par
    # ``lancer_application_unifiee``, sans sortir du contrat public du routeur.
    routeur.initialiser_joueur_humain()

    hote = "0.0.0.0" if args.reseau else "127.0.0.1"
    serveur = ServeurScrabble((hote, args.port), DOSSIER_WEB, routeur, fenetre_pont, diffusion)

    hote_affiche = "0.0.0.0 (réseau local)" if args.reseau else "127.0.0.1 (cette machine)"
    print(_BANNIERE.format(hote=hote_affiche, port=args.port), file=sys.stderr)
    print(f"Données utilisateur : {args.dossier_donnees}", file=sys.stderr)

    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
        journal.cloturer_session()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
