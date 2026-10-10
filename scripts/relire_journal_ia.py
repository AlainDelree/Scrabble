#!/usr/bin/env python3
"""Relit, tour par tour, le journal de décision des joueurs ordinateur (issue #445).

Contexte
--------
Pour juger le style d'un personnage (Opportuniste, et d'autres plus tard), il
faut voir ce qu'un ordinateur avait comme lettres et quels coups il aurait pu
jouer, pas seulement le coup qu'il a choisi. Depuis l'issue #445, chaque action
d'un ordinateur (coup, passe) enregistre dans la sauvegarde de la partie son
chevalet juste avant l'action et les meilleurs coups qu'il avait, selon le
score stratégique — voir :mod:`scrabble.moteur.ia`
(:func:`~scrabble.moteur.ia.evaluer_coups`) et :mod:`scrabble.moteur.partie`
(:class:`~scrabble.moteur.partie.JournalDecisionIA`).

Ce script affiche ce journal sous une forme lisible, collable dans une
conversation : un tableau texte, tour par tour, suivi d'un résumé par joueur.
Il ouvre la base **en lecture seule** (voir
:func:`scrabble.persistance.stockage.lire_actions_journalisees`) : aucune
écriture, aucun risque pour une partie en cours.

Les parties enregistrées avant l'issue #445 n'ont pas de journal : leurs
coups sont affichés seuls, avec la mention « chevalet non enregistré ».

Usage
-----
    python scripts/relire_journal_ia.py data/parties.db 42
    python scripts/relire_journal_ia.py data/parties.db 42 --joueur "Thomas"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scrabble.moteur.partie import (  # noqa: E402
    ACTION_COUP,
    ACTION_ECHANGE,
    ACTION_PASSE,
)
from scrabble.moteur.personnages import PERSONNAGES  # noqa: E402
from scrabble.moteur.plateau_partie import PlateauPartie  # noqa: E402
from scrabble.persistance.stockage import (  # noqa: E402
    ActionJournalisee,
    ConfigurationPartie,
    lire_actions_journalisees,
    lire_configuration_partie,
)
from scrabble.regles.plateau import TypeCase  # noqa: E402

#: Types de case comptant comme « mot double ou triple » pour le résumé.
_CASES_MOT_DOUBLE_TRIPLE = frozenset({TypeCase.MOT_DOUBLE, TypeCase.MOT_TRIPLE})


def _libelle_joueur(config: dict) -> str:
    """Nom affichable d'un joueur : prénom (personnage, niveau) pour une IA."""
    if config["humain"]:
        return f"{config['nom']} (humain)"
    niveau = config.get("niveau") or "?"
    cle_personnage = config.get("personnage") or ""
    if cle_personnage and cle_personnage in PERSONNAGES:
        personnage = PERSONNAGES[cle_personnage].prenom
        return f"{config['nom']} ({personnage}, {niveau})"
    return f"{config['nom']} ({niveau})"


def _ligne_chevalet(config: dict, action: ActionJournalisee) -> str | None:
    """Chevalet avant l'action, ou ``None`` si rien à afficher (joueur humain).

    Un chevalet humain n'est jamais journalisé (confidentialité, hors sujet
    ici) : ce n'est pas une absence de données à signaler, contrairement à
    une vieille partie IA enregistrée avant l'issue #445.
    """
    if config["humain"]:
        return None
    if action.journal_ia is None:
        return "(chevalet non enregistré — partie antérieure à cette fonctionnalité)"
    return " ".join(action.journal_ia.chevalet_avant)


def _ligne_alternative(alt, choisi: bool) -> str:
    marque = " <- choisi" if choisi else ""
    return (
        f"{alt.mot!r} ({alt.ligne},{alt.colonne}) {alt.direction} "
        f"réel={alt.score_reel} stratégique={alt.score_strategique}{marque}"
    )


def _afficher_action(indice: int, config_joueurs: list[dict], action: ActionJournalisee) -> None:
    config = config_joueurs[action.index_joueur]
    print(f"--- Tour {indice} — {_libelle_joueur(config)} ---")
    ligne_chevalet = _ligne_chevalet(config, action)
    if ligne_chevalet is not None:
        print(f"  Chevalet avant : {ligne_chevalet}")

    if action.action == ACTION_COUP and action.coup is not None and action.detail is not None:
        mot = action.detail.mots[0].texte if action.detail.mots else "?"
        print(
            f"  Coup joué      : {mot!r} en ({action.coup.ligne},{action.coup.colonne}) "
            f"{action.coup.direction.value} — score {action.detail.total}"
        )
    elif action.action == ACTION_PASSE:
        print("  Action         : passe")
    elif action.action == ACTION_ECHANGE:
        print(f"  Action         : échange de {len(action.jetons_echanges)} lettre(s)")

    journal = action.journal_ia
    if journal is not None:
        print(f"  Rang du coup choisi : {journal.rang_choisi} / {journal.nb_coups_possibles}")
        if journal.meilleurs:
            print("  Meilleurs coups (score stratégique) :")
            mots_affiches = set()
            for alt in journal.meilleurs:
                cle = (alt.mot, alt.ligne, alt.colonne, alt.direction)
                mots_affiches.add(cle)
                est_choisi = (
                    journal.coup_choisi is not None
                    and cle
                    == (
                        journal.coup_choisi.mot,
                        journal.coup_choisi.ligne,
                        journal.coup_choisi.colonne,
                        journal.coup_choisi.direction,
                    )
                )
                print(f"    - {_ligne_alternative(alt, est_choisi)}")
            if journal.coup_choisi is not None:
                cle_choisi = (
                    journal.coup_choisi.mot,
                    journal.coup_choisi.ligne,
                    journal.coup_choisi.colonne,
                    journal.coup_choisi.direction,
                )
                if cle_choisi not in mots_affiches:
                    print(
                        "    (hors du top, coup réellement joué) "
                        f"{_ligne_alternative(journal.coup_choisi, True)}"
                    )
        elif journal.nb_coups_possibles == 0 and action.action != ACTION_COUP:
            print("  Aucun coup n'était disponible.")
    print()


class _StatsJoueur:
    """Compteurs accumulés pour le résumé final d'un joueur."""

    def __init__(self) -> None:
        self.nb_coups = 0
        self.nb_bonus = 0
        self.nb_mot_double_triple = 0
        self.total_lettres_posees = 0
        self.nb_jokers = 0
        self.score_jokers = 0
        self.nb_passes = 0
        self.nb_echanges = 0


def _construire_resume(
    config_joueurs: list[dict], actions: list[ActionJournalisee]
) -> dict[int, _StatsJoueur]:
    """Rejoue les coups sur un plateau neuf pour compter les lettres nouvellement posées.

    Aucune dépendance au journal de décision : fonctionne identiquement pour
    une partie ancienne (sans journal) ou récente — seul l'affichage par tour
    distingue les deux, pas le résumé.
    """
    stats = {i: _StatsJoueur() for i in range(len(config_joueurs))}
    plateau = PlateauPartie()
    for action in actions:
        s = stats[action.index_joueur]
        if action.action == ACTION_PASSE:
            s.nb_passes += 1
        elif action.action == ACTION_ECHANGE:
            s.nb_echanges += 1
        elif action.action == ACTION_COUP and action.coup is not None:
            nouvelles = plateau.poser_coup(action.coup)
            s.nb_coups += 1
            s.total_lettres_posees += len(nouvelles)
            if action.detail is not None:
                cases_bonus = [cb for mot in action.detail.mots for cb in mot.cases_bonus]
                if cases_bonus:
                    s.nb_bonus += 1
                if any(tc in _CASES_MOT_DOUBLE_TRIPLE for (_, _, tc) in cases_bonus):
                    s.nb_mot_double_triple += 1
            if any(tuile.joker for tuile in action.coup.tuiles):
                s.nb_jokers += 1
                if action.detail is not None:
                    s.score_jokers += action.detail.total
    return stats


def _afficher_resume(config_joueurs: list[dict], stats: dict[int, _StatsJoueur]) -> None:
    print("=== Résumé par joueur ===")
    for indice, config in enumerate(config_joueurs):
        s = stats[indice]
        print(f"- {_libelle_joueur(config)} :")
        if s.nb_coups:
            print(f"    coups joués            : {s.nb_coups}")
            print(f"    dont case bonus        : {s.nb_bonus} ({100 * s.nb_bonus / s.nb_coups:.0f} %)")
            print(
                "    dont mot double/triple : "
                f"{s.nb_mot_double_triple} ({100 * s.nb_mot_double_triple / s.nb_coups:.0f} %)"
            )
            print(f"    lettres posées/coup    : {s.total_lettres_posees / s.nb_coups:.1f} en moyenne")
        else:
            print("    aucun coup joué")
        print(f"    jokers joués           : {s.nb_jokers} (score cumulé {s.score_jokers})")
        print(f"    passes                 : {s.nb_passes}")
        print(f"    échanges               : {s.nb_echanges}")


def relire(
    chemin_base: str, id_partie: int, joueur: str | None = None
) -> None:
    """Affiche le journal de décision complet d'une partie, tour par tour."""
    config: ConfigurationPartie = lire_configuration_partie(id_partie, chemin_base)
    actions = lire_actions_journalisees(id_partie, chemin_base)

    print(f"=== Partie #{id_partie} (graine {config.graine}) ===")
    for indice, j in enumerate(config.joueurs):
        print(f"  Joueur {indice} : {_libelle_joueur(j)}")
    print()

    for indice, action in enumerate(actions):
        if joueur is not None and action.nom_joueur != joueur:
            continue
        _afficher_action(indice, config.joueurs, action)

    stats = _construire_resume(config.joueurs, actions)
    indices_affiches = [
        i
        for i, j in enumerate(config.joueurs)
        if joueur is None or j["nom"] == joueur
    ]
    _afficher_resume(
        [config.joueurs[i] for i in indices_affiches],
        {pos: stats[i] for pos, i in enumerate(indices_affiches)},
    )


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("base", help="Chemin du fichier SQLite de parties (ex. data/parties.db).")
    parser.add_argument("id_partie", type=int, help="Identifiant de la partie à relire.")
    parser.add_argument(
        "--joueur", default=None, help="Ne montrer que les actions de ce joueur (par nom)."
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _construire_parser().parse_args(argv)
    relire(args.base, args.id_partie, args.joueur)


if __name__ == "__main__":
    main()
