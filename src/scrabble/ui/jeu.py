"""Écran de jeu : affichage du plateau et du chevalet (pywebview).

Première brique de l'écran de jeu (suite de l'écran d'accueil, issue #27).
Cet écran est **en lecture seule** : il affiche le plateau, les tuiles déjà
posées, les scores, le joueur courant et le nombre de jetons restants dans le
sac. Aucune pose de mot n'est encore possible ici (ce sera l'étape suivante).

Confidentialité du chevalet
---------------------------
Dans une partie à plusieurs joueurs humains sur le même écran, le chevalet du
joueur courant n'est **jamais** affiché automatiquement : il reste masqué par
défaut. Seul un clic explicite sur « voir mes lettres » le révèle, et « cacher
mes lettres » le remasque à tout moment (pas seulement au changement de tour).
Côté API, une seule règle structurelle garantit ce principe : :meth:`ApiJeu.
obtenir_chevalet` n'expose **que** le chevalet du joueur dont l'index est
demandé — il n'existe aucune méthode renvoyant tous les chevalets d'un coup, et
:func:`etat_public` ne contient aucune identité de lettre.

Lancement de l'écran pour test (mode démonstration) ::

    python -m scrabble.ui.jeu

Ce mode construit une :class:`~scrabble.moteur.partie.Partie` d'exemple à deux
joueurs, avec un plateau partiellement rempli (voir :func:`construire_partie_demo`),
et ouvre l'écran de jeu sans passer par l'écran d'accueil.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import webview

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.plateau_partie import PlateauPartie, Tuile
from scrabble.moteur.validation import DictionnaireMots
from scrabble.regles.lettres import JOKER, valeur_lettre
from scrabble.regles.plateau import TAILLE, type_case

DOSSIER_WEB = Path(__file__).parent / "web"


# --------------------------------------------------------------------------- #
# Sérialisation de l'état de partie vers des structures JSON (logique non-UI)
# --------------------------------------------------------------------------- #
# Ces fonctions sont volontairement pures et sans dépendance à pywebview : elles
# sont testables directement (voir tests/test_jeu.py). Le type de chaque case
# provient de scrabble.regles.plateau.type_case — il n'est PAS redéfini côté JS.


def serialiser_case(plateau: PlateauPartie, ligne: int, colonne: int) -> dict[str, Any]:
    """Sérialise une case : son type de bonus et la tuile éventuellement posée.

    Le champ ``type`` est la valeur du :class:`~scrabble.regles.plateau.TypeCase`
    (``"MT"``, ``"MD"``, ``"LT"``, ``"LD"``, ``"centre"`` ou ``"normale"``). Si
    la case porte une tuile, ``lettre`` est la lettre affichée et ``joker`` dit
    si c'est un joker (valeur nulle) ; sinon ``lettre`` vaut ``None``.
    """
    tuile = plateau.tuile(ligne, colonne)
    return {
        "type": type_case(ligne, colonne).value,
        "lettre": tuile.lettre if tuile is not None else None,
        "joker": bool(tuile.joker) if tuile is not None else False,
    }


def serialiser_plateau(plateau: PlateauPartie) -> list[list[dict[str, Any]]]:
    """Sérialise les ``TAILLE`` × ``TAILLE`` cases du plateau en lignes de cases."""
    return [
        [serialiser_case(plateau, ligne, colonne) for colonne in range(TAILLE)]
        for ligne in range(TAILLE)
    ]


def serialiser_joueur_public(joueur: Joueur, index: int, courant: bool) -> dict[str, Any]:
    """Sérialise les infos **publiques** d'un joueur (sans révéler ses lettres).

    Contient le nombre de lettres du chevalet (``nb_lettres``) mais **jamais**
    leur identité : l'affichage masqué peut ainsi montrer le bon nombre de
    rectangles grisés sans rien dévoiler.
    """
    return {
        "index": index,
        "nom": joueur.nom,
        "humain": joueur.humain,
        "niveau": joueur.niveau.name if joueur.niveau is not None else None,
        "score": joueur.score,
        "nb_lettres": len(joueur.chevalet),
        "courant": courant,
    }


def serialiser_chevalet(joueur: Joueur) -> list[dict[str, Any]]:
    """Sérialise le chevalet d'un joueur : lettre, valeur et drapeau joker.

    Un joker (jeton :data:`~scrabble.regles.lettres.JOKER`) n'a pas encore de
    lettre attribuée sur le chevalet : il est renvoyé avec ``lettre`` = ``"*"``,
    ``valeur`` = 0 et ``joker`` = ``True``.
    """
    return [
        {
            "lettre": jeton,
            "valeur": valeur_lettre(jeton),
            "joker": jeton == JOKER,
        }
        for jeton in joueur.chevalet
    ]


def etat_public(partie: Partie, id_partie: int | None) -> dict[str, Any]:
    """État complet de la partie **sans aucune identité de lettre de chevalet**.

    C'est la vue partagée affichable par tous : plateau, scores, joueur courant,
    jetons restants dans le sac et état de fin. Les chevalets n'y figurent que
    par leur taille (``nb_lettres``) ; leur contenu ne s'obtient que via
    :meth:`ApiJeu.obtenir_chevalet`, un joueur à la fois.
    """
    return {
        "id_partie": id_partie,
        "taille": TAILLE,
        "plateau": serialiser_plateau(partie.plateau),
        "joueurs": [
            serialiser_joueur_public(joueur, index, index == partie.index_courant)
            for index, joueur in enumerate(partie.joueurs)
        ],
        "index_courant": partie.index_courant,
        "jetons_sac": partie.sac.jetons_restants(),
        "terminee": partie.terminee,
        "gagnants": [j.nom for j in partie.gagnants] if partie.terminee else [],
    }


# --------------------------------------------------------------------------- #
# API Python exposée au JavaScript
# --------------------------------------------------------------------------- #


class ApiJeu:
    """API Python exposée au JavaScript de l'écran de jeu (lecture seule).

    L'API respecte la règle de confidentialité : ``obtenir_etat`` ne révèle
    aucune lettre de chevalet, et ``obtenir_chevalet`` n'expose que le chevalet
    d'**un seul** joueur (celui dont l'index est demandé) à la fois.
    """

    def __init__(self, partie: Partie, id_partie: int | None) -> None:
        self._partie = partie
        self._id_partie = id_partie
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """Associe la fenêtre pywebview pour les callbacks."""
        self._window = window

    def obtenir_etat(self) -> dict[str, Any]:
        """Retourne l'état public de la partie (sans lettres de chevalet)."""
        return etat_public(self._partie, self._id_partie)

    def obtenir_chevalet(self, index_joueur: int) -> dict[str, Any]:
        """Retourne le chevalet du **seul** joueur d'index ``index_joueur``.

        C'est le point d'entrée du bouton « voir mes lettres ». Il ne renvoie
        jamais le chevalet d'un autre joueur ni la totalité des chevalets : le
        joueur qui révèle ses lettres ne dévoile rien de celles des autres.
        """
        if not isinstance(index_joueur, int) or not (
            0 <= index_joueur < len(self._partie.joueurs)
        ):
            return {"succes": False, "erreur": "Index de joueur invalide."}
        joueur = self._partie.joueurs[index_joueur]
        return {
            "succes": True,
            "index": index_joueur,
            "nom": joueur.nom,
            "lettres": serialiser_chevalet(joueur),
        }


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #


def lancer_jeu(partie: Partie, id_partie: int | None) -> None:
    """Lance l'écran de jeu pour la ``partie`` donnée (bloquant).

    ``partie`` est typiquement celle créée par l'écran d'accueil (issue #27) ;
    ``id_partie`` est son identifiant de persistance (peut être ``None`` en
    mode démonstration autonome).
    """
    api = ApiJeu(partie, id_partie)
    chemin_html = DOSSIER_WEB / "jeu.html"
    window = webview.create_window(
        "Scrabble - Partie en cours",
        str(chemin_html),
        js_api=api,
        width=980,
        height=820,
        resizable=True,
    )
    api.set_window(window)
    webview.start()


class _DictionnaireFactice:
    """Dictionnaire minimal pour le mode démonstration (accepte tout mot).

    L'écran de jeu étant en lecture seule, aucun coup n'est validé ici ; ce stub
    évite de charger le vrai dictionnaire juste pour afficher une partie d'exemple.
    """

    def contient(self, mot: str) -> bool:  # noqa: D102 - stub de démonstration
        return True


def construire_partie_demo() -> tuple[Partie, int | None]:
    """Construit une partie d'exemple (2 joueurs, plateau partiellement rempli).

    Sert au test manuel autonome de cet écran (``python -m scrabble.ui.jeu``),
    sans passer par l'écran d'accueil. Les tuiles sont posées directement sur le
    plateau et les scores fixés à des valeurs plausibles : le but est de valider
    le **rendu** (cases bonus, tuiles, joker, scores, joueur courant, sac), pas
    de rejouer une partie réelle. Un joker (« blanc ») figure dans le mot vertical
    pour illustrer sa distinction visuelle.
    """
    dictionnaire: DictionnaireMots = _DictionnaireFactice()
    joueurs = [
        Joueur(nom="Camille", humain=True),
        Joueur(nom="Léon", humain=False, niveau=Niveau.INTERMEDIAIRE),
    ]
    partie = Partie(joueurs, dictionnaire, graine=20260716)

    # Mot horizontal « MAISON » passant par la case centrale (7, 7).
    mot_h = "MAISON"
    for i, lettre in enumerate(mot_h):
        partie.plateau.poser_tuile(7, 4 + i, Tuile(lettre))
    # Mot vertical « OPUS » croisant le « O » de MAISON en (7, 8).
    # Le « U » est joué avec un joker (lettre blanche) pour la démonstration.
    partie.plateau.poser_tuile(8, 8, Tuile("P"))
    partie.plateau.poser_tuile(9, 8, Tuile("U", joker=True))
    partie.plateau.poser_tuile(10, 8, Tuile("S"))

    # Scores plausibles pour deux coups joués et tour de Camille.
    partie.joueurs[0].score = 14
    partie.joueurs[1].score = 9
    partie.index_courant = 0
    return partie, None


def main() -> int:
    """Point d'entrée de test : lance l'écran de jeu en mode démonstration."""
    partie, id_partie = construire_partie_demo()
    lancer_jeu(partie, id_partie)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
