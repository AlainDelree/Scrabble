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
l'issue #22 avait choisi de **ne pas** appliquer ce bonus par défaut. Ce bonus
est désormais **configurable** (issue #134) via le paramètre ``bonus_fin_partie``
de la partie (câblé depuis ``config.py`` par l'appelant UI, sans dépendance du
moteur à la config) : désactivé par défaut, il préserve le comportement
historique. Quand il est activé **et** que la partie se termine parce qu'un
joueur a vidé son chevalet (motif :data:`MOTIF_CHEVALET_VIDE`), le finisseur
reçoit la somme des ``valeur_chevalet()`` des autres joueurs avant l'application
des pénalités. Une fin par blocage (:data:`MOTIF_BLOCAGE`, toutes les passes
consécutives) n'attribue jamais ce bonus, même réglage activé.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import random

# Alias distinct du paramètre local ``journal`` de :meth:`Partie.jouer_tour_ia`
# (un ``JournalDecisionIA`` par tour, sans rapport) : utiliser le nom ``journal``
# tel quel masquerait le module pour le reste de la fonction.
from scrabble import journal as journal_app
from scrabble.moteur import ia, personnages
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

# Motifs de fin de partie transmis à :meth:`Partie._terminer` par l'appelant :
# chevalet du joueur courant vidé (sac vide) vs blocage (passes consécutives).
# Seul le premier motif ouvre droit au bonus officiel du finisseur (issue #134).
MOTIF_CHEVALET_VIDE = "chevalet_vide"
MOTIF_BLOCAGE = "blocage"


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

    ``personnage`` (issue #438, lot A ; sélectionnable depuis l'issue #440,
    lot D) est une chaîne vide par défaut. Une fois renseigné, il porte
    toujours l'identité **réelle** (une clé de
    :data:`scrabble.moteur.personnages.PERSONNAGES`, p. ex. ``"opportuniste"``)
    — jamais le libellé « Aléatoire » de l'écran d'accueil, y compris quand
    c'est un tirage au hasard qui l'a choisi (voir ``personnage_aleatoire``
    ci-dessous) : une reprise de partie ne doit jamais changer de style de
    jeu.

    ``personnage_aleatoire`` (issue #440, lot D) indique si ``personnage`` a
    été obtenu par un tirage « Aléatoire » plutôt que choisi explicitement à
    l'accueil. Ne change rien au déroulement de la partie — seulement à
    l'affichage : c'est ce drapeau qui déclenche la révélation d'identité de
    l'écran de résultat (:func:`scrabble.ui.jeu.revelations_personnages`),
    jamais affichée pour un personnage choisi explicitement.
    """

    nom: str
    humain: bool = True
    chevalet: list[str] = field(default_factory=list)
    score: int = 0
    niveau: Niveau | None = None
    personnage: str = ""
    personnage_aleatoire: bool = False

    def valeur_chevalet(self) -> int:
        """Somme des valeurs des lettres encore sur le chevalet (jokers = 0)."""
        return sum(valeur_lettre(jeton) for jeton in self.chevalet)


@dataclass(frozen=True)
class JournalDecisionIA:
    """Journal de décision d'une action d'ordinateur, pour relecture a posteriori (issue #445).

    Capturé uniquement pour juger après coup le style d'un joueur IA (voir
    ``scripts/`` pour le script de relecture) : **jamais** affiché en jeu, ni
    transmis à l'interface (``ui.jeu.etat_public``,
    ``ui.jeu.serialiser_entree_historique`` n'y touchent pas — voir leurs
    tests de confidentialité). N'influence en rien la sélection du coup : il
    est construit en appelant :func:`~scrabble.moteur.ia.evaluer_coups` *en
    plus* de :func:`~scrabble.moteur.ia.choisir_coup`, jamais à sa place.

    ``chevalet_avant`` est le chevalet du joueur juste avant l'action (jokers
    représentés par :data:`scrabble.regles.lettres.JOKER`, comme partout
    ailleurs dans le moteur — donc déjà « reconnaissables »).

    ``meilleurs`` donne les (au plus 5) meilleurs coups selon le score
    stratégique ; ``coup_choisi`` est la fiche du coup réellement joué (même
    s'il ne fait pas partie de ``meilleurs``) ; ``rang_choisi`` son rang parmi
    ``nb_coups_possibles`` coups possibles (1 = meilleur). Pour une passe ou
    un échange, ``coup_choisi`` et ``rang_choisi`` restent ``None`` ;
    ``meilleurs``/``nb_coups_possibles`` reflètent les coups qui, malgré tout,
    étaient disponibles (vides si aucun).
    """

    chevalet_avant: tuple[str, ...]
    nb_coups_possibles: int
    meilleurs: tuple[ia.AlternativeCoup, ...]
    rang_choisi: int | None
    coup_choisi: ia.AlternativeCoup | None


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

    Pour un coup, ``positions_posees`` liste les cases ``(ligne, colonne)``
    **nouvellement** remplies par ce coup (les tuiles déjà présentes traversées
    par le mot en sont exclues) : c'est ce que renvoie
    :meth:`~scrabble.moteur.plateau_partie.PlateauPartie.poser_coup`, réutilisé
    tel quel sans recalcul. L'UI s'en sert pour mettre brièvement en évidence le
    dernier coup d'un ordinateur sur le plateau (issue #58). Vide pour une passe
    ou un échange.

    Toujours pour un coup, ``lettres_piochees`` donne la liste exacte des
    jetons tirés du sac pour recompléter le chevalet à 7 après la pose (issue
    #357) : contrairement à un calcul par diff de chevalet avant/après, cette
    liste reste correcte même quand une lettre piochée a la même valeur qu'une
    lettre posée. Vide pour une passe ou un échange, et si le sac était déjà
    vide.
    """

    index_joueur: int
    nom_joueur: str
    action: str
    coup: Coup | None = None
    detail: DetailScore | None = None
    lettres_echangees: int = 0
    jetons_echanges: list[str] = field(default_factory=list)
    positions_posees: list[tuple[int, int]] = field(default_factory=list)
    lettres_piochees: list[str] = field(default_factory=list)
    score_cumule: int = 0
    journal_ia: JournalDecisionIA | None = None


def creer_partie(
    noms_humains: list[str],
    dictionnaire: DictionnaireMots,
    *,
    nb_ia: int = 0,
    noms_ia: list[str] | None = None,
    niveaux_ia: list[Niveau] | None = None,
    personnages_ia: list[str] | None = None,
    generateur_aleatoire: random.Random | None = None,
    graine: int | None = None,
    tirage_ordre: bool = False,
    bonus_fin_partie: bool = False,
    dictionnaires_ia: dict[Niveau, DictionnaireMots] | None = None,
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

    ``bonus_fin_partie`` (défaut ``False``) active le bonus officiel au finisseur
    (issue #134) ; l'appelant UI le renseigne depuis ``config.py``.

    ``dictionnaires_ia`` (défaut ``None``) associe à chaque :class:`Niveau`
    présent le Trie consulté par l'IA pour **générer** ses coups (issue #206,
    étendu par l'issue #369 lot C à un Trie propre par niveau — vocabulaire par
    palier de fréquence). Un niveau absent du mapping (ou ``dictionnaires_ia``
    entièrement ``None``) retombe sur ``dictionnaire`` complet (comportement
    historique, zéro coût). La validation d'un coup (humain **comme** IA) reste
    toujours sur ``dictionnaire`` complet — voir :class:`Partie`.

    ``personnages_ia`` (issue #440, lot D) donne, par IA, la clé de
    :data:`scrabble.moteur.personnages.PERSONNAGES` choisie à l'accueil, ou
    :data:`scrabble.moteur.personnages.CLE_ALEATOIRE` pour un tirage caché.
    ``None`` (défaut, IA sans entrée) laisse :attr:`Joueur.personnage` à sa
    chaîne vide historique — comportement inchangé pour tout appelant qui ne
    renseigne pas ce paramètre. Pour une entrée ``CLE_ALEATOIRE``, un
    personnage réel est tiré **une seule fois**, ici, uniquement parmi les
    personnages du registre disponibles au niveau de CETTE IA (issue #447,
    lot G, :func:`scrabble.moteur.personnages.personnages_disponibles_a_niveau`)
    ET à la taille de CETTE table (issue #449, lot I,
    :func:`scrabble.moteur.personnages.personnages_disponibles_a_nb_joueurs`,
    ``total`` = nombre d'humains + nombre d'IA), Classique compris quand il y
    figure, via :func:`scrabble.moteur.personnages.tirer_personnage` ;
    l'identité réelle tirée est celle enregistrée dans
    :attr:`Joueur.personnage` — jamais le libellé « Aléatoire » — avec
    :attr:`Joueur.personnage_aleatoire` à ``True`` pour que l'UI sache la
    révéler en fin de partie. Cette fonction moteur ne vérifie elle-même
    aucune disponibilité (ni de personnage, ni de niveau, ni de taille de
    table) : le contrôle a lieu en amont, côté UI
    (:meth:`~scrabble.ui.accueil.ApiAccueil.ajouter_ordinateur`,
    :meth:`~scrabble.ui.accueil.ApiAccueil.lancer_partie`) — ``creer_partie``
    reste utilisable avec n'importe quelle combinaison, y compris pour le
    script de mesure de force (``scripts/mesurer_force_niveaux.py``).
    ``generateur_aleatoire`` rend ce tirage déterministe en test ; à défaut
    (``None``), il retombe sur le module :mod:`random` global.

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
        personnage = ""
        personnage_aleatoire = False
        if personnages_ia is not None and indice < len(personnages_ia):
            cle = personnages_ia[indice]
            if cle == personnages.CLE_ALEATOIRE:
                personnage = personnages.tirer_personnage(
                    generateur_aleatoire, niveau, total
                ).cle
                personnage_aleatoire = True
            else:
                personnage = cle
        joueurs.append(
            Joueur(
                nom=nom,
                humain=False,
                niveau=niveau,
                personnage=personnage,
                personnage_aleatoire=personnage_aleatoire,
            )
        )
    if tirage_ordre:
        resultat = determiner_ordre_jeu(joueurs, random.Random(graine))
        joueurs = [joueurs[indice] for indice in resultat.ordre]
    return Partie(
        joueurs,
        dictionnaire,
        graine=graine,
        bonus_fin_partie=bonus_fin_partie,
        dictionnaires_ia=dictionnaires_ia,
    )


def recreer_partie_meme_joueurs(
    partie: "Partie",
    dictionnaire: DictionnaireMots,
    *,
    graine: int | None = None,
    tirage_ordre: bool = True,
) -> "Partie":
    """Crée une **nouvelle** partie avec les mêmes joueurs qu'une partie donnée.

    Reprend la liste des joueurs de ``partie`` — leurs **noms**, leur nature
    (**humain/ordinateur**) et, pour les IA, leur **niveau** de difficulté — et
    reconstruit une partie neuve via :func:`creer_partie`, sans rejouer l'écran
    de configuration. Le réglage ``bonus_fin_partie`` de la partie d'origine est
    conservé, ainsi que son **vocabulaire d'IA** par niveau (issues #206, #369
    lot C) : le mapping ``dictionnaires_ia`` de la partie d'origine est repris
    tel quel (mêmes niveaux d'IA, donc mêmes clés utiles) ; s'il est vide (IA
    sur le dictionnaire complet), la nouvelle partie reste sur son
    ``dictionnaire``.

    C'est le pivot de l'action « Recommencer » de la modale de fin de partie
    (issue #142) : la partie terminée n'est pas modifiée (elle reste dans
    l'historique) ; on en repart avec un **nouveau tirage**. Comme aucun état de
    plateau, de sac, de score ni d'historique n'est copié, tout est neuf :

    * ``graine`` (défaut ``None`` → graine aléatoire du sac) rend le tirage des
      lettres et l'ordre différents à chaque appel ;
    * ``tirage_ordre`` (défaut ``True``) rejoue le tirage d'ordre : l'ordre de
      jeu peut donc différer de celui de la partie d'origine.

    Les joueurs sont regroupés humains puis IA (contrat de :func:`creer_partie`)
    avant l'éventuel tirage d'ordre, qui les réordonne ensuite.

    Le **personnage** de chaque IA (issue #440, lot D) est lui aussi repropagé
    tel quel, au même titre que le niveau : ``Joueur.personnage`` porte déjà
    l'identité réelle (jamais le libellé « Aléatoire », voir
    :func:`creer_partie`), donc aucun nouveau tirage n'a lieu ici même pour un
    personnage obtenu par tirage au hasard dans la partie d'origine — un
    « Recommencer » garde le même style de jeu, nouvelle partie ou pas.
    """
    noms_humains = [j.nom for j in partie.joueurs if j.humain]
    noms_ia = [j.nom for j in partie.joueurs if not j.humain]
    niveaux_ia = [j.niveau for j in partie.joueurs if not j.humain]
    personnages_ia = [j.personnage for j in partie.joueurs if not j.humain]
    # Vocabulaire IA par niveau (issues #206, #369 lot C) : repropagé tel quel.
    # Un mapping vide (IA sur le dictionnaire complet) reste vide côté nouvelle
    # partie — pas besoin de le distinguer explicitement de ``None``, les deux
    # produisent le même comportement de repli dans ``Partie.__init__``.
    return creer_partie(
        noms_humains=noms_humains,
        dictionnaire=dictionnaire,
        nb_ia=len(noms_ia),
        noms_ia=noms_ia,
        niveaux_ia=niveaux_ia,
        personnages_ia=personnages_ia,
        graine=graine,
        tirage_ordre=tirage_ordre,
        bonus_fin_partie=partie.bonus_fin_partie,
        dictionnaires_ia=partie.dictionnaires_ia,
    )


class Partie:
    """État complet et déroulement d'une partie de Scrabble.

    Attributs publics : ``joueurs`` (1 à 4), ``plateau`` (:class:`PlateauPartie`),
    ``sac`` (:class:`Sac`), ``graine`` (la graine du sac, ``None`` si aléatoire),
    ``index_courant``, ``historique`` (liste d':class:`EntreeHistorique`),
    ``passes_consecutives``, ``terminee``, ``bonus_fin_partie`` (réglage du bonus
    officiel au finisseur, issue #134) et, une fois la partie finie, ``gagnants``
    (liste — gère les égalités).

    ``graine`` est conservée telle quelle : c'est elle, avec la suite ordonnée
    des actions, qui rend le déroulement d'une partie entièrement reproductible
    (base de la persistance, :mod:`scrabble.persistance.stockage`).

    Validation vs génération : un Trie par niveau d'IA (issues #206, #369 lot C)
    ----------------------------------------------------------------------------
    ``dictionnaire`` (complet) sert **toujours** à la validation d'un coup
    (:func:`valider_coup`), qu'il soit joué par un humain ou par une IA : le
    joueur humain n'est jamais restreint, et un coup généré par une IA reste
    soumis à cette même validation. ``dictionnaires_ia`` sert seulement à la
    **génération** des coups de l'IA (:func:`scrabble.moteur.ia.choisir_coup`) :
    c'est un mapping ``{Niveau: Trie}`` — plus un Trie unique partagé par toutes
    les IA de la table (verrou structurel identifié par le rapport de lecture
    #366, corrigé par le lot C) — puisque deux IA de niveaux différents peuvent
    désormais jouer sur deux vocabulaires distincts (un palier de fréquence par
    niveau, voir ``scrabble.moteur.ia.resoudre_palier``). Un niveau **absent**
    du mapping (dont ``dictionnaires_ia`` vide ou ``None``, tout comme
    :data:`~scrabble.moteur.ia.Niveau.EXPERT` et
    :data:`~scrabble.moteur.ia.Niveau.CHAMPION_DU_MONDE` construits sans
    entrée — refonte de l'échelle, issue #401) retombe sur ``dictionnaire``
    complet — comportement historique inchangé et défensif, conservé même si
    l'appelant UI construit désormais toujours le mapping par palier sans
    condition (issue #370, lot E : suppression du réglage global « vocabulaire
    humain », issue #206).
    """

    def __init__(
        self,
        joueurs: list[Joueur],
        dictionnaire: DictionnaireMots,
        *,
        graine: int | None = None,
        sac: Sac | None = None,
        bonus_fin_partie: bool = False,
        dictionnaires_ia: dict[Niveau, DictionnaireMots] | None = None,
    ) -> None:
        if not 1 <= len(joueurs) <= MAX_JOUEURS:
            raise ValueError(
                f"Nombre de joueurs invalide : {len(joueurs)} "
                f"(attendu 1..{MAX_JOUEURS})."
            )
        self.joueurs = joueurs
        self.dictionnaire = dictionnaire
        # Tries de génération des coups de l'IA, par niveau (issues #206, #369
        # lot C). Copié défensivement pour ne jamais partager de mutation avec
        # l'appelant. Un niveau absent (mapping vide par défaut) retombe sur
        # ``dictionnaire`` complet dans ``jouer_tour_ia`` — aucun filtre, coût
        # nul, comportement historique inchangé.
        self.dictionnaires_ia: dict[Niveau, DictionnaireMots] = (
            dict(dictionnaires_ia) if dictionnaires_ia else {}
        )
        self.graine = graine
        # Réglage câblé par l'appelant (issue #134) : bonus officiel au finisseur
        # sur fin par chevalet vidé. Le moteur n'importe pas ``config.py``.
        self.bonus_fin_partie = bonus_fin_partie
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

    def jouer_coup(
        self, coup: Coup, *, journal_ia: JournalDecisionIA | None = None
    ) -> EntreeHistorique:
        """Fait poser ``coup`` par le joueur courant et passe au suivant.

        Valide le coup (:func:`valider_coup`), vérifie que les lettres nouvelles
        proviennent bien du chevalet, applique le coup, met à jour le score et
        le chevalet (retrait des lettres posées puis complément depuis le sac),
        consigne l'action et enchaîne (fin de partie ou joueur suivant).

        ``journal_ia`` (issue #445) n'est renseigné que par
        :meth:`jouer_tour_ia` ; un appelant humain (UI) ne le transmet jamais,
        ``None`` par défaut reproduisant exactement le comportement d'avant
        son introduction.

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
        piochees = self._completer_chevalet(joueur)
        self.passes_consecutives = 0
        entree = self._enregistrer(
            joueur,
            ACTION_COUP,
            coup=coup,
            detail=detail,
            positions_posees=nouvelles,
            lettres_piochees=piochees,
            journal_ia=journal_ia,
        )
        if self.sac.est_vide() and not joueur.chevalet:
            self._terminer(MOTIF_CHEVALET_VIDE)
        else:
            self._avancer()
        return entree

    def passer(
        self, *, journal_ia: JournalDecisionIA | None = None
    ) -> EntreeHistorique:
        """Fait passer le joueur courant ; termine si tous passent d'affilée.

        ``journal_ia`` : voir :meth:`jouer_coup`.
        """
        self._assurer_en_cours()
        joueur = self.joueur_courant()
        self.passes_consecutives += 1
        entree = self._enregistrer(joueur, ACTION_PASSE, journal_ia=journal_ia)
        if self.passes_consecutives >= len(self.joueurs):
            self._terminer(MOTIF_BLOCAGE)
        else:
            self._avancer()
        return entree

    def echanger(
        self, jetons: list[str], *, journal_ia: JournalDecisionIA | None = None
    ) -> EntreeHistorique:
        """Échange ``jetons`` du chevalet courant contre de nouveaux du sac.

        L'échange n'est possible que si le sac contient au moins autant de
        jetons que demandé. Les nouveaux jetons sont tirés **avant** de remettre
        les anciens dans le sac (on ne repioche pas ses propres lettres). Un
        échange n'est pas une passe : il remet à zéro le compteur de passes
        consécutives.

        ``journal_ia`` : voir :meth:`jouer_coup`.

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
            journal_ia=journal_ia,
        )
        self._avancer()
        return entree

    # -- Tours automatiques (IA) ---------------------------------------- #

    def jouer_tour_ia(
        self, profil: ia.ProfilPersonnage | None = None
    ) -> EntreeHistorique:
        """Joue le tour du joueur courant s'il est une IA.

        L'IA choisit un coup via :func:`scrabble.moteur.ia.choisir_coup` selon
        son niveau de difficulté, ou passe si aucun coup n'est jouable. Le Trie
        transmis à :func:`~scrabble.moteur.ia.choisir_coup` est celui du
        **niveau du joueur courant** (:attr:`dictionnaires_ia`), pas un Trie
        global partagé par toutes les IA de la table (issue #369, lot C) — un
        niveau absent du mapping retombe sur ``dictionnaire`` complet.

        ``profil`` (issue #438, lot A) est transmis à
        :func:`~scrabble.moteur.ia.choisir_coup`, en plus du niveau — jamais à
        sa place. ``None`` (défaut) n'est pas transmis du tout (plutôt que
        transmis explicitement comme ``None``), pour que l'appel reproduise
        exactement le comportement d'avant son introduction, y compris vis-à-
        vis des tests qui substituent :func:`~scrabble.moteur.ia.choisir_coup`
        par un faux sans paramètre ``profil``. Aucun appelant actuel ne
        renseigne ce paramètre encore (pas de personnage sélectionnable, voir
        :attr:`Joueur.personnage`).

        Journal de décision (issue #445) : le chevalet du joueur juste avant
        l'action et les meilleurs coups qu'il avait sont capturés via
        :func:`~scrabble.moteur.ia.evaluer_coups`, appelé **après**
        :func:`~scrabble.moteur.ia.choisir_coup` (jamais à sa place) — sans
        incidence sur le coup choisi ni sur la consommation du générateur
        aléatoire, puisque c'est une fonction pure, sans aléa, qui ne fait que
        retrier les mêmes coups générés. Transmis à :meth:`jouer_coup` /
        :meth:`passer` pour être consigné dans l'historique.

        Vocabulaire long (issue #450, lot H bis) : quand ``profil`` a
        ``vocabulaire_long`` actif, ``self.dictionnaire`` (déjà, pour toute
        partie, le Trie complet qui valide chaque coup posé) est transmis en
        plus à :func:`~scrabble.moteur.ia.choisir_coup` et
        :func:`~scrabble.moteur.ia.evaluer_coups` comme lexique complet —
        aucun chargement supplémentaire, rien transmis pour les profils qui ne
        le demandent pas. Même transmission (issue #452, lot J) quand
        ``profil.mots_favoris`` est renseigné (personnages Titeuf et Lettré,
        issue #454, lot K) : les deux champs déclenchent indépendamment le
        même envoi de ``self.dictionnaire``.

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
        dictionnaire_ia = self.dictionnaires_ia.get(joueur.niveau, self.dictionnaire)
        # Lexique complet pour le style « vocabulaire long » (issue #450, lot H
        # bis) : ``self.dictionnaire`` est déjà, pour TOUTE partie, le Trie
        # complet qui valide chaque coup posé (voir la docstring de
        # :class:`Partie`) — rien à charger de plus. On ne le transmet à l'IA
        # que si ``profil.vocabulaire_long`` est actif, pour que les parties
        # sans Chasseur de scrabbles (ou tout profil qui ne le demande pas)
        # n'en subissent aucun coût supplémentaire.
        dictionnaire_complet = (
            self.dictionnaire
            if profil is not None and (profil.vocabulaire_long or profil.mots_favoris)
            else None
        )
        chevalet_avant = tuple(joueur.chevalet)
        # ``dictionnaire_complet`` n'est transmis explicitement que lorsqu'il
        # est réellement nécessaire (profil non None ET vocabulaire_long
        # actif) : certains tests substituent ``choisir_coup``/``evaluer_coups``
        # par un faux dont la signature ne connaît pas encore ce paramètre
        # (p. ex. ``test_jouer_tour_ia_avec_profil_le_transmet_a_choisir_coup``)
        # — passer ``dictionnaire_complet=None`` sans condition leur serait
        # un argument inattendu.
        if profil is None:
            coup = ia.choisir_coup(
                self.plateau, joueur.chevalet, dictionnaire_ia, joueur.niveau
            )
        elif dictionnaire_complet is None:
            coup = ia.choisir_coup(
                self.plateau,
                joueur.chevalet,
                dictionnaire_ia,
                joueur.niveau,
                profil=profil,
            )
        else:
            coup = ia.choisir_coup(
                self.plateau,
                joueur.chevalet,
                dictionnaire_ia,
                joueur.niveau,
                profil=profil,
                dictionnaire_complet=dictionnaire_complet,
            )
        # ``evaluer_coups`` exige un Trie complet (attribut ``racine`` du
        # protocole ``TrieProtocol``, voir ``generateur.py``) : certains tests
        # substituent au dictionnaire un double minimal n'exposant que
        # ``contient`` (p. ex. ``tests._aides_test_jeu._DicoFactice``), prévu
        # pour fonctionner tant que ``choisir_coup`` lui-même reste
        # monkeypatché et n'appelle jamais ``generer_coups``. Le journal est
        # alors simplement absent plutôt qu'en erreur.
        if hasattr(dictionnaire_ia, "racine"):
            if dictionnaire_complet is None:
                evaluation = ia.evaluer_coups(
                    self.plateau,
                    list(chevalet_avant),
                    dictionnaire_ia,
                    joueur.niveau,
                    profil=profil,
                    coup_choisi=coup,
                )
            else:
                evaluation = ia.evaluer_coups(
                    self.plateau,
                    list(chevalet_avant),
                    dictionnaire_ia,
                    joueur.niveau,
                    profil=profil,
                    coup_choisi=coup,
                    dictionnaire_complet=dictionnaire_complet,
                )
        else:
            evaluation = ia.EvaluationCoupsIA()
        journal = JournalDecisionIA(
            chevalet_avant=chevalet_avant,
            nb_coups_possibles=evaluation.nb_coups_possibles,
            meilleurs=evaluation.meilleurs,
            rang_choisi=evaluation.rang_choisi,
            coup_choisi=evaluation.coup_choisi,
        )
        if coup is None:
            # Défense en profondeur (issue #463) : si le Trie transmis à l'IA
            # est vide (vocabulaire de niveau vide/absent, échappé aux
            # contrôles de l'accueil — p. ex. partie reprise dont le niveau
            # est devenu indisponible depuis), consigner l'anomalie plutôt que
            # de laisser l'ordinateur passer tous ses tours sans aucune trace.
            # ``taille`` (plutôt que ``len()``) reste silencieux pour les
            # faux dictionnaires de test qui n'exposent que ``contient``.
            if getattr(dictionnaire_ia, "taille", None) == 0:
                journal_app.erreur(
                    f"Partie : {joueur.nom!r} (niveau {joueur.niveau.name}) "
                    "passe son tour avec un vocabulaire IA vide — anomalie, "
                    "prévenir Alain."
                )
            return self.passer(journal_ia=journal)
        return self.jouer_coup(coup, journal_ia=journal)

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

    def _completer_chevalet(self, joueur: Joueur) -> list[str]:
        """Complète le chevalet jusqu'à 7 (ou moins si le sac s'épuise).

        Renvoie la liste des jetons effectivement tirés du sac (issue #357),
        pour que l'appelant puisse la faire remonter sans recalcul par diff.
        """
        manque = TAILLE_CHEVALET - len(joueur.chevalet)
        if manque <= 0:
            return []
        piochees = self.sac.tirer(manque)
        joueur.chevalet.extend(piochees)
        return piochees

    def _enregistrer(
        self,
        joueur: Joueur,
        action: str,
        *,
        coup: Coup | None = None,
        detail: DetailScore | None = None,
        lettres_echangees: int = 0,
        jetons_echanges: list[str] | None = None,
        positions_posees: list[tuple[int, int]] | None = None,
        lettres_piochees: list[str] | None = None,
        journal_ia: JournalDecisionIA | None = None,
    ) -> EntreeHistorique:
        entree = EntreeHistorique(
            index_joueur=self.index_courant,
            nom_joueur=joueur.nom,
            action=action,
            coup=coup,
            detail=detail,
            lettres_echangees=lettres_echangees,
            jetons_echanges=list(jetons_echanges) if jetons_echanges else [],
            positions_posees=list(positions_posees) if positions_posees else [],
            lettres_piochees=list(lettres_piochees) if lettres_piochees else [],
            score_cumule=joueur.score,
            journal_ia=journal_ia,
        )
        self.historique.append(entree)
        return entree

    def _avancer(self) -> None:
        """Passe la main au joueur suivant (ordre circulaire)."""
        self.index_courant = (self.index_courant + 1) % len(self.joueurs)

    def _terminer(self, motif: str) -> None:
        """Clôt la partie : bonus éventuel, pénalité des restes puis gagnant(s).

        ``motif`` distingue la fin par chevalet vidé (:data:`MOTIF_CHEVALET_VIDE`)
        de la fin par blocage (:data:`MOTIF_BLOCAGE`). Si le réglage
        ``bonus_fin_partie`` est activé **et** que la fin est due à un chevalet
        vidé, le finisseur (le joueur courant, qui vient de poser son dernier
        jeton — l'index n'a pas encore avancé) reçoit la somme des lettres
        restant chez les autres joueurs, en plus de la pénalité qui leur est
        appliquée juste après. Sinon (blocage, ou réglage désactivé), seule la
        pénalité soustractive historique s'applique.
        """
        self.terminee = True
        if motif == MOTIF_CHEVALET_VIDE and self.bonus_fin_partie:
            finisseur = self.joueur_courant()
            bonus = sum(
                joueur.valeur_chevalet()
                for joueur in self.joueurs
                if joueur is not finisseur
            )
            finisseur.score += bonus
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
