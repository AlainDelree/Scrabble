"""Écran d'accueil : configuration d'une nouvelle partie (pywebview).

Point d'entrée de l'application de jeu Scrabble. Permet de :
- ajouter des joueurs humains (jusqu'à 4)
- ajouter des adversaires « ordinateur » (jusqu'à 3) avec un niveau de difficulté
- lancer une partie avec la configuration choisie
- reprendre une partie en cours

Une fois la partie créée ou reprise, l'écran d'accueil se ferme et l'écran de
jeu s'ouvre automatiquement avec la partie en cours (issue #52).

Vocabulaire : l'écran dit « ordinateur » et jamais « IA » (moins intimidant).
Les identifiants de code (Joueur.humain, Niveau) restent inchangés.

La fermeture de l'accueil après un lancer/reprendre se fait depuis Python via
``ApiAccueil.fermer_fenetre()`` (``window.destroy()``) et non via
``window.close()`` côté JS, qui n'est pas honoré par tous les backends
pywebview (GTK/WebKit sous Linux) et laissait le bouton bloqué sur « Création
en cours... » (issue #53).

Lancement de l'écran pour test ::

    python -m scrabble.ui.accueil

Test manuel (issue #53) — vérifier l'enchaînement accueil → jeu :

1. Lancer ``python -m scrabble.ui.accueil`` (ou l'accueil depuis l'app).
2. Ajouter au moins un joueur humain et un ordinateur (n'importe quel niveau).
3. Cliquer « Lancer la partie ». Attendu : la fenêtre d'accueil se FERME
   réellement (elle ne reste pas bloquée sur « Création en cours... ») et
   l'écran de jeu s'ouvre avec les bons joueurs.
4. Fermer le jeu, relancer l'accueil, puis dans « Parties en cours » cliquer
   « Reprendre » sur une partie. Attendu : même comportement — l'accueil se
   ferme (pas de blocage sur « Chargement... ») et l'écran de jeu s'ouvre sur
   la partie reprise.
5. Filet de sécurité : si ``destroy()`` échoue, le bouton se réactive avec un
   message d'erreur (au lieu de rester figé indéfiniment).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import webview

from scrabble import journal
from scrabble.config import (
    AVATARS_DISPONIBLES,
    THEMES_PLATEAU,
    TYPES_ECHANGE,
    charger_config,
)
from scrabble.dictionnaire.dictionnaire import (
    SOURCES,
    charger_dictionnaire,
    marquer_classique,
    modifier_appartenance,
    obtenir_trie,
    obtenir_trie_ia,
    rechercher_statut,
)
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import MAX_JOUEURS, Partie, creer_partie
from scrabble.persistance.stockage import (
    CHEMIN_DEFAUT,
    ResumePartie,
    demarrer_suivi,
    lister_parties,
    reprendre_partie,
)
from scrabble.reglages import lire_reglage, modifier_reglage
from scrabble.ui import TAPIS_VERT
from scrabble.ui.noms_ordinateur import tirer_prenoms

DOSSIER_WEB = Path(__file__).parent / "web"

# Un seul joueur humain est autorisé par partie (issue #175). Le support
# historique de plusieurs humains simultanés a été abandonné : le jeu n'est
# utilisé qu'avec UN humain face à des ordinateurs. Cette limite est appliquée
# côté configuration/création uniquement — la reprise d'une partie sauvegardée
# reste possible même si elle comportait plusieurs humains (voir stockage.py).
MAX_HUMAINS = 1
MAX_ORDINATEURS = 3

NIVEAUX_LABELS: dict[str, Niveau] = {
    "Débutant": Niveau.DEBUTANT,
    "Facile": Niveau.FACILE,
    "Intermédiaire": Niveau.INTERMEDIAIRE,
    "Avancé": Niveau.AVANCE,
    "Expert": Niveau.EXPERT,
}

# Libellés français des valeurs à choix fini pour le panneau Réglages intégré
# à l'accueil (issue #169, ex-fenêtre autonome ``ui/reglages.py``). Les clés
# restent les identifiants de code (alignés avec config.THEMES_PLATEAU,
# config.TYPES_ECHANGE et dictionnaire.SOURCES) ; le JS construit ses <option>
# et boutons radio directement à partir de ces couples {valeur, libelle}.
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


@dataclass
class JoueurConfig:
    """Configuration d'un joueur avant création de la partie."""

    nom: str
    humain: bool = True
    niveau: Niveau | None = None


@dataclass
class ConfigPartie:
    """Configuration complète de la partie à créer."""

    joueurs: list[JoueurConfig] = field(default_factory=list)

    @property
    def nb_humains(self) -> int:
        """Nombre de joueurs humains configurés."""
        return sum(1 for j in self.joueurs if j.humain)

    @property
    def nb_ordinateurs(self) -> int:
        """Nombre d'ordinateurs configurés."""
        return sum(1 for j in self.joueurs if not j.humain)

    @property
    def nb_total(self) -> int:
        """Nombre total de joueurs."""
        return len(self.joueurs)

    def noms_utilises(self) -> set[str]:
        """Ensemble des prénoms déjà attribués (humains et ordinateurs)."""
        return {j.nom for j in self.joueurs}

    def peut_ajouter_humain(self) -> bool:
        """Vrai si on peut encore ajouter un joueur humain."""
        return self.nb_humains < MAX_HUMAINS and self.nb_total < MAX_JOUEURS

    def peut_ajouter_ordinateur(self) -> bool:
        """Vrai si on peut encore ajouter un ordinateur."""
        return self.nb_ordinateurs < MAX_ORDINATEURS and self.nb_total < MAX_JOUEURS

    def peut_lancer(self) -> bool:
        """Vrai si la configuration permet de lancer une partie.

        Il faut **exactement un** joueur humain (issue #175) : au moins un
        (contrat historique du moteur) et au plus un (le multi-humains n'est
        plus supporté). ``ajouter_humain``/``peut_ajouter_humain`` empêchent
        déjà d'en configurer plusieurs via l'UI ; cette égalité stricte est le
        garde-fou backend non contournable, doublé du message explicite de
        :meth:`ApiAccueil.lancer_partie`.
        """
        return self.nb_humains == 1

    def ajouter_humain(self, nom: str) -> bool:
        """Ajoute un joueur humain si possible. Retourne le succès."""
        if not self.peut_ajouter_humain():
            return False
        self.joueurs.append(JoueurConfig(nom=nom, humain=True))
        return True

    def ajouter_ordinateur(self, nom: str, niveau: Niveau) -> bool:
        """Ajoute un ordinateur si possible. Retourne le succès."""
        if not self.peut_ajouter_ordinateur():
            return False
        self.joueurs.append(JoueurConfig(nom=nom, humain=False, niveau=niveau))
        return True

    def retirer(self, index: int) -> bool:
        """Retire le joueur à l'index donné. Retourne le succès."""
        if 0 <= index < len(self.joueurs):
            del self.joueurs[index]
            return True
        return False


class ApiAccueil:
    """API Python exposée au JavaScript de l'écran d'accueil."""

    def __init__(self) -> None:
        self.config_partie = ConfigPartie()
        self._partie: Partie | None = None
        self._id_partie: int | None = None
        self._window: webview.Window | None = None
        # Détail nécessaire au tirage d'ordre, désormais affiché DANS la fenêtre
        # Jeu et non plus en modale de l'accueil (issue #170). ``lancer_partie``
        # le renseigne (``{noms_creation, graine, noms_humains}``) et
        # :func:`lancer_accueil` le transmet à :func:`~scrabble.ui.jeu.lancer_jeu`.
        self._infos_tirage: dict[str, Any] | None = None

    def set_window(self, window: webview.Window) -> None:
        """Associe la fenêtre pywebview pour les callbacks."""
        self._window = window

    def fermer_fenetre(self) -> dict[str, Any]:
        """Ferme la fenêtre d'accueil depuis Python (issue #53).

        Appelée par le JS après un lancer/reprendre réussi. Fermer la fenêtre
        côté Python via ``window.destroy()`` est plus fiable que ``window.close()``
        côté JS, qui n'est pas intercepté par tous les backends pywebview
        (notamment GTK/WebKit sous Linux). Une fois toutes les fenêtres fermées,
        ``webview.start()`` retourne et ``lancer_jeu(...)`` peut s'exécuter.

        Retourne ``{"succes": True}`` si la fermeture a été demandée, sinon
        ``{"succes": False, "erreur": ...}`` pour que le JS réactive le bouton
        plutôt que de rester bloqué.
        """
        if self._window is None:
            return {"succes": False, "erreur": "Aucune fenêtre associée."}
        try:
            self._window.destroy()
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            return {"succes": False, "erreur": f"Fermeture impossible : {e}"}

    def obtenir_prenom_principal(self) -> str:
        """Retourne le prénom principal configuré, ou chaîne vide."""
        try:
            return lire_reglage("prenom_principal") or ""
        except (KeyError, Exception):
            return ""

    def obtenir_avatar_principal(self) -> str:
        """Retourne l'avatar principal choisi dans les réglages (issue #148).

        Renvoie l'identifiant d'avatar (voir :data:`AVATARS_DISPONIBLES`) tel que
        configuré dans les réglages (``avatar_principal``, issue #139), ou chaîne
        vide si aucun avatar n'est choisi. On revalide contre
        :data:`AVATARS_DISPONIBLES` par prudence : ``lire_reglage`` normalise déjà
        la valeur, mais une valeur inattendue (config manipulée à la main) ne doit
        pas produire un chemin d'image invalide côté accueil. Toute erreur de
        lecture est absorbée (chaîne vide) : l'accueil retombe alors sur l'icône
        générique, jamais sur une exception.
        """
        try:
            valeur = lire_reglage("avatar_principal") or ""
        except (KeyError, Exception):
            return ""
        return valeur if valeur in AVATARS_DISPONIBLES else ""

    def initialiser_joueur_humain(self) -> bool:
        """Ajoute d'office le joueur humain de référence (issue #141).

        Le support multi-humains ayant été abandonné, il n'y a plus de raison
        de demander à l'utilisateur d'ajouter manuellement son joueur humain à
        chaque création de partie : il doit figurer d'office dans « Joueurs
        autour de la table » dès l'ouverture de l'accueil. On reprend le prénom
        déjà configuré dans les réglages (``prenom_principal``).

        Appelée par :func:`lancer_accueil` juste avant l'ouverture de la
        fenêtre, de sorte que le premier ``obtenir_etat()`` du JS voie déjà le
        joueur. Le joueur reste **retirable** ensuite (aucune présence forcée
        irréversible) : la méthode est idempotente et ne réajoute rien si un
        humain est déjà présent (elle ne s'oppose donc pas à un retrait
        volontaire déjà effectué dans la même configuration).

        Sans prénom principal configuré (champ vide), aucun joueur n'est ajouté
        et l'écran s'ouvre comme avant — à charge pour l'utilisateur d'ajouter
        un joueur manuellement. Retourne ``True`` si un joueur a été ajouté.
        """
        if self.config_partie.nb_humains > 0:
            journal.info(
                "Accueil : seeding du joueur humain ignoré (un humain est déjà "
                "présent dans la configuration)."
            )
            return False
        prenom = self.obtenir_prenom_principal().strip()
        if not prenom:
            journal.info(
                "Accueil : seeding du joueur humain ignoré (aucun prénom "
                "principal configuré dans les réglages)."
            )
            return False
        if not self.config_partie.ajouter_humain(prenom):
            journal.info(
                "Accueil : seeding du joueur humain échoué "
                f"(ajouter_humain a refusé « {prenom} »)."
            )
            return False
        journal.info(
            f"Accueil : joueur humain de référence ajouté d'office ({prenom})."
        )
        return True

    def reinitialiser_pour_retour_accueil(self) -> None:
        """Remet l'accueil dans son état d'ouverture après un retour Jeu→Accueil (issue #181).

        Dans le chemin de **production**, l'écran d'accueil est *recréé* à chaque
        retour au menu : une ``ApiAccueil`` neuve repart d'une configuration
        vierge, re-seede le joueur humain et la liste « parties en cours » est
        relue à l'ouverture. Dans la **coquille unifiée** (issue #179), la même
        instance d':class:`ApiAccueil` est réutilisée d'une visite à l'autre (la
        fenêtre navigue par ``load_url`` plutôt que d'être recréée) : sans remise
        à zéro explicite, la configuration de la partie précédente (joueurs
        ajoutés, humain déjà présent, ``_partie``/``_id_partie`` résiduels)
        subsisterait à la réouverture de ``accueil.html``.

        On restaure donc à la main l'état d'un accueil fraîchement construit :

        * ``config_partie`` remis à une :class:`ConfigPartie` vierge ;
        * ``_partie``/``_id_partie``/``_infos_tirage`` remis à ``None`` (aucune
          partie préparée ne doit fuiter dans un futur ``demarrer_jeu``) ;
        * joueur humain de référence re-seedé (:meth:`initialiser_joueur_humain`,
          exactement comme au lancement de la coquille).

        La liste « parties en cours » n'est pas mise en cache côté Python
        (:meth:`lister_parties_en_cours` relit la persistance à chaque appel) :
        le ``load_url('accueil.html')`` qui suit ce retour déclenche, via le
        ``pywebviewready`` du JS, un nouvel appel — la liste est donc toujours à
        jour sans état à purger ici.

        Ne touche ni à la fenêtre (``_window``, partagée et persistante) ni à la
        session de journalisation (une seule couvre toute la coquille unifiée,
        issue #179) : cette méthode ne fait que réinitialiser l'état métier.
        """
        self.config_partie = ConfigPartie()
        self._partie = None
        self._id_partie = None
        self._infos_tirage = None
        self.initialiser_joueur_humain()
        journal.info(
            "Accueil : état réinitialisé pour un retour à l'accueil "
            "(coquille unifiée)."
        )

    def sauvegarder_prenom_principal(self, prenom: str) -> bool:
        """Sauvegarde le prénom comme prénom principal."""
        try:
            modifier_reglage("prenom_principal", prenom)
            return True
        except (KeyError, TypeError, Exception):
            return False

    def obtenir_etat(self) -> dict[str, Any]:
        """Retourne l'état actuel de la configuration.

        Le joueur humain de référence (le premier humain de la liste) porte
        l'avatar choisi dans les réglages (``avatar_principal``, issue #148) dans
        le champ ``avatar`` : l'accueil affiche ainsi le même portrait que celui
        utilisé tout au long de la partie (:func:`~scrabble.ui.jeu.calculer_avatars`
        réserve déjà ``avatar_principal`` à ce joueur). Les autres joueurs — et le
        joueur humain quand aucun avatar n'est configuré — ont ``avatar`` à
        ``None`` : l'accueil retombe alors sur l'icône générique.
        """
        avatar_principal = self.obtenir_avatar_principal()
        reference = next(
            (i for i, j in enumerate(self.config_partie.joueurs) if j.humain),
            None,
        )
        return {
            "joueurs": [
                {
                    "nom": j.nom,
                    "humain": j.humain,
                    "niveau": j.niveau.name if j.niveau else None,
                    "avatar": (
                        avatar_principal
                        if (i == reference and avatar_principal)
                        else None
                    ),
                }
                for i, j in enumerate(self.config_partie.joueurs)
            ],
            "peut_ajouter_humain": self.config_partie.peut_ajouter_humain(),
            "peut_ajouter_ordinateur": self.config_partie.peut_ajouter_ordinateur(),
            "peut_lancer": self.config_partie.peut_lancer(),
            "nb_humains": self.config_partie.nb_humains,
            "nb_ordinateurs": self.config_partie.nb_ordinateurs,
            "nb_total": self.config_partie.nb_total,
        }

    def ajouter_humain(self, nom: str, sauvegarder: bool = False) -> dict[str, Any]:
        """Ajoute un joueur humain avec le nom donné."""
        nom = nom.strip()
        if not nom:
            return {"succes": False, "erreur": "Le prénom ne peut pas être vide."}
        if not self.config_partie.peut_ajouter_humain():
            return {
                "succes": False,
                "erreur": "Un seul joueur humain est autorisé par partie.",
            }
        if sauvegarder:
            self.sauvegarder_prenom_principal(nom)
        self.config_partie.ajouter_humain(nom)
        journal.info(f"Accueil : joueur humain ajouté ({nom}).")
        return {"succes": True, "etat": self.obtenir_etat()}

    def ajouter_ordinateur(self, niveau_label: str) -> dict[str, Any]:
        """Ajoute un ordinateur avec le niveau donné (label français)."""
        if not self.config_partie.peut_ajouter_ordinateur():
            return {
                "succes": False,
                "erreur": f"Maximum {MAX_ORDINATEURS} ordinateurs (total {MAX_JOUEURS}).",
            }
        niveau = NIVEAUX_LABELS.get(niveau_label)
        if niveau is None:
            return {"succes": False, "erreur": f"Niveau inconnu : {niveau_label}"}
        noms_pris = self.config_partie.noms_utilises()
        try:
            prenoms = tirer_prenoms(1, noms_pris)
            nom = prenoms[0]
        except Exception as e:
            journal.erreur("Accueil : échec du tirage de prénom d'ordinateur.", e)
            return {"succes": False, "erreur": f"Impossible de tirer un prénom : {e}"}
        self.config_partie.ajouter_ordinateur(nom, niveau)
        journal.info(f"Accueil : ordinateur ajouté ({nom}, niveau {niveau.name}).")
        return {"succes": True, "etat": self.obtenir_etat()}

    def retirer_joueur(self, index: int) -> dict[str, Any]:
        """Retire le joueur à l'index donné."""
        if not self.config_partie.retirer(index):
            return {"succes": False, "erreur": "Index invalide."}
        journal.info(f"Accueil : joueur retiré (index {index}).")
        return {"succes": True, "etat": self.obtenir_etat()}

    @staticmethod
    def _construire_trie_ia() -> Any:
        """Trie restreint de l'IA si « vocabulaire humain » est actif, sinon ``None``.

        Réglage global unique (issue #206), indépendant du niveau de difficulté :
        désactivé (défaut) → ``None`` (l'IA joue sur le dictionnaire complet,
        comportement historique inchangé, coût nul). Activé → Trie restreint
        (:func:`~scrabble.dictionnaire.dictionnaire.obtenir_trie_ia`) construit sur
        la **même** source que le Trie complet du jeu — appelé, comme
        ``obtenir_trie()``, sans forcer de source, pour garantir que le vocabulaire
        de l'IA reste un sous-ensemble strict du dictionnaire de validation.
        """
        if not bool(charger_config().get("vocabulaire_humain", False)):
            return None
        return obtenir_trie_ia()

    def lancer_partie(self) -> dict[str, Any]:
        """Crée et démarre la partie avec la configuration actuelle.

        L'ordre de jeu est décidé par un **tirage d'ordre** (``creer_partie(...,
        tirage_ordre=True)``, issue #33) : chaque joueur tire une lettre et
        l'ordre de jeu suit l'ordre alphabétique des lettres tirées.

        Depuis l'issue #170, ce tirage n'est plus affiché en modale de l'accueil :
        il l'est dans la fenêtre Jeu, « à la place » du plateau. On mémorise donc
        ici, dans ``_infos_tirage``, ce qu'il faut pour le rejouer côté Jeu
        (``noms_creation`` dans l'ordre de création — humains puis ordinateurs —,
        ``graine`` et ``noms_humains``) ; :func:`lancer_accueil` le transmet à
        :func:`~scrabble.ui.jeu.lancer_jeu`. L'accueil n'affiche donc plus rien du
        tirage et se ferme directement.

        En cas de succès, le champ ``pret`` vaut ``True`` : le JS doit alors
        fermer la fenêtre d'accueil (``api.fermer_fenetre()``) pour que l'écran
        de jeu puisse s'ouvrir directement dans l'état « pré-partie » (tirage).
        """
        # Garde-fou backend (issue #175) : refuse explicitement plus d'un
        # joueur humain, avec un message dédié — indépendamment de toute
        # contrainte UI (potentiellement contournable). Le cas « aucun humain »
        # garde son propre message ci-dessous.
        if self.config_partie.nb_humains > 1:
            return {
                "succes": False,
                "erreur": (
                    "Une partie ne peut comporter qu'un seul joueur humain "
                    f"(configuré : {self.config_partie.nb_humains})."
                ),
            }
        if not self.config_partie.peut_lancer():
            return {
                "succes": False,
                "erreur": "Il faut au moins un joueur humain pour lancer la partie.",
            }
        try:
            noms_humains = [
                j.nom for j in self.config_partie.joueurs if j.humain
            ]
            noms_ia = [j.nom for j in self.config_partie.joueurs if not j.humain]
            niveaux_ia = [
                j.niveau for j in self.config_partie.joueurs if not j.humain
            ]
            graine = random.randint(0, 2**31 - 1)
            trie = obtenir_trie()
            # Réglage du bonus officiel au finisseur (issue #134), lu depuis la
            # config auto-réparante et câblé dans le moteur via creer_partie.
            bonus_fin_partie = bool(charger_config().get("bonus_fin_partie", False))
            # Réglage « vocabulaire humain » (issue #206) : Trie restreint de l'IA.
            trie_ia = self._construire_trie_ia()
            self._partie = creer_partie(
                noms_humains=noms_humains,
                dictionnaire=trie,
                nb_ia=len(noms_ia),
                noms_ia=noms_ia,
                niveaux_ia=niveaux_ia,
                graine=graine,
                tirage_ordre=True,
                bonus_fin_partie=bonus_fin_partie,
                dictionnaire_ia=trie_ia,
            )
            self._id_partie = demarrer_suivi(self._partie)
            # Détail à rejouer côté Jeu pour l'écran de tirage (issue #170) :
            # l'ordre de création (humains puis ordinateurs) et la graine suffisent
            # à ``detail_tirage_ordre`` pour reproduire exactement le tirage.
            self._infos_tirage = {
                "noms_creation": noms_humains + noms_ia,
                "graine": graine,
                "noms_humains": noms_humains,
            }
            journal.info(
                f"Accueil : partie #{self._id_partie} lancée "
                f"({len(self._partie.joueurs)} joueurs)."
            )
            return {
                "succes": True,
                "pret": True,
                "id_partie": self._id_partie,
                "message": f"Partie #{self._id_partie} créée avec {len(self._partie.joueurs)} joueurs.",
            }
        except Exception as e:
            journal.erreur("Accueil : échec du lancement de la partie.", e)
            return {"succes": False, "erreur": str(e)}

    # Le détail du tirage d'ordre (``_detail_tirage_ordre``) et son annulation
    # (``annuler_partie_creee``) ont migré vers ``scrabble.ui.jeu`` (issue #170) :
    # le tirage est désormais affiché et piloté dans la fenêtre Jeu.

    def lister_parties_en_cours(self) -> list[dict[str, Any]]:
        """Renvoie les parties proposées à l'accueil (issues #54, #150).

        ``lister_parties()`` renvoie déjà les parties triées par date de mise à
        jour décroissante. On propose au plus **deux** encarts, la plus récente
        de chaque catégorie :

        - la partie **en cours** la plus récente, à reprendre (issue #54) ;
        - la partie **terminée** la plus récente, à consulter — son plateau
          final et son classement (issue #150). Le filtre qui excluait
          auparavant les parties terminées est donc levé.

        Limiter à une par catégorie garde l'accueil épuré (esprit de l'issue
        #54) tout en évitant qu'une partie qui vient de se terminer ne masque la
        partie en cours (ou l'inverse). Les encarts sont renvoyés du plus récent
        au plus ancien. Chaque dict porte un booléen ``terminee`` pour que le JS
        affiche le badge « Terminée » et le libellé « Consulter ».

        Chaque joueur est renvoyé avec son **score courant** (issue #76) :
        ``joueurs`` est une liste de ``{"nom", "score"}``, le score étant celui
        exposé par ``ResumePartie.scores_actuels`` (déduit de l'historique sans
        rejouer la partie). Si l'information manque, le score vaut 0.
        """
        try:
            toutes = lister_parties()
            # ``toutes`` est trié date décroissante : le premier de chaque
            # catégorie est le plus récent.
            en_cours = next((p for p in toutes if not p.terminee), None)
            terminee = next((p for p in toutes if p.terminee), None)
            selection = [p for p in (en_cours, terminee) if p is not None]
            # Ordre chronologique décroissant conservé quel que soit le statut.
            selection.sort(key=lambda p: p.date_maj, reverse=True)
            resultat = []
            for p in selection:
                scores = p.scores_actuels or []
                joueurs = [
                    {
                        "nom": j["nom"],
                        "score": scores[i] if i < len(scores) else 0,
                    }
                    for i, j in enumerate(p.joueurs)
                ]
                resultat.append(
                    {
                        "id": p.id,
                        "date_maj": p.date_maj,
                        "joueurs": joueurs,
                        "nb_joueurs": len(p.joueurs),
                        "terminee": p.terminee,
                    }
                )
            return resultat
        except Exception:
            return []

    def reprendre(self, id_partie: int) -> dict[str, Any]:
        """Reprend une partie existante.

        En cas de succès, le champ ``pret`` vaut ``True`` : le JS doit alors
        fermer la fenêtre d'accueil (``api.fermer_fenetre()``) pour que l'écran
        de jeu puisse s'ouvrir avec la partie reprise.
        """
        try:
            trie = obtenir_trie()
            # Réglage « vocabulaire humain » (issue #206) : une partie reprise doit
            # continuer de restreindre son IA si le réglage est actif.
            trie_ia = self._construire_trie_ia()
            self._partie = reprendre_partie(
                id_partie, trie, dictionnaire_ia=trie_ia
            )
            self._id_partie = id_partie
            # Reprise = pas de tirage d'ordre à rejouer : on efface tout
            # ``_infos_tirage`` résiduel d'un éventuel « Lancer la partie »
            # antérieur. Sans effet dans le chemin de production (une ``ApiAccueil``
            # neuve par ouverture d'accueil), mais indispensable dans la coquille
            # unifiée (issue #180) où l'instance persiste toute la session : sinon
            # la reprise ouvrirait à tort l'écran de tirage.
            self._infos_tirage = None
            journal.info(f"Accueil : partie #{id_partie} reprise.")
            return {
                "succes": True,
                "pret": True,
                "id_partie": id_partie,
                "message": f"Partie #{id_partie} reprise.",
            }
        except KeyError as e:
            journal.erreur(f"Accueil : partie #{id_partie} introuvable à la reprise.", e)
            return {"succes": False, "erreur": f"Partie #{id_partie} introuvable."}
        except Exception as e:
            journal.erreur(f"Accueil : échec de la reprise de la partie #{id_partie}.", e)
            return {"succes": False, "erreur": str(e)}

    def obtenir_niveaux(self) -> list[str]:
        """Retourne la liste des niveaux de difficulté (labels français)."""
        return list(NIVEAUX_LABELS.keys())

    # ``annuler_partie_creee`` et ``journaliser_mesure_fenetre`` (diagnostic de la
    # géométrie de l'ex-modale de tirage) ont été retirées avec le déplacement du
    # tirage vers la fenêtre Jeu (issue #170). L'annulation du tirage est désormais
    # gérée par :meth:`~scrabble.ui.jeu.ApiJeu.annuler_tirage`.

    # ------------------------------------------------------------------ #
    # Panneau Réglages intégré (issue #169)
    #
    # Les réglages sont désormais un panneau affiché/masqué DANS la fenêtre
    # d'accueil (fini la fenêtre pywebview autonome ``ui/reglages.py`` et sa
    # transition visuelle disgracieuse) : le clic sur ⚙ bascule la vue côté JS,
    # et l'API ci-dessous — reprise à l'identique de l'ex-``ApiReglages`` —
    # sert les onglets Général et Dictionnaire depuis la même ``ApiAccueil``.
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
            "vocabulaire_humain": self._lire_bool("vocabulaire_humain"),
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

    def marquer_classique_mot(self, mot: str, present: bool) -> dict[str, Any]:
        """Marque/démarque un mot comme « classique du jeu » puis renvoie le statut.

        Délègue à :func:`~scrabble.dictionnaire.dictionnaire.marquer_classique`.
        Un marquage refusé (mot absent des deux sources ODS8/Hunspell) remonte
        au JS via ``{"succes": False, "erreur": ...}`` sans modifier de fichier.
        """
        verbe = "marqué classique" if present else "démarqué classique"
        try:
            norme = marquer_classique(mot, present)
            journal.info(f"Réglages : « {norme} » {verbe}.")
            statut = rechercher_statut(norme)
            statut["succes"] = True
            return statut
        except ValueError as e:
            return {"succes": False, "erreur": str(e)}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            journal.erreur(
                f"Réglages : échec du marquage classique de « {mot} ».", e
            )
            return {"succes": False, "erreur": str(e)}

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


def lancer_accueil(
    ouvrir_jeu: bool = True, reutiliser_session: bool = False
) -> tuple[Partie | None, int | None]:
    """Lance l'écran d'accueil et retourne la partie créée (ou None).

    Retourne un tuple (partie, id_partie). Les deux sont None si l'utilisateur
    a fermé la fenêtre sans lancer de partie.

    Si ``ouvrir_jeu`` est ``True`` (défaut) et qu'une partie a été créée ou
    reprise, l'écran de jeu s'ouvre automatiquement après la fermeture de
    l'écran d'accueil. Le flux complet est alors :
    accueil → création/reprise → fermeture accueil → ouverture jeu.

    ``reutiliser_session`` (issue #74) : quand l'accueil est rouvert depuis
    l'écran de jeu après un « Retour au menu » (:func:`~scrabble.ui.jeu.
    lancer_jeu`), la session de journalisation déjà ouverte est **réutilisée**
    plutôt que d'en démarrer une nouvelle (cohérent avec l'issue #66). Le
    ``try/finally`` la clôture ensuite normalement à la fermeture de cet accueil.
    Par sécurité, si aucune session n'est ouverte alors qu'on demande la réutiliser,
    on en démarre malgré tout une (invariant : une session vivante pendant l'écran).

    Cohabitation pywebview : ``webview.start()`` bloque jusqu'à la fermeture de
    toutes les fenêtres. Pour enchaîner deux fenêtres (accueil puis jeu), on
    ferme l'accueil depuis Python (le JS appelle ``api.fermer_fenetre()`` après
    un lancer/reprendre réussi, ce qui déclenche ``window.destroy()``), puis on
    rappelle ``webview.start()`` sur la nouvelle fenêtre de jeu. Fermer via
    ``destroy()`` côté Python est plus fiable que ``window.close()`` côté JS,
    qui n'est pas honoré par tous les backends (GTK/WebKit sous Linux, issue
    #53). Chaque écran gère ainsi sa propre boucle pywebview, ce qui évite les
    complications d'ouverture de fenêtre secondaire au sein d'une boucle déjà
    démarrée.
    """
    from scrabble.ui.backend_graphique import configurer_backend_graphique
    from scrabble.ui.jeu import lancer_jeu

    # Sélection du backend graphique AVANT le premier ``webview.start()`` du
    # processus (issue #93) : sous GNOME/Wayland, GTK tourne en client Wayland
    # natif où ``move()``/``window.x``/``on_top`` sont ignorés. On bascule sur
    # XWayland (``GDK_BACKEND=x11``) pour rétablir le positionnement du chevalet.
    # Ici, à l'entrée de l'accueil, précède la toute première ouverture de
    # display GTK de l'application (l'écran de jeu enchaîné en hérite ensuite).
    configurer_backend_graphique()

    # Session de journalisation ouverte au tout début du lancement (issue #66).
    # Elle est réutilisée par l'écran de jeu en cas d'enchaînement normal (voir
    # ``lancer_jeu``), qui la clôture alors lui-même. Le ``try/finally`` garantit
    # la clôture même si une exception non prévue traverse cette fonction :
    # ``cloturer_session`` est idempotente, donc l'appel final est sans effet si
    # l'écran de jeu a déjà clôturé la session.
    if not reutiliser_session or journal.session_courante() is None:
        journal.demarrer_session()
    try:
        api = ApiAccueil()
        # Joueur humain présent d'office (issue #141) : le support multi-humains
        # étant abandonné, le joueur de référence figure dès l'ouverture dans
        # « Joueurs autour de la table » (repris de ``prenom_principal``), sans
        # ajout manuel. Fait avant ``webview.start()`` pour que le premier
        # ``obtenir_etat()`` du JS le voie déjà. Il reste retirable ensuite.
        api.initialiser_joueur_humain()
        # Trace d'objectivation (issue #145) : on journalise l'état que le
        # premier ``obtenir_etat()`` du JS renverra, pour lever toute ambiguïté
        # entre « le joueur n'est pas ajouté » (bug logique) et « il est ajouté
        # mais pas rendu » (bug d'affichage) lors d'un test en conditions
        # réelles.
        _etat_ouverture = api.obtenir_etat()
        journal.info(
            "Accueil : état exposé au premier rendu — "
            f"{_etat_ouverture['nb_humains']} humain(s), "
            f"{_etat_ouverture['nb_ordinateurs']} ordinateur(s) ; "
            f"joueurs = {[j['nom'] for j in _etat_ouverture['joueurs']]}."
        )
        chemin_html = DOSSIER_WEB / "accueil.html"
        window = webview.create_window(
            "Scrabble - Nouvelle partie",
            str(chemin_html),
            js_api=api,
            # Fenêtre maximisée par défaut (issue #159) : l'accueil (configuration
            # des joueurs et panneau Réglages intégré, issue #169) reste lisible au
            # lieu de s'ouvrir en petit format flottant. ``maximized=True`` étant un
            # no-op sous XWayland (cf. #95), le déploiement effectif est forcé après
            # démarrage de la boucle par le callback ``deployer_fenetre_maximisee``
            # passé à ``webview.start`` plus bas. ``width``/``height`` restent la
            # taille de restauration/repli.
            maximized=True,
            width=700,
            # Taille de restauration/repli (issues #82 puis #115) : le tirage
            # d'ordre a migré vers la fenêtre Jeu (issue #170), mais 780 px reste
            # une hauteur de repli confortable pour la configuration et le panneau
            # Réglages sur les écrans qui n'honorent pas la maximisation.
            height=780,
            resizable=True,
            # Fond vert dès le mappage de la fenêtre (issue #113) : évite le
            # blanc par défaut de pywebview pendant le chargement HTML/CSS.
            background_color=TAPIS_VERT,
        )
        api.set_window(window)
        # Déploiement plein écran une fois la boucle GUI démarrée (issue #159) :
        # contournement du no-op de ``maximized=True`` sous XWayland (cf. #95), de
        # la même façon que le plateau (jeu.py). Le callback reçoit ``(window, nom)``.
        from scrabble.ui.backend_graphique import deployer_fenetre_maximisee

        webview.start(deployer_fenetre_maximisee, (window, "accueil"))

        partie, id_partie = api._partie, api._id_partie
        if ouvrir_jeu and partie is not None:
            journal.info(f"Accueil : enchaînement vers l'écran de jeu (partie #{id_partie}).")
            # ``_infos_tirage`` est renseigné uniquement après un « Lancer la
            # partie » (nouvelle partie) : l'écran de jeu affiche alors le tirage
            # d'ordre à la place du plateau (issue #170). Après une « Reprise », il
            # reste ``None`` : l'écran de jeu s'ouvre directement jouable.
            lancer_jeu(partie, id_partie, api._infos_tirage)
        return partie, id_partie
    finally:
        journal.cloturer_session()


def main() -> int:
    """Point d'entrée pour test : lance l'écran et affiche le résultat."""
    partie, id_partie = lancer_accueil()
    if partie is None:
        print("Aucune partie lancée (fenêtre fermée).")
        return 0
    print(f"Partie #{id_partie} créée avec {len(partie.joueurs)} joueur(s) :")
    for i, joueur in enumerate(partie.joueurs):
        type_joueur = "humain" if joueur.humain else f"ordinateur ({joueur.niveau.name})"
        print(f"  {i + 1}. {joueur.nom} ({type_joueur})")
    print(f"Graine : {partie.graine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
