"""Mixin ApiJeu : gestion du tour et de la fin de partie (issue #250).

Ce mixin regroupe les méthodes liées à :
- la gestion du tour (passer, faire jouer l'IA) ;
- la finalisation de la partie (persistance, journalisation) ;
- les actions de fin de partie (retour au menu, recommencer).

Dépendances internes (via ``self``) :
- ``MixinDiffusion`` : ``self._diffuser()`` pour rediffuser l'état après mutation.
- ``MixinPose`` (implicite) : lors de ``recommencer``, une nouvelle partie est chargée
  avec un tirage d'ordre (pas de dépendance directe aux méthodes de pose, mais
  l'état de pose est remis à zéro).

Attributs attendus sur ``self`` :
- ``_partie``, ``_id_partie``, ``_chemin_persistance`` : partie courante et persistance.
- ``_selection``, ``_en_attente``, ``_joker_demande`` : état de pose (remis à zéro).
- ``_fin_journalisee``, ``_fin_persistee`` : drapeaux de fin de partie.
- ``_retour_menu``, ``_recommencer`` : drapeaux d'action post-fermeture.
- ``_nouvelle_partie``, ``_nouvel_id_partie``, ``_nouvelles_infos_tirage`` : recommencer.
- ``_window_plateau`` : fenêtre pywebview à fermer.
- ``_ia_en_cours`` : verrou anti-réentrance du tour IA (issue #364).
"""

from __future__ import annotations

import random
import sys
from typing import TYPE_CHECKING, Any

from scrabble.moteur.partie import EntreeHistorique, recreer_partie_meme_joueurs
from scrabble.persistance import demarrer_suivi

if TYPE_CHECKING:
    from scrabble.moteur.partie import Partie


def _mod_jeu():
    """Accès au module jeu déjà chargé (évite l'import circulaire)."""
    return sys.modules["scrabble.ui.jeu"]


class MixinTourEtFinPartie:
    """Mixin : gestion du tour courant et de la fin de partie."""

    def passer(self) -> dict[str, Any]:
        """Fait **passer** le tour du joueur courant sans rien échanger (issue #132).

        Point d'entrée du bouton « Passer son tour ». Sur le modèle de
        :meth:`echanger_tout`, mais sans toucher au sac : c'est le recours qui
        débloque un joueur humain sac vide (rapport #130), tout en restant un
        droit normal du jeu utilisable à tout moment de son tour. Délègue à
        :func:`passer_tour` (qui appelle
        :meth:`~scrabble.moteur.partie.Partie.passer`).

        En cas de succès : ``{"succes": True, "etat": <état public rafraîchi>}``
        (tour suivant, ou fin de partie par blocage si tous ont passé d'affilée),
        l'état de pose est remis à zéro et rediffusé aux deux fenêtres. Si la
        partie est déjà terminée : ``{"succes": False, "erreur": <message>}`` —
        l'état n'est pas modifié.
        """
        nom = self._partie.joueur_courant().nom
        nb_avant = len(self._partie.historique)
        resultat = _mod_jeu().passer_tour(self._partie, self._id_partie)
        if resultat.get("succes"):
            _mod_jeu().journal.info(f"Jeu : {nom} passe son tour.")
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._journaliser_fin_partie()
            self._finaliser_si_terminee()
            # Tour suivant (ou fin de partie) : on repart d'un état de pose vierge
            # et on rediffuse le nouvel état public / privé aux deux fenêtres.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            self._diffuser()
        else:
            _mod_jeu().journal.info(f"Jeu : passe refusée pour {nom} — {resultat.get('erreur')}")
        return resultat

    def faire_jouer_ia(self) -> dict[str, Any]:
        """Fait jouer **un seul** tour d'ordinateur (celui du joueur courant).

        Point d'entrée du bouton « ▶ Jouer » de la fiche du joueur ordinateur
        courant (issue #149, ex-« ▶ Faire jouer l'ordinateur » de la zone
        d'attente ; issue #35, revu issue #55 : un clic = un seul ordinateur).
        S'appuie sur
        :meth:`~scrabble.moteur.partie.Partie.jouer_tour_ia` : joue exactement le
        tour de l'ordinateur courant, puis renvoie
        ``{"succes": True, "nb_tours": ..., "etat": <état public rafraîchi>}``
        (``nb_tours`` = 1 si un tour a été joué). Sans effet si le joueur courant
        est déjà humain (``nb_tours`` = 0). Si l'ordinateur suivant est encore un
        ordinateur, un bouton « ▶ Jouer » réapparaît dans sa fiche : l'humain
        reclique pour le faire jouer à son tour.

        C'est la seule façon prévue de faire avancer le jeu pendant un tour IA :
        l'humain n'a jamais à manipuler le chevalet d'un ordinateur à sa place.

        Verrou anti-réentrance (``_ia_en_cours``, issue #364, suite de #363) :
        un second appel reçu pendant qu'un premier est encore en cours de
        traitement est **refusé** (``{"succes": False, "erreur": ...}``) sans
        toucher à la partie. Utile en défense en profondeur : le JS désactive
        déjà le bouton cliqué, mais le panneau du joueur courant est reconstruit
        à **chaque** diffusion (voir ``jeu.js``), ce qui recrée un bouton actif
        avant que la réponse de l'appel en cours ne soit revenue — des clics
        rapides répétés pouvaient donc déclencher un second tour IA en
        parallèle. Le drapeau est remis à zéro dans un bloc ``finally`` : même
        une exception inattendue pendant le tour ne le laisse jamais bloqué.
        """
        if self._ia_en_cours:
            return {
                "succes": False,
                "erreur": "Un tour d'ordinateur est déjà en cours.",
            }
        self._ia_en_cours = True
        try:
            nom = self._partie.joueur_courant().nom
            nb_avant = len(self._partie.historique)
            resultat = _mod_jeu().jouer_tours_ia_ui(self._partie, self._id_partie)
            if resultat.get("nb_tours"):
                _mod_jeu().journal.info(f"Jeu : tour d'ordinateur joué ({nom}).")
                self._persister_entrees(self._partie.historique[nb_avant:])
                self._journaliser_fin_partie()
                self._finaliser_si_terminee()
                # Tour suivant : état de pose remis à zéro et rediffusé (nouvel
                # état public au plateau, nouveau chevalet en zone C intégrée)
                # — #90.
                self._selection = None
                self._en_attente = []
                self._joker_demande = None
                self._diffuser()
            return resultat
        finally:
            self._ia_en_cours = False

    def _persister_entrees(self, entrees: list[EntreeHistorique]) -> None:
        """Persiste en base chaque action produite par le moteur (issue #81).

        Diagnostic de l'issue #81 : les :class:`EntreeHistorique` produites par le
        moteur (un coup, un tour d'ordinateur, un échange) n'étaient jamais
        transmises à la persistance — une reprise reconstruisait donc toujours un
        plateau vide. Cette méthode branche
        :func:`~scrabble.persistance.enregistrer_action` après chaque action
        réussie, en préservant l'ordre.

        L'écriture est encadrée par un ``try/except`` : l'action de jeu reste
        valide côté joueur même si la persistance échoue, mais l'échec est rendu
        **visible** dans le journal (``_mod_jeu().journal.erreur``) plutôt que d'être avalé
        silencieusement. En mode démonstration (``_id_partie`` à ``None``), il n'y
        a aucune partie suivie en base : rien n'est écrit.
        """
        if self._id_partie is None:
            return
        for entree in entrees:
            try:
                _mod_jeu().enregistrer_action(
                    self._id_partie, entree, self._chemin_persistance
                )
            except Exception as e:  # noqa: BLE001 - on trace, sans planter le jeu
                _mod_jeu().journal.erreur(
                    f"Jeu : échec de l'enregistrement d'une action "
                    f"(partie #{self._id_partie}).",
                    e,
                )

    def _finaliser_si_terminee(self) -> None:
        """Marque la partie terminée en base (une seule fois) — issue #81.

        Appelée après chaque action susceptible de terminer la partie (coup,
        tour d'ordinateur, échange). Tant que la partie n'est pas terminée, ou si
        elle l'a déjà été persistée, la méthode est sans effet. Comme
        :meth:`_persister_entrees`, l'échec d'écriture est journalisé sans planter
        le jeu, et le mode démonstration (``_id_partie`` à ``None``) est ignoré.
        """
        if self._id_partie is None or self._fin_persistee:
            return
        if not self._partie.terminee:
            return
        self._fin_persistee = True
        try:
            _mod_jeu().finaliser_partie(
                self._id_partie, self._partie, self._chemin_persistance
            )
        except Exception as e:  # noqa: BLE001 - on trace, sans planter le jeu
            _mod_jeu().journal.erreur(
                f"Jeu : échec de la finalisation de la partie "
                f"#{self._id_partie}.",
                e,
            )

    def _journaliser_fin_partie(self) -> None:
        """Journalise (une seule fois) la fin de partie et son ou ses gagnants.

        Appelée après chaque action susceptible de terminer la partie (pose d'un
        coup humain, tour d'ordinateur). Le drapeau ``_fin_journalisee`` garantit
        qu'on n'écrit la ligne « fin de partie » qu'une fois, même si l'UI
        redéclenche des actions sans effet une fois la partie terminée.
        """
        if self._partie.terminee and not self._fin_journalisee:
            self._fin_journalisee = True
            gagnants = ", ".join(j.nom for j in self._partie.gagnants) or "aucun"
            _mod_jeu().journal.info(f"Jeu : fin de partie — gagnant(s) : {gagnants}.")

    def retour_menu(self) -> dict[str, Any]:
        """Ferme la fenêtre de jeu pour revenir à l'accueil (issues #74/#193).

        Point d'entrée du bouton « 🏠 Retour au menu ». Ferme la fenêtre de jeu
        **depuis Python** via ``window.destroy()`` — et non ``window.close()``
        côté JS, non honoré par tous les backends pywebview (GTK/WebKit sous
        Linux, issues #53/#57). Depuis le nettoyage du modèle de fenêtres (issue
        #193), l'écran de jeu ne comporte plus qu'une seule fenêtre physique
        (plateau + chevalet intégré) : une seule fenêtre à détruire. Une fois
        fermée, ``webview.start()`` rend la main à :func:`lancer_jeu`, qui, voyant
        le drapeau ``_retour_menu``, rouvre l'écran d'accueil
        (:func:`lancer_accueil`) en **réutilisant la session de journalisation**
        déjà ouverte (cohérent avec l'issue #66).

        La partie n'est pas modifiée ici : elle reste persistée et reprenable
        via « Reprendre une partie » (le suivi en base est mis à jour en continu
        après chaque action, issues #22/#25). Un éventuel coup en attente (non
        validé) est simplement abandonné — l'avertissement de confirmation est
        géré côté interface.

        Retourne ``{"succes": True}`` si la fermeture a été demandée, sinon
        ``{"succes": False, "erreur": ...}`` (le JS réactive alors le bouton
        plutôt que de rester bloqué).
        """
        if self._window_plateau is None:
            return {"succes": False, "erreur": "Aucune fenêtre associée."}
        try:
            _mod_jeu().journal.info(
                f"Jeu : retour au menu demandé (partie #{self._id_partie})."
            )
            self._retour_menu = True
            self._window_plateau.destroy()
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            # La fermeture a échoué : on ne rouvrira pas l'accueil (les fenêtres
            # de jeu restent ouvertes et le JS réactive le bouton).
            self._retour_menu = False
            return {"succes": False, "erreur": f"Fermeture impossible : {e}"}

    def creer_partie_recommencee(self) -> "Partie":
        """Fabrique une nouvelle partie reprenant les joueurs de la partie courante.

        Cœur « moteur/API » de l'action « Recommencer » (issue #142) : réutilise
        les mêmes joueurs (noms, humain/ordinateur, niveaux de difficulté) via
        :func:`~scrabble.moteur.partie.recreer_partie_meme_joueurs`, avec une
        **graine explicite tirée au hasard** (nécessaire au suivi de persistance,
        qui refuse une partie sans graine) et un **nouveau tirage d'ordre**. Le
        dictionnaire et le réglage ``bonus_fin_partie`` sont hérités de la partie
        courante — on ne repasse pas par l'écran de configuration.

        La partie terminée courante n'est pas touchée : elle reste finalisée en
        base (voir :meth:`_finaliser_si_terminee`) et consultable dans
        l'historique. Méthode isolée pour rester testable sans fenêtre.

        Effet de bord (issue #170) : mémorise dans ``_nouvelles_infos_tirage`` le
        détail nécessaire au tirage d'ordre de la nouvelle partie (mêmes noms dans
        l'ordre de création — humains puis ordinateurs — et la graine tirée), afin
        que l'écran de jeu relancé affiche à son tour l'écran de tirage.
        """
        graine = random.randint(0, 2**31 - 1)
        noms_humains = [j.nom for j in self._partie.joueurs if j.humain]
        noms_ia = [j.nom for j in self._partie.joueurs if not j.humain]
        self._nouvelles_infos_tirage = {
            "noms_creation": noms_humains + noms_ia,
            "graine": graine,
            "noms_humains": noms_humains,
        }
        return recreer_partie_meme_joueurs(
            self._partie,
            self._partie.dictionnaire,
            graine=graine,
            tirage_ordre=True,
        )

    def preparer_partie_recommencee(
        self,
    ) -> tuple["Partie", int | None, dict[str, Any] | None]:
        """Crée et suit en base la nouvelle partie de « Recommencer » (issue #181).

        Cœur « moteur + persistance » de l'action « Recommencer », isolé pour être
        partagé entre le chemin de production (:meth:`recommencer`, qui enchaîne
        ensuite un ``destroy()`` des fenêtres et positionne les drapeaux inter-
        boucles) et la coquille unifiée
        (:meth:`~scrabble.ui.application.ApiRouteur.recommencer_jeu`, qui enchaîne
        un ``load_url('jeu.html')``). Fabrique la nouvelle partie
        (:meth:`creer_partie_recommencee`, mêmes joueurs, nouveau tirage) et, hors
        mode démonstration (``_id_partie`` non ``None``), la déclare en base
        (:func:`~scrabble.persistance.demarrer_suivi`) sans toucher à l'ancienne.

        Retourne ``(nouvelle_partie, nouvel_id, infos_tirage)`` — ``infos_tirage``
        étant le détail préparé par :meth:`creer_partie_recommencee`
        (``_nouvelles_infos_tirage``) pour rejouer l'écran de tirage d'ordre. Ne
        positionne **aucun** drapeau inter-boucles (``_recommencer`` &co.) : ceux-ci
        n'existent que pour le pont entre boucles séparées du chemin de production.
        """
        nouvelle = self.creer_partie_recommencee()
        nouvel_id: int | None = None
        if self._id_partie is not None:
            nouvel_id = demarrer_suivi(nouvelle, self._chemin_persistance)
        _mod_jeu().journal.info(
            f"Jeu : recommencer une partie avec les mêmes joueurs "
            f"(ancienne #{self._id_partie} → nouvelle #{nouvel_id})."
        )
        return nouvelle, nouvel_id, self._nouvelles_infos_tirage

    def recommencer(self) -> dict[str, Any]:
        """Rejoue une nouvelle partie avec les mêmes joueurs (issue #142).

        Troisième action de la modale de fin de partie. Crée une partie neuve
        (:meth:`preparer_partie_recommencee`) puis ferme la fenêtre de jeu à la
        manière de :meth:`retour_menu`. Une fois la boucle rendue,
        :func:`lancer_jeu` relance l'écran de jeu sur cette nouvelle partie
        (drapeau ``_recommencer``).

        En mode démonstration (``_id_partie`` à ``None``), aucune persistance
        n'est déclenchée : la nouvelle partie n'est simplement pas suivie.

        Retourne ``{"succes": True}`` si la fermeture a été demandée, sinon
        ``{"succes": False, "erreur": ...}`` (le JS réactive alors le bouton).
        """
        if self._window_plateau is None:
            return {"succes": False, "erreur": "Aucune fenêtre associée."}
        try:
            nouvelle, nouvel_id, _ = self.preparer_partie_recommencee()
            self._nouvelle_partie = nouvelle
            self._nouvel_id_partie = nouvel_id
            self._recommencer = True
            self._window_plateau.destroy()
            return {"succes": True}
        except Exception as e:  # noqa: BLE001 - on remonte l'erreur au JS
            # Échec (création ou fermeture) : on n'enchaîne pas de nouvelle partie
            # (les fenêtres restent ouvertes et le JS réactive le bouton).
            self._recommencer = False
            self._nouvelle_partie = None
            self._nouvel_id_partie = None
            return {"succes": False, "erreur": f"Recommencer impossible : {e}"}
