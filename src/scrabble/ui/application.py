"""Coquille mono-fenêtre unifiée + routeur d'API (issue #179).

Suite au rapport d'investigation #178 (confirmé) : Accueil et Jeu doivent être
fusionnés en **une seule fenêtre physique** — via ``load_url`` (changement de
document dans la même fenêtre) plutôt que par cohabitation DOM — pilotée par un
**routeur d'API à deux sous-API préservées** plutôt qu'une fusion des classes
``ApiAccueil``/``ApiJeu``.

Ce module pose la **fondation invisible** de ce chantier :

- :class:`ApiRouteur` — objet-pont mince exposé au JS comme ``js_api``. Il
  détient une instance d'``ApiAccueil`` et une d'``ApiJeu``, garde la trace de
  la vue active (« accueil » ou « jeu »), et route dynamiquement chaque appel JS
  vers la sous-API **actuellement active**. Cela résout notamment la collision
  réelle sur ``obtenir_etat`` (méthode présente dans les deux classes) sans rien
  renommer côté JS existant.
- :func:`lancer_application_unifiee` — nouvelle coquille qui crée **une seule**
  fenêtre pywebview (``accueil.html``, avec le routeur comme ``js_api``) et
  démarre **une seule** boucle ``webview.start()``.

À ce stade, **aucune transition accueil→jeu n'est câblée** (objectif de l'issue
B) : ce module se développe en parallèle du chemin historique
(``lancer_accueil``/``lancer_jeu``), qui reste intact et fonctionnel. La coquille
n'est donc branchée par aucun point d'entrée par défaut ; elle est testable en
isolation.

Issue #182 : la fermeture par la croix est sécurisée dans ce modèle mono-boucle
(le chevalet compagnon masqué est bien détruit, cf. ``ApiJeu.installer_fermeture_croisee``),
un parcours de bout en bout est couvert par les tests, et un point d'entrée de
**test manuel volontaire** est exposé (:func:`main` — ``python -m
scrabble.ui.application``) **sans** modifier le chemin de production par défaut.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import webview

from scrabble import journal
from scrabble.moteur.partie import Partie
from scrabble.ui import TAPIS_VERT
from scrabble.ui.accueil import ApiAccueil
from scrabble.ui.jeu import ApiJeu

DOSSIER_WEB = Path(__file__).parent / "web"

# Identifiants des deux vues physiques que le routeur sait servir.
VUE_ACCUEIL = "accueil"
VUE_JEU = "jeu"
VUES = (VUE_ACCUEIL, VUE_JEU)


class ApiRouteur:
    """Routeur d'API à deux sous-API préservées (issue #179).

    Objet-pont **mince** passé à pywebview comme ``js_api`` de la fenêtre unique.
    Il détient une instance d':class:`~scrabble.ui.accueil.ApiAccueil` et une
    d':class:`~scrabble.ui.jeu.ApiJeu` (cette dernière pouvant être « vide » tant
    qu'aucune partie n'est chargée, cf. :meth:`ApiJeu.charger_partie`), et route
    chaque appel JS vers la sous-API **actuellement active** selon la vue chargée.

    Résolution de collision : ``obtenir_etat`` existe dans les DEUX classes. Le
    routeur tranche l'ambiguïté au moment de l'appel, selon ``vue_active``, sans
    renommer quoi que ce soit côté JS existant (``accueil.js`` et ``jeu.js``
    appellent tous deux ``api.obtenir_etat()`` ; chacun est chargé quand sa propre
    vue est active, donc chacun tombe sur la bonne sous-API).

    Exposition dynamique à pywebview : pywebview énumère les méthodes publiques de
    l'objet ``js_api`` (``dir()``, hors ``_``). On installe donc, à la
    construction, un **attribut d'instance** par nom de méthode publique de l'une
    ou l'autre sous-API : une petite fonction de routage qui redirige vers la
    sous-API active à l'appel. Les méthodes de **contrôle** propres au routeur
    (``set_window``, ``activer_vue``, ``charger_jeu``) sont, elles, de vraies
    méthodes de classe, jamais routées.

    Course à garder en tête (rapport #178) : dans les issues suivantes, le routeur
    devra être pointé sur la bonne sous-API (:meth:`activer_vue`) **avant** un
    ``load_url``, pour que le premier appel du JS fraîchement chargé tombe déjà
    sur la bonne cible. :meth:`activer_vue` est donc conçue pour être appelée
    juste avant la navigation (aucune navigation n'étant encore câblée ici).
    """

    # Noms réservés au contrôle du routeur : jamais routés vers une sous-API,
    # même si un nom identique existe côté ``ApiAccueil``/``ApiJeu``. (Ces noms
    # correspondent à de vraies méthodes de classe ci-dessous ; le filtre
    # ``hasattr(type(self), nom)`` de :meth:`_installer_routes` suffirait, mais
    # cet ensemble explicite documente l'intention.)
    _CONTROLE = frozenset(
        {
            "set_window",
            "activer_vue",
            "charger_jeu",
            "demarrer_jeu",
            "retourner_accueil",
            "recommencer_jeu",
            "annuler_tirage_accueil",
        }
    )

    def __init__(
        self,
        api_accueil: ApiAccueil | None = None,
        api_jeu: ApiJeu | None = None,
        vue_active: str = VUE_ACCUEIL,
    ) -> None:
        if vue_active not in VUES:
            raise ValueError(f"Vue inconnue : {vue_active!r} (attendu : {VUES}).")
        self._api_accueil = api_accueil if api_accueil is not None else ApiAccueil()
        # ``ApiJeu`` créée « vide » : la partie sera chargée après coup via
        # :meth:`charger_jeu` (nouveau modèle mono-fenêtre, issue #179).
        self._api_jeu = api_jeu if api_jeu is not None else ApiJeu()
        self._vue_active = vue_active
        # Handle de la fenêtre physique **unique** partagée. Renseigné par
        # :meth:`set_window` (qui le propage aussi aux deux sous-API).
        self._window: webview.Window | None = None
        self._installer_routes()

    # ------------------------------------------------------------------ #
    # État interne du routeur (accès privés — non exposés au JS)
    # ------------------------------------------------------------------ #

    def _api_active(self) -> ApiAccueil | ApiJeu:
        """Retourne la sous-API vers laquelle router selon la vue active."""
        return self._api_accueil if self._vue_active == VUE_ACCUEIL else self._api_jeu

    # ------------------------------------------------------------------ #
    # Câblage dynamique des routes
    # ------------------------------------------------------------------ #

    def _installer_routes(self) -> None:
        """Installe une route par méthode publique de l'une OU l'autre sous-API.

        Chaque route est une fonction (stockée comme attribut d'instance, donc
        vue par ``dir()`` et par l'énumération de pywebview) qui, à l'appel,
        redirige vers la sous-API active. Les noms de contrôle du routeur et tout
        nom déjà porté par une méthode de la classe ``ApiRouteur`` sont ignorés
        (la méthode de classe l'emporte).
        """
        noms: set[str] = set()
        for sous_api in (self._api_accueil, self._api_jeu):
            for nom in dir(sous_api):
                if nom.startswith("_"):
                    continue
                if not callable(getattr(sous_api, nom, None)):
                    continue
                noms.add(nom)
        for nom in sorted(noms):
            if nom in self._CONTROLE or hasattr(type(self), nom):
                continue
            setattr(self, nom, self._creer_route(nom))

    def _creer_route(self, nom: str):
        """Fabrique la fonction de routage pour la méthode ``nom``.

        La fonction résout la sous-API active **à l'appel** (pas à la
        construction) : un ``activer_vue`` intercalé change donc bien la cible.
        Si la sous-API active n'expose pas ``nom`` (ex. ``obtenir_niveaux`` propre
        à l'accueil, appelée alors que la vue jeu est active), une
        ``AttributeError`` explicite est levée — signe d'un JS qui appelle une
        méthode hors de sa vue.
        """

        def route(*args: Any, **kwargs: Any) -> Any:
            active = self._api_active()
            methode = getattr(active, nom, None)
            if methode is None:
                raise AttributeError(
                    f"La vue active « {self._vue_active} » n'expose pas "
                    f"la méthode « {nom} »."
                )
            return methode(*args, **kwargs)

        route.__name__ = nom
        route.__qualname__ = f"ApiRouteur.route<{nom}>"
        return route

    # ------------------------------------------------------------------ #
    # Méthodes de contrôle (exposées au JS mais jamais routées)
    # ------------------------------------------------------------------ #

    def set_window(self, window: webview.Window) -> None:
        """Porte le handle de la fenêtre physique unique et le propage.

        Les deux sous-API ont besoin de la même fenêtre (l'accueil pour
        ``fermer_fenetre``, le jeu pour ses diffusions/positionnements). On la
        pose ici et on la relaie à chacune via leur propre ``set_window``
        (``ApiJeu.set_window`` renseigne sa fenêtre « plateau », le chevalet
        restant hors périmètre de cette issue — issue B).
        """
        self._window = window
        self._api_accueil.set_window(window)
        self._api_jeu.set_window(window)

    def activer_vue(self, vue: str) -> dict[str, Any]:
        """Bascule la vue active vers laquelle les appels JS sont routés.

        À appeler **avant** un futur ``load_url`` (course signalée par le rapport
        #178) pour que le premier appel du JS fraîchement chargé tombe déjà sur la
        bonne sous-API. Aucune navigation n'étant encore câblée dans cette issue,
        cette méthode ne fait pour l'instant que déplacer le curseur de routage.
        """
        if vue not in VUES:
            return {"succes": False, "erreur": f"Vue inconnue : {vue!r}."}
        self._vue_active = vue
        journal.info(f"Routeur : vue active = « {vue} ».")
        return {"succes": True, "vue": vue}

    def charger_jeu(
        self,
        partie: Partie,
        id_partie: int | None,
        infos_tirage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Charge une partie dans la sous-API Jeu (sans encore basculer la vue).

        Fine délégation à :meth:`ApiJeu.charger_partie` : prépare la sous-API Jeu
        pour une partie donnée (remise à zéro complète de son état incluse), en
        vue d'une bascule ultérieure ``activer_vue(VUE_JEU)`` + ``load_url`` (non
        câblée ici). Séparer le chargement de la bascule laisse l'appelant décider
        de l'ordre (typiquement : charger, activer, puis naviguer).
        """
        self._api_jeu.charger_partie(partie, id_partie, infos_tirage)
        return {"succes": True}

    def demarrer_jeu(self) -> dict[str, Any]:
        """Transition Accueil→Jeu dans la fenêtre unique via ``load_url`` (issue #180).

        Point d'entrée appelé depuis ``accueil.js`` (boutons « Lancer la partie »
        et « Reprendre une partie ») **uniquement dans la coquille unifiée** : le
        JS ne l'appelle que s'il détecte cette méthode (``typeof
        api.demarrer_jeu === 'function'``), sinon il conserve le comportement de
        production (``api.fermer_fenetre()``). Voir la note de détection dans
        ``accueil.js``.

        À ce stade, ``ApiAccueil.lancer_partie``/``reprendre`` (déjà appelée par le
        JS et routée vers la sous-API accueil) a créé/repris la partie et l'a
        déposée dans ``self._api_accueil`` (``_partie``/``_id_partie``/
        ``_infos_tirage``). On la lit ici **côté Python** — un objet ``Partie`` ne
        peut pas transiter par le pont JS —, exactement comme le chemin historique
        (``lancer_accueil`` lit ``api._partie`` avant d'appeler ``lancer_jeu``).

        Séquence, dans l'ordre exigé par le rapport #178 (point 3, course de
        routage) :

        1. :meth:`charger_jeu` — installe la partie dans la sous-API Jeu (remise à
           zéro complète comprise) ;
        2. :meth:`activer_vue` ``(VUE_JEU)`` — **avant** la navigation, pour que le
           premier ``obtenir_etat()``/``obtenir_tirage_ordre()`` du ``jeu.js``
           fraîchement chargé (déclenché par son propre ``pywebviewready``) tombe
           déjà sur la sous-API Jeu ;
        3. ``window.load_url('jeu.html')`` — même fenêtre physique, pas de
           destruction/recréation ;
        4. :meth:`ApiJeu.finaliser_entree_vue_jeu` — maximise le plateau, révèle le
           chevalet (si pas de tirage en cours) et l'amorce, en tâche de fond.

        Retourne ``{"succes": True}`` ou une charge d'erreur (le JS réactive alors
        le bouton) si aucune partie n'est prête.
        """
        # Lecture côté Python de la partie préparée par la sous-API accueil (même
        # accès direct que ``lancer_accueil`` dans le chemin historique).
        partie = self._api_accueil._partie
        id_partie = self._api_accueil._id_partie
        infos_tirage = self._api_accueil._infos_tirage
        if partie is None:
            return {
                "succes": False,
                "erreur": "Aucune partie prête à démarrer (lancer/reprendre requis).",
            }
        # 1. Charger la partie dans la sous-API Jeu (délégation à ApiJeu.charger_partie).
        self.charger_jeu(partie, id_partie, infos_tirage)
        # 2. Basculer le routage AVANT la navigation (course #178, point 3).
        self.activer_vue(VUE_JEU)
        # 3. Naviguer vers jeu.html dans la MÊME fenêtre (load_url, décision #178).
        if self._window is not None:
            self._window.load_url(str(DOSSIER_WEB / "jeu.html"))
            journal.info(
                f"Routeur : navigation Accueil→Jeu (load_url jeu.html, "
                f"partie #{id_partie})."
            )
        # 4. Rejouer la finalisation (maximisation, chevalet) à chaque entrée en
        #    vue Jeu — la coquille unifiée n'a qu'une seule boucle webview.start.
        self._api_jeu.finaliser_entree_vue_jeu()
        return {"succes": True}

    def retourner_accueil(self) -> dict[str, Any]:
        """Transition Jeu→Accueil dans la fenêtre unique via ``load_url`` (issue #181).

        Méthode de contrôle appelée depuis ``jeu.js`` (« 🏠 Retour au menu »)
        **uniquement dans la coquille unifiée** : le JS ne l'appelle que s'il la
        détecte (``typeof api.retourner_accueil === 'function'``), sinon il conserve
        le comportement de production (``api.retour_menu()`` → ``destroy()`` des
        fenêtres + réouverture d'une nouvelle boucle Accueil). Voir la note de
        détection dans ``jeu.js``.

        Contrairement au chemin de production, on ne détruit **rien** : la fenêtre
        physique unique navigue de ``jeu.html`` vers ``accueil.html`` et le chevalet
        compagnon (persistant depuis #180) est simplement masqué. Aucune session de
        journalisation n'est ouverte ou fermée ici : la coquille unifiée n'en a
        qu'une, ouverte/fermée par :func:`lancer_application_unifiee` autour de
        l'unique ``webview.start()`` (issue #179).

        Séquence, dans l'ordre exigé par le rapport #178 (course de routage) :

        1. :meth:`ApiJeu.masquer_chevalet` — le chevalet compagnon repasse masqué ;
        2. :meth:`ApiAccueil.reinitialiser_pour_retour_accueil` — l'``ApiAccueil``
           persistante est remise dans son état d'ouverture (config vierge, humain
           re-seedé, ``_partie``/``_id_partie`` purgés ; la liste « parties en
           cours » sera relue par le JS au chargement) ;
        3. :meth:`activer_vue` ``(VUE_ACCUEIL)`` — **avant** la navigation, pour que
           le premier ``obtenir_etat()`` de l'``accueil.js`` fraîchement chargé
           tombe déjà sur la sous-API Accueil ;
        4. ``window.load_url('accueil.html')`` — même fenêtre physique.
        """
        self._api_jeu.masquer_chevalet()
        self._api_accueil.reinitialiser_pour_retour_accueil()
        self.activer_vue(VUE_ACCUEIL)
        if self._window is not None:
            self._window.load_url(str(DOSSIER_WEB / "accueil.html"))
            journal.info(
                "Routeur : navigation Jeu→Accueil (load_url accueil.html)."
            )
        return {"succes": True}

    def recommencer_jeu(self) -> dict[str, Any]:
        """Recommence une partie (mêmes joueurs) dans la fenêtre unique (issue #181).

        Méthode de contrôle appelée depuis ``jeu.js`` (« Recommencer » de la modale
        de fin de partie) **uniquement dans la coquille unifiée** : le JS ne
        l'appelle que s'il la détecte (``typeof api.recommencer_jeu === 'function'``),
        sinon il conserve le comportement de production (``api.recommencer()`` →
        ``destroy()`` + récursion ``lancer_jeu``). Voir la note de détection dans
        ``jeu.js``.

        On reste dans la vue logique Jeu (pas de bascule), mais on **recharge le
        DOM** (``load_url('jeu.html')``) pour repartir d'un état JS neuf, exactement
        comme une entrée en jeu depuis l'accueil. Aucune session de journalisation
        n'est ouverte/fermée (une seule couvre toute la coquille, issue #179) ;
        aucun drapeau inter-boucles (``_recommencer`` &co.) n'est positionné — ce
        chemin ne pontant pas deux boucles séparées.

        Séquence :

        1. :meth:`ApiJeu.preparer_partie_recommencee` — crée la nouvelle partie et
           la suit en base (l'ancienne reste intacte), en récupérant ses infos de
           tirage d'ordre ;
        2. :meth:`charger_jeu` — installe la nouvelle partie dans la sous-API Jeu
           (remise à zéro complète comprise, nouveau tirage à mener) ;
        3. :meth:`activer_vue` ``(VUE_JEU)`` — déjà active, réaffirmée par symétrie
           avec :meth:`demarrer_jeu` ;
        4. ``window.load_url('jeu.html')`` — recharge le document dans la MÊME
           fenêtre ;
        5. :meth:`ApiJeu.masquer_chevalet` — chevalet remis masqué le temps du
           nouveau tirage (:meth:`ApiJeu.terminer_tirage` le révélera au
           « Continuer ») ;
        6. :meth:`ApiJeu.finaliser_entree_vue_jeu` — maximise le plateau et amorce
           le chevalet (masqué), en tâche de fond.
        """
        nouvelle, nouvel_id, infos_tirage = (
            self._api_jeu.preparer_partie_recommencee()
        )
        self.charger_jeu(nouvelle, nouvel_id, infos_tirage)
        self.activer_vue(VUE_JEU)
        if self._window is not None:
            self._window.load_url(str(DOSSIER_WEB / "jeu.html"))
            journal.info(
                f"Routeur : recommencer (load_url jeu.html, nouvelle "
                f"#{nouvel_id})."
            )
        # Nouveau tirage à mener : le chevalet compagnon repart masqué.
        self._api_jeu.masquer_chevalet()
        self._api_jeu.finaliser_entree_vue_jeu()
        return {"succes": True}

    def annuler_tirage_accueil(self) -> dict[str, Any]:
        """Annule le tirage et revient à l'accueil, fenêtre unique (issue #181).

        Méthode de contrôle appelée depuis ``jeu.js`` (bouton « Annuler » de
        l'écran de tirage d'ordre) **uniquement dans la coquille unifiée** : le JS
        ne l'appelle que s'il la détecte (``typeof api.annuler_tirage_accueil ===
        'function'``), sinon il conserve le comportement de production
        (``api.annuler_tirage()`` → ``supprimer_partie`` + ``destroy()``). Voir la
        note de détection dans ``jeu.js``.

        À ce stade la partie a été créée et suivie en base mais **aucun coup n'a
        été joué** : on la supprime (:meth:`ApiJeu.supprimer_partie_annulee`) pour
        qu'elle n'apparaisse pas comme partie fantôme dans « Reprendre une partie »,
        puis on emprunte exactement le même chemin de retour que « Retour au menu »
        (:meth:`retourner_accueil`) — chevalet masqué, accueil réinitialisé,
        navigation ``load_url``.
        """
        self._api_jeu.supprimer_partie_annulee()
        return self.retourner_accueil()


def lancer_application_unifiee(routeur: ApiRouteur | None = None) -> ApiRouteur:
    """Lance la coquille mono-fenêtre unique (issue #179) — non branchée par défaut.

    Crée **une seule** fenêtre pywebview chargeant ``accueil.html`` avec le
    :class:`ApiRouteur` comme ``js_api``, et démarre **une seule** boucle
    ``webview.start()``. La sélection du backend graphique
    (``configurer_backend_graphique``) est remontée au tout début, avant ce
    premier (et unique) ``webview.start()`` (exigence de l'issue #93, ici
    centralisée pour la fenêtre unique).

    **Aucune transition n'est encore câblée** : la fenêtre s'ouvre sur l'accueil
    et le routeur y est pointé (``activer_vue(VUE_ACCUEIL)``), mais rien ne fait
    encore basculer vers le Jeu. Cette fonction cohabite avec le chemin
    historique ``lancer_accueil``/``lancer_jeu`` sans le remplacer.

    ``routeur`` est injectable (tests / futurs appelants) ; par défaut un
    :class:`ApiRouteur` neuf est construit. Retourne le routeur utilisé.
    """
    # Import local (comme le chemin historique) pour éviter d'imposer pywebview
    # aux imports de test qui n'ouvrent aucune fenêtre.
    from scrabble.ui.backend_graphique import (
        configurer_backend_graphique,
        deployer_fenetre_maximisee,
    )
    from scrabble.ui.jeu import _creer_fenetre_chevalet

    # Bascule XWayland AVANT le premier (et unique) ``webview.start()`` du
    # processus (issue #93) : sous GNOME/Wayland, GTK ignore ``move()``/
    # positionnement en client Wayland natif. Remontée ici en tête de la coquille
    # mono-fenêtre.
    configurer_backend_graphique()

    if journal.session_courante() is None:
        journal.demarrer_session()
    try:
        if routeur is None:
            routeur = ApiRouteur()
        # Vue accueil active dès le départ : la fenêtre charge ``accueil.html``,
        # donc le premier ``obtenir_etat()`` du JS doit tomber sur ``ApiAccueil``.
        routeur.activer_vue(VUE_ACCUEIL)
        # Joueur humain présent d'office (issue #141), comme dans ``lancer_accueil``.
        routeur._api_accueil.initialiser_joueur_humain()

        chemin_html = DOSSIER_WEB / "accueil.html"
        window = webview.create_window(
            "Scrabble",
            str(chemin_html),
            js_api=routeur,
            # Fenêtre maximisée par défaut (issue #159) ; ``maximized=True`` étant
            # un no-op sous XWayland (#95), le déploiement effectif est forcé par
            # le callback ``deployer_fenetre_maximisee`` après démarrage de la
            # boucle. ``width``/``height`` = taille de restauration/repli.
            maximized=True,
            width=700,
            height=780,
            resizable=True,
            # Fond vert dès le mappage (issue #113) : évite le flash blanc.
            background_color=TAPIS_VERT,
        )
        routeur.set_window(window)

        # Chevalet compagnon (issue #180) : il reste une fenêtre physique séparée
        # (raison légitime déjà actée par #178), mais il est créé **une seule fois**
        # ici, au lancement — masqué (``hidden=True``) — au lieu d'être créé/détruit
        # à chaque partie. La logique de création est factorisée avec le chemin
        # historique (:func:`~scrabble.ui.jeu._creer_fenetre_chevalet`). Son
        # ``js_api`` est directement la sous-API Jeu : ``chevalet.js`` parle toujours
        # au jeu, jamais au routeur (aucune de ses méthodes n'est en collision).
        # Toutes les fenêtres doivent être déclarées avant l'unique ``webview.start``.
        window_chevalet = _creer_fenetre_chevalet(routeur._api_jeu, hidden=True)
        # Rattache les DEUX fenêtres à ``ApiJeu`` via ``set_windows`` (plateau =
        # fenêtre unique partagée avec l'accueil ; chevalet = compagnon masqué).
        # ``show()``/``hide()`` du chevalet se feront à l'entrée/sortie de la vue Jeu
        # (:meth:`ApiJeu.finaliser_entree_vue_jeu` / :meth:`ApiJeu.terminer_tirage`).
        routeur._api_jeu.set_windows(window, window_chevalet)
        # Fermeture croisée (issue #94) : fermer nativement l'une des deux fenêtres
        # détruit l'autre et quitte l'application (pas de fenêtre orpheline).
        routeur._api_jeu.installer_fermeture_croisee()

        journal.info(
            "Application unifiée : fenêtre unique ouverte sur l'accueil "
            "(chevalet compagnon créé masqué)."
        )
        # UNE seule boucle pywebview pour toute l'application (issue #179).
        webview.start(deployer_fenetre_maximisee, (window, "application"))
        return routeur
    finally:
        journal.cloturer_session()


def main() -> int:
    """Point d'entrée de **test manuel** de la coquille unifiée (issue #182).

    Permet à Alain de lancer **volontairement** la coquille mono-fenêtre unifiée
    en conditions réelles, **sans toucher au chemin de production par défaut** :
    ``main.py`` continue d'utiliser ``lancer_accueil``/``lancer_jeu`` tant qu'une
    décision de basculement n'a pas été prise (cf. checklist ``SMOKE_TEST.md``,
    § « Coquille unifiée »).

    Usage, depuis la racine du dépôt (``src`` devant être sur le ``PYTHONPATH``,
    exactement comme en test — cf. ``pytest.ini`` : ``pythonpath = src``) ::

        PYTHONPATH=src python -m scrabble.ui.application

    Ce point d'entrée dédié est le **seul** moyen d'activer la coquille unifiée à
    ce stade : aucune variable d'environnement ni bascule implicite n'a été posée
    dans ``main.py``, pour qu'un lancement de production ne puisse jamais tomber
    par accident sur ce chemin non encore validé visuellement.
    """
    lancer_application_unifiee()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
