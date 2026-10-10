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
* ``bonus_premium`` renforcé au-delà de la valeur la plus haute déjà en
  production. :data:`scrabble.moteur.ia._BONUS_PREMIUM` va de 3 (DEBUTANT) à
  20 (EXPERT/CHAMPION_DU_MONDE) par paliers croissants : +2, +3, +4, +8, +0
  d'un niveau au suivant. Le plus grand de ces paliers est +8 (AVANCE →
  EXPERT). Opportuniste reprend la valeur la plus haute déjà calibrée (20) et
  lui applique ce même plus grand palier une fois de plus
  (:data:`BONUS_PREMIUM_OPPORTUNISTE` = 100, choisi par mesure : 28 se voyait à peine, et au-delà de 100 plus rien ne change) : un biais nettement
  au-dessus de tout niveau existant, mais du même ordre de grandeur que
  l'échelle déjà validée plutôt qu'une valeur arbitraire.

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
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from scrabble.moteur.ia import ProfilPersonnage

#: Renforcement du bonus premium d'Opportuniste (voir docstring du module) :
#: valeur la plus haute déjà en production (20, EXPERT/CHAMPION_DU_MONDE) +
#: le plus grand palier observé entre deux niveaux adjacents (+8, AVANCE ->
#: EXPERT).
BONUS_PREMIUM_OPPORTUNISTE = 100

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


@dataclass(frozen=True)
class Personnage:
    """Un personnage : prénom, description de caractère (FR), profil stratégique."""

    cle: str
    prenom: str
    description: str
    profil: ProfilPersonnage


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
    ),
}


def obtenir_personnage(cle: str) -> Personnage:
    """Renvoie le personnage enregistré sous ``cle``.

    :raises KeyError: si ``cle`` ne correspond à aucune entrée de
        :data:`PERSONNAGES`.
    """
    return PERSONNAGES[cle]


def tirer_personnage(generateur: random.Random | None = None) -> Personnage:
    """Tire un personnage uniformément parmi **tous** ceux du registre.

    Classique compris (issue #440, lot D, point 3) : le tirage « Aléatoire »
    porte sur l'ensemble de :data:`PERSONNAGES`, sans favoriser ni exclure le
    personnage neutre. ``generateur`` est injectable pour un tirage
    déterministe en test ; à défaut, utilise le module :mod:`random` global
    (``random.choice`` s'appelle de la même façon sur le module que sur une
    instance de :class:`random.Random`).
    """
    rng = generateur if generateur is not None else random
    return rng.choice(list(PERSONNAGES.values()))


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
    "dans_la_partie"}``.

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
        }
        for personnage in PERSONNAGES.values()
    ]
    resultat.append(
        {
            "cle": CLE_ALEATOIRE,
            "prenom": "Aléatoire",
            "description": DESCRIPTION_ALEATOIRE,
            "dans_la_partie": aleatoire_dans_partie,
        }
    )
    return resultat
