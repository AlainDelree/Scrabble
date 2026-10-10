"""Registre des personnages IA : profils de personnalité par-dessus les niveaux (issue #439, lot B).

Rôle : un seul endroit où déclarer un personnage — prénom, description de
caractère (affichable au joueur plus tard) et le
:class:`~scrabble.moteur.ia.ProfilPersonnage` de surcharges stratégiques qu'il
applique (issue #438, lot A). Ajouter un personnage revient à ajouter une
entrée à :data:`PERSONNAGES` ci-dessous ; rien d'autre à toucher dans ce
module.

Portée (issue #439) : ce registre n'est consulté ni par ``ui/`` (aucun
sélecteur de personnage n'existe encore — contrainte explicite de l'issue)
ni par :meth:`scrabble.moteur.partie.Partie.jouer_tour_ia` (qui continue de
recevoir un ``ProfilPersonnage`` explicite, jamais résolu automatiquement
depuis :attr:`~scrabble.moteur.partie.Joueur.personnage`) — uniquement par les
tests et par le script de mesure de force
(``scripts/mesurer_force_niveaux.py``).

Personnage Classique
---------------------
Absence de biais : :class:`~scrabble.moteur.ia.ProfilPersonnage` vide,
comportement bit à bit identique à l'absence de profil (garanti par
construction, voir la docstring de ``ProfilPersonnage``). Présent dans le
registre pour que les comparaisons (tests, script de mesure) le nomment comme
les autres plutôt que de traiter « pas de personnage » comme un cas à part.

Personnage Opportuniste
------------------------
Se précipite sur les cases bonus, néglige ce qu'il garde sur son
chevalet. D'après le rapport d'investigation (issue #437), ce style s'exprime
entièrement avec deux réglages déjà existants de ``ProfilPersonnage`` —
aucun nouveau calcul :

* ``poids_leave=0.0`` : indifférence totale à la qualité du reliquat. Reprend
  tel quel la valeur de production de DEBUTANT/FACILE
  (:data:`scrabble.moteur.ia._POIDS_LEAVE`), pas une valeur inédite.
* ``bonus_premium`` fortement renforcé : :data:`BONUS_PREMIUM_OPPORTUNISTE`
  = 100, valeur choisie par mesure avec ``scripts/mesurer_force_niveaux.py``.
  Les réglages de production de :data:`scrabble.moteur.ia._BONUS_PREMIUM`
  vont de 3 (DEBUTANT) à 20 (EXPERT/CHAMPION_DU_MONDE) ; une première
  valeur de 28, déduite de cette échelle, ne se voyait presque pas en jeu.
  À 100, Opportuniste joue nettement plus de coups sur cases mot
  double/triple que Classique, pour une force comparable à niveau égal
  (44 à 50 % de victoires sur les six niveaux, 100 parties chacun) ;
  au-delà de 100, plus rien ne change.

  Cette surcharge est **plate** (une constante, pas une table indexée par
  niveau) : par construction de ``ProfilPersonnage`` (issue #438, lot A),
  Opportuniste applique le même ``bonus_premium=100`` quel que soit le niveau
  du joueur — le trait de caractère ne varie pas avec sa force. ``malus_longueur``
  n'est volontairement pas surchargé : seuls les deux réglages évoqués par
  l'intention du personnage (issue #439) sont touchés.

Voir le rapport de l'issue #439 pour les résultats de mesure (taux de
victoire, écart de score) de ce calibrage face à Classique, au même niveau,
et une éventuelle proposition d'ajustement si la mesure le justifie — la
valeur ne doit pas être retouchée en boucle pour « faire passer » une mesure,
seulement sur validation explicite d'Alain.

Personnage Chasseur de scrabbles
----------------------------------
Guette les coups posant les 7 lettres du chevalet d'un coup (un
« scrabble ») et garde ses meilleures lettres pour y arriver. D'après le
rapport d'investigation (issue #437), ce style est « réalisable en
partie » : le bonus direct sur la pose de 7 lettres relève de la même
famille de calcul que le bonus premium (une constante ajoutée au score
stratégique selon un critère sur le coup, voir
:data:`scrabble.moteur.ia._SEUIL_BONUS_SCRABBLE`) ; l'anticipation fine du
reliquat (deviner par avance qu'on approche d'un scrabble jouable) reste
hors périmètre — on s'appuie uniquement sur deux réglages :

* ``bonus_scrabble`` = :data:`BONUS_SEPT_LETTRES_CHASSEUR` = 150 : nouveau
  champ de :class:`~scrabble.moteur.ia.ProfilPersonnage` (issue #448, lot H),
  neutre (0) en l'absence de personnage, quel que soit le niveau. Valeur de
  départ déduite par analogie avec :data:`BONUS_PREMIUM_OPPORTUNISTE` (100) :
  l'événement déclencheur (poser les 7 lettres) est bien plus rare que
  « toucher une case premium », donc le bonus doit être encore plus
  déterminant pour l'emporter sur un coup concurrent mieux payé en score
  brut — 150 reprend l'échelle d'Opportuniste en l'augmentant d'un facteur
  comparable à celui qui sépare déjà ce dernier (x5) du bonus premium de
  production (20 à EXPERT/CHAMPION_DU_MONDE).
* ``poids_leave`` = :data:`POIDS_LEAVE_CHASSEUR_SCRABBLES` = 2.0 : poids du
  leave renforcé pour préférer conserver les bonnes lettres (plutôt qu'un
  reliquat quelconque) en vue d'un futur scrabble. Le plafond de production
  (:data:`scrabble.moteur.ia._POIDS_LEAVE`) culmine à 1.0 (EXPERT,
  CHAMPION_DU_MONDE) ; Chasseur de scrabbles double ce plafond, comme
  Opportuniste multiplie le bonus premium de production par un facteur net
  plutôt que de le dépasser d'un cran.

  Ces deux surcharges sont **plates** (une constante chacune, pas une table
  indexée par niveau), par construction de ``ProfilPersonnage`` — le trait
  de caractère ne varie pas avec la force du joueur, seul le vocabulaire
  disponible (câblé par niveau ailleurs) change les occasions réelles de
  scrabble.

Les valeurs ci-dessus sont des points de départ raisonnés (le dictionnaire
réel n'est pas disponible dans ce worktree isolé pour les mesurer par
parties jouées, voir le rapport de l'issue #448, lot H) — provisoires,
destinées à être ajustées par Alain après mesure avec
``scripts/mesurer_force_niveaux.py``, comme pour Opportuniste.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from scrabble.moteur.ia import Niveau, ProfilPersonnage

#: Renforcement du bonus premium d'Opportuniste (voir docstring du module) :
#: valeur la plus haute déjà en production (20, EXPERT/CHAMPION_DU_MONDE) +
#: le plus grand palier observé entre deux niveaux adjacents (+8, AVANCE ->
#: EXPERT).
BONUS_PREMIUM_OPPORTUNISTE = 100

#: Bonus de pose de 7 lettres du personnage Chasseur de scrabbles (voir
#: docstring du module, issue #448, lot H) : valeur de départ, à ajuster par
#: mesure.
BONUS_SEPT_LETTRES_CHASSEUR = 150

#: Poids du leave renforcé du personnage Chasseur de scrabbles (voir
#: docstring du module, issue #448, lot H) : valeur de départ, à ajuster par
#: mesure.
POIDS_LEAVE_CHASSEUR_SCRABBLES = 2.0

#: Clé pseudo-personnage exposée à l'UI (issue #440, lot D) : « Aléatoire »
#: n'est **jamais** une entrée de :data:`PERSONNAGES` — elle désigne le choix
#: « tire un personnage réel au lancement de la partie et cache-le ». Le
#: moteur ne connaît que des personnages réels : cette clé n'apparaît donc
#: jamais dans :attr:`~scrabble.moteur.partie.Joueur.personnage`, seulement
#: dans la configuration de l'écran d'accueil, avant résolution.
CLE_ALEATOIRE = "aleatoire"

#: Texte de mystère affiché à l'accueil quand « Aléatoire » est sélectionné
#: (issue #440, lot D) : ne doit rien révéler de l'identité qui sera tirée.
DESCRIPTION_ALEATOIRE = (
    "Un caractère sera tiré au sort au lancement de la partie et restera "
    "secret jusqu'à l'écran de résultat."
)


#: Tous les niveaux de difficulté — valeur par défaut de
#: :attr:`Personnage.niveaux_disponibles` (issue #447, lot G) : un personnage
#: qui ne déclare rien reste disponible partout, comme Classique.
TOUS_NIVEAUX: frozenset[Niveau] = frozenset(Niveau)

#: Niveaux où Opportuniste est disponible (issue #447, lot G) : de Facile à
#: Champion du monde, **pas** Débutant. D'après les mesures de l'issue #437,
#: à Débutant l'ordinateur joue tiré au hasard parmi 70 % des meilleurs coups
#: et Opportuniste y utilise les cases bonus à peine plus souvent que
#: Classique (20,5 % contre 20,1 %) : son caractère n'y est pas perceptible.
NIVEAUX_OPPORTUNISTE: frozenset[Niveau] = TOUS_NIVEAUX - {Niveau.DEBUTANT}

#: Niveaux où Chasseur de scrabbles est disponible (issue #448, lot H,
#: provisoire) : d'Avancé à Champion du monde. D'après le rapport
#: d'investigation (issue #437), les scrabbles sont rares aux niveaux plus
#: bas (environ 0,01 par partie à Intermédiaire, 0,1 à 0,2 à Avancé) : son
#: caractère y serait peu perceptible. Plage volontairement resserrée par
#: rapport à Opportuniste (qui commence à Facile) — à élargir ou réduire par
#: Alain après mesure réelle, **en un seul endroit** (cette constante).
NIVEAUX_CHASSEUR_SCRABBLES: frozenset[Niveau] = frozenset(
    {Niveau.AVANCE, Niveau.EXPERT, Niveau.CHAMPION_DU_MONDE}
)

#: Toutes les tailles de table (nombre total de joueurs) — valeur par défaut
#: de :attr:`Personnage.nb_joueurs_disponibles` (issue #449, lot I) : un
#: personnage qui ne déclare rien reste disponible à toutes les tailles,
#: comme Classique. Une table ne compte jamais moins de deux joueurs (il
#: faut au moins un adversaire) ni plus de quatre
#: (:data:`scrabble.moteur.partie.MAX_JOUEURS`).
TOUTES_TAILLES: frozenset[int] = frozenset({2, 3, 4})

#: Tailles de table où Opportuniste est disponible (issue #449, lot I) :
#: deux joueurs seulement. Tous les réglages et mesures des personnages ont
#: été faits en parties à deux (rapport d'investigation #437) ; rien n'a été
#: vérifié à trois ou quatre joueurs (plateau qui se remplit plus vite, moins
#: de coups par joueur) — réservé par prudence pour cette première diffusion,
#: à élargir par Alain après mesure, **en un seul endroit** (cette constante).
NB_JOUEURS_OPPORTUNISTE: frozenset[int] = frozenset({2})

#: Tailles de table où Chasseur de scrabbles est disponible (issue #449, lot
#: I) : deux joueurs seulement, même raison qu'Opportuniste ci-dessus.
NB_JOUEURS_CHASSEUR_SCRABBLES: frozenset[int] = frozenset({2})


@dataclass(frozen=True)
class Personnage:
    """Un personnage : prénom, description de caractère (FR), profil stratégique.

    ``niveaux_disponibles`` (issue #447, lot G) : l'ensemble des niveaux où ce
    personnage peut être choisi — facultatif, vaut :data:`TOUS_NIVEAUX` par
    défaut (cas de Classique), pour qu'un futur personnage sans déclaration
    explicite reste disponible partout.

    ``nb_joueurs_disponibles`` (issue #449, lot I) : l'ensemble des tailles de
    table (nombre total de joueurs) où ce personnage peut être choisi —
    facultatif lui aussi, vaut :data:`TOUTES_TAILLES` par défaut (cas de
    Classique), indépendamment de ``niveaux_disponibles``. Les deux
    restrictions se combinent (ET logique) : un personnage doit être
    disponible à la fois au niveau et à la taille de table concernés.
    """

    cle: str
    prenom: str
    description: str
    profil: ProfilPersonnage
    niveaux_disponibles: frozenset[Niveau] = field(
        default_factory=lambda: TOUS_NIVEAUX
    )
    nb_joueurs_disponibles: frozenset[int] = field(
        default_factory=lambda: TOUTES_TAILLES
    )


#: Registre unique des personnages (issue #439, lot B). Ajouter un
#: personnage = ajouter une entrée ici.
PERSONNAGES: dict[str, Personnage] = {
    "classique": Personnage(
        cle="classique",
        prenom="Classique",
        description="Joue normalement selon son niveau.",
        profil=ProfilPersonnage(),
    ),
    "opportuniste": Personnage(
        cle="opportuniste",
        prenom="Opportuniste",
        description=(
            "Se précipite sur les cases bonus dès qu'elles sont à "
            "sa portée, quitte à négliger la qualité des lettres qu'il garde "
            "sur son chevalet."
        ),
        profil=ProfilPersonnage(
            bonus_premium=BONUS_PREMIUM_OPPORTUNISTE,
            poids_leave=0.0,
        ),
        niveaux_disponibles=NIVEAUX_OPPORTUNISTE,
        nb_joueurs_disponibles=NB_JOUEURS_OPPORTUNISTE,
    ),
    "chasseur_de_scrabbles": Personnage(
        cle="chasseur_de_scrabbles",
        prenom="Chasseur de scrabbles",
        description=(
            "Guette les occasions de poser ses 7 lettres d'un coup et garde "
            "ses meilleures lettres en réserve pour y arriver."
        ),
        profil=ProfilPersonnage(
            bonus_scrabble=BONUS_SEPT_LETTRES_CHASSEUR,
            poids_leave=POIDS_LEAVE_CHASSEUR_SCRABBLES,
        ),
        niveaux_disponibles=NIVEAUX_CHASSEUR_SCRABBLES,
        nb_joueurs_disponibles=NB_JOUEURS_CHASSEUR_SCRABBLES,
    ),
}


def obtenir_personnage(cle: str) -> Personnage:
    """Renvoie le personnage enregistré sous ``cle``.

    :raises KeyError: si ``cle`` ne correspond à aucune entrée de
        :data:`PERSONNAGES`.
    """
    return PERSONNAGES[cle]


def tirer_personnage(
    generateur: random.Random | None = None,
    niveau: Niveau | None = None,
    nb_joueurs: int | None = None,
) -> Personnage:
    """Tire un personnage parmi ceux du registre disponibles à ``niveau`` et
    ``nb_joueurs``.

    Classique compris (issue #440, lot D, point 3) : le tirage « Aléatoire »
    ne favorise ni n'exclut le personnage neutre. ``generateur`` est
    injectable pour un tirage déterministe en test ; à défaut, utilise le
    module :mod:`random` global (``random.choice`` s'appelle de la même façon
    sur le module que sur une instance de :class:`random.Random`).

    ``niveau`` (issue #447, lot G) restreint le tirage aux personnages
    disponibles à ce niveau (:func:`personnages_disponibles_a_niveau`) — à
    appeler uniquement là où :func:`aleatoire_disponible_a_niveau` est vrai
    (au moins deux personnages y figurent), ce que le contrôle côté serveur
    garantit déjà avant tout tirage.

    ``nb_joueurs`` (issue #449, lot I) restreint pareillement le tirage aux
    personnages disponibles à cette taille de table
    (:func:`personnages_disponibles_a_nb_joueurs`). Les deux restrictions se
    combinent (ET logique) quand elles sont fournies ensemble — c'est
    ``creer_partie`` qui les transmet toutes les deux pour une IA donnée.

    ``None`` (défaut pour chacun des deux) conserve l'ancien comportement :
    tirage sur tout le registre, sans la restriction correspondante — utilisé
    par les appelants qui ne connaissent pas encore de niveau ou de taille de
    table particuliers.
    """
    rng = generateur if generateur is not None else random
    reserve = list(PERSONNAGES.values())
    if niveau is not None:
        reserve = [p for p in reserve if niveau in p.niveaux_disponibles]
    if nb_joueurs is not None:
        reserve = [p for p in reserve if nb_joueurs in p.nb_joueurs_disponibles]
    return rng.choice(reserve)


def personnages_disponibles_a_niveau(niveau: Niveau) -> list[Personnage]:
    """Personnages réels du registre disponibles à ``niveau`` (issue #447, lot G).

    Dans l'ordre d'insertion de :data:`PERSONNAGES` (Classique en tête).
    N'inclut jamais l'entrée pseudo-personnage « Aléatoire » : voir
    :func:`aleatoire_disponible_a_niveau` pour sa propre règle de
    disponibilité, déduite de celle-ci.
    """
    return [p for p in PERSONNAGES.values() if niveau in p.niveaux_disponibles]


def aleatoire_disponible_a_niveau(niveau: Niveau) -> bool:
    """Vrai si « Aléatoire » a un sens à ``niveau`` (issue #447, lot G).

    Règle déduite automatiquement des déclarations des personnages réels,
    sans qu'Aléatoire ait lui-même à déclarer quoi que ce soit : il lui faut
    au moins **deux** personnages disponibles à ce niveau (hors lui-même),
    tirer au hasard parmi un seul personnage n'ayant aucun sens. Un futur
    personnage ajouté au registre et compatible avec un niveau aujourd'hui à
    un seul personnage disponible rend donc Aléatoire à nouveau disponible à
    ce niveau, sans aucune autre modification.
    """
    return len(personnages_disponibles_a_niveau(niveau)) >= 2


def personnage_disponible_a_niveau(personnage_cle: str, niveau: Niveau) -> bool:
    """Vrai si ``personnage_cle`` (réel, ou :data:`CLE_ALEATOIRE`) peut être
    choisi à ``niveau`` (issue #447, lot G).

    Une clé inconnue du registre (et différente de :data:`CLE_ALEATOIRE`)
    renvoie ``False`` plutôt que de lever : à l'appelant (contrôle côté
    serveur) de distinguer « personnage inconnu » de « indisponible à ce
    niveau » s'il le souhaite.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return aleatoire_disponible_a_niveau(niveau)
    personnage = PERSONNAGES.get(personnage_cle)
    return personnage is not None and niveau in personnage.niveaux_disponibles


def personnages_disponibles_a_nb_joueurs(nb_joueurs: int) -> list[Personnage]:
    """Personnages réels du registre disponibles à ``nb_joueurs`` (issue #449, lot I).

    Dans l'ordre d'insertion de :data:`PERSONNAGES` (Classique en tête).
    N'inclut jamais l'entrée pseudo-personnage « Aléatoire » : voir
    :func:`aleatoire_disponible_a_nb_joueurs` pour sa propre règle de
    disponibilité, déduite de celle-ci. Indépendant de
    :func:`personnages_disponibles_a_niveau` (deux dimensions distinctes qui
    se combinent chez l'appelant).
    """
    return [p for p in PERSONNAGES.values() if nb_joueurs in p.nb_joueurs_disponibles]


def aleatoire_disponible_a_nb_joueurs(nb_joueurs: int) -> bool:
    """Vrai si « Aléatoire » a un sens à ``nb_joueurs`` (issue #449, lot I).

    Règle déduite automatiquement des déclarations des personnages réels,
    sans qu'Aléatoire ait lui-même à déclarer quoi que ce soit : il lui faut
    au moins **deux** personnages disponibles à cette taille de table (hors
    lui-même), tirer au hasard parmi un seul personnage n'ayant aucun sens.
    Un futur personnage ajouté au registre et compatible avec une taille
    aujourd'hui à un seul personnage disponible rend donc Aléatoire à nouveau
    disponible à cette taille, sans aucune autre modification. Aujourd'hui :
    disponible à deux joueurs (Classique + Opportuniste + Chasseur de
    scrabbles), indisponible à trois ou quatre (seul Classique y figure).
    """
    return len(personnages_disponibles_a_nb_joueurs(nb_joueurs)) >= 2


def personnage_disponible_a_nb_joueurs(personnage_cle: str, nb_joueurs: int) -> bool:
    """Vrai si ``personnage_cle`` (réel, ou :data:`CLE_ALEATOIRE`) peut être
    choisi pour une table de ``nb_joueurs`` (issue #449, lot I).

    Une clé inconnue du registre (et différente de :data:`CLE_ALEATOIRE`)
    renvoie ``False`` plutôt que de lever : à l'appelant (contrôle côté
    serveur) de distinguer « personnage inconnu » de « indisponible à cette
    taille de table » s'il le souhaite.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return aleatoire_disponible_a_nb_joueurs(nb_joueurs)
    personnage = PERSONNAGES.get(personnage_cle)
    return personnage is not None and nb_joueurs in personnage.nb_joueurs_disponibles


#: Message affiché quand les personnages sont réservés aux parties à deux
#: joueurs (issue #449, lot I, points 2, 3 et 4) : explication du sélecteur
#: désactivé à l'accueil (point 2), remise à Classique d'un adversaire déjà
#: configuré (point 3) et refus côté serveur (point 4) partagent le même
#: texte.
MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS = (
    "Les personnages sont réservés aux parties à deux joueurs."
)

#: Libellés français des nombres de joueurs (issue #449, lot I), réservés à
#: l'affichage des tailles de table de disponibilité d'un personnage
#: (:func:`libelle_tailles`, :func:`libelle_tailles_aleatoire`).
_MOTS_NB_JOUEURS: dict[int, str] = {2: "deux", 3: "trois", 4: "quatre"}

#: Message affiché pour une taille de table où « Aléatoire » est
#: indisponible (issue #449, lot I) — le même quelle que soit la taille
#: concernée, puisque la raison ne dépend jamais de la taille elle-même,
#: seulement du nombre de personnages réels qui y sont disponibles.
MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT = (
    "Aléatoire demande au moins deux personnages disponibles à cette taille "
    "de table."
)


def _libelle_tailles(tailles: frozenset[int]) -> str:
    """Texte des tailles de table d'un ensemble, pour affichage (issue #449, lot I).

    « Toutes les parties » si ``tailles`` couvre :data:`TOUTES_TAILLES` ;
    « Parties à <nombre> joueurs » pour une taille unique ; « Parties de
    <premier> à <dernier> joueurs » pour un intervalle contigu de plusieurs
    tailles ; sinon (motif non contigu, hypothétique) « Parties à <nombre> ou
    <nombre> joueurs ».
    """
    if tailles == TOUTES_TAILLES:
        return "Toutes les parties"
    ordre = sorted(TOUTES_TAILLES)
    presentes = [n for n in ordre if n in tailles]
    mots = [_MOTS_NB_JOUEURS[n] for n in presentes]
    if len(mots) == 1:
        return f"Parties à {mots[0]} joueurs"
    if presentes == list(range(presentes[0], presentes[-1] + 1)):
        return f"Parties de {mots[0]} à {mots[-1]} joueurs"
    return "Parties à " + " ou ".join(mots) + " joueurs"


def libelle_tailles(personnage: Personnage) -> str:
    """Texte des tailles de table où ``personnage`` est disponible (issue
    #449, lot I, point 5) : « Toutes les parties » ou « Parties à deux
    joueurs »."""
    return _libelle_tailles(personnage.nb_joueurs_disponibles)


def tailles_disponibles_aleatoire() -> frozenset[int]:
    """Tailles de table où « Aléatoire » est disponible (issue #449, lot I, point 5)."""
    return frozenset(n for n in TOUTES_TAILLES if aleatoire_disponible_a_nb_joueurs(n))


def libelle_tailles_aleatoire() -> str:
    """Texte des tailles de table où « Aléatoire » est disponible, même
    présentation que :func:`libelle_tailles` (issue #449, lot I, point 5)."""
    return _libelle_tailles(tailles_disponibles_aleatoire())


def explication_disponibilite_tailles(personnage_cle: str) -> str:
    """Courte explication de la restriction de tailles de table de
    ``personnage_cle`` (issue #449, lot I), à afficher au même titre que
    :func:`explication_disponibilite_niveaux`.

    Chaîne vide quand le personnage est disponible à toutes les tailles (cas
    de Classique, et de tout personnage sans déclaration) : rien à expliquer.
    Pour Aléatoire, :data:`MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT` dès
    qu'au moins une taille lui est fermée. Pour un personnage réel restreint
    à deux joueurs (motif observé à ce jour, Opportuniste et Chasseur de
    scrabbles compris) : :data:`MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS`.
    Motif différent (hypothétique) : repli sur :func:`libelle_tailles`.
    """
    if personnage_cle == CLE_ALEATOIRE:
        if tailles_disponibles_aleatoire() == TOUTES_TAILLES:
            return ""
        return MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT
    personnage = PERSONNAGES.get(personnage_cle)
    if personnage is None:
        return ""
    tailles = personnage.nb_joueurs_disponibles
    if tailles == TOUTES_TAILLES:
        return ""
    if tailles == frozenset({2}):
        return MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS
    return f"Disponible : {_libelle_tailles(tailles)}"


#: Libellés français des niveaux (issue #447, lot G), dans l'ordre de
#: :class:`~scrabble.moteur.ia.Niveau` — réservés à l'affichage des niveaux de
#: disponibilité d'un personnage (:func:`libelle_niveaux`,
#: :func:`explication_disponibilite_niveaux`). Dupliqués à dessein de
#: ``scrabble.ui.accueil._LIBELLES_NIVEAUX`` plutôt que partagés : ce module
#: (``moteur``) ne doit pas dépendre de ``ui``, et l'inverse est déjà le cas.
_LIBELLES_NIVEAU: dict[Niveau, str] = {
    Niveau.DEBUTANT: "Débutant",
    Niveau.FACILE: "Facile",
    Niveau.INTERMEDIAIRE: "Intermédiaire",
    Niveau.AVANCE: "Avancé",
    Niveau.EXPERT: "Expert",
    Niveau.CHAMPION_DU_MONDE: "Champion du monde",
}

#: Message affiché pour un niveau où « Aléatoire » est indisponible (issue
#: #447, lot G, point 2) — le même quel que soit le niveau concerné, puisque
#: la raison ne dépend jamais du niveau lui-même, seulement du nombre de
#: personnages réels qui y sont disponibles.
MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT = (
    "Aléatoire demande au moins deux personnages disponibles à ce niveau."
)


def _libelle_niveaux(niveaux: frozenset[Niveau]) -> str:
    """Texte des niveaux d'un ensemble, pour affichage (issue #447, lot G).

    « Tous les niveaux » si ``niveaux`` couvre :data:`TOUS_NIVEAUX` ; sinon
    « <premier> à <dernier> » (ou le niveau seul s'il n'y en a qu'un), dans
    l'ordre de :class:`~scrabble.moteur.ia.Niveau` — suffisant pour les motifs
    observés à ce jour (un intervalle contigu de niveaux).
    """
    if niveaux == TOUS_NIVEAUX:
        return "Tous les niveaux"
    ordonnes = [n for n in Niveau if n in niveaux]
    labels = [_LIBELLES_NIVEAU[n] for n in ordonnes]
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]} à {labels[-1]}"


def libelle_niveaux(personnage: Personnage) -> str:
    """Texte des niveaux où ``personnage`` est disponible (issue #447, lot G,
    point 5) : « Tous les niveaux » ou « <premier> à <dernier> »."""
    return _libelle_niveaux(personnage.niveaux_disponibles)


def niveaux_disponibles_aleatoire() -> frozenset[Niveau]:
    """Niveaux où « Aléatoire » est disponible (issue #447, lot G, point 5)."""
    return frozenset(n for n in Niveau if aleatoire_disponible_a_niveau(n))


def libelle_niveaux_aleatoire() -> str:
    """Texte des niveaux où « Aléatoire » est disponible, même présentation
    que :func:`libelle_niveaux` (issue #447, lot G, point 5)."""
    return _libelle_niveaux(niveaux_disponibles_aleatoire())


def explication_disponibilite_niveaux(personnage_cle: str) -> str:
    """Courte explication de la restriction de niveaux de ``personnage_cle``
    (issue #447, lot G, point 2), à afficher sous le sélecteur de personnage.

    Chaîne vide quand le personnage est disponible à tous les niveaux (cas de
    Classique, et de tout personnage sans déclaration) : rien à expliquer.
    Pour Aléatoire, :data:`MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT` dès qu'au
    moins un niveau lui est fermé. Pour un personnage réel indisponible sur un
    préfixe de niveaux les plus faibles (motif observé à ce jour, Opportuniste
    compris) : « Disponible à partir de <premier niveau disponible> ». Motif
    différent (hypothétique) : repli sur :func:`libelle_niveaux`.
    """
    if personnage_cle == CLE_ALEATOIRE:
        if niveaux_disponibles_aleatoire() == TOUS_NIVEAUX:
            return ""
        return MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT
    personnage = PERSONNAGES.get(personnage_cle)
    if personnage is None:
        return ""
    niveaux = personnage.niveaux_disponibles
    if niveaux == TOUS_NIVEAUX:
        return ""
    ordre = list(Niveau)
    manquants = [n for n in ordre if n not in niveaux]
    presents = [n for n in ordre if n in niveaux]
    if presents and ordre.index(presents[0]) == len(manquants):
        return f"Disponible à partir de {_LIBELLES_NIVEAU[presents[0]]}"
    return f"Disponible : {_libelle_niveaux(niveaux)}"


def _prenom_affichable(cle: str) -> str:
    """Prénom affichable d'un personnage réel du registre, Classique compris.

    Défense en profondeur : une clé devenue inconnue (le registre n'est
    jamais réduit en pratique) retombe sur la clé elle-même plutôt que de
    faire planter l'affichage.
    """
    personnage = PERSONNAGES.get(cle)
    return personnage.prenom if personnage is not None else cle


def libelle_choix_accueil(personnage_cle: str) -> str:
    """Texte à afficher entre parenthèses pour un choix fait à l'accueil (issue #441).

    ``personnage_cle`` est ici la clé **encore non résolue** mémorisée par
    :class:`~scrabble.ui.accueil.JoueurConfig` : soit une clé de
    :data:`PERSONNAGES`, soit :data:`CLE_ALEATOIRE` (le tirage réel n'a lieu
    qu'au lancement de la partie, voir
    :func:`~scrabble.moteur.partie.creer_partie`). Chaîne vide pour Classique
    (ou l'absence de personnage) : l'accueil affiche alors le prénom seul,
    comme avant l'introduction du sélecteur.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return "Aléatoire"
    if not personnage_cle or personnage_cle == "classique":
        return ""
    return _prenom_affichable(personnage_cle)


def libelle_personnage_partie(
    personnage_cle: str, personnage_aleatoire: bool, reveler: bool = False
) -> str:
    """Texte à afficher entre parenthèses pour un ``Joueur`` en partie (issue #441).

    ``personnage_cle``/``personnage_aleatoire`` reprennent les champs de
    :class:`~scrabble.moteur.partie.Joueur` — ``personnage_cle`` porte ici
    toujours l'identité **réelle** (jamais le libellé « Aléatoire »).

    Pour un personnage tiré au hasard (``personnage_aleatoire`` vrai), le
    libellé reste « Aléatoire » tant que ``reveler`` est faux (pendant toute
    la partie — l'identité ne doit pas fuiter), puis devient « Aléatoire :
    <Personnage> » une fois révélé, Classique compris : jamais le prénom seul,
    pour que le joueur ne croie pas à un défaut d'affichage.

    Pour un personnage choisi explicitement, chaîne vide pour Classique (ou
    l'absence de personnage, sauvegarde antérieure à l'issue #438) : seul un
    personnage tiré au hasard doit être annoncé pour Classique.
    """
    if personnage_aleatoire:
        if reveler:
            return f"Aléatoire : {_prenom_affichable(personnage_cle)}"
        return "Aléatoire"
    if not personnage_cle or personnage_cle == "classique":
        return ""
    return _prenom_affichable(personnage_cle)


def lister_personnages(
    cles_dans_partie: frozenset[str] = frozenset(),
    aleatoire_dans_partie: bool = False,
) -> list[dict[str, Any]]:
    """Liste présentable pour la fenêtre « Les personnages » (issue #442, lot F).

    Une entrée par personnage de :data:`PERSONNAGES` (dans l'ordre
    d'insertion, donc Classique en tête), puis « Aléatoire » toujours en
    dernier — construite dynamiquement depuis le registre comme
    :func:`~scrabble.ui.accueil.ApiAccueil.obtenir_personnages`, pour qu'un
    personnage ajouté plus tard au registre y apparaisse sans autre
    modification. Chaque entrée est ``{"cle", "prenom", "description",
    "dans_la_partie", "niveaux_label", "tailles_label"}`` — ``niveaux_label``
    (issue #447, lot G, point 5) est le texte des niveaux où le personnage
    est disponible (:func:`libelle_niveaux`/:func:`libelle_niveaux_aleatoire`)
    et ``tailles_label`` (issue #449, lot I, point 5) le texte des tailles de
    table où il est disponible (:func:`libelle_tailles`/
    :func:`libelle_tailles_aleatoire`), même présentation à l'accueil et en
    jeu puisque les deux fenêtres consomment cette même fonction (directement
    ici, ou via :meth:`~scrabble.ui.accueil.ApiAccueil.obtenir_personnages`
    qui reprend la même logique).

    ``cles_dans_partie`` (vide par défaut — cas de l'accueil, où il n'y a pas
    encore de partie) marque les personnages choisis À L'AVANCE par un
    adversaire de la partie en cours (``dans_la_partie``). Ne jamais y
    inclure la clé d'un personnage tiré au hasard : ce paramètre ne pilote
    donc jamais le marquage de l'entrée « Aléatoire » elle-même (voir
    ``aleatoire_dans_partie`` ci-dessous), afin que la fenêtre ne laisse
    jamais deviner le résultat d'un tirage avant la révélation finale.

    ``aleatoire_dans_partie`` (issue #443, lot F bis) marque l'entrée
    « Aléatoire » dès qu'au moins un adversaire a été RÉGLÉ sur Aléatoire
    (:attr:`~scrabble.moteur.partie.Joueur.personnage_aleatoire`), quel que
    soit le personnage réellement tiré. Cela ne révèle rien : le libellé
    « (Aléatoire) » est déjà affiché à côté du prénom de cet adversaire
    pendant toute la partie (voir
    :func:`libelle_personnage_partie`) — seule l'identité tirée reste
    secrète, jamais le fait d'avoir réglé un adversaire sur Aléatoire.
    """
    resultat = [
        {
            "cle": personnage.cle,
            "prenom": personnage.prenom,
            "description": personnage.description,
            "dans_la_partie": personnage.cle in cles_dans_partie,
            "niveaux_label": libelle_niveaux(personnage),
            "tailles_label": libelle_tailles(personnage),
        }
        for personnage in PERSONNAGES.values()
    ]
    resultat.append(
        {
            "cle": CLE_ALEATOIRE,
            "prenom": "Aléatoire",
            "description": DESCRIPTION_ALEATOIRE,
            "dans_la_partie": aleatoire_dans_partie,
            "niveaux_label": libelle_niveaux_aleatoire(),
            "tailles_label": libelle_tailles_aleatoire(),
        }
    )
    return resultat
