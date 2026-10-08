"""Tests de l'affichage des personnages IA côté écran de jeu (issue #440, lot D).

Couvre :
- la révélation en fin de partie des personnages tirés « Aléatoire »
  (``revelations_personnages``), absente pendant la partie et pour un
  personnage choisi explicitement ;
- l'exposition de cette révélation dans ``etat_public`` ;
- la résolution du ``ProfilPersonnage`` effectivement transmis à l'IA
  (``_profil_joueur_ia``) et son câblage dans ``jouer_tours_ia_ui``.
"""

from __future__ import annotations

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.personnages import PERSONNAGES
from scrabble.ui.jeu import _profil_joueur_ia, etat_public, revelations_personnages
from tests._aides_test_jeu import _DicoFactice


def _partie_avec_ia(personnage: str = "", personnage_aleatoire: bool = False) -> Partie:
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(
            nom="Thomas",
            humain=False,
            niveau=Niveau.FACILE,
            personnage=personnage,
            personnage_aleatoire=personnage_aleatoire,
        ),
    ]
    return Partie(joueurs, _DicoFactice(), graine=1)


class TestRevelationsPersonnages:
    """Révélation en fin de partie des personnages tirés au hasard."""

    def test_vide_tant_que_la_partie_n_est_pas_terminee(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        assert revelations_personnages(partie) == []

    def test_vide_en_fin_de_partie_pour_un_personnage_choisi_explicitement(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=False)
        partie.terminee = True
        assert revelations_personnages(partie) == []

    def test_vide_en_fin_de_partie_sans_personnage(self):
        partie = _partie_avec_ia("", personnage_aleatoire=False)
        partie.terminee = True
        assert revelations_personnages(partie) == []

    def test_revele_le_personnage_tire_au_hasard_en_fin_de_partie(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        partie.terminee = True

        resultat = revelations_personnages(partie)

        attendu = PERSONNAGES["opportuniste"]
        assert resultat == [
            {
                "nom": "Thomas",
                "personnage_prenom": attendu.prenom,
                "personnage_description": attendu.description,
            }
        ]

    def test_jamais_le_joueur_humain(self):
        """Défense en profondeur : un humain n'est jamais révélé, même si le
        drapeau était (par erreur) renseigné."""
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        partie.joueurs[0].personnage = "opportuniste"
        partie.joueurs[0].personnage_aleatoire = True
        partie.terminee = True

        resultat = revelations_personnages(partie)
        assert [r["nom"] for r in resultat] == ["Thomas"]


class TestEtatPublicRevelations:
    """``etat_public`` expose la révélation (ou son absence) au JS."""

    def test_liste_vide_en_cours_de_partie(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        etat = etat_public(partie, id_partie=1)
        assert etat["revelations_personnages"] == []

    def test_liste_peuplee_en_fin_de_partie(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        partie.terminee = True
        etat = etat_public(partie, id_partie=1)
        assert len(etat["revelations_personnages"]) == 1
        assert etat["revelations_personnages"][0]["nom"] == "Thomas"


class TestProfilJoueurIa:
    """Résolution du ``ProfilPersonnage`` transmis à l'IA (issue #440, lot D)."""

    def test_personnage_vide_renvoie_aucun_profil(self):
        joueur = Joueur(nom="Thomas", humain=False, niveau=Niveau.FACILE)
        assert _profil_joueur_ia(joueur) is None

    def test_personnage_inconnu_renvoie_aucun_profil(self):
        """Défense en profondeur : ne doit jamais faire planter un tour d'IA."""
        joueur = Joueur(
            nom="Thomas", humain=False, niveau=Niveau.FACILE, personnage="ninja"
        )
        assert _profil_joueur_ia(joueur) is None

    def test_personnage_classique_renvoie_le_profil_du_registre(self):
        joueur = Joueur(
            nom="Thomas", humain=False, niveau=Niveau.FACILE, personnage="classique"
        )
        assert _profil_joueur_ia(joueur) == PERSONNAGES["classique"].profil

    def test_personnage_opportuniste_renvoie_le_profil_du_registre(self):
        joueur = Joueur(
            nom="Thomas", humain=False, niveau=Niveau.FACILE, personnage="opportuniste"
        )
        assert _profil_joueur_ia(joueur) == PERSONNAGES["opportuniste"].profil


class TestJouerToursIaUiTransmetLePersonnage:
    """``jouer_tours_ia_ui`` transmet le profil résolu à ``choisir_coup``."""

    def test_profil_opportuniste_transmis_a_choisir_coup(self, monkeypatch):
        import scrabble.moteur.ia as ia_mod
        from scrabble.ui.jeu import jouer_tours_ia_ui

        captures: dict = {}

        def faux_choisir_coup(plateau, chevalet, dictionnaire, niveau, *, profil=None):
            captures["profil"] = profil
            return None

        monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir_coup)

        partie = _partie_avec_ia("opportuniste")
        partie.index_courant = 1  # l'IA (Thomas), pas l'humaine (Alice)
        jouer_tours_ia_ui(partie, id_partie=None)

        assert captures["profil"] == PERSONNAGES["opportuniste"].profil

    def test_sans_personnage_aucun_profil_transmis(self, monkeypatch):
        """Non-régression : un faux ``choisir_coup`` sans paramètre ``profil``
        (comme avant l'issue #438) continue de fonctionner tant qu'aucun
        personnage n'est choisi."""
        import scrabble.moteur.ia as ia_mod
        from scrabble.ui.jeu import jouer_tours_ia_ui

        captures: dict = {}

        def faux_choisir_coup(plateau, chevalet, dictionnaire, niveau):
            captures["appele"] = True
            return None

        monkeypatch.setattr(ia_mod, "choisir_coup", faux_choisir_coup)

        partie = _partie_avec_ia("")
        partie.index_courant = 1  # l'IA (Thomas), pas l'humaine (Alice)
        jouer_tours_ia_ui(partie, id_partie=None)

        assert captures.get("appele") is True
