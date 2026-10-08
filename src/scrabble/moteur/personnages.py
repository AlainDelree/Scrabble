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
Se précipite sur les cases à multiplicateur, néglige ce qu'il garde sur son
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
  (:data:`BONUS_PREMIUM_OPPORTUNISTE` = 20 + 8 = 28) : un biais nettement
  au-dessus de tout niveau existant, mais du même ordre de grandeur que
  l'échelle déjà validée plutôt qu'une valeur arbitraire.

  Cette surcharge est **plate** (une constante, pas une table indexée par
  niveau) : par construction de ``ProfilPersonnage`` (issue #438, lot A),
  Opportuniste applique le même ``bonus_premium=28`` quel que soit le niveau
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

from dataclasses import dataclass

from scrabble.moteur.ia import ProfilPersonnage

#: Renforcement du bonus premium d'Opportuniste (voir docstring du module) :
#: valeur la plus haute déjà en production (20, EXPERT/CHAMPION_DU_MONDE) +
#: le plus grand palier observé entre deux niveaux adjacents (+8, AVANCE ->
#: EXPERT).
BONUS_PREMIUM_OPPORTUNISTE = 28


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
        description=(
            "Joue sans biais de personnalité : comportement standard du "
            "niveau choisi."
        ),
        profil=ProfilPersonnage(),
    ),
    "opportuniste": Personnage(
        cle="opportuniste",
        prenom="Opportuniste",
        description=(
            "Se précipite sur les cases à multiplicateur dès qu'elles sont à "
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
