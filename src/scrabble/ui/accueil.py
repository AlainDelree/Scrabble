"""Écran d'accueil : configuration d'une nouvelle partie (pywebview).

Point d'entrée de l'application de jeu Scrabble. Permet de :
- ajouter des joueurs humains (jusqu'à 4)
- ajouter des adversaires « ordinateur » (jusqu'à 3) avec un niveau de difficulté
- lancer une partie avec la configuration choisie
- reprendre une partie en cours

Vocabulaire : l'écran dit « ordinateur » et jamais « IA » (moins intimidant).
Les identifiants de code (Joueur.humain, Niveau) restent inchangés.

Lancement de l'écran pour test ::

    python -m scrabble.ui.accueil
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import webview

from scrabble.config import charger_config
from scrabble.dictionnaire.dictionnaire import charger_dictionnaire, obtenir_trie
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
            return {"succes": False, "erreur": f"Impossible de tirer un prénom : {e}"}
        self.config_partie.ajouter_ordinateur(nom, niveau)
        return {"succes": True, "etat": self.obtenir_etat()}

    def retirer_joueur(self, index: int) -> dict[str, Any]:
        """Retire le joueur à l'index donné."""
        if not self.config_partie.retirer(index):
            return {"succes": False, "erreur": "Index invalide."}
        return {"succes": True, "etat": self.obtenir_etat()}

    def lancer_partie(self) -> dict[str, Any]:
        """Crée et démarre la partie avec la configuration actuelle."""
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
            )
            self._id_partie = demarrer_suivi(self._partie)
            return {
                "succes": True,
                "id_partie": self._id_partie,
                "message": f"Partie #{self._id_partie} créée avec {len(self._partie.joueurs)} joueurs.",
            }
        except Exception as e:
            return {"succes": False, "erreur": str(e)}

    def lister_parties_en_cours(self) -> list[dict[str, Any]]:
        """Liste les parties non terminées disponibles pour reprise."""
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
                for p in en_cours
            ]
        except Exception:
            return []

    def reprendre(self, id_partie: int) -> dict[str, Any]:
        """Reprend une partie existante."""
        try:
            trie = obtenir_trie()
            self._partie = reprendre_partie(id_partie, trie)
            self._id_partie = id_partie
            return {
                "succes": True,
                "id_partie": id_partie,
                "message": f"Partie #{id_partie} reprise.",
            }
        except KeyError:
            return {"succes": False, "erreur": f"Partie #{id_partie} introuvable."}
        except Exception as e:
            return {"succes": False, "erreur": str(e)}

    def obtenir_niveaux(self) -> list[str]:
        """Retourne la liste des niveaux de difficulté (labels français)."""
        return list(NIVEAUX_LABELS.keys())


def lancer_accueil() -> tuple[Partie | None, int | None]:
    """Lance l'écran d'accueil et retourne la partie créée (ou None).

    Retourne un tuple (partie, id_partie). Les deux sont None si l'utilisateur
    a fermé la fenêtre sans lancer de partie.
    """
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
    return api._partie, api._id_partie


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
