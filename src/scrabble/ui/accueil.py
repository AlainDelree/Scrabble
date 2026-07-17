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
from scrabble.config import charger_config
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
)
from scrabble.reglages import lire_reglage, modifier_reglage
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

    def sauvegarder_prenom_principal(self, prenom: str) -> bool:
        """Sauvegarde le prénom comme prénom principal."""
        try:
            modifier_reglage("prenom_principal", prenom)
            return True
        except (KeyError, TypeError, Exception):
            return False

    def obtenir_etat(self) -> dict[str, Any]:
        """Retourne l'état actuel de la configuration."""
        return {
            "joueurs": [
                {
                    "nom": j.nom,
                    "humain": j.humain,
                    "niveau": j.niveau.name if j.niveau else None,
                }
                for j in self.config_partie.joueurs
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
            self._partie = creer_partie(
                noms_humains=noms_humains,
                dictionnaire=trie,
                nb_ia=len(noms_ia),
                noms_ia=noms_ia,
                niveaux_ia=niveaux_ia,
                graine=graine,
                tirage_ordre=True,
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
        """Renvoie la seule partie en cours la plus récente (issue #54).

        ``lister_parties()`` renvoie déjà les parties triées par date de mise à
        jour décroissante : on ne propose à la reprise que la plus récente. Le
        retour reste une liste (0 ou 1 élément) pour ne pas casser le contrat
        avec le JS.
        """
        try:
            toutes = lister_parties()
            en_cours = [p for p in toutes if not p.terminee]
            return [
                {
                    "id": p.id,
                    "date_maj": p.date_maj,
                    "joueurs": [j["nom"] for j in p.joueurs],
                    "nb_joueurs": len(p.joueurs),
                }
                for p in en_cours[:1]
            ]
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

    def obtenir_niveaux(self) -> list[str]:
        """Retourne la liste des niveaux de difficulté (labels français)."""
        return list(NIVEAUX_LABELS.keys())


def lancer_accueil(ouvrir_jeu: bool = True) -> tuple[Partie | None, int | None]:
    """Lance l'écran d'accueil et retourne la partie créée (ou None).

    Retourne un tuple (partie, id_partie). Les deux sont None si l'utilisateur
    a fermé la fenêtre sans lancer de partie.

    Si ``ouvrir_jeu`` est ``True`` (défaut) et qu'une partie a été créée ou
    reprise, l'écran de jeu s'ouvre automatiquement après la fermeture de
    l'écran d'accueil. Le flux complet est alors :
    accueil → création/reprise → fermeture accueil → ouverture jeu.

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
    from scrabble.ui.jeu import lancer_jeu

    # Session de journalisation ouverte au tout début du lancement (issue #66).
    # Elle est réutilisée par l'écran de jeu en cas d'enchaînement normal (voir
    # ``lancer_jeu``), qui la clôture alors lui-même. Le ``try/finally`` garantit
    # la clôture même si une exception non prévue traverse cette fonction :
    # ``cloturer_session`` est idempotente, donc l'appel final est sans effet si
    # l'écran de jeu a déjà clôturé la session.
    journal.demarrer_session()
    try:
        api = ApiAccueil()
        chemin_html = DOSSIER_WEB / "accueil.html"
        window = webview.create_window(
            "Scrabble - Nouvelle partie",
            str(chemin_html),
            js_api=api,
            width=700,
            height=600,
            resizable=True,
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
