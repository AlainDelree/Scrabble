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

from scrabble.config import THEMES_PLATEAU, charger_config
from scrabble.dictionnaire.dictionnaire import normaliser_mot
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import ActionInvalide, Joueur, Partie
from scrabble.moteur.plateau_partie import (
    Coup,
    Direction,
    PlateauPartie,
    Tuile,
    dans_plateau,
)
from scrabble.moteur.validation import CoupInvalide, DictionnaireMots
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


def compter_humains(partie: Partie) -> int:
    """Nombre de joueurs **humains** dans la partie (champ ``Joueur.humain``).

    Sert à décider si le bouton « voir mes lettres » a un sens : avec un seul
    humain, il n'y a personne à qui cacher son chevalet, donc l'UI l'affiche
    directement sans bouton bascule ni état masqué. Avec deux humains ou plus,
    le chevalet reste masqué par défaut (confidentialité entre adversaires).
    """
    return sum(1 for joueur in partie.joueurs if joueur.humain)


def etat_public(partie: Partie, id_partie: int | None) -> dict[str, Any]:
    """État complet de la partie **sans aucune identité de lettre de chevalet**.

    C'est la vue partagée affichable par tous : plateau, scores, joueur courant,
    jetons restants dans le sac et état de fin. Les chevalets n'y figurent que
    par leur taille (``nb_lettres``) ; leur contenu ne s'obtient que via
    :meth:`ApiJeu.obtenir_chevalet`, un joueur à la fois.

    ``nb_humains`` (nombre de joueurs humains) permet à l'UI de n'afficher le
    bouton « voir mes lettres » que lorsqu'il y a au moins deux humains.
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
        "nb_humains": compter_humains(partie),
        "terminee": partie.terminee,
        "gagnants": [j.nom for j in partie.gagnants] if partie.terminee else [],
    }


# --------------------------------------------------------------------------- #
# Construction d'un Coup à partir de placements « clic-clic » (logique non-UI)
# --------------------------------------------------------------------------- #
# Le JavaScript accumule des « placements en attente » : pour chaque lettre
# déposée sur une case vide, un dict {ligne, colonne, lettre, joker}. Ces
# fonctions transforment cette liste en un :class:`Coup` prêt pour le moteur,
# sans aucune dépendance à pywebview : elles sont testables directement (voir
# tests/test_jeu.py). Elles ne valident PAS les règles du Scrabble (rôle de
# :mod:`scrabble.moteur.validation`) ; elles garantissent seulement que la
# structure du coup est cohérente (lettres alignées et contiguës).


def _direction_depuis_valeur(valeur: Any) -> Direction | None:
    """Convertit ``"H"``/``"V"`` (ou une :class:`Direction`) en direction.

    Renvoie ``None`` si ``valeur`` ne désigne aucune direction connue (cas d'un
    coup à plusieurs lettres où la direction se déduit du placement).
    """
    if isinstance(valeur, Direction):
        return valeur
    if isinstance(valeur, str):
        try:
            return Direction(valeur.upper())
        except ValueError:
            return None
    return None


def _lire_placement(placement: Any) -> tuple[int, int, str, bool]:
    """Valide et normalise un placement JS en ``(ligne, colonne, lettre, joker)``.

    :raises ValueError: si la position est absente/hors plateau ou si la lettre
        n'est pas une majuscule ``A``–``Z`` (un joker porte aussi la lettre
        qu'il représente).
    """
    if not isinstance(placement, dict):
        raise ValueError("Placement invalide : dictionnaire attendu.")
    ligne = placement.get("ligne")
    colonne = placement.get("colonne")
    lettre = placement.get("lettre")
    joker = bool(placement.get("joker", False))
    if not isinstance(ligne, int) or not isinstance(colonne, int):
        raise ValueError("Placement invalide : position (ligne, colonne) manquante.")
    if not dans_plateau(ligne, colonne):
        raise ValueError(
            f"Placement hors plateau en (ligne={ligne}, colonne={colonne})."
        )
    if isinstance(lettre, str):
        lettre = lettre.upper()
    if not (isinstance(lettre, str) and len(lettre) == 1 and "A" <= lettre <= "Z"):
        raise ValueError(f"Lettre de placement invalide : {lettre!r}.")
    return ligne, colonne, lettre, joker


def _deduire_direction(
    placements: list[tuple[int, int, str, bool]], direction: Direction | None
) -> Direction:
    """Déduit le sens du mot depuis les cases posées (ou l'impose si une seule).

    * Deux lettres ou plus : le sens se déduit de leur alignement (même ligne →
      horizontal, même colonne → vertical). Une seule lettre en attente laisse
      le choix libre — ``direction`` (fournie par l'UI) est alors utilisée, à
      défaut l'horizontale.
    * Lève :class:`ValueError` si les lettres ne sont ni alignées en ligne ni en
      colonne.
    """
    lignes = {ligne for ligne, _, _, _ in placements}
    colonnes = {colonne for _, colonne, _, _ in placements}
    if len(placements) == 1:
        return direction if direction is not None else Direction.HORIZONTALE
    meme_ligne = len(lignes) == 1
    meme_colonne = len(colonnes) == 1
    if meme_ligne and not meme_colonne:
        return Direction.HORIZONTALE
    if meme_colonne and not meme_ligne:
        return Direction.VERTICALE
    raise ValueError(
        "Les lettres posées ne sont ni alignées en ligne ni en colonne."
    )


def construire_coup(
    plateau: PlateauPartie,
    placements: list[Any],
    direction: Any = None,
) -> Coup:
    """Construit un :class:`Coup` à partir des placements en attente du JS.

    ``placements`` est la liste des lettres déposées (dicts
    ``{ligne, colonne, lettre, joker}``). Le coup renvoyé couvre le segment
    contigu du mot principal, de la première à la dernière lettre nouvelle, en
    **incluant les tuiles déjà présentes** que le mot enjambe (leur lettre est
    reprise telle quelle). ``direction`` (``"H"``/``"V"``) ne sert qu'au cas
    d'une seule lettre en attente ; sinon le sens se déduit de l'alignement.

    :raises ValueError: liste vide, position hors plateau, lettre invalide, deux
        lettres sur la même case, pose sur une case déjà occupée, lettres non
        alignées, ou trou (case vide) au milieu du mot.
    """
    if not placements:
        raise ValueError("Aucune lettre à poser sur le plateau.")
    lus = [_lire_placement(placement) for placement in placements]

    poses: dict[tuple[int, int], Tuile] = {}
    for ligne, colonne, lettre, joker in lus:
        if (ligne, colonne) in poses:
            raise ValueError(
                f"Deux lettres posées sur la même case (ligne={ligne}, "
                f"colonne={colonne})."
            )
        if not plateau.case_vide(ligne, colonne):
            raise ValueError(
                f"Une lettre est posée sur une case déjà occupée (ligne={ligne}, "
                f"colonne={colonne})."
            )
        poses[(ligne, colonne)] = Tuile(lettre, joker=joker)

    sens = _deduire_direction(lus, _direction_depuis_valeur(direction))
    if sens is Direction.HORIZONTALE:
        ligne = lus[0][0]
        colonnes = [colonne for _, colonne, _, _ in lus]
        depart = (ligne, min(colonnes))
        cases = [(ligne, colonne) for colonne in range(min(colonnes), max(colonnes) + 1)]
    else:
        colonne = lus[0][1]
        lignes = [ligne for ligne, _, _, _ in lus]
        depart = (min(lignes), colonne)
        cases = [(ligne, colonne) for ligne in range(min(lignes), max(lignes) + 1)]

    tuiles: list[Tuile] = []
    for position in cases:
        if position in poses:
            tuiles.append(poses[position])
        else:
            existante = plateau.tuile(*position)
            if existante is None:
                raise ValueError(
                    "Les lettres posées ne sont pas contiguës : il reste une case "
                    f"vide au milieu du mot (ligne={position[0]}, "
                    f"colonne={position[1]})."
                )
            tuiles.append(existante)

    return Coup(depart[0], depart[1], sens, tuple(tuiles))


def jouer_placements(
    partie: Partie,
    placements: list[Any],
    direction: Any = None,
) -> dict[str, Any]:
    """Construit le coup, le fait jouer par ``partie`` et renvoie succès/erreur.

    Cœur non-UI de :meth:`ApiJeu.poser_mot`. Tous les échecs prévisibles sont
    transformés en ``{"succes": False, "erreur": <message clair>}`` sans lever :

    * structure de coup incohérente (:class:`ValueError` de
      :func:`construire_coup`) ;
    * placement illégal (:class:`~scrabble.moteur.validation.CoupInvalide`) ;
    * lettres absentes du chevalet ou partie terminée
      (:class:`~scrabble.moteur.partie.ActionInvalide`).

    En cas de succès, l'appelant recharge l'état via :func:`etat_public` : rien
    n'est perdu côté attente puisque le moteur a consommé les lettres.
    """
    try:
        coup = construire_coup(partie.plateau, placements, direction)
    except ValueError as err:
        return {"succes": False, "erreur": str(err)}
    try:
        entree = partie.jouer_coup(coup)
    except CoupInvalide as err:
        return {"succes": False, "erreur": str(err)}
    except ActionInvalide as err:
        return {"succes": False, "erreur": str(err)}
    points = entree.detail.total if entree.detail is not None else 0
    return {
        "succes": True,
        "points": points,
        "nom": entree.nom_joueur,
    }


# --------------------------------------------------------------------------- #
# Zone de brouillon et actions de tour supplémentaires (logique non-UI)
# --------------------------------------------------------------------------- #
# Ces fonctions restent pures / testables directement (aucune dépendance à
# pywebview). La vérification dictionnaire est en LECTURE SEULE : elle ne touche
# jamais à l'état de la partie. L'échange complet délègue à Partie.echanger, qui
# consomme le tour et lève ActionInvalide si le sac est trop pauvre.


def _concatener_lettres(lettres: Any) -> str:
    """Concatène ``lettres`` (liste de jetons ou chaîne) en une seule chaîne.

    Accepte aussi bien la liste des jetons du brouillon (chacun une chaîne d'un
    caractère) qu'une chaîne déjà assemblée. Tout élément non-chaîne est ignoré.
    """
    if isinstance(lettres, str):
        return lettres
    if isinstance(lettres, (list, tuple)):
        return "".join(str(jeton) for jeton in lettres if isinstance(jeton, str))
    return ""


def verifier_mot_dictionnaire(
    dictionnaire: DictionnaireMots, lettres: Any
) -> dict[str, Any]:
    """Teste l'appartenance au dictionnaire du mot formé par ``lettres``.

    ``lettres`` est la suite de jetons arrangés dans la zone de brouillon (dans
    l'ordre affiché), soit sous forme de liste, soit déjà concaténée. Le mot est
    normalisé (majuscules, NFC) comme le Trie ODS8 l'attend, puis testé via
    :meth:`dictionnaire.contient`. **Lecture seule** : aucune mutation de la
    partie ni du dictionnaire.

    Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool}`` ; si la suite est
    vide (après normalisation), ``{"succes": False, "erreur": <message>}``. Un
    joker (``*``) laissé dans le brouillon n'est pas une lettre fixe : il empêche
    tout mot d'être trouvé (le test renverra ``valide`` faux), ce qui est le
    comportement attendu d'un simple test d'appartenance.
    """
    mot = normaliser_mot(_concatener_lettres(lettres))
    if not mot:
        return {
            "succes": False,
            "erreur": "La zone de brouillon ne contient aucune lettre à vérifier.",
        }
    return {"succes": True, "mot": mot, "valide": bool(dictionnaire.contient(mot))}


def echanger_chevalet_complet(
    partie: Partie, id_partie: int | None
) -> dict[str, Any]:
    """Remet **tout** le chevalet du joueur courant dans le sac et passe le tour.

    Cœur non-UI de :meth:`ApiJeu.echanger_tout`. Délègue à
    :meth:`~scrabble.moteur.partie.Partie.echanger` avec la totalité du chevalet
    courant : l'échange consomme déjà le tour, aucun passe séparé n'est requis.
    Le cas « sac trop pauvre pour échanger tout le chevalet » (ou partie
    terminée) est capturé et transformé en ``{"succes": False, "erreur": ...}``
    sans plantage. En cas de succès, l'état public rafraîchi est joint.
    """
    joueur = partie.joueur_courant()
    jetons = list(joueur.chevalet)
    try:
        partie.echanger(jetons)
    except ActionInvalide as err:
        return {"succes": False, "erreur": str(err)}
    return {"succes": True, "etat": etat_public(partie, id_partie)}


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

    def obtenir_theme_plateau(self) -> str:
        """Retourne le thème visuel du plateau choisi dans les réglages.

        Lit ``theme_plateau`` de :func:`~scrabble.config.charger_config` (champ
        auto-réparant : une valeur inconnue retombe sur ``"classique"``). Le JS
        applique la classe CSS ``theme-<nom>`` correspondante au plateau et
        choisit les libellés (complets ou abrégés). Par sécurité, si la valeur
        lue n'est pas un thème connu, on renvoie ``"classique"``.
        """
        theme = charger_config().get("theme_plateau", "classique")
        return theme if theme in THEMES_PLATEAU else "classique"

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

    def poser_mot(
        self, placements: list[Any], direction: Any = None
    ) -> dict[str, Any]:
        """Pose le mot décrit par ``placements`` (mécanique clic-clic du JS).

        ``placements`` est la liste des lettres déposées sur des cases vides
        (dicts ``{ligne, colonne, lettre, joker}``) ; ``direction`` (``"H"`` ou
        ``"V"``) ne sert que pour une seule lettre en attente, le sens se
        déduisant sinon de l'alignement. La méthode construit un
        :class:`~scrabble.moteur.plateau_partie.Coup`, appelle
        :meth:`~scrabble.moteur.partie.Partie.jouer_coup` et renvoie :

        * en cas de succès : ``{"succes": True, "points": ..., "etat": ...}``
          où ``etat`` est l'état public rafraîchi (plateau, scores, tour) ;
        * en cas d'échec : ``{"succes": False, "erreur": <message clair>}`` — les
          lettres en attente ne sont pas perdues (le JS les conserve pour
          correction).

        Confidentialité : la réponse ne contient jamais l'identité des lettres
        d'un chevalet (``etat`` est l'état public, sans chevalet).
        """
        resultat = jouer_placements(self._partie, placements, direction)
        if resultat.get("succes"):
            resultat["etat"] = etat_public(self._partie, self._id_partie)
        return resultat

    def verifier_mot(self, lettres: Any) -> dict[str, Any]:
        """Teste dans le dictionnaire le mot formé par la zone de brouillon.

        ``lettres`` est la suite de jetons arrangés dans le brouillon (dans
        l'ordre affiché). Le test est en **lecture seule** : il ne pose aucun
        coup, ne consomme aucun tour et ne modifie en rien l'état de la partie.
        Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool}`` ou, si le
        brouillon est vide, ``{"succes": False, "erreur": <message>}``.
        """
        return verifier_mot_dictionnaire(self._partie.dictionnaire, lettres)

    def echanger_tout(self) -> dict[str, Any]:
        """Remet tout le chevalet du joueur courant dans le sac et passe le tour.

        Utilise :meth:`~scrabble.moteur.partie.Partie.echanger` avec la totalité
        du chevalet courant (l'échange consomme déjà le tour). En cas de succès :
        ``{"succes": True, "etat": <état public rafraîchi>}`` (tour suivant,
        chevalet à remasquer selon le nombre d'humains). Si le sac ne contient
        pas assez de jetons (ou partie terminée) :
        ``{"succes": False, "erreur": <message clair>}`` — l'état n'est pas
        modifié.
        """
        return echanger_chevalet_complet(self._partie, self._id_partie)


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
