"""Mixin « échange de lettres » pour l'API Jeu (issue #249).

Ce mixin regroupe les méthodes liées à l'**échange de lettres** avec le sac :
échange complet du chevalet, entrée/sortie du mode d'échange partiel, bascule
de la sélection d'échange, et validation de l'échange partiel.

Dépendances vers MixinDiffusion
-------------------------------
Ce mixin utilise les primitives suivantes de :class:`~.api_diffusion.MixinDiffusion` :

- ``self._diffuser()`` — appelée après chaque mutation de l'état d'échange
  (entrée/sortie du mode, bascule de sélection, validation) pour mettre à jour
  la fenêtre Jeu.
- ``self._refuser_hors_tour()`` — garde de tour vérifiant que le joueur de
  référence est bien le joueur courant avant toute mutation d'échange.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from scrabble.moteur.partie import EntreeHistorique, Partie


class MixinEchange:
    """Méthodes d'échange de lettres pour ApiJeu (issue #249)."""

    # Attributs attendus sur la classe hôte (ApiJeu), déclarés pour les
    # annotations — pas de valeur par défaut, ils vivent sur l'instance.
    _partie: Partie | None
    _id_partie: int | None
    _selection: int | None
    _en_attente: list[dict[str, Any]]
    _joker_demande: dict[str, Any] | None
    _type_echange: str
    _mode_echange: bool
    _selection_echange: list[int]

    # Méthodes attendues de MixinDiffusion (via l'héritage multiple d'ApiJeu).
    def _diffuser(self) -> None: ...
    def _refuser_hors_tour(self) -> dict[str, Any] | None: ...

    # Méthodes attendues d'ApiJeu (utilisées par les échanges).
    def _persister_entrees(self, entrees: "list[EntreeHistorique]") -> None: ...
    def _finaliser_si_terminee(self) -> None: ...

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
        from scrabble.ui import jeu as mod_jeu
        from scrabble.ui.jeu import echanger_chevalet_complet

        nom = self._partie.joueur_courant().nom
        nb_avant = len(self._partie.historique)
        resultat = echanger_chevalet_complet(self._partie, self._id_partie)
        if resultat.get("succes"):
            mod_jeu.journal.info(f"Jeu : échange complet du chevalet par {nom}.")
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._finaliser_si_terminee()
            # Nouveau tirage + tour suivant : on repart d'un état de pose vierge
            # et on rediffuse le nouvel état public (plateau) et le nouveau
            # chevalet (zone C intégrée) — issue #90.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._diffuser()
        else:
            mod_jeu.journal.info(f"Jeu : échange refusé pour {nom} — {resultat.get('erreur')}")
        return resultat

    # ---- Échange partiel (issue #138) --------------------------------- #

    def commencer_echange(self) -> dict[str, Any]:
        """Entre dans le mode de **sélection** pour l'échange partiel (issue #138).

        Point d'entrée du bouton « ♻️ Échanger des lettres… », affiché à la place
        de l'échange complet quand le réglage ``type_echange`` vaut ``"partiel"``.
        Abandonne toute pose en cours (le joueur ne fait pas les deux à la fois),
        vide la sélection d'échange et active :attr:`_mode_echange`, puis diffuse.

        Réservé au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99/#130). Refusé si le réglage n'est pas ``"partiel"``.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if self._type_echange != "partiel":
            return {
                "succes": False,
                "erreur": "L'échange partiel n'est pas activé dans les réglages.",
            }
        self._selection = None
        self._en_attente = []
        self._joker_demande = None
        self._selection_echange = []
        self._mode_echange = True
        self._diffuser()
        return {"succes": True}

    def annuler_echange(self) -> dict[str, Any]:
        """Quitte le mode de sélection d'échange partiel sans rien échanger.

        Vide la sélection d'échange et désactive :attr:`_mode_echange`, puis
        rediffuse. C'est le moyen clair d'annuler une sélection en cours avant de
        la valider (issue #138). Réservé au tour du joueur de référence.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        self._selection_echange = []
        self._mode_echange = False
        self._diffuser()
        return {"succes": True}

    def basculer_echange(self, index: Any) -> dict[str, Any]:
        """Marque/démarque la lettre d'index ``index`` pour l'échange partiel.

        Appelée par le panneau chevalet, en mode échange (:attr:`_mode_echange`),
        au clic sur une lettre : un premier clic la marque, un reclic la démarque
        (sélection multiple, distincte de la sélection simple de pose). ``index``
        vise la position de la lettre dans le chevalet du joueur courant (qui est
        le joueur de référence, la garde de tour l'assurant). Diffuse l'état.

        Réservé au tour du joueur de référence (garde :meth:`_refuser_hors_tour`).
        Refusé hors du mode échange ou sur un index invalide.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if not self._mode_echange:
            return {"succes": False, "erreur": "Le mode échange n'est pas actif."}
        if isinstance(index, bool) or not isinstance(index, int):
            return {"succes": False, "erreur": "Index de lettre invalide."}
        if not 0 <= index < len(self._partie.joueur_courant().chevalet):
            return {"succes": False, "erreur": "Index de lettre hors du chevalet."}
        if index in self._selection_echange:
            self._selection_echange.remove(index)
        else:
            self._selection_echange.append(index)
        self._diffuser()
        return {"succes": True, "selection_echange": list(self._selection_echange)}

    def echanger_selection(self, indices: Any = None) -> dict[str, Any]:
        """Échange les lettres sélectionnées et passe le tour (issue #138).

        Point d'entrée du bouton « Échanger la sélection et passer ». Les lettres
        visées sont désignées par leurs ``indices`` dans le chevalet du joueur
        courant ; si ``indices`` vaut ``None`` (appel depuis l'UI), on utilise la
        sélection d'échange courante (:attr:`_selection_echange`). Convertit les
        index en jetons puis délègue à :func:`echanger_jetons`, qui applique
        exactement les mêmes règles que l'échange complet (sac suffisant, remise
        en jeu, tirage de remplacement, passage du tour).

        Une sélection **vide** est refusée (1 à 7 lettres, jamais 0). En cas de
        succès : ``{"succes": True, "etat": <état public>}`` (tour suivant, état
        de pose et sélection d'échange remis à zéro, mode échange quitté). En cas
        d'échec (sac trop pauvre, index invalide, partie terminée, hors tour) :
        ``{"succes": False, "erreur": <message>}`` — l'état n'est pas modifié.

        Réservé au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99/#130) : c'est cette garde qui assure que les index visent bien
        le chevalet du joueur de référence (alors joueur courant).
        """
        from scrabble.ui import jeu as mod_jeu
        from scrabble.ui.jeu import echanger_jetons

        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if indices is None:
            indices = list(self._selection_echange)
        joueur = self._partie.joueur_courant()
        nb = len(joueur.chevalet)
        if not isinstance(indices, list) or not indices:
            return {"succes": False, "erreur": "Aucune lettre sélectionnée à échanger."}
        vus: set[int] = set()
        for i in indices:
            if (
                isinstance(i, bool)
                or not isinstance(i, int)
                or not 0 <= i < nb
                or i in vus
            ):
                return {"succes": False, "erreur": "Sélection de lettres invalide."}
            vus.add(i)
        jetons = [joueur.chevalet[i] for i in indices]
        nom = joueur.nom
        nb_avant = len(self._partie.historique)
        resultat = echanger_jetons(self._partie, self._id_partie, jetons)
        if resultat.get("succes"):
            mod_jeu.journal.info(
                f"Jeu : échange partiel de {len(jetons)} lettre(s) par {nom}."
            )
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._finaliser_si_terminee()
            # Nouveau tirage + tour suivant : on repart d'un état de pose et
            # d'échange vierge, puis on rediffuse les deux fenêtres (issue #90).
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._selection_echange = []
            self._mode_echange = False
            self._diffuser()
        else:
            mod_jeu.journal.info(
                f"Jeu : échange partiel refusé pour {nom} — {resultat.get('erreur')}"
            )
        return resultat
