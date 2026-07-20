"""Fenêtre de réglages à onglets « Général » et « Dictionnaire » (pywebview).

Deuxième partie de la fenêtre de réglages (issue #111, suite du plan #109 et du
backend #110). Fenêtre graphique **autonome**, distincte de l'accueil et de
l'écran de jeu, qui expose enfin dans une UI les réglages jusqu'ici pilotables
seulement en ligne de commande, et offre l'édition manuelle du dictionnaire.

Deux onglets (bascule pur CSS/JS, cohérente avec le reste du projet — pas de
framework) :

* **Général** — s'appuie sur le socle existant (``config.py`` / ``reglages.py``,
  aucun nouveau système de persistance) : prénom principal, avatar du joueur
  (issue #143, sélecteur visuel), thème du plateau, source de dictionnaire
  active. ``mode_saisie`` / ``niveau_ia`` restent des clés dormantes (issue #109)
  et ne sont volontairement **pas** exposées.

* **Dictionnaire** — recherche d'un mot et statut **par source** (ODS / Hunspell)
  via :func:`~scrabble.dictionnaire.dictionnaire.rechercher_statut` : présent /
  absent, ajouté / retiré manuellement, avec ajout/suppression manuel dans une
  source précise (:func:`~scrabble.dictionnaire.dictionnaire.modifier_appartenance`)
  et la définition si disponible (``definitions.json``, ODS8 uniquement).

Ouverture
---------
La fenêtre s'ouvre depuis l'écran d'accueil (bouton « ⚙ Réglages ») en tant que
**seconde fenêtre** de la boucle pywebview déjà démarrée
(:meth:`~scrabble.ui.accueil.ApiAccueil.ouvrir_reglages`) ; à sa fermeture, le
contrôle revient naturellement à l'accueil. Elle peut aussi être lancée seule
pour test via :func:`lancer_reglages` (``python -m scrabble.ui.reglages``), qui
gère alors sa propre boucle ``webview.start()`` après avoir sélectionné le
backend graphique (issue #93), comme l'accueil et l'écran de jeu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import webview

from scrabble import journal
from scrabble.config import AVATARS_DISPONIBLES, THEMES_PLATEAU, TYPES_ECHANGE
from scrabble.dictionnaire.dictionnaire import (
    SOURCES,
    modifier_appartenance,
    rechercher_statut,
)
from scrabble.reglages import lire_reglage, modifier_reglage
from scrabble.ui import TAPIS_VERT

DOSSIER_WEB = Path(__file__).parent / "web"

# Libellés français des valeurs à choix fini, pour les menus de l'onglet Général
# et l'affichage des colonnes de l'onglet Dictionnaire. Les clés restent les
# identifiants de code (alignés avec config.THEMES_PLATEAU et dictionnaire.SOURCES).
LABELS_THEMES: dict[str, str] = {
    "classique": "Classique",
    "vert": "Vert",
    "abrege": "Abrégé",
}
LABELS_SOURCES: dict[str, str] = {
    "ods": "ODS 8",
    "hunspell": "Hunspell",
}
LABELS_TYPES_ECHANGE: dict[str, str] = {
    "complet": "Échange complet",
    "partiel": "Échange partiel",
}


class ApiReglages:
    """API Python exposée au JavaScript de la fenêtre de réglages (js_api)."""

    def __init__(self) -> None:
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """Associe la fenêtre pywebview pour les callbacks (fermeture)."""
        self._window = window

    def fermer_fenetre(self) -> dict[str, Any]:
        """Ferme la fenêtre de réglages depuis Python.

        Comme pour l'accueil (issue #53), la fermeture via ``window.destroy()``
        côté Python est plus fiable que ``window.close()`` côté JS, qui n'est pas
        honoré par tous les backends pywebview (GTK/WebKit sous Linux). Retourne
        ``{"succes": bool, ...}`` pour que le JS réagisse au lieu de rester figé.
        """
        if self._window is None:
            return {"succes": False, "erreur": "Aucune fenêtre associée."}
        try:
            self._window.destroy()
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            return {"succes": False, "erreur": f"Fermeture impossible : {e}"}

    # ------------------------------------------------------------------ #
    # Onglet Général
    # ------------------------------------------------------------------ #

    def obtenir_reglages_generaux(self) -> dict[str, Any]:
        """Renvoie les valeurs courantes + les options des menus déroulants.

        S'appuie entièrement sur ``reglages.lire_reglage`` (donc sur la config
        auto-réparante) : les valeurs renvoyées sont déjà normalisées. Les
        options sont livrées ``[{"valeur", "libelle"}, ...]`` pour que le JS
        construise directement les ``<option>`` sans dupliquer les libellés.
        """
        return {
            "prenom_principal": self._lire("prenom_principal"),
            "theme_plateau": self._lire("theme_plateau"),
            "source_dictionnaire": self._lire("source_dictionnaire"),
            "bonus_fin_partie": self._lire_bool("bonus_fin_partie"),
            "type_echange": self._lire("type_echange"),
            "avatar_principal": self._lire("avatar_principal"),
            # Grille d'avatars disponibles pour le sélecteur visuel (issue #143) :
            # on livre l'identifiant et le chemin du SVG (relatif à la page web)
            # pour que le JS construise les vignettes sans dupliquer la liste.
            "avatars": [
                {"valeur": a, "image": f"avatars/{a}.svg"}
                for a in AVATARS_DISPONIBLES
            ],
            "themes": [
                {"valeur": t, "libelle": LABELS_THEMES.get(t, t)}
                for t in THEMES_PLATEAU
            ],
            "sources": [
                {"valeur": s, "libelle": LABELS_SOURCES.get(s, s)}
                for s in SOURCES
            ],
            "types_echange": [
                {"valeur": t, "libelle": LABELS_TYPES_ECHANGE.get(t, t)}
                for t in TYPES_ECHANGE
            ],
        }

    def enregistrer_reglage(self, cle: str, valeur: Any) -> dict[str, Any]:
        """Enregistre un réglage de l'onglet Général et renvoie la valeur retenue.

        Passe par ``reglages.modifier_reglage`` (normalisation + écriture atomique
        de ``config.py``). Pour ``source_dictionnaire``, non contraint par
        ``config.py`` mais qui ne connaît que :data:`SOURCES`, on rejette en amont
        toute valeur inconnue (une source invalide dégraderait silencieusement la
        validation en repartant sur l'ODS). ``valeur`` est une chaîne pour la
        plupart des clés (vide autorisée pour le prénom principal, en texte
        libre) et un booléen pour les clés booléennes (ex. ``bonus_fin_partie``).
        Retourne ``{"succes", "valeur"}`` ou ``{"succes": False, "erreur"}``.
        """
        try:
            if cle == "source_dictionnaire" and valeur not in SOURCES:
                return {
                    "succes": False,
                    "erreur": f"Source de dictionnaire inconnue : « {valeur} ».",
                }
            retenue = modifier_reglage(cle, valeur)
            journal.info(f"Réglages : « {cle} » = {retenue!r}.")
            return {"succes": True, "valeur": retenue}
        except KeyError:
            return {"succes": False, "erreur": f"Réglage inconnu : « {cle} »."}
        except TypeError as e:
            return {"succes": False, "erreur": str(e)}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            journal.erreur(f"Réglages : échec d'enregistrement de « {cle} ».", e)
            return {"succes": False, "erreur": str(e)}

    @staticmethod
    def _lire(cle: str) -> str:
        """Lit un réglage en tolérant l'absence (renvoie chaîne vide)."""
        try:
            return lire_reglage(cle) or ""
        except Exception:  # noqa: BLE001 - config illisible : on dégrade en vide
            return ""

    @staticmethod
    def _lire_bool(cle: str) -> bool:
        """Lit un réglage booléen en tolérant l'absence (renvoie ``False``)."""
        try:
            return bool(lire_reglage(cle))
        except Exception:  # noqa: BLE001 - config illisible : on dégrade en False
            return False

    # ------------------------------------------------------------------ #
    # Onglet Dictionnaire
    # ------------------------------------------------------------------ #

    def rechercher_mot(self, mot: str) -> dict[str, Any]:
        """Recherche un mot et renvoie son statut par source + définition.

        Délègue à :func:`~scrabble.dictionnaire.dictionnaire.rechercher_statut`.
        ⚠️ Le premier accès à la source Hunspell la déplie (plusieurs secondes,
        puis mise en cache mémoire) : le JS affiche un indicateur d'attente. Une
        source indisponible (spylls absent) est signalée par ``indisponible`` sans
        planter. Renvoie ``{"succes": True, ...statut...}`` ou une erreur.
        """
        try:
            statut = rechercher_statut(mot)
            statut["succes"] = True
            return statut
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            journal.erreur(f"Réglages : échec de recherche de « {mot} ».", e)
            return {"succes": False, "erreur": str(e)}

    def ajouter_mot(self, mot: str, source: str) -> dict[str, Any]:
        """Ajoute manuellement un mot à une source précise, puis renvoie le statut."""
        return self._modifier(mot, source, present=True, verbe="ajouté à")

    def retirer_mot(self, mot: str, source: str) -> dict[str, Any]:
        """Retire manuellement un mot d'une source précise, puis renvoie le statut."""
        return self._modifier(mot, source, present=False, verbe="retiré de")

    @staticmethod
    def _modifier(
        mot: str, source: str, present: bool, verbe: str
    ) -> dict[str, Any]:
        """Applique un ajout/retrait manuel et renvoie le statut rafraîchi.

        L'écriture des fichiers de personnalisation périme automatiquement le
        cache Trie de la source (mtime) ; le statut renvoyé est recalculé après
        modification pour que l'UI reflète immédiatement le nouvel état.
        """
        try:
            norme = modifier_appartenance(mot, source, present)
            journal.info(
                f"Réglages : « {norme} » {verbe} la source « {source} »."
            )
            statut = rechercher_statut(norme)
            statut["succes"] = True
            return statut
        except ValueError as e:
            return {"succes": False, "erreur": str(e)}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            journal.erreur(
                f"Réglages : échec de modification de « {mot} » "
                f"(source {source}).",
                e,
            )
            return {"succes": False, "erreur": str(e)}


def creer_fenetre_reglages(api: ApiReglages | None = None) -> webview.Window:
    """Crée la fenêtre pywebview des réglages et l'associe à son API.

    Isolé de :func:`lancer_reglages` pour que l'accueil puisse ouvrir la fenêtre
    comme **seconde fenêtre** de sa boucle déjà démarrée (sans relancer
    ``webview.start()``), tout en partageant exactement la même configuration de
    fenêtre. Retourne la fenêtre créée.
    """
    if api is None:
        api = ApiReglages()
    chemin_html = DOSSIER_WEB / "reglages.html"
    window = webview.create_window(
        "Scrabble - Réglages",
        str(chemin_html),
        js_api=api,
        # Fenêtre maximisée par défaut (issue #159), comme l'accueil et le plateau :
        # la fiche joueur / les onglets de réglages restent lisibles sans format
        # flottant réduit. ``maximized=True`` étant un no-op sous XWayland (cf. #95),
        # le déploiement effectif est forcé par ``deployer_fenetre_maximisee`` après
        # démarrage de la boucle (voir :func:`lancer_reglages` et l'ouverture depuis
        # l'accueil). ``width``/``height`` restent la taille de restauration/repli.
        maximized=True,
        width=760,
        height=720,
        resizable=True,
        # Fond vert dès le mappage de la fenêtre (issue #113) : évite le blanc
        # par défaut de pywebview pendant le chargement HTML/CSS.
        background_color=TAPIS_VERT,
    )
    api.set_window(window)
    return window


def lancer_reglages() -> None:
    """Lance la fenêtre de réglages dans sa propre boucle pywebview (test/CLI).

    Sélectionne d'abord le backend graphique (issue #93) — utile seulement si
    aucune autre fenêtre pywebview n'a encore été ouverte dans le processus —
    puis ouvre la fenêtre et bloque sur ``webview.start()`` jusqu'à sa fermeture.
    Quand la fenêtre est ouverte **depuis l'accueil**, on passe au contraire par
    :func:`creer_fenetre_reglages` sans redémarrer la boucle.
    """
    from scrabble.ui.backend_graphique import (
        configurer_backend_graphique,
        deployer_fenetre_maximisee,
    )

    configurer_backend_graphique()
    window = creer_fenetre_reglages()
    # Déploiement plein écran une fois la boucle démarrée (issue #159), comme
    # l'accueil et le plateau (contournement du no-op XWayland de maximized=True).
    webview.start(deployer_fenetre_maximisee, (window, "réglages"))


def main() -> int:
    """Point d'entrée pour test manuel : ouvre la fenêtre de réglages."""
    session_ouverte = journal.session_courante() is not None
    if not session_ouverte:
        journal.demarrer_session()
    try:
        lancer_reglages()
    finally:
        if not session_ouverte:
            journal.cloturer_session()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
