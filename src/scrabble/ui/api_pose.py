"""Mixin « pose de lettres » pour l'API Jeu (issue #248).

Ce mixin regroupe les méthodes liées à la **pose de lettres** sur le plateau :
sélection dans le chevalet, placement en attente sur le plateau, retrait,
remplacement, annulation, validation du coup (poser_mot), et vérification du
coup ou d'un mot dans le dictionnaire.

Dépendances vers MixinDiffusion
-------------------------------
Ce mixin utilise les primitives suivantes de :class:`~.api_diffusion.MixinDiffusion` :

- ``self._diffuser()`` — appelée après chaque mutation de l'état de pose
  (sélection, placement, retrait, annulation, validation) pour mettre à jour
  la fenêtre Jeu.
- ``self._etat_plateau()`` — utilisée indirectement via ``etat_public`` après
  validation d'un coup.
- ``self._refuser_hors_tour()`` — garde de tour vérifiant que le joueur de
  référence est bien le joueur courant avant toute mutation de pose.
- ``self._pousser()`` — utilisée indirectement via ``_diffuser``.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from scrabble.regles.lettres import JOKER, valeur_lettre

if TYPE_CHECKING:
    from scrabble.moteur.partie import EntreeHistorique, Partie


class MixinPose:
    """Méthodes de pose de lettres et de validation pour ApiJeu (issue #248)."""

    # Attributs attendus sur la classe hôte (ApiJeu), déclarés pour les
    # annotations — pas de valeur par défaut, ils vivent sur l'instance.
    _partie: Partie | None
    _id_partie: int | None
    _selection: int | None
    _en_attente: list[dict[str, Any]]
    _joker_demande: dict[str, Any] | None
    _lettres_pioches: list[str]

    # Méthodes attendues de MixinDiffusion (via l'héritage multiple d'ApiJeu).
    def _diffuser(self) -> None: ...
    def _refuser_hors_tour(self) -> dict[str, Any] | None: ...

    def selectionner_lettre(self, index: Any) -> dict[str, Any]:
        """Sélectionne (ou désélectionne) la lettre du chevalet d'index ``index``.

        Appelée par le panneau chevalet au clic sur une lettre. ``index`` à
        ``None`` (ou l'index déjà sélectionné) annule la sélection. Met à jour
        ``_selection`` puis diffuse l'état à la fenêtre.

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, la sélection est refusée sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if index is None:
            self._selection = None
        elif not isinstance(index, int):
            return {"succes": False, "erreur": "Index de lettre invalide."}
        elif self._selection == index:
            self._selection = None  # reclic sur la même lettre : on désélectionne
        else:
            self._selection = index
        # Toute (re)sélection annule une demande de choix de lettre de joker en
        # cours : elle permet notamment d'abandonner proprement la modale joker.
        self._joker_demande = None
        self._diffuser()
        return {"succes": True, "selection": self._selection}

    def poser_lettre_en_attente(
        self,
        ligne: Any,
        colonne: Any,
        lettre: Any = None,
        joker: Any = None,
        valeur: Any = None,
        index: Any = None,
    ) -> dict[str, Any]:
        """Place une lettre en attente sur la case ``(ligne, colonne)`` — issue #90.

        Deux modes d'appel, unifiés ici pour respecter strictement la séparation
        de confidentialité (la fenêtre plateau ne connaît aucune lettre du
        chevalet) :

        * **Depuis la fenêtre plateau** (clic sur une case vide) : seuls
          ``ligne``/``colonne`` sont fournis. La lettre est résolue côté Python à
          partir de ``_selection`` et du chevalet du joueur courant. Si la lettre
          sélectionnée est un **joker**, aucune lettre n'est encore posée : on
          mémorise la case (``_joker_demande``) et on renvoie ``joker_requis`` —
          le menu de choix de la lettre du joker s'ouvre alors côté JS.
        * **Depuis le panneau chevalet** (après choix de la lettre d'un joker) :
          ``lettre``/``joker``/``valeur``/``index`` sont fournis explicitement et
          le placement est finalisé tel quel.

        Renvoie ``{"succes": True}`` (ou ``joker_requis``) et diffuse le nouvel
        état ; ``{"succes": False, "erreur": ...}`` si le placement est refusé
        (aucune sélection, index invalide, case occupée…).

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, la pose est refusée sans toucher à l'état.
        """
        from scrabble.moteur.plateau_partie import dans_plateau

        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        if not isinstance(ligne, int) or not isinstance(colonne, int):
            return {"succes": False, "erreur": "Position de pose invalide."}
        if not dans_plateau(ligne, colonne):
            return {"succes": False, "erreur": "Position hors plateau."}
        if not self._partie.plateau.case_vide(ligne, colonne):
            return {
                "succes": False,
                "erreur": "Cette case porte déjà une tuile.",
            }
        # Mode « finalisation » : la lettre (et son index) sont fournis. Traité
        # avant le garde « lettre déjà posée ici » car une finalisation peut
        # légitimement écraser une lettre en attente (remplacement par un joker,
        # issue #129).
        if lettre is not None and index is not None:
            self._joker_demande = None
            # Remplacement d'une lettre en attente par un joker (issue #129) :
            # l'ancienne lettre a été laissée en place jusqu'à la validation de la
            # modale de choix ; on la retire ici pour que le joker prenne sa place
            # (l'ancienne redevient disponible au chevalet). Sur une case vierge,
            # ce filtre est sans effet.
            self._en_attente = [
                p for p in self._en_attente
                if not (p["ligne"] == ligne and p["colonne"] == colonne)
            ]
            return self._ajouter_placement(
                ligne, colonne, str(lettre), bool(joker),
                int(valeur) if valeur is not None else 0, int(index),
            )

        if any(p["ligne"] == ligne and p["colonne"] == colonne for p in self._en_attente):
            return {"succes": False, "erreur": "Une lettre est déjà posée ici."}

        # Mode « clic plateau » : on résout la lettre via la sélection courante.
        if self._selection is None:
            return {
                "succes": False,
                "erreur": "Sélectionnez d'abord une lettre de votre chevalet.",
            }
        idx = self._selection
        chevalet = self._partie.joueur_courant().chevalet
        if not (0 <= idx < len(chevalet)):
            return {"succes": False, "erreur": "Lettre sélectionnée invalide."}
        jeton = chevalet[idx]
        if jeton == JOKER:
            # La lettre du joker se choisit côté chevalet : on diffère la pose.
            self._joker_demande = {"ligne": ligne, "colonne": colonne, "index": idx}
            self._diffuser()
            return {
                "succes": True,
                "joker_requis": True,
                "ligne": ligne,
                "colonne": colonne,
                "index": idx,
            }
        return self._ajouter_placement(
            ligne, colonne, jeton, False, valeur_lettre(jeton), idx
        )

    def _ajouter_placement(
        self,
        ligne: int,
        colonne: int,
        lettre: str,
        joker: bool,
        valeur: int,
        index: int,
    ) -> dict[str, Any]:
        """Ajoute un placement résolu à ``_en_attente``, réinitialise la sélection."""
        self._en_attente.append(
            {
                "ligne": ligne,
                "colonne": colonne,
                "lettre": lettre,
                "joker": joker,
                "valeur": 0 if joker else valeur,
                "index": index,
            }
        )
        self._selection = None
        self._joker_demande = None
        self._diffuser()
        return {"succes": True}

    def retirer_lettre_en_attente(self, ligne: Any, colonne: Any) -> dict[str, Any]:
        """Retire le placement en attente de la case ``(ligne, colonne)`` — issue #90.

        Appelée au clic sur une tuile en attente (retrait de la pose). La lettre
        redevient disponible au chevalet. Diffuse le nouvel état aux deux
        fenêtres. Sans effet (mais succès) si aucune lettre n'attend sur la case.

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, le retrait est refusé sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        avant = len(self._en_attente)
        self._en_attente = [
            p for p in self._en_attente
            if not (p["ligne"] == ligne and p["colonne"] == colonne)
        ]
        if len(self._en_attente) != avant:
            self._selection = None
            self._diffuser()
        return {"succes": True}

    def remplacer_ou_retirer_lettre_en_attente(
        self, ligne: Any, colonne: Any
    ) -> dict[str, Any]:
        """Clic sur une case portant une lettre en attente du tour courant — issue #129.

        Point d'entrée unique appelé par la fenêtre plateau au clic sur une case
        qui porte déjà une lettre **en attente** (pas une tuile validée). La
        fenêtre plateau ignore l'état de sélection du chevalet ; c'est donc ici,
        côté Python, que se décide le comportement :

        * **aucune lettre sélectionnée** (``_selection is None``) : simple retrait,
          la lettre redevient disponible au chevalet — comportement historique
          strictement préservé (cas limite 1) ;
        * **une lettre sélectionnée** : la lettre sélectionnée **prend la place**
          de la lettre en attente, laquelle **retourne** au chevalet, en un seul
          geste. Si la lettre sélectionnée est un **joker**, on diffère la pose
          via la modale de choix (``_joker_demande``) exactement comme sur une
          case vide : l'ancienne lettre reste en place jusqu'à la validation du
          choix, et la finalisation la remplacera (annuler la modale ne change
          alors rien).

        Ne concerne jamais une case sans lettre en attente ni une tuile validée
        (le JS n'y route pas ce clic) ; renvoie ``{"succes": True}`` sans effet si
        aucune lettre n'attend sur la case. Réservée au tour du joueur de
        référence (garde :meth:`_refuser_hors_tour`).
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        placement = next(
            (
                p for p in self._en_attente
                if p["ligne"] == ligne and p["colonne"] == colonne
            ),
            None,
        )
        if placement is None:
            # Rien en attente ici : aucun effet (le JS ne devrait pas router ici).
            return {"succes": True}
        # Sans sélection active : on conserve le retrait simple (cas limite 1).
        if self._selection is None:
            return self.retirer_lettre_en_attente(ligne, colonne)
        idx = self._selection
        chevalet = self._partie.joueur_courant().chevalet
        if not (0 <= idx < len(chevalet)):
            return {"succes": False, "erreur": "Lettre sélectionnée invalide."}
        jeton = chevalet[idx]
        if jeton == JOKER:
            # Le remplacement par un joker passe par la modale de choix : on ne
            # retire pas encore l'ancienne lettre (la finalisation le fera), pour
            # qu'un abandon de la modale laisse la case inchangée.
            self._joker_demande = {"ligne": ligne, "colonne": colonne, "index": idx}
            self._diffuser()
            return {
                "succes": True,
                "joker_requis": True,
                "ligne": ligne,
                "colonne": colonne,
                "index": idx,
            }
        # Remplacement direct : l'ancienne lettre retourne au chevalet, la nouvelle
        # prend sa place sur la même case (``_ajouter_placement`` remet la sélection
        # à None et diffuse — une seule opération perçue côté joueur).
        self._en_attente = [p for p in self._en_attente if p is not placement]
        return self._ajouter_placement(
            ligne, colonne, jeton, False, valeur_lettre(jeton), idx
        )

    def annuler_pose(self) -> dict[str, Any]:
        """Abandonne toute la pose en cours (sélection + placements) — issue #90.

        Vide ``_selection`` et ``_en_attente`` (aucune lettre n'est consommée : le
        moteur n'a rien joué) puis diffuse l'état remis à zéro aux deux fenêtres.

        Réservée au tour du joueur de référence (garde :meth:`_refuser_hors_tour`,
        issue #99) : hors tour, l'annulation est refusée sans toucher à l'état.
        """
        refus = self._refuser_hors_tour()
        if refus is not None:
            return refus
        self._selection = None
        self._en_attente = []
        self._joker_demande = None
        self._diffuser()
        return {"succes": True}

    def poser_mot(self, placements: list[Any] | None = None) -> dict[str, Any]:
        """Pose le mot formé par les lettres en attente (``_en_attente``) — issue #90.

        Depuis l'issue #90, la mécanique clic-clic est pilotée par l'état interne :
        le panneau chevalet a construit ``_en_attente`` au fil des appels à
        :meth:`poser_lettre_en_attente`, et cette méthode le lit directement — le
        JS ne passe donc plus de ``placements``. Le paramètre ``placements`` reste
        accepté (rétro-compatibilité et tests) : s'il est fourni, il **remplace**
        l'état de pose courant avant le jeu.

        Le sens du mot se déduit de l'alignement des lettres ; pour une lettre
        unique il est fixé à l'horizontale en interne (issue #43 : sans
        conséquence sur la validation ni le score). La méthode construit un
        :class:`~scrabble.moteur.plateau_partie.Coup`, appelle
        :meth:`~scrabble.moteur.partie.Partie.jouer_coup` et renvoie :

        * en cas de succès : ``{"succes": True, "points": ..., "etat": ...}`` où
          ``etat`` est l'état public rafraîchi. ``_selection``/``_en_attente`` sont
          réinitialisés (le moteur a consommé les lettres) et le nouvel état est
          diffusé aux deux fenêtres via :meth:`_diffuser` ;
        * en cas d'échec : ``{"succes": False, "erreur": <message clair>}`` — les
          lettres en attente **ne sont pas perdues** (elles restent dans
          ``_en_attente`` pour correction).

        Confidentialité : la réponse ne contient jamais l'identité des lettres
        d'un chevalet (``etat`` est l'état public, sans chevalet).
        """
        from scrabble.ui import jeu as mod_jeu
        from scrabble.ui.jeu import etat_public, jouer_placements

        if placements is not None:
            self._en_attente = [self._normaliser_placement(p) for p in placements]
        nb_avant = len(self._partie.historique)
        resultat = jouer_placements(self._partie, self._en_attente)
        if resultat.get("succes"):
            # Lettres tout juste piochées, remontées directement par le moteur
            # (issue #357 — évite le calcul par diff de chevalet, incorrect
            # quand une lettre piochée a la même valeur qu'une lettre posée,
            # cf. issue #356 ; utilisées pour l'animation du chevalet, issue #325).
            self._lettres_pioches = list(resultat.get("lettres_piochees", []))
            detail = resultat.get("detail")
            mot = (
                detail["mots"][0]["texte"]
                if detail and detail.get("mots")
                else "?"
            )
            mod_jeu.journal.info(
                f"Jeu : coup posé par {resultat.get('nom')} — "
                f"{mot} ({resultat.get('points')} pts)."
            )
            self._persister_entrees(self._partie.historique[nb_avant:])
            self._journaliser_fin_partie()
            self._finaliser_si_terminee()
            # Le coup est joué : on repart d'un état de pose vierge et on
            # rediffuse le nouvel état (public / privé) aux deux fenêtres.
            self._selection = None
            self._en_attente = []
            self._joker_demande = None
            resultat["etat"] = etat_public(self._partie, self._id_partie)
            self._diffuser()
        else:
            # Un coup refusé (mot hors dictionnaire, placement illégal…) est un
            # déroulé de jeu normal, pas un bug : on le trace en INFO pour pouvoir
            # reconstituer la session, sans déclencher la rétention du fichier
            # (réservée aux vraies erreurs, voir module ``journal``).
            mod_jeu.journal.info(f"Jeu : coup refusé — {resultat.get('erreur')}")
        return resultat

    @staticmethod
    def _normaliser_placement(placement: Any) -> dict[str, Any]:
        """Normalise un placement (dict JS ou interne) en placement interne complet.

        Garantit la présence des clés attendues par ``_en_attente``
        (``ligne, colonne, lettre, joker, valeur, index``) à partir d'un dict qui
        peut n'en fournir qu'une partie (p. ex. ``{ligne, colonne, lettre, joker}``
        venu d'un test ou d'un ancien appelant). ``valeur`` et ``index`` sont
        déduits/comblés si absents.
        """
        if not isinstance(placement, dict):
            return {"ligne": None, "colonne": None, "lettre": None,
                    "joker": False, "valeur": 0, "index": None}
        joker = bool(placement.get("joker", False))
        lettre = placement.get("lettre")
        if "valeur" in placement and placement["valeur"] is not None:
            valeur = placement["valeur"]
        elif joker or not isinstance(lettre, str):
            valeur = 0
        else:
            valeur = valeur_lettre(lettre.upper())
        return {
            "ligne": placement.get("ligne"),
            "colonne": placement.get("colonne"),
            "lettre": lettre,
            "joker": joker,
            "valeur": 0 if joker else valeur,
            "index": placement.get("index"),
        }

    def verifier_coup(self, placements: list[Any] | None = None) -> dict[str, Any]:
        """Calcule les points du coup en attente **sans le jouer** (issue #69).

        Point d'entrée du bouton « 🔎 Vérifier et calculer ». Depuis l'issue #90 la
        méthode lit ``_en_attente`` (le JS ne passe plus de ``placements``) ;
        ``placements`` reste accepté pour compat/tests et remplace alors l'état de
        pose courant. Délègue à :func:`simuler_coup`, qui valide le coup et calcule
        son score sur une **copie** du plateau, sans rien modifier de la partie :
        ni le plateau réel, ni le chevalet, ni l'historique, ni le tour. Les
        lettres en attente ne sont donc pas perdues et aucun tour n'est consommé.

        Renvoie, comme un coup réellement joué,
        ``{"succes": True, "points": ..., "nom": ..., "detail": ...}`` si le coup
        est valide, ou ``{"succes": False, "erreur": <message clair>}`` sinon
        (aucun score affiché dans ce cas). La réponse ne contient jamais l'identité
        des lettres d'un chevalet.
        """
        from scrabble.ui import jeu as mod_jeu
        from scrabble.ui.jeu import simuler_coup

        if placements is not None:
            self._en_attente = [self._normaliser_placement(p) for p in placements]
        resultat = simuler_coup(self._partie, self._en_attente)
        if resultat.get("succes"):
            detail = resultat.get("detail")
            mot = (
                detail["mots"][0]["texte"]
                if detail and detail.get("mots")
                else "?"
            )
            mod_jeu.journal.info(
                f"Jeu : coup vérifié (non joué) — {mot} "
                f"({resultat.get('points')} pts)."
            )
        else:
            mod_jeu.journal.info(f"Jeu : vérification de coup — {resultat.get('erreur')}")
        return resultat

    def verifier_mot(self, lettres: Any) -> dict[str, Any]:
        """Teste dans le dictionnaire le mot formé par la zone de brouillon.

        ``lettres`` est la suite de jetons arrangés dans le brouillon (dans
        l'ordre affiché). Le test est en **lecture seule** : il ne pose aucun
        coup, ne consomme aucun tour et ne modifie en rien l'état de la partie.
        Renvoie ``{"succes": True, "mot": <MOT>, "valide": bool, "definition":
        [{"texte": ..., "origine": "standard"|"belge"}, ...] | None}`` ou, si
        le brouillon est vide, ``{"succes": False, "erreur": <message>}``. La
        ``definition`` est ``None`` quand le mot est invalide ou sans aucune
        glose — l'UI affiche alors « définition indisponible ».

        Restriction à la source active (issue #127) : les gloses **standards**
        (ODS8, issue #124) ne sont renvoyées que si la partie est jouée avec
        ``"ods"`` comme source de dictionnaire (``config["source_dictionnaire"]``,
        seule source de vérité de la source active — ni ``Partie`` ni
        ``Dictionnaire`` ne la mémorisent) ; en source ``"hunspell"``, elles
        sont toujours absentes, pour rester strictement cohérent avec ce qui
        valide réellement les coups sur le plateau. Les gloses **belges**
        (issue #276) échappent à cette restriction : elles sont renvoyées dès
        qu'elles existent, quelle que soit la source active ou le mode
        Belgicisme de la partie en cours.
        """
        from scrabble.ui import jeu as mod_jeu
        from scrabble.ui.jeu import verifier_mot_dictionnaire

        source = mod_jeu.charger_config().get("source_dictionnaire", "ods")
        return verifier_mot_dictionnaire(
            self._partie.dictionnaire, lettres, source=source
        )

    # Méthodes attendues d'ApiJeu (utilisées par poser_mot).
    def _persister_entrees(self, entrees: "list[EntreeHistorique]") -> None: ...
    def _journaliser_fin_partie(self) -> None: ...
    def _finaliser_si_terminee(self) -> None: ...
