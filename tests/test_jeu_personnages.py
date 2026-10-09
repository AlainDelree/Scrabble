"""Tests de l'affichage des personnages IA côté écran de jeu (issue #440, lot D ;
affichage « Prénom (Personnage) » : issue #441, lot D bis).

Couvre :
- la révélation en fin de partie des personnages tirés « Aléatoire »
  (``revelations_personnages``), absente pendant la partie et pour un
  personnage choisi explicitement ;
- l'exposition de cette révélation dans ``etat_public`` ;
- la résolution du ``ProfilPersonnage`` effectivement transmis à l'IA
  (``_profil_joueur_ia``) et son câblage dans ``jouer_tours_ia_ui``.
- le libellé ``personnage_libelle`` exposé par ``serialiser_joueur_public``/
  ``etat_public`` (issue #441) : vide pour Classique, le prénom du personnage
  sinon, « Aléatoire » pendant la partie et « Aléatoire : <Personnage> » une
  fois celle-ci terminée — jamais révélé pour un personnage choisi
  explicitement. Le champ ``nom`` lui-même reste inchangé (prénom seul).
"""

from __future__ import annotations

from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.moteur.personnages import CLE_ALEATOIRE, PERSONNAGES
from scrabble.ui.jeu import (
    ApiJeu,
    _profil_joueur_ia,
    etat_public,
    revelations_personnages,
    serialiser_joueur_public,
)
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


class TestPersonnageLibelleAffichage:
    """``personnage_libelle`` affiché à côté du prénom (issue #441).

    ``nom`` reste toujours le prénom seul (historique des coups, sauvegardes
    et tests qui s'appuient sur le nom inchangés) : seul ``personnage_libelle``
    porte le texte à mettre entre parenthèses, calculé côté Python.
    """

    def test_personnage_classique_pas_de_parenthese(self):
        joueur = Joueur(
            nom="Thomas", humain=False, niveau=Niveau.FACILE, personnage="classique"
        )
        pub = serialiser_joueur_public(joueur, index=0, courant=False)
        assert pub["nom"] == "Thomas"
        assert pub["personnage_libelle"] == ""

    def test_sans_personnage_pas_de_parenthese(self):
        """Sauvegarde antérieure à l'issue #438 : personnage vide."""
        joueur = Joueur(nom="Thomas", humain=False, niveau=Niveau.FACILE)
        pub = serialiser_joueur_public(joueur, index=0, courant=False)
        assert pub["personnage_libelle"] == ""

    def test_personnage_explicite_porte_son_prenom(self):
        joueur = Joueur(
            nom="Thomas", humain=False, niveau=Niveau.FACILE, personnage="opportuniste"
        )
        pub = serialiser_joueur_public(joueur, index=0, courant=False)
        assert pub["nom"] == "Thomas"
        assert pub["personnage_libelle"] == "Opportuniste"

    def test_aleatoire_pendant_la_partie_affiche_aleatoire_seul(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        etat = etat_public(partie, id_partie=1)
        joueur_ia = next(j for j in etat["joueurs"] if not j["humain"])
        assert joueur_ia["nom"] == "Thomas"
        assert joueur_ia["personnage_libelle"] == "Aléatoire"

    def test_aleatoire_revele_en_fin_de_partie_pour_chaque_personnage(self):
        """Une fois ``partie.terminee``, le libellé devient « Aléatoire :
        <Personnage> », Classique compris (point 3 de l'issue #441)."""
        for cle, personnage in PERSONNAGES.items():
            partie = _partie_avec_ia(cle, personnage_aleatoire=True)
            partie.terminee = True
            etat = etat_public(partie, id_partie=1)
            joueur_ia = next(j for j in etat["joueurs"] if not j["humain"])
            assert joueur_ia["nom"] == "Thomas"
            assert joueur_ia["personnage_libelle"] == f"Aléatoire : {personnage.prenom}"

    def test_personnage_choisi_explicitement_jamais_revele_en_fin_de_partie(self):
        """Un personnage choisi à l'avance n'a rien à « révéler » : son nom
        l'annonçait déjà pendant toute la partie (contrainte du point 3)."""
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=False)
        partie.terminee = True
        etat = etat_public(partie, id_partie=1)
        joueur_ia = next(j for j in etat["joueurs"] if not j["humain"])
        assert joueur_ia["personnage_libelle"] == "Opportuniste"

    def test_humain_jamais_de_parenthese(self):
        partie = _partie_avec_ia("opportuniste", personnage_aleatoire=True)
        partie.terminee = True
        etat = etat_public(partie, id_partie=1)
        humain = next(j for j in etat["joueurs"] if j["humain"])
        assert humain["personnage_libelle"] == ""


def _partie_avec_deux_ia(
    personnage_a: str = "",
    aleatoire_a: bool = False,
    personnage_b: str = "",
    aleatoire_b: bool = False,
) -> Partie:
    """Partie à un humain et deux ordinateurs, pour tester le repérage
    « dans cette partie » de la fenêtre « Les personnages » (issue #442, lot F)."""
    joueurs = [
        Joueur(nom="Alice", humain=True),
        Joueur(
            nom="Thomas",
            humain=False,
            niveau=Niveau.FACILE,
            personnage=personnage_a,
            personnage_aleatoire=aleatoire_a,
        ),
        Joueur(
            nom="Marie",
            humain=False,
            niveau=Niveau.FACILE,
            personnage=personnage_b,
            personnage_aleatoire=aleatoire_b,
        ),
    ]
    return Partie(joueurs, _DicoFactice(), graine=1)


class TestApiJeuObtenirPersonnages:
    """Fenêtre « Les personnages » en cours de partie (issue #442, lot F).

    ``ApiJeu.obtenir_personnages`` repère les personnages choisis À L'AVANCE
    par les adversaires de la partie en cours, sans jamais rien révéler d'un
    personnage tiré au hasard — la description de l'issue insiste sur ce
    point comme condition de test explicite.
    """

    def test_sans_partie_chargee_renvoie_la_liste_sans_marquage(self):
        """``ApiJeu()`` vide (pas encore de ``charger_partie``) doit tout de
        même renvoyer la liste complète, simplement sans aucun marquage."""
        api = ApiJeu()
        personnages = api.obtenir_personnages()
        cles = [p["cle"] for p in personnages]
        assert cles == [*PERSONNAGES.keys(), CLE_ALEATOIRE]
        assert all(not p["dans_la_partie"] for p in personnages)

    def test_personnage_choisi_explicitement_est_marque_dans_la_partie(self):
        partie = _partie_avec_deux_ia(personnage_a="opportuniste", aleatoire_a=False)
        api = ApiJeu(partie, id_partie=None)

        personnages = api.obtenir_personnages()

        marques = {p["cle"] for p in personnages if p["dans_la_partie"]}
        assert marques == {"opportuniste"}

    def test_personnage_tire_au_hasard_nest_jamais_marque(self):
        """Même si l'identité réellement tirée est connue du moteur
        (``Joueur.personnage``), le tirage ne doit rien laisser deviner avant
        la fin de la partie : SON entrée (« Opportuniste ») ne doit pas être
        marquée — seule l'entrée Aléatoire l'est (issue #443, lot F bis),
        sans jamais révéler que c'est précisément Opportuniste qui a été
        tiré."""
        partie = _partie_avec_deux_ia(
            personnage_a="opportuniste", aleatoire_a=True
        )
        api = ApiJeu(partie, id_partie=None)

        personnages = api.obtenir_personnages()

        marques = {p["cle"] for p in personnages if p["dans_la_partie"]}
        assert marques == {CLE_ALEATOIRE}
        opportuniste = next(p for p in personnages if p["cle"] == "opportuniste")
        assert opportuniste["dans_la_partie"] is False

    def test_aleatoire_marque_des_quun_adversaire_y_est_regle(self):
        """Issue #443 (lot F bis) : un adversaire choisi explicitement et un
        autre réglé sur Aléatoire cohabitent — le premier est marqué par sa
        propre entrée, ET l'entrée Aléatoire est marquée à son tour (elle ne
        révèle rien : « (Aléatoire) » est déjà affiché à côté du prénom de cet
        adversaire)."""
        partie = _partie_avec_deux_ia(
            personnage_a="opportuniste",
            aleatoire_a=False,
            personnage_b="classique",
            aleatoire_b=True,
        )
        api = ApiJeu(partie, id_partie=None)

        personnages = api.obtenir_personnages()

        marques = {p["cle"] for p in personnages if p["dans_la_partie"]}
        assert marques == {"opportuniste", CLE_ALEATOIRE}

    def test_aleatoire_non_marque_si_aucun_adversaire_regle_dessus(self):
        partie = _partie_avec_deux_ia(personnage_a="opportuniste", aleatoire_a=False)
        api = ApiJeu(partie, id_partie=None)

        personnages = api.obtenir_personnages()

        aleatoire = next(p for p in personnages if p["cle"] == CLE_ALEATOIRE)
        assert aleatoire["dans_la_partie"] is False

    def test_lecture_pure_sans_effet_sur_la_partie(self):
        """Ouvrir la fenêtre ne doit modifier ni le tour en cours, ni l'état
        de la partie, ni rien persister (contrainte explicite de l'issue)."""
        partie = _partie_avec_deux_ia(personnage_a="opportuniste")
        api = ApiJeu(partie, id_partie=None)
        index_avant = partie.index_courant
        terminee_avant = partie.terminee

        api.obtenir_personnages()

        assert partie.index_courant == index_avant
        assert partie.terminee == terminee_avant
        assert partie is api._partie


class TestMemesDonneesAccueilEtJeu:
    """La fenêtre de l'accueil et celle du jeu reposent sur les mêmes données
    et le même composant d'affichage (issue #443, lot F bis, point 4)."""

    def test_meme_cle_prenom_description_sans_partie_chargee(self):
        """Sans partie en cours (cas de l'accueil), ``ApiJeu.obtenir_personnages``
        et ``ApiAccueil.obtenir_personnages`` décrivent exactement les mêmes
        personnages, dans le même ordre."""
        from scrabble.ui.accueil import ApiAccueil

        personnages_jeu = ApiJeu().obtenir_personnages()
        personnages_accueil = ApiAccueil().obtenir_personnages()

        extrait_jeu = [
            {k: p[k] for k in ("cle", "prenom", "description")}
            for p in personnages_jeu
        ]
        extrait_accueil = [
            {k: p[k] for k in ("cle", "prenom", "description")}
            for p in personnages_accueil
        ]
        assert extrait_jeu == extrait_accueil

    def test_les_deux_fenetres_partagent_le_meme_controleur_js(self):
        """``accueil.js`` et ``jeu.js`` construisent tous deux leur modale via
        ``window.Commun.creerModalePersonnages`` (``commun.js``), et les deux
        pages chargent ``personnages.css`` — un seul endroit pour les styles
        de la liste, afin que les deux présentations ne puissent plus
        diverger (voir ``src/scrabble/ui/web/personnages.css``)."""
        from pathlib import Path

        web = Path(__file__).resolve().parents[1] / "src" / "scrabble" / "ui" / "web"
        accueil_js = (web / "accueil.js").read_text(encoding="utf-8")
        jeu_js = (web / "jeu.js").read_text(encoding="utf-8")
        accueil_html = (web / "accueil.html").read_text(encoding="utf-8")
        jeu_html = (web / "jeu.html").read_text(encoding="utf-8")

        assert "creerModalePersonnages" in accueil_js
        assert "creerModalePersonnages" in jeu_js
        assert 'href="personnages.css"' in accueil_html
        assert 'href="personnages.css"' in jeu_html
