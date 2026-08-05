"""Tests des boutons, tours et fin de partie de l'écran de jeu (issue #261).

Couvre :
- apparence des boutons d'échange (issue #147)
- bouton « Jouer » dans la fiche d'un ordinateur (issue #149)
- passage de tour (issue #132)
- enchaînement des tours IA (issue #35)
- retour au menu (issue #74)
- recommencer une partie (issue #142)
- retour au menu en fenêtre unique (issue #193)
"""

import pytest

from scrabble.dictionnaire.dictionnaire import Trie
from scrabble.moteur.ia import Niveau
from scrabble.moteur.partie import Joueur, Partie
from scrabble.persistance import demarrer_suivi, lister_parties
from tests._aides_test_jeu import _DicoFactice, _FenetreEspionne, _partie_simple
from scrabble.ui.jeu import ApiJeu, jouer_tours_ia_ui, passer_tour


class TestApparenceBoutonsEchange:
    """Cohérence visuelle des boutons d'échange dans le markup (issue #147).

    Vérification headless : « Échanger des lettres… » (mode partiel) doit avoir
    l'apparence d'un vrai bouton **dès son état initial**, avant tout clic — la
    même famille visuelle (« btn btn-secondaire ») que « Remettre toutes ses
    lettres et passer » (mode complet, issue #139). Une fois le mode de sélection
    engagé (« après clic »), les boutons révélés (« Échanger la sélection… » /
    « Annuler la sélection ») doivent eux aussi porter le style « btn ».
    """

    @staticmethod
    def _classes(html: str, id_bouton: str) -> list[str]:
        """Renvoie la liste des classes CSS du ``<button id=...>`` demandé."""
        import re

        motif = re.compile(
            r'<button\b[^>]*\bid="' + re.escape(id_bouton) + r'"[^>]*>',
            re.DOTALL,
        )
        balise = motif.search(html)
        assert balise is not None, f"bouton #{id_bouton} introuvable dans jeu.html"
        classe = re.search(r'\bclass="([^"]*)"', balise.group(0))
        assert classe is not None, f"bouton #{id_bouton} sans attribut class"
        return classe.group(1).split()

    def _html(self) -> str:
        from scrabble.ui.jeu import DOSSIER_WEB

        return (DOSSIER_WEB / "jeu.html").read_text(encoding="utf-8")

    def test_bouton_commencer_echange_a_apparence_de_bouton(self):
        """État initial (avant clic) : « Échanger des lettres… » est un vrai bouton."""
        classes = self._classes(self._html(), "btn-commencer-echange")
        assert "btn" in classes
        assert "btn-secondaire" in classes
        # Plus de style « lien discret » : plus de changement d'apparence au clic.
        assert "lien-discret" not in classes

    def test_coherence_entre_modes_complet_et_partiel(self):
        """Les deux déclencheurs d'échange partagent la même famille visuelle."""
        html = self._html()
        complet = self._classes(html, "btn-echanger-tout")
        partiel = self._classes(html, "btn-commencer-echange")
        assert "btn" in complet and "btn-secondaire" in complet
        assert set(complet) == set(partiel)

    def test_boutons_selection_restent_des_boutons(self):
        """Après clic : les boutons de sélection révélés gardent le style « btn »."""
        html = self._html()
        assert "btn" in self._classes(html, "btn-echanger-selection")
        assert "btn" in self._classes(html, "btn-annuler-echange")


class TestBoutonJouerDansFicheJoueur:
    """Bouton « ▶ Jouer » dans la fiche d'un ordinateur courant (issue #149).

    Vérification headless du markup : pendant le tour d'un ordinateur, sa fiche
    joueur expose un bouton « ▶ Jouer » (classe ``panneau-btn-jouer``) à la place
    de l'ancien label « ● son tour », qui déclenche ``api.faire_jouer_ia`` ; l'humain
    courant garde sa pastille « ● à vous ». L'ancien bouton séparé de la zone
    d'attente IA (``#btn-jouer-ia``, « Faire jouer l'ordinateur ») est retiré ; et
    depuis l'issue #160 le cadre d'attente lui-même (« En attente du coup de… ») est
    entièrement supprimé.
    """

    def _lire(self, nom: str) -> str:
        from scrabble.ui.jeu import DOSSIER_WEB

        return (DOSSIER_WEB / nom).read_text(encoding="utf-8")

    def test_fiche_ordinateur_courant_a_un_bouton_jouer(self):
        """La branche « ordinateur courant » produit un bouton « Jouer »."""
        js = self._lire("jeu.js")
        # Le bouton porte la classe dédiée, le style primaire et le texte « Jouer ».
        assert "panneau-btn-jouer" in js
        assert "▶ Jouer" in js
        assert "btn btn-primaire panneau-btn-jouer" in js

    def test_humain_courant_garde_la_pastille_a_vous(self):
        """L'humain courant conserve « ● à vous » (pas de bouton Jouer)."""
        js = self._lire("jeu.js")
        assert "● à vous" in js

    def test_ancien_label_son_tour_retire(self):
        """Le label « son tour » a disparu (remplacé par le bouton Jouer).

        On cible la chaîne LITTÉRALE ``'son tour'`` de l'ancien ternaire de badge ;
        « Passer son tour » (autre fonctionnalité) reste évidemment présent ailleurs.
        """
        js = self._lire("jeu.js")
        assert "'son tour'" not in js

    def test_bouton_declenche_faire_jouer_ia(self):
        """Le bouton de la fiche est câblé au flux api.faire_jouer_ia."""
        js = self._lire("jeu.js")
        # Le bouton du panneau est relié à lancerTourIA, qui appelle l'API.
        assert "querySelector('.panneau-btn-jouer')" in js
        assert "lancerTourIA" in js
        assert "api.faire_jouer_ia()" in js

    def test_ancien_bouton_separe_retire(self):
        """Plus de bouton « Faire jouer l'ordinateur » dans la zone d'attente."""
        html = self._lire("jeu.html")
        js = self._lire("jeu.js")
        assert 'id="btn-jouer-ia"' not in html
        assert "btn-jouer-ia" not in js
        assert "btnJouerIA" not in js

    def test_cadre_attente_supprime(self):
        """Le cadre « En attente du coup de… » est supprimé (issue #160).

        La réorganisation des actions de tour autour de la fiche du joueur humain
        (issue #160) supprime complètement ce bandeau : pendant le tour d'un
        ordinateur, son coup se déclenche déjà via le bouton « ▶ Jouer » de sa
        propre fiche (issue #149), ce cadre n'apportait plus rien. On vérifie que
        ni le conteneur, ni le message, ni le texte ne subsistent.
        """
        html = self._lire("jeu.html")
        js = self._lire("jeu.js")
        assert 'id="zone-attente-ia"' not in html
        assert 'id="attente-ia-message"' not in html
        assert "En attente du coup de" not in js


class TestPasserTour:
    """Passage « sec » du tour (sans échange) — débloque un humain sac vide (#132)."""

    def _partie(self) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
        ]
        partie = Partie(joueurs, _DicoFactice(), graine=3)
        partie.index_courant = 0
        return partie

    def test_passe_incremente_le_compteur_et_avance(self):
        partie = self._partie()
        assert partie.passes_consecutives == 0

        res = passer_tour(partie, None)

        assert res["succes"] is True
        assert "etat" in res
        # La passe a bien été comptée et le tour a avancé, sans terminer (2 joueurs).
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1
        assert partie.terminee is False
        # L'état renvoyé reste public (aucune lettre de chevalet).
        for joueur_pub in res["etat"]["joueurs"]:
            assert "lettres" not in joueur_pub

    def test_humain_sac_vide_peut_passer(self):
        # Cas moteur du rapport #130 : sac vide, l'humain ne peut ni poser ni
        # échanger, mais DOIT pouvoir passer.
        partie = self._partie()
        partie.sac.tirer(partie.sac.jetons_restants())
        assert partie.sac.jetons_restants() == 0

        res = passer_tour(partie, None)

        assert res["succes"] is True
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1

    def test_api_passer_delegue_et_incremente(self):
        partie = self._partie()
        api = ApiJeu(partie, 42)
        res = api.passer()
        assert res["succes"] is True
        assert res["etat"]["id_partie"] == 42
        assert partie.passes_consecutives == 1
        assert partie.index_courant == 1

    def test_passe_refusee_partie_terminee(self):
        partie = self._partie()
        partie.terminee = True

        res = passer_tour(partie, None)

        assert res["succes"] is False
        assert res.get("erreur")
        assert "etat" not in res

    def test_tous_passent_atteint_la_fin_par_blocage(self):
        # De bout en bout : une partie où TOUS les joueurs (ici deux humains)
        # passent consécutivement atteint la fin par blocage — le critère
        # ``passes_consecutives >= len(joueurs)`` est désormais atteignable même
        # avec des humains (via l'API), ce qui était impossible avant #132.
        partie = self._partie()
        api = ApiJeu(partie, id_partie=None)

        res1 = api.passer()
        assert res1["succes"] is True
        assert partie.terminee is False
        assert partie.passes_consecutives == 1

        res2 = api.passer()
        assert res2["succes"] is True
        # Deux joueurs, deux passes consécutives : partie bloquée → terminée.
        assert partie.passes_consecutives >= len(partie.joueurs)
        assert partie.terminee is True
        assert res2["etat"]["terminee"] is True


class TestJouerToursIaUi:
    """Enchaînement des tours IA côté API (jouer_tours_ia_ui / faire_jouer_ia)."""

    def _partie_ia(self) -> Partie:
        """Humain (index 0) puis deux ordinateurs, sur un dictionnaire réel."""
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Robot1", humain=False, niveau=Niveau.EXPERT),
            Joueur(nom="Robot2", humain=False, niveau=Niveau.EXPERT),
        ]
        return Partie(joueurs, Trie.depuis_iterable(["CADRE"]), graine=1)

    def test_joueur_humain_courant_aucun_tour(self):
        partie = self._partie_ia()
        partie.index_courant = 0
        res = jouer_tours_ia_ui(partie, None)
        assert res["succes"] is True
        assert res["nb_tours"] == 0
        assert partie.index_courant == 0  # rien n'a bougé
        assert res["etat"]["index_courant"] == 0

    def test_un_seul_tour_ia_par_appel(self):
        partie = self._partie_ia()
        partie.index_courant = 1  # tour du premier ordinateur
        # Chevalets sans voyelle jouable : les IA passent leur tour (2 de 3 passes
        # consécutives ne terminent pas une partie à 3 joueurs).
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        # Un seul clic = un seul tour d'ordinateur (issue #55) : après cet appel,
        # c'est au tour du DEUXIÈME ordinateur, pas encore à l'humain.
        res = jouer_tours_ia_ui(partie, None)
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert partie.index_courant == 2
        assert partie.joueur_courant().humain is False
        assert res["etat"]["index_courant"] == 2
        assert res["etat"]["tour_humain"] is False
        # Deuxième clic : le second ordinateur joue, puis la main revient à
        # l'humain.
        res2 = jouer_tours_ia_ui(partie, None)
        assert res2["nb_tours"] == 1
        assert partie.index_courant == 0
        assert partie.joueur_courant().humain is True
        assert res2["etat"]["tour_humain"] is True

    def test_api_faire_jouer_ia_delegue(self):
        partie = self._partie_ia()
        partie.index_courant = 1
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        api = ApiJeu(partie, 99)
        # Un seul tour joué par appel (issue #55) : reste au tour du 2e ordinateur.
        res = api.faire_jouer_ia()
        assert res["succes"] is True
        assert res["nb_tours"] == 1
        assert res["etat"]["id_partie"] == 99
        assert partie.index_courant == 2
        assert partie.joueur_courant().humain is False

    def test_api_faire_jouer_ia_sans_effet_si_humain(self):
        partie = self._partie_ia()
        partie.index_courant = 0
        api = ApiJeu(partie, None)
        res = api.faire_jouer_ia()
        assert res["nb_tours"] == 0
        assert partie.index_courant == 0

    def test_faire_jouer_ia_refuse_appel_concurrent(self):
        """Verrou anti-réentrance (issue #364) : un second appel est refusé.

        Simule un clic rapide répété — le panneau reconstruit à chaque
        diffusion peut recréer un bouton « ▶ Jouer » actif avant la réponse
        du premier appel — en posant directement le drapeau ``_ia_en_cours``
        avant d'appeler ``faire_jouer_ia`` une seconde fois : la partie ne
        doit pas avancer.
        """
        partie = self._partie_ia()
        partie.index_courant = 1
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        api = ApiJeu(partie, None)
        api._ia_en_cours = True  # simule un premier appel encore en vol
        res = api.faire_jouer_ia()
        assert res["succes"] is False
        assert "cours" in res["erreur"].lower()
        assert partie.index_courant == 1  # rien n'a bougé

    def test_faire_jouer_ia_remet_le_drapeau_a_zero_apres_exception(self, monkeypatch):
        """Le drapeau ``_ia_en_cours`` est remis à zéro même si le tour explose.

        Garanti par le bloc ``finally`` de ``faire_jouer_ia`` (issue #364) :
        un appel suivant, une fois l'incident passé, doit pouvoir rejouer
        normalement plutôt que rester bloqué en permanence.
        """
        import scrabble.ui.jeu as mod_jeu

        partie = self._partie_ia()
        partie.index_courant = 1
        partie.joueurs[1].chevalet[:] = list("BCDFGHJ")
        partie.joueurs[2].chevalet[:] = list("BCDFGHJ")
        api = ApiJeu(partie, None)

        def _explose(*args, **kwargs):
            raise RuntimeError("boum")

        with monkeypatch.context() as m:
            m.setattr(mod_jeu, "jouer_tours_ia_ui", _explose)
            with pytest.raises(RuntimeError):
                api.faire_jouer_ia()

        assert api._ia_en_cours is False
        # Le patch est levé : un appel suivant fonctionne à nouveau normalement.
        res = api.faire_jouer_ia()
        assert res["succes"] is True
        assert res["nb_tours"] == 1


class TestApiJeuRetourMenu:
    """Tests de ``ApiJeu.retour_menu`` (issue #74).

    Vérifie que la fenêtre de jeu est fermée depuis Python via
    ``window.destroy()`` (fiable sous GTK/WebKit, issues #53/#57) et que le
    drapeau ``_retour_menu`` est positionné pour que ``lancer_jeu`` rouvre
    l'accueil. Testé sans vraie fenêtre grâce à un objet factice.
    """

    def test_retour_menu_appelle_destroy_et_marque_le_drapeau(self):
        class FakeWindow:
            def __init__(self):
                self.detruite = False

            def destroy(self):
                self.detruite = True

        api = ApiJeu(_partie_simple(), id_partie=7)
        fake = FakeWindow()
        api.set_window(fake)

        resultat = api.retour_menu()

        assert resultat["succes"] is True
        assert fake.detruite is True
        assert api._retour_menu is True

    def test_retour_menu_sans_fenetre(self):
        api = ApiJeu(_partie_simple(), id_partie=None)
        resultat = api.retour_menu()

        assert resultat["succes"] is False
        assert "erreur" in resultat
        # Aucune fenêtre : pas de retour au menu déclenché.
        assert api._retour_menu is False

    def test_retour_menu_exception_destroy_naboutit_pas(self):
        class FakeWindow:
            def destroy(self):
                raise RuntimeError("backend HS")

        api = ApiJeu(_partie_simple(), id_partie=1)
        api.set_window(FakeWindow())

        resultat = api.retour_menu()

        assert resultat["succes"] is False
        assert "backend HS" in resultat["erreur"]
        # La fermeture a échoué : on ne rouvrira PAS l'accueil.
        assert api._retour_menu is False


class TestApiJeuRecommencer:
    """Tests de ``ApiJeu.recommencer`` / ``creer_partie_recommencee`` (issue #142).

    Vérifie que « Recommencer » fabrique une nouvelle partie avec les mêmes
    joueurs (nom, humain/IA, niveau), qu'elle est suivie en base sans supprimer
    l'ancienne partie, et que les deux fenêtres sont fermées (drapeau
    ``_recommencer``). Testé sans vraie fenêtre grâce à un objet factice.
    """

    class _FakeWindow:
        def __init__(self):
            self.detruite = False

        def destroy(self):
            self.detruite = True

    def _partie_mixte(self, graine: int = 3) -> Partie:
        joueurs = [
            Joueur(nom="Alice", humain=True),
            Joueur(nom="Bob", humain=True),
            Joueur(nom="Ordi", humain=False, niveau=Niveau.EXPERT),
        ]
        return Partie(joueurs, _DicoFactice(), graine=graine)

    def test_creer_partie_recommencee_memes_joueurs(self):
        origine = self._partie_mixte()
        api = ApiJeu(origine, id_partie=None)

        nouvelle = api.creer_partie_recommencee()

        assert nouvelle is not origine
        cle = lambda p: {(j.nom, j.humain, j.niveau) for j in p.joueurs}
        assert cle(nouvelle) == cle(origine)
        # Partie neuve : graine explicite (pour le suivi), historique vierge.
        assert nouvelle.graine is not None
        assert nouvelle.historique == []
        assert not nouvelle.terminee

    def test_recommencer_persiste_la_nouvelle_sans_supprimer_l_ancienne(self, tmp_path):
        chemin = tmp_path / "parties.db"
        origine = self._partie_mixte()
        id_origine = demarrer_suivi(origine, chemin)

        api = ApiJeu(origine, id_partie=id_origine, chemin_persistance=chemin)
        fake = self._FakeWindow()
        api.set_window(fake)

        resultat = api.recommencer()

        assert resultat["succes"] is True
        assert fake.detruite is True
        assert api._recommencer is True
        assert api._nouvelle_partie is not None
        # Un nouvel identifiant, distinct de l'ancien, a été attribué.
        assert api._nouvel_id_partie is not None
        assert api._nouvel_id_partie != id_origine
        # L'ancienne partie n'a PAS été supprimée : les deux coexistent en base.
        ids = {p.id for p in lister_parties(chemin)}
        assert ids == {id_origine, api._nouvel_id_partie}

    def test_recommencer_mode_demo_ne_persiste_pas(self):
        # id_partie None (démonstration) : la nouvelle partie n'est pas suivie,
        # mais la mécanique de fermeture/relance fonctionne quand même.
        api = ApiJeu(self._partie_mixte(), id_partie=None)
        fake = self._FakeWindow()
        api.set_window(fake)

        resultat = api.recommencer()

        assert resultat["succes"] is True
        assert api._recommencer is True
        assert api._nouvelle_partie is not None
        assert api._nouvel_id_partie is None

    def test_recommencer_sans_fenetre(self):
        api = ApiJeu(self._partie_mixte(), id_partie=None)
        resultat = api.recommencer()

        assert resultat["succes"] is False
        assert "erreur" in resultat
        assert api._recommencer is False
        assert api._nouvelle_partie is None

    def test_recommencer_exception_destroy_naboutit_pas(self):
        class FakeWindowKO:
            def destroy(self):
                raise RuntimeError("backend HS")

        api = ApiJeu(self._partie_mixte(), id_partie=None)
        api.set_window(FakeWindowKO())

        resultat = api.recommencer()

        assert resultat["succes"] is False
        assert "backend HS" in resultat["erreur"]
        # Échec de fermeture : on n'enchaîne PAS de nouvelle partie.
        assert api._recommencer is False
        assert api._nouvelle_partie is None


class TestApiJeuRetourMenuFenetreUnique:
    """``retour_menu`` détruit la fenêtre unique (issue #193)."""

    def test_retour_menu_avec_seule_fenetre_plateau(self):
        # Compat mono-fenêtre : set_window ne renseigne que le plateau.
        api = ApiJeu(_partie_simple(), id_partie=1)
        fake = _FenetreEspionne()
        api.set_window(fake)
        res = api.retour_menu()
        assert res["succes"] is True
        assert fake.detruite is True
        # « Retour au menu » repositionne le drapeau qui rouvre l'accueil.
        assert api._retour_menu is True
