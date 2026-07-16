"""Boucle de partie de Scrabble : joueurs, chevalets, tours, fin de partie.

Rôle : orchestrer une partie complète autour des briques figées de
:mod:`scrabble.moteur` (plateau, validation, score, sac) **sans les modifier**.
Ce module gère ce que le moteur ignore volontairement : les joueurs et leurs
chevalets, le déroulement circulaire des tours, l'historique des coups, et les
conditions de fin de partie avec calcul du score final.

Configuration
-------------
De 1 à 4 joueurs au total, dont au moins un humain (voir :func:`creer_partie`).
Les joueurs IA sont pilotés par le stub :mod:`scrabble.moteur.ia`, appelé
automatiquement (:meth:`Partie.jouer_tour_ia` / :meth:`Partie.jouer_tours_ia`).

Actions d'un tour
-----------------
Le joueur courant peut :

* **poser un coup** (:meth:`Partie.jouer_coup`) — validé par
  :func:`scrabble.moteur.validation.valider_coup`, scoré par
  :func:`scrabble.moteur.score.detailler_score` ;
* **passer** (:meth:`Partie.passer`) ;
* **échanger des lettres** (:meth:`Partie.echanger`) — uniquement si le sac
  contient au moins autant de jetons que de lettres échangées.

Fin de partie
-------------
La partie s'arrête lorsque **le sac est vide et qu'un joueur a vidé son
chevalet**, ou lorsque **tous les joueurs passent consécutivement** (compteur
de passes consécutives égal au nombre de joueurs).

Score final — choix documenté
------------------------------
À la fin, on **retranche à chaque joueur la valeur des lettres restantes sur
son chevalet** (règle standard). La règle officielle ajoute en plus, au joueur
qui a vidé son chevalet, le total des lettres restantes chez les adversaires ;
l'issue #22 demande explicitement de **ne pas** appliquer ce bonus à ce stade
(« pas de bonus supplémentaire »). On se limite donc à la pénalité soustractive,
qui suffit à départager et reste cohérente quel que soit le mode de fin (sac
vide ou passes consécutives).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import random

from scrabble.moteur import ia
from scrabble.moteur.ia import Niveau
from scrabble.moteur.ordre import determiner_ordre_jeu
from scrabble.moteur.plateau_partie import Coup, PlateauPartie
from scrabble.moteur.score import DetailScore, detailler_score
from scrabble.moteur.tirage import Sac
from scrabble.moteur.validation import DictionnaireMots, valider_coup
from scrabble.regles.lettres import JOKER, valeur_lettre

#: Nombre de jetons d'un chevalet plein.
TAILLE_CHEVALET = 7

#: Nombre maximal de joueurs autour d'une partie.
MAX_JOUEURS = 4

# Types d'action consignés dans l'historique.
ACTION_COUP = "coup"
ACTION_PASSE = "passe"
ACTION_ECHANGE = "echange"


class ActionInvalide(ValueError):
    """Levée quand une action de tour est impossible (message explicite).

    Couvre les rejets propres à la boucle de partie : lettres absentes du
    chevalet, sac trop pauvre pour un échange, action sur une partie terminée.
    Les illégalités de placement d'un coup restent signalées par
    :class:`scrabble.moteur.validation.CoupInvalide`.
    """


@dataclass
class Joueur:
    """Un joueur : nom, nature (humain/IA), chevalet et score cumulé.

    ``chevalet`` est une liste de jetons (chaînes d'un caractère, majuscule ou
    :data:`scrabble.regles.lettres.JOKER`), au plus :data:`TAILLE_CHEVALET`.

    Pour un joueur IA (``humain=False``), le champ ``niveau`` indique la
    stratégie de sélection de coup (:class:`~scrabble.moteur.ia.Niveau`).
    Pour un joueur humain, ``niveau`` doit rester ``None``.
    """

    nom: str
    humain: bool = True
    chevalet: list[str] = field(default_factory=list)
    score: int = 0
    niveau: Niveau | None = None

    def valeur_chevalet(self) -> int:
        """Somme des valeurs des lettres encore sur le chevalet (jokers = 0)."""
        return sum(valeur_lettre(jeton) for jeton in self.chevalet)


@dataclass
class EntreeHistorique:
    """Trace d'une action de tour, base d'un futur affichage/historique.

    Contient au minimum : le joueur (index et nom), le type d'action, le coup
    joué et son :class:`~scrabble.moteur.score.DetailScore` le cas échéant, et
    le score cumulé du joueur **après** l'action.

    Pour un échange, ``lettres_echangees`` en donne le nombre et
    ``jetons_echanges`` la liste exacte (dans l'ordre remis au sac) des jetons
    échangés : cette liste précise — pas seulement son cardinal — est ce qui
    permet de rejouer l'échange à l'identique lors d'une reprise après
    plantage (voir :mod:`scrabble.persistance.stockage`).
    """

    index_joueur: int
    nom_joueur: str
    action: str
    coup: Coup | None = None
    detail: DetailScore | None = None
    lettres_echangees: int = 0
    jetons_echanges: list[str] = field(default_factory=list)
    score_cumule: int = 0


def creer_partie(
    noms_humains: list[str],
    dictionnaire: DictionnaireMots,
    *,
    nb_ia: int = 0,
    noms_ia: list[str] | None = None,
    niveaux_ia: list[Niveau] | None = None,
    graine: int | None = None,
    tirage_ordre: bool = False,
) -> "Partie":
    """Construit une partie à partir d'une configuration humains/IA.

    ``noms_humains`` doit contenir au moins un nom (1 à 4 humains). ``nb_ia``
    ajoute des joueurs IA en complément, le total étant plafonné à
    :data:`MAX_JOUEURS`. ``noms_ia`` permet de nommer les IA (sinon « IA 1 »,
    « IA 2 »…). ``niveaux_ia`` spécifie le niveau de chaque IA (sinon
    :attr:`Niveau.INTERMEDIAIRE` par défaut).

    Ordre de jeu — deux modes :

    * ``tirage_ordre=False`` (défaut) : l'ordre de jeu est l'ordre de création
      (humains puis IA), sans aucun tirage — comportement historique inchangé.
    * ``tirage_ordre=True`` : l'ordre est décidé par un tirage alphabétique
      (:func:`scrabble.moteur.ordre.determiner_ordre_jeu`) avant la construction
      de la partie ; la liste des joueurs est réordonnée en conséquence, si bien
      que l'ordre de jeu de la :class:`Partie` (porté, comme toujours, par
      l'ordre de sa liste ``joueurs``) reflète le tirage. La distribution des 7
      lettres de chevalet a lieu ensuite, normalement, sur le sac complet.

    ``graine``, si fournie, sert **et** au tirage d'ordre **et** au sac de la
    partie (deux tirages indépendants mais tous deux reproductibles), gardant le
    déroulement complet déterministe.

    :raises ValueError: si aucun humain, si ``nb_ia`` est négatif, ou si le
        total de joueurs sort de l'intervalle 1..:data:`MAX_JOUEURS`.
    """
    if not noms_humains:
        raise ValueError("Une partie requiert au moins un joueur humain.")
    if nb_ia < 0:
        raise ValueError(f"Nombre d'IA négatif : {nb_ia}.")
    total = len(noms_humains) + nb_ia
    if total > MAX_JOUEURS:
        raise ValueError(
            f"Trop de joueurs : {total} (maximum {MAX_JOUEURS} = humains + IA)."
        )
    joueurs = [Joueur(nom=nom, humain=True) for nom in noms_humains]
    for indice in range(nb_ia):
        if noms_ia is not None and indice < len(noms_ia):
            nom = noms_ia[indice]
        else:
            nom = f"IA {indice + 1}"
        if niveaux_ia is not None and indice < len(niveaux_ia):
            niveau = niveaux_ia[indice]
        else:
            niveau = Niveau.INTERMEDIAIRE
        joueurs.append(Joueur(nom=nom, humain=False, niveau=niveau))
    if tirage_ordre:
        resultat = determiner_ordre_jeu(joueurs, random.Random(graine))
        joueurs = [joueurs[indice] for indice in resultat.ordre]
    return Partie(joueurs, dictionnaire, graine=graine)


class Partie:
    """État complet et déroulement d'une partie de Scrabble.

    Attributs publics : ``joueurs`` (1 à 4), ``plateau`` (:class:`PlateauPartie`),
    ``sac`` (:class:`Sac`), ``graine`` (la graine du sac, ``None`` si aléatoire),
    ``index_courant``, ``historique`` (liste d':class:`EntreeHistorique`),
    ``passes_consecutives``, ``terminee`` et, une fois la partie finie,
    ``gagnants`` (liste — gère les égalités).

    ``graine`` est conservée telle quelle : c'est elle, avec la suite ordonnée
    des actions, qui rend le déroulement d'une partie entièrement reproductible
    (base de la persistance, :mod:`scrabble.persistance.stockage`).
    """

    def __init__(
        self,
        joueurs: list[Joueur],
        dictionnaire: DictionnaireMots,
        *,
        graine: int | None = None,
        sac: Sac | None = None,
    ) -> None:
        if not 1 <= len(joueurs) <= MAX_JOUEURS:
            raise ValueError(
                f"Nombre de joueurs invalide : {len(joueurs)} "
                f"(attendu 1..{MAX_JOUEURS})."
            )
        self.joueurs = joueurs
        self.dictionnaire = dictionnaire
        self.graine = graine
        self.plateau = PlateauPartie()
        self.sac = sac if sac is not None else Sac(graine)
        self.index_courant = 0
        self.historique: list[EntreeHistorique] = []
        self.passes_consecutives = 0
        self.terminee = False
        self.gagnants: list[Joueur] = []
        self._distribuer_initial()

    # -- Initialisation -------------------------------------------------- #

    def _distribuer_initial(self) -> None:
        """Distribue 7 jetons à chaque joueur dans l'ordre de création."""
        for joueur in self.joueurs:
            joueur.chevalet.extend(self.sac.tirer(TAILLE_CHEVALET))

    # -- Lecture --------------------------------------------------------- #

    def joueur_courant(self) -> Joueur:
        """Renvoie le joueur dont c'est le tour."""
        return self.joueurs[self.index_courant]

    # -- Actions de tour ------------------------------------------------- #

    def jouer_coup(self, coup: Coup) -> EntreeHistorique:
        """Fait poser ``coup`` par le joueur courant et passe au suivant.

        Valide le coup (:func:`valider_coup`), vérifie que les lettres nouvelles
        proviennent bien du chevalet, applique le coup, met à jour le score et
        le chevalet (retrait des lettres posées puis complément depuis le sac),
        consigne l'action et enchaîne (fin de partie ou joueur suivant).

        :raises CoupInvalide: si le placement est illégal.
        :raises ActionInvalide: si la partie est terminée ou si les lettres du
            coup ne sont pas toutes présentes sur le chevalet.
        """
        self._assurer_en_cours()
        joueur = self.joueur_courant()
        valider_coup(self.plateau, coup, self.dictionnaire)
        requis = self._jetons_du_coup(coup)
        if not _multiset_inclus(requis, joueur.chevalet):
            raise ActionInvalide(
                "Les lettres nouvelles du coup ne sont pas toutes présentes sur "
                f"le chevalet de {joueur.nom!r}."
            )
        nouvelles = self.plateau.poser_coup(coup)
        detail = detailler_score(self.plateau, nouvelles, coup.direction)
        joueur.score += detail.total
        _retirer_jetons(joueur.chevalet, requis)
        self._completer_chevalet(joueur)
        self.passes_consecutives = 0
        entree = self._enregistrer(joueur, ACTION_COUP, coup=coup, detail=detail)
        if self.sac.est_vide() and not joueur.chevalet:
            self._terminer()
        else:
            self._avancer()
        return entree

    def passer(self) -> EntreeHistorique:
        """Fait passer le joueur courant ; termine si tous passent d'affilée."""
        self._assurer_en_cours()
        joueur = self.joueur_courant()
        self.passes_consecutives += 1
        entree = self._enregistrer(joueur, ACTION_PASSE)
        if self.passes_consecutives >= len(self.joueurs):
            self._terminer()
        else:
            self._avancer()
        return entree

    def echanger(self, jetons: list[str]) -> EntreeHistorique:
        """Échange ``jetons`` du chevalet courant contre de nouveaux du sac.

        L'échange n'est possible que si le sac contient au moins autant de
        jetons que demandé. Les nouveaux jetons sont tirés **avant** de remettre
        les anciens dans le sac (on ne repioche pas ses propres lettres). Un
        échange n'est pas une passe : il remet à zéro le compteur de passes
        consécutives.

        :raises ActionInvalide: partie terminée, liste vide, lettres absentes du
            chevalet, ou sac trop pauvre.
        """
        self._assurer_en_cours()
        joueur = self.joueur_courant()
        if not jetons:
            raise ActionInvalide("Aucune lettre à échanger.")
        if not _multiset_inclus(jetons, joueur.chevalet):
            raise ActionInvalide(
                "Les lettres à échanger ne sont pas toutes sur le chevalet de "
                f"{joueur.nom!r}."
            )
        if self.sac.jetons_restants() < len(jetons):
            raise ActionInvalide(
                f"Le sac ne contient pas assez de jetons pour échanger "
                f"{len(jetons)} lettre(s) ({self.sac.jetons_restants()} restant(s))."
            )
        nouveaux = self.sac.tirer(len(jetons))
        _retirer_jetons(joueur.chevalet, jetons)
        self.sac.remettre(jetons)
        joueur.chevalet.extend(nouveaux)
        self.passes_consecutives = 0
        entree = self._enregistrer(
            joueur,
            ACTION_ECHANGE,
            lettres_echangees=len(jetons),
            jetons_echanges=list(jetons),
        )
        self._avancer()
        return entree

    # -- Tours automatiques (IA) ---------------------------------------- #

    def jouer_tour_ia(self) -> EntreeHistorique:
        """Joue le tour du joueur courant s'il est une IA.

        L'IA choisit un coup via :func:`scrabble.moteur.ia.choisir_coup` selon
        son niveau de difficulté, ou passe si aucun coup n'est jouable.

        :raises ActionInvalide: si le joueur courant est humain, n'a pas de
            niveau défini, ou la partie est finie.
        """
        self._assurer_en_cours()
        joueur = self.joueur_courant()
        if joueur.humain:
            raise ActionInvalide(
                f"Le joueur courant {joueur.nom!r} est humain, pas une IA."
            )
        if joueur.niveau is None:
            raise ActionInvalide(
                f"Le joueur IA {joueur.nom!r} n'a pas de niveau défini."
            )
        coup = ia.choisir_coup(
            self.plateau, joueur.chevalet, self.dictionnaire, joueur.niveau
        )
        if coup is None:
            return self.passer()
        return self.jouer_coup(coup)

    def jouer_tours_ia(self) -> list[EntreeHistorique]:
        """Enchaîne automatiquement les tours des IA jusqu'à un humain ou la fin.

        Renvoie la liste des actions jouées (vide si le joueur courant est déjà
        humain ou la partie terminée).
        """
        entrees: list[EntreeHistorique] = []
        while not self.terminee and not self.joueur_courant().humain:
            entrees.append(self.jouer_tour_ia())
        return entrees

    # -- Rouages internes ------------------------------------------------ #

    def _assurer_en_cours(self) -> None:
        if self.terminee:
            raise ActionInvalide("La partie est terminée : plus aucune action.")

    def _jetons_du_coup(self, coup: Coup) -> list[str]:
        """Jetons que le chevalet doit fournir : un par case **nouvelle**.

        Les cases déjà occupées (tuiles traversées) ne consomment rien. Une case
        nouvelle portant un joker consomme un jeton :data:`JOKER`.
        """
        requis: list[str] = []
        for ligne, colonne, tuile in coup.cases():
            if self.plateau.case_vide(ligne, colonne):
                requis.append(JOKER if tuile.joker else tuile.lettre)
        return requis

    def _completer_chevalet(self, joueur: Joueur) -> None:
        """Complète le chevalet jusqu'à 7 (ou moins si le sac s'épuise)."""
        manque = TAILLE_CHEVALET - len(joueur.chevalet)
        if manque > 0:
            joueur.chevalet.extend(self.sac.tirer(manque))

    def _enregistrer(
        self,
        joueur: Joueur,
        action: str,
        *,
        coup: Coup | None = None,
        detail: DetailScore | None = None,
        lettres_echangees: int = 0,
        jetons_echanges: list[str] | None = None,
    ) -> EntreeHistorique:
        entree = EntreeHistorique(
            index_joueur=self.index_courant,
            nom_joueur=joueur.nom,
            action=action,
            coup=coup,
            detail=detail,
            lettres_echangees=lettres_echangees,
            jetons_echanges=list(jetons_echanges) if jetons_echanges else [],
            score_cumule=joueur.score,
        )
        self.historique.append(entree)
        return entree

    def _avancer(self) -> None:
        """Passe la main au joueur suivant (ordre circulaire)."""
        self.index_courant = (self.index_courant + 1) % len(self.joueurs)

    def _terminer(self) -> None:
        """Clôt la partie : pénalité des lettres restantes puis gagnant(s)."""
        self.terminee = True
        for joueur in self.joueurs:
            joueur.score -= joueur.valeur_chevalet()
        meilleur = max(joueur.score for joueur in self.joueurs)
        self.gagnants = [j for j in self.joueurs if j.score == meilleur]


# --------------------------------------------------------------------------- #
# Utilitaires de gestion des jetons du chevalet (multiensembles)
# --------------------------------------------------------------------------- #

def _multiset_inclus(sous_ensemble: list[str], ensemble: list[str]) -> bool:
    """Vrai si ``sous_ensemble`` est inclus dans ``ensemble`` (multiplicités)."""
    disponible = Counter(ensemble)
    for jeton, nombre in Counter(sous_ensemble).items():
        if disponible[jeton] < nombre:
            return False
    return True


def _retirer_jetons(chevalet: list[str], jetons: list[str]) -> None:
    """Retire du chevalet chacun des ``jetons`` (suppose leur présence)."""
    for jeton in jetons:
        chevalet.remove(jeton)
