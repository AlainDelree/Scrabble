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
from scrabble.config import AVATARS_DISPONIBLES, charger_config
from scrabble.dictionnaire.dictionnaire import charger_dictionnaire, obtenir_trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.ordre import determiner_ordre_jeu
from scrabble.moteur.partie import MAX_JOUEURS, Partie, creer_partie
from scrabble.persistance.stockage import (
    CHEMIN_DEFAUT,
    ResumePartie,
    demarrer_suivi,
    lister_parties,
    reprendre_partie,
    supprimer_partie,
)
from scrabble.reglages import lire_reglage, modifier_reglage
from scrabble.ui import TAPIS_VERT
from scrabble.ui.noms_ordinateur import tirer_prenoms

DOSSIER_WEB = Path(__file__).parent / "web"

MAX_HUMAINS = 4
MAX_ORDINATEURS = 3

NIVEAUX_LABELS: dict[str, Niveau] = {
    "Débutant": Niveau.DEBUTANT,
    "Facile": Niveau.FACILE,
    "Intermédiaire": Niveau.INTERMEDIAIRE,
    "Expert": Niveau.EXPERT,
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
        """Vrai si la configuration permet de lancer une partie."""
        return self.nb_humains >= 1

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
                "erreur": f"Maximum {MAX_HUMAINS} joueurs humains (total {MAX_JOUEURS}).",
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

    def lancer_partie(self) -> dict[str, Any]:
        """Crée et démarre la partie avec la configuration actuelle.

        L'ordre de jeu est décidé par un **tirage d'ordre** (``creer_partie(...,
        tirage_ordre=True)``, issue #33) : chaque joueur tire une lettre et
        l'ordre de jeu suit l'ordre alphabétique des lettres tirées. Le détail
        du tirage est exposé dans la réponse (clé ``tirage_ordre``) pour que le
        JS l'affiche avant de fermer l'accueil (issue #54).

        En cas de succès, le champ ``pret`` vaut ``True`` : le JS doit alors
        fermer la fenêtre d'accueil (``api.fermer_fenetre()``) pour que l'écran
        de jeu puisse s'ouvrir avec la partie créée.
        """
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
            self._partie = creer_partie(
                noms_humains=noms_humains,
                dictionnaire=trie,
                nb_ia=len(noms_ia),
                noms_ia=noms_ia,
                niveaux_ia=niveaux_ia,
                graine=graine,
                tirage_ordre=True,
                bonus_fin_partie=bonus_fin_partie,
            )
            self._id_partie = demarrer_suivi(self._partie)
            journal.info(
                f"Accueil : partie #{self._id_partie} lancée "
                f"({len(self._partie.joueurs)} joueurs)."
            )
            return {
                "succes": True,
                "pret": True,
                "id_partie": self._id_partie,
                "tirage_ordre": self._detail_tirage_ordre(
                    noms_humains + noms_ia, graine, set(noms_humains)
                ),
                "message": f"Partie #{self._id_partie} créée avec {len(self._partie.joueurs)} joueurs.",
            }
        except Exception as e:
            journal.erreur("Accueil : échec du lancement de la partie.", e)
            return {"succes": False, "erreur": str(e)}

    @staticmethod
    def _detail_tirage_ordre(
        noms_creation: list[str],
        graine: int,
        noms_humains: set[str] | None = None,
    ) -> dict[str, Any]:
        """Reconstitue le détail du tirage d'ordre pour affichage côté JS.

        ``creer_partie(tirage_ordre=True)`` réordonne bien les joueurs mais ne
        renvoie pas le détail du tirage. On le rejoue ici avec **la même graine**
        (``random.Random(graine)``) : ``determiner_ordre_jeu`` ne dépend que du
        nombre de joueurs et de la graine, le résultat est donc identique à celui
        appliqué à la partie (l'ordre reproduit exactement ``partie.joueurs``).

        ``noms_creation`` est la liste des noms dans l'ordre de création (humains
        puis ordinateurs), qui est l'ordre d'origine sur lequel raisonne
        :class:`~scrabble.moteur.ordre.ResultatTirageOrdre` (``lettres[i]``
        correspond au joueur ``i`` de cette liste ; ``ordre`` en donne les
        indices rangés dans l'ordre de jeu).

        ``noms_humains`` (optionnel) est l'ensemble des noms de joueurs humains :
        chaque tirage porte alors un booléen ``humain`` pour que le JS remplace,
        côté joueur humain, la révélation automatique par une interaction
        « secouer le sac puis tirer » (issue #61). Absent, tous les tirages sont
        considérés non humains (rétrocompatibilité).

        Retourne
        ``{"tirages": [{"nom", "lettre", "humain"}, ...], "ordre": [nom, ...]}``.
        """
        humains = noms_humains or set()
        resultat = determiner_ordre_jeu(noms_creation, random.Random(graine))
        tirages = [
            {
                "nom": noms_creation[i],
                "lettre": resultat.lettres[i],
                "humain": noms_creation[i] in humains,
            }
            for i in range(len(noms_creation))
        ]
        ordre = [noms_creation[i] for i in resultat.ordre]
        return {"tirages": tirages, "ordre": ordre}

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
            self._partie = reprendre_partie(id_partie, trie)
            self._id_partie = id_partie
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

    def annuler_partie_creee(self) -> dict[str, Any]:
        """Annule la partie tout juste créée et la retire de la persistance (issue #67).

        Appelée quand l'utilisateur clique « Annuler » dans la modale de tirage
        d'ordre : à ce stade la partie a déjà été créée (:func:`creer_partie`) et
        suivie (:func:`demarrer_suivi`), mais aucun coup n'a encore été joué. On
        la supprime donc de la base (:func:`supprimer_partie`) pour qu'elle
        n'apparaisse pas comme partie fantôme dans « Reprendre une partie »
        (rien à perdre). L'écran d'accueil reste ouvert : le JS ferme la modale
        et ramène l'utilisateur à la configuration des joueurs.

        Retourne ``{"succes": True, "supprimee": bool}`` (``supprimee`` faux s'il
        n'y avait rien à supprimer) ou ``{"succes": False, "erreur": ...}``.
        """
        id_partie = self._id_partie
        if id_partie is None:
            # Rien à annuler : aucune partie n'a été créée/suivie.
            return {"succes": True, "supprimee": False}
        try:
            supprimee = supprimer_partie(id_partie)
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            journal.erreur(
                f"Accueil : échec de l'annulation de la partie #{id_partie}.", e
            )
            return {"succes": False, "erreur": str(e)}
        self._partie = None
        self._id_partie = None
        journal.info(
            f"Accueil : partie #{id_partie} annulée et supprimée "
            "(aucun coup joué)."
        )
        return {"succes": True, "supprimee": supprimee}

    def obtenir_niveaux(self) -> list[str]:
        """Retourne la liste des niveaux de difficulté (labels français)."""
        return list(NIVEAUX_LABELS.keys())

    def journaliser_mesure_fenetre(self, mesures: dict[str, Any]) -> dict[str, Any]:
        """Journalise les dimensions réelles de la fenêtre de tirage (issue #116).

        Après deux correctifs de taille (issues #83, #115) restés inopérants en
        conditions réelles, on objective la géométrie effective sous WebKitGTK au
        lieu de la déduire d'un harnais headless Chromium. Le JS mesure, à
        l'ouverture de la modale de tirage, la hauteur/largeur réellement
        disponibles (``innerHeight`` après soustraction du chrome/barre de titre)
        ainsi que la taille rendue de l'aire du sac, et transmet le tout ici pour
        trace — même discipline que celle appliquée au chevalet (issues #92-97)
        une fois une mesure headless jugée insuffisante.

        Purement informatif : n'altère aucun état, retourne toujours un succès.
        """
        try:
            details = ", ".join(f"{cle}={valeur}" for cle, valeur in mesures.items())
            journal.info(f"Accueil : géométrie réelle modale de tirage — {details}.")
        except Exception as e:  # noqa: BLE001 - une trace ne doit jamais bloquer
            journal.erreur("Accueil : échec de journalisation de la géométrie.", e)
        return {"succes": True}

    def ouvrir_reglages(self) -> dict[str, Any]:
        """Ouvre la fenêtre de réglages à onglets (issue #111).

        La fenêtre de réglages est ouverte comme **seconde fenêtre** de la boucle
        pywebview déjà démarrée par l'accueil (``webview.create_window`` sans
        relancer ``webview.start()``) : point d'entrée naturel hors partie, où
        changer la source de dictionnaire ou le thème est sans risque. À sa
        fermeture, le contrôle revient à l'accueil, qui reste ouvert en dessous.

        L'import est différé pour ne pas coupler le chargement de l'accueil à la
        fenêtre de réglages. Retourne ``{"succes": bool, ...}`` pour que le JS
        signale un éventuel échec plutôt que de rester silencieux.
        """
        try:
            from scrabble.ui.reglages import creer_fenetre_reglages

            creer_fenetre_reglages()
            journal.info("Accueil : ouverture de la fenêtre de réglages.")
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            journal.erreur("Accueil : échec d'ouverture des réglages.", e)
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
            width=700,
            # Hauteur relevée (issues #82 puis #115) : la modale de tirage
            # d'ordre affiche AUTANT de lignes que de joueurs (toutes présentes
            # dès le départ, même masquées en fondu → elles occupent la place)
            # plus le sac et une consigne pouvant tenir sur deux lignes. 720 px
            # (issue #82) ne suffisait qu'au cas — irréaliste — d'un seul
            # tirage : dès 2 joueurs (partie minimale), le bouton « Tirer une
            # lettre » repassait sous le scroll de secours. 780 px laisse le cas
            # courant (2 à 3 joueurs + consigne sur deux lignes) entièrement
            # visible sans défilement. Le CSS (#modale-tirage à corps scrollable
            # + aire du sac bornée en vh) reste le filet de sécurité pour les
            # écrans plus courts et les parties à nombreux joueurs.
            height=780,
            resizable=True,
            # Fond vert dès le mappage de la fenêtre (issue #113) : évite le
            # blanc par défaut de pywebview pendant le chargement HTML/CSS.
            background_color=TAPIS_VERT,
        )
        api.set_window(window)
        webview.start()

        partie, id_partie = api._partie, api._id_partie
        if ouvrir_jeu and partie is not None:
            journal.info(f"Accueil : enchaînement vers l'écran de jeu (partie #{id_partie}).")
            lancer_jeu(partie, id_partie)
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
