"""Verrouillage du dictionnaire côté serveur (issue #479).

Trois mécaniques distinctes, toutes pensées pour empêcher un client distant de
reconstituer le dictionnaire de jeu (``data/dictionnaire/``, jamais diffusé) à
coups d'appels automatisés :

1. :data:`FONCTIONS_DICTIONNAIRE_INTERDITES` — les quatre méthodes de gestion
   des mots de l'onglet Dictionnaire des réglages (``ApiAccueil``), qui
   répondent « le mot existe / n'existe pas » sans aucune limite côté bureau.
   Interceptées par ``scrabble.serveur.httpd`` AVANT toute résolution de
   fonction, et exclues de la liste des fonctions exposées au navigateur
   (``scrabble.serveur.pont.fonctions_exposees``) pour qu'elles n'apparaissent
   même pas comme appelables (``typeof api.xxx !== 'function'``, comme une
   fonction qui n'existe pas).

2. :class:`LimiteurFrequence` — ``verifier_coup``/``verifier_mot`` restent
   d'authentiques fonctions de jeu (le bouton « Vérifier et calculer » et le
   champ « Tapez un mot à tester »), mais répondent toutes deux « valide »/
   « refusé » pour n'importe quelle entrée : elles sont donc chacune limitées
   en fréquence par adresse de client, avec une pause qui s'allonge en cas
   d'insistance après un refus. ``poser_mot`` (le bouton « Jouer ce coup »)
   rejoue le même oracle — accepté/refusé — et reçoit donc la même limite que
   ``verifier_coup`` (issue #483) : un appel compte qu'il soit finalement
   accepté ou refusé. **Réglages dans un seul endroit** :
   :data:`LIMITES_FREQUENCE` et :data:`PALIERS_BLOCAGE_SECONDES` ci-dessous
   (voir aussi ``CONTEXTE.md``, section « Serveur local »).

3. :func:`verifier_pose_hors_chevalet`/:func:`verifier_placements_hors_chevalet`
   — ``poser_lettre_en_attente`` (mode « finalisation », après le choix de la
   lettre d'un joker) et ``verifier_coup``/``poser_mot`` (quand ``placements``
   est fourni explicitement, au lieu de l'état de pose interne habituel)
   acceptent aujourd'hui, côté ``scrabble.ui``, n'importe quelle lettre sans
   vérifier qu'elle vient réellement du chevalet du joueur courant — un
   détournement qui transforme ces fonctions en oracle de dictionnaire à
   lettres arbitraires. Le contrôle est rejoué ici, en lisant le chevalet
   **via les fonctions publiques déjà exposées** (``obtenir_etat`` +
   ``obtenir_chevalet``) : aucun accès à l'état privé d'``ApiJeu``, donc aucune
   modification de ``scrabble.ui``.

Toutes les décisions de ce module sont journalisées par l'appelant
(``scrabble.serveur.httpd``) SANS jamais inclure les arguments de l'appel
(lettres, mots) — seule l'adresse du client et le nom de la fonction/limite
concernée (point 5 de l'issue #479).
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from typing import Any, Callable

from scrabble.regles.lettres import JOKER

# --------------------------------------------------------------------------- #
# Point 1 — fonctions de gestion des mots, interdites en mode serveur
# --------------------------------------------------------------------------- #

#: Les quatre méthodes de l'onglet Dictionnaire des réglages (``ApiAccueil``,
#: ``scrabble.ui.accueil``) : gèrent la liste des mots de jeu, jamais appelées
#: depuis le téléphone (l'onglet disparaît côté serveur, voir ``httpd``). Toute
#: AUTRE fonction qui révèle l'existence d'un mot ou propose des mots à partir
#: de lettres arbitraires a été recherchée (rapport de clôture de l'issue
#: #479) : aucune ne s'est trouvée hors de ``verifier_mot``/``verifier_coup``,
#: déjà traitées séparément (point 2 ci-dessous).
FONCTIONS_DICTIONNAIRE_INTERDITES = frozenset(
    {"rechercher_mot", "ajouter_mot", "retirer_mot", "marquer_classique_mot"}
)

#: Message renvoyé pour un appel à l'une de ces quatre fonctions — distinct du
#: générique « Fonction inconnue » (une fonction réellement absente), pour que
#: le journal et une éventuelle relecture distinguent clairement un appel
#: délibérément bloqué d'une faute de frappe dans le nom de la fonction.
MESSAGE_FONCTION_INTERDITE = (
    "Fonction de gestion du dictionnaire indisponible sur ce serveur : "
    "réservée à l'application de bureau."
)

# --------------------------------------------------------------------------- #
# Point 4 — limites de fréquence des vérifications
# --------------------------------------------------------------------------- #

#: Réglages des trois limites, modifiables UNIQUEMENT ici (documenté dans
#: CONTEXTE.md) : ``{nom_fonction: (appels_max_par_minute, appels_max_par_jour)}``.
#: Ordres de grandeur délibérément larges pour qu'un joueur honnête ne les
#: atteigne jamais (de l'ordre d'un coup par tour) ; ``verifier_mot`` est plus
#: stricte que ``verifier_coup``/``poser_mot`` car elle accepte n'importe
#: quelle suite de lettres (pas besoin qu'un coup soit en cours de pose), donc
#: un oracle plus direct sur le dictionnaire. ``poser_mot`` reprend exactement
#: les plafonds de ``verifier_coup`` (issue #483) : poser un mot et observer
#: s'il est accepté ou refusé est le même oracle de dictionnaire que
#: « vérifier et calculer », une fois celui-ci verrouillé par l'issue #479.
LIMITES_FREQUENCE: dict[str, tuple[int, int]] = {
    "verifier_coup": (30, 1000),
    "poser_mot": (30, 1000),
    "verifier_mot": (10, 200),
}

#: Paliers de pause (secondes) appliqués en cas d'insistance après un refus —
#: 1 min, puis 5 min, puis 15 min, plafonné au dernier palier au-delà.
PALIERS_BLOCAGE_SECONDES: tuple[float, ...] = (60.0, 300.0, 900.0)

#: Fenêtres glissantes (secondes) des deux compteurs par client.
_FENETRE_MINUTE_SECONDES = 60.0
_FENETRE_JOUR_SECONDES = 86400.0

MESSAGE_LIMITE_FREQUENCE = "Trop de vérifications, réessayez dans quelques minutes."


class _EtatClient:
    """État mutable d'un client pour UNE fonction limitée (``LimiteurFrequence``)."""

    __slots__ = ("appels_minute", "appels_jour", "blocage_jusqua", "niveau_blocage")

    def __init__(self) -> None:
        self.appels_minute: list[float] = []
        self.appels_jour: list[float] = []
        self.blocage_jusqua: float = 0.0
        self.niveau_blocage: int = 0


class LimiteurFrequence:
    """Compteur en mémoire par adresse de client — remis à zéro au redémarrage.

    Pensé pour un seul processus ``ThreadingHTTPServer`` (verrou interne,
    partagé par tous les fils de connexion). La clé est l'adresse du client
    (``self.client_address[0]`` côté ``httpd``) : en l'absence de comptes, voir
    ``CONTEXTE.md`` — la limite sera rattachée au compte quand les comptes
    existeront.

    Deux fenêtres glissantes (par minute, par jour) ; au-delà de l'une ou
    l'autre, le client est bloqué pour la durée du palier courant
    (:data:`PALIERS_BLOCAGE_SECONDES`), qui s'allonge à chaque nouveau refus
    pendant ou après un blocage (« insistance ») et se réinitialise au premier
    appel de nouveau accepté.
    """

    def __init__(self, max_par_minute: int, max_par_jour: int) -> None:
        self._max_par_minute = max_par_minute
        self._max_par_jour = max_par_jour
        self._verrou = threading.Lock()
        self._etats: dict[str, _EtatClient] = {}

    def autoriser(self, adresse: str, maintenant: float | None = None) -> bool:
        """Décide si un nouvel appel de ``adresse`` est autorisé À CET INSTANT.

        ``maintenant`` (horodatage ``time.time()``) est un paramètre explicite
        — jamais lu implicitement dans la boucle — pour que les tests
        simulent le passage du temps sans attendre réellement une minute ou
        un jour.
        """
        instant = maintenant if maintenant is not None else time.time()
        with self._verrou:
            etat = self._etats.setdefault(adresse, _EtatClient())
            if instant < etat.blocage_jusqua:
                self._escalader(etat, instant)
                return False
            etat.appels_minute = [
                t for t in etat.appels_minute if instant - t < _FENETRE_MINUTE_SECONDES
            ]
            etat.appels_jour = [
                t for t in etat.appels_jour if instant - t < _FENETRE_JOUR_SECONDES
            ]
            if (
                len(etat.appels_minute) >= self._max_par_minute
                or len(etat.appels_jour) >= self._max_par_jour
            ):
                self._escalader(etat, instant)
                return False
            etat.appels_minute.append(instant)
            etat.appels_jour.append(instant)
            etat.niveau_blocage = 0
            return True

    def _escalader(self, etat: _EtatClient, instant: float) -> None:
        palier = PALIERS_BLOCAGE_SECONDES[
            min(etat.niveau_blocage, len(PALIERS_BLOCAGE_SECONDES) - 1)
        ]
        etat.blocage_jusqua = instant + palier
        etat.niveau_blocage += 1


def construire_limiteurs() -> dict[str, LimiteurFrequence]:
    """Un :class:`LimiteurFrequence` par fonction de :data:`LIMITES_FREQUENCE`."""
    return {
        nom: LimiteurFrequence(max_minute, max_jour)
        for nom, (max_minute, max_jour) in LIMITES_FREQUENCE.items()
    }


# --------------------------------------------------------------------------- #
# Point 3 — lettres posées/vérifiées limitées au chevalet réel
# --------------------------------------------------------------------------- #

MESSAGE_CHEVALET_INVALIDE = "Cette lettre ne correspond pas à votre chevalet."

#: Paramètres réels de ``MixinPose.poser_lettre_en_attente``/``verifier_coup``/
#: ``poser_mot`` (``scrabble.ui.api_pose``), dans leur ordre positionnel exact
#: — nécessaires pour relier arguments positionnels ET par mot-clé envoyés par
#: le navigateur, puisque les fonctions exposées par ``ApiRouteur`` sont des
#: enveloppes génériques ``(*args, **kwargs)`` (``application.py:_creer_route``)
#: qui ne portent plus les noms de paramètres réels pour l'introspection.
_PARAMETRES_POSE = ("ligne", "colonne", "lettre", "joker", "valeur", "index")
_PARAMETRES_PLACEMENTS = ("placements",)


def _valeurs_nommees(
    noms: tuple[str, ...], args: list[Any], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Reconstruit ``{nom_paramètre: valeur}`` à partir d'args/kwargs JSON reçus."""
    valeurs = dict(zip(noms, args))
    valeurs.update(kwargs)
    return valeurs


def chevalet_du_joueur_courant(
    fonctions: dict[str, Callable[..., Any]],
) -> list[str] | None:
    """Jetons du chevalet du joueur dont c'est le tour, ou ``None`` si indisponible.

    Lit **uniquement** deux fonctions déjà publiques du routeur —
    ``obtenir_etat`` (pour ``index_courant``) puis ``obtenir_chevalet`` (pour
    les jetons de ce joueur, ``"*"`` pour un joker non encore choisi) — jamais
    l'état privé d'``ApiJeu``. ``None`` couvre tout cas où la lecture échoue
    (vue accueil active, aucune partie chargée, etc.) : l'appelant renonce
    alors au contrôle et laisse le vrai appel échouer de lui-même avec son
    propre message (ex. « Aucune partie chargée »).
    """
    fn_etat = fonctions.get("obtenir_etat")
    fn_chevalet = fonctions.get("obtenir_chevalet")
    if fn_etat is None or fn_chevalet is None:
        return None
    try:
        etat = fn_etat()
        if not isinstance(etat, dict) or not isinstance(etat.get("index_courant"), int):
            return None
        chevalet = fn_chevalet(etat["index_courant"])
        if not isinstance(chevalet, dict) or not chevalet.get("succes"):
            return None
        lettres = chevalet.get("lettres")
        if not isinstance(lettres, list):
            return None
        return [jeton.get("lettre") for jeton in lettres if isinstance(jeton, dict)]
    except Exception:  # noqa: BLE001 - un filet de sécurité ne doit jamais planter
        return None


def verifier_pose_hors_chevalet(
    fonctions: dict[str, Callable[..., Any]], args: list[Any], kwargs: dict[str, Any]
) -> str | None:
    """Rejoue, pour ``poser_lettre_en_attente``, le contrôle absent côté ``ui``.

    Ne s'applique qu'au mode « finalisation » (``lettre``/``index`` fournis —
    même garde que :func:`~scrabble.ui.api_pose.MixinPose.poser_lettre_en_attente`
    lui-même) : le mode « clic plateau » (``ligne``/``colonne`` seuls) résout
    déjà la lettre depuis le chevalet réel, sans rien recevoir du client.

    Un joker du chevalet (jeton :data:`~scrabble.regles.lettres.JOKER`) reste
    utilisable avec n'importe quelle lettre choisie (``joker=True``), mais
    SEULEMENT si l'emplacement visé du chevalet porte réellement un joker.
    """
    valeurs = _valeurs_nommees(_PARAMETRES_POSE, args, kwargs)
    lettre = valeurs.get("lettre")
    index = valeurs.get("index")
    if lettre is None or index is None:
        return None
    chevalet = chevalet_du_joueur_courant(fonctions)
    if chevalet is None:
        return None
    if not isinstance(index, int) or not (0 <= index < len(chevalet)):
        return MESSAGE_CHEVALET_INVALIDE
    jeton = chevalet[index]
    if bool(valeurs.get("joker")):
        if jeton != JOKER:
            return MESSAGE_CHEVALET_INVALIDE
    elif not isinstance(lettre, str) or jeton != lettre.upper():
        return MESSAGE_CHEVALET_INVALIDE
    return None


def verifier_placements_hors_chevalet(
    fonctions: dict[str, Callable[..., Any]], args: list[Any], kwargs: dict[str, Any]
) -> str | None:
    """Rejoue, pour ``verifier_coup``/``poser_mot``, le contrôle absent côté ``ui``.

    Ne s'applique que si ``placements`` est fourni explicitement (sinon les
    deux fonctions relisent l'état de pose interne, déjà protégé par
    :func:`verifier_pose_hors_chevalet` en amont). Vérifie que le multiensemble
    des jetons requis (``"*"`` pour chaque lettre marquée ``joker``) est bien
    inclus dans le chevalet réel du joueur courant — même logique que
    ``Partie._multiset_inclus``/``Partie.jouer_coup``, rejouée ici en lecture
    seule avant tout calcul de score ou test dictionnaire.
    """
    valeurs = _valeurs_nommees(_PARAMETRES_PLACEMENTS, args, kwargs)
    placements = valeurs.get("placements")
    if not placements:
        return None
    chevalet = chevalet_du_joueur_courant(fonctions)
    if chevalet is None:
        return None
    requis: list[str] = []
    for placement in placements:
        if not isinstance(placement, dict):
            return MESSAGE_CHEVALET_INVALIDE
        if bool(placement.get("joker")):
            requis.append(JOKER)
            continue
        lettre = placement.get("lettre")
        if not isinstance(lettre, str) or not lettre:
            return MESSAGE_CHEVALET_INVALIDE
        requis.append(lettre.upper())
    disponible = Counter(chevalet)
    for jeton, nombre in Counter(requis).items():
        if disponible[jeton] < nombre:
            return MESSAGE_CHEVALET_INVALIDE
    return None


#: Association fonction → contrôleur de chevalet (point 3), consultée par
#: ``scrabble.serveur.httpd`` avant tout appel réel.
CONTROLES_CHEVALET: dict[
    str, Callable[[dict[str, Callable[..., Any]], list[Any], dict[str, Any]], str | None]
] = {
    "poser_lettre_en_attente": verifier_pose_hors_chevalet,
    "verifier_coup": verifier_placements_hors_chevalet,
    "poser_mot": verifier_placements_hors_chevalet,
}
