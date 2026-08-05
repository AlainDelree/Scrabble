"""Tests du rendu visuel des 6 niveaux à l'écran d'accueil (issue #371, lot F).

Couvre les parties non-Python de ce lot par lecture directe des fichiers
statiques (même technique que ``tests/test_jeu_tour_fin_partie.py`` pour
jeu.html/jeu.js) :

- le 6e bouton « Champion du monde » (accueil.html) ;
- le dégradé à six paliers et son contraste WCAG AA **par bande**
  (accueil.css) ;
- les maps de libellés de niveau côté JS (accueil.js, jeu.js), avec un
  garde-fou paramétré sur tous les membres de :class:`Niveau` (sur le modèle
  du test paramétré du lot D, issue #368) ;
- la consommation JS de ``ApiAccueil.obtenir_disponibilite_niveaux``.
"""

import re

import pytest

from scrabble.moteur.ia import Niveau
from scrabble.ui.accueil import DOSSIER_WEB, NIVEAUX_LABELS


def _lire(nom: str) -> str:
    return (DOSSIER_WEB / nom).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Contraste WCAG AA (formule officielle de luminance relative) — utilitaires
# purement locaux à ce fichier de test, aucune dépendance externe.
# --------------------------------------------------------------------------- #

def _linearise(c: int) -> float:
    c_norme = c / 255
    if c_norme <= 0.03928:
        return c_norme / 12.92
    return ((c_norme + 0.055) / 1.055) ** 2.4


def _luminance(hex_couleur: str) -> float:
    hex_couleur = hex_couleur.lstrip("#")
    r, g, b = (int(hex_couleur[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linearise(r) + 0.7152 * _linearise(g) + 0.0722 * _linearise(b)


def _contraste(hex1: str, hex2: str) -> float:
    l1, l2 = _luminance(hex1), _luminance(hex2)
    l1, l2 = max(l1, l2), min(l1, l2)
    return (l1 + 0.05) / (l2 + 0.05)


SEUIL_AA = 4.5


class TestSixiemeBouton:
    """Le bouton « Champion du monde » est présent à l'accueil (issue #371)."""

    def test_bouton_champion_du_monde_present(self):
        html = _lire("accueil.html")
        assert 'data-niveau="Champion du monde"' in html
        assert re.search(
            r'data-niveau="Champion du monde">\s*Champion du monde\s*<', html
        )

    @pytest.mark.parametrize("label", list(NIVEAUX_LABELS))
    def test_chaque_label_a_son_bouton(self, label):
        """Chaque entrée de NIVEAUX_LABELS a un bouton correspondant dans le HTML.

        Paramétré sur NIVEAUX_LABELS (pas une liste en dur) : un futur ajout de
        niveau fera échouer ce test tant que le bouton HTML n'existe pas.
        """
        html = _lire("accueil.html")
        assert f'data-niveau="{label}"' in html

    def test_exactement_six_boutons_de_niveau(self):
        html = _lire("accueil.html")
        boutons = re.findall(r'class="btn btn-niveau" data-niveau="([^"]+)"', html)
        assert len(boutons) == len(NIVEAUX_LABELS) == 6
        assert set(boutons) == set(NIVEAUX_LABELS)


class TestDegradeSixPaliers:
    """Dégradé crème → brun à six arrêts, contraste WCAG AA par bande (issue #371)."""

    @staticmethod
    def _blocs_repos(css: str) -> dict:
        """{niveau: {"background": hex, "color": hex}} pour l'état au repos."""
        blocs = {}
        for m in re.finditer(
            r'\[data-niveau="([^"]+)"\]\s*\{([^}]+)\}', css
        ):
            niveau, corps = m.group(1), m.group(2)
            bg = re.search(r"background:\s*(#[0-9a-fA-F]{6})", corps)
            couleur = re.search(r"\bcolor:\s*(#[0-9a-fA-F]{6})", corps)
            if bg and couleur:
                blocs[niveau] = {"background": bg.group(1), "color": couleur.group(1)}
        return blocs

    @staticmethod
    def _blocs_survol(css: str) -> dict:
        """{niveau: {"background": hex, "color": hex ou None}} pour :hover."""
        blocs = {}
        for m in re.finditer(
            r'\[data-niveau="([^"]+)"\]:hover:not\(:disabled\)\s*\{([^}]+)\}', css
        ):
            niveau, corps = m.group(1), m.group(2)
            bg = re.search(r"background:\s*(#[0-9a-fA-F]{6})", corps)
            couleur = re.search(r"\bcolor:\s*(#[0-9a-fA-F]{6})", corps)
            if bg:
                blocs[niveau] = {
                    "background": bg.group(1),
                    "color": couleur.group(1) if couleur else None,
                }
        return blocs

    def test_six_paliers_definis_au_repos(self):
        css = _lire("accueil.css")
        blocs = self._blocs_repos(css)
        assert set(blocs) == set(NIVEAUX_LABELS)

    def test_six_paliers_definis_au_survol(self):
        css = _lire("accueil.css")
        blocs = self._blocs_survol(css)
        assert set(blocs) == set(NIVEAUX_LABELS)

    @pytest.mark.parametrize("niveau", list(NIVEAUX_LABELS))
    def test_contraste_aa_au_repos(self, niveau):
        css = _lire("accueil.css")
        bloc = self._blocs_repos(css)[niveau]
        ratio = _contraste(bloc["background"], bloc["color"])
        assert ratio >= SEUIL_AA, (
            f"{niveau} : contraste {bloc['background']}/{bloc['color']} = "
            f"{ratio:.2f} < {SEUIL_AA} (repos)"
        )

    @pytest.mark.parametrize("niveau", list(NIVEAUX_LABELS))
    def test_contraste_aa_au_survol(self, niveau):
        css = _lire("accueil.css")
        repos = self._blocs_repos(css)[niveau]
        survol = self._blocs_survol(css)[niveau]
        couleur = survol["color"] or repos["color"]
        ratio = _contraste(survol["background"], couleur)
        assert ratio >= SEUIL_AA, (
            f"{niveau} : contraste {survol['background']}/{couleur} = "
            f"{ratio:.2f} < {SEUIL_AA} (survol)"
        )

    def test_degrade_est_monotone_du_plus_clair_au_plus_fonce(self):
        """Chaque palier est strictement plus sombre que le précédent.

        Vérifie l'ORDRE visuel voulu par l'issue (« crème → brun du plus
        clair au plus foncé, Champion du monde étant le plus foncé »), pas
        seulement le contraste individuel de chaque bande.
        """
        css = _lire("accueil.css")
        blocs = self._blocs_repos(css)
        ordre = ["Débutant", "Facile", "Intermédiaire", "Avancé", "Expert",
                 "Champion du monde"]
        luminances = [_luminance(blocs[n]["background"]) for n in ordre]
        assert luminances == sorted(luminances, reverse=True)

    def test_bordure_expert_pas_reutilisee_comme_fond_champion(self):
        """#3d2606 (bordure d'Expert) ne doit pas devenir le fond de Champion.

        L'issue signale explicitement ce piège : réutiliser #3d2606 (déjà
        l'ancien survol d'Expert, et toujours sa bordure) comme fond de
        Champion du monde ferait coïncider un nouveau fond au repos avec une
        couleur déjà porteuse d'un autre sens visuel dans le dégradé.
        """
        css = _lire("accueil.css")
        blocs = self._blocs_repos(css)
        assert blocs["Champion du monde"]["background"].lower() != "#3d2606"


class TestLabelsNiveauJS:
    """Maps JS de libellés de niveau : garde-fou paramétré (issue #371, lot F).

    Sur le modèle du test paramétré du lot D (issue #368) : itérer sur TOUS
    les membres de :class:`Niveau` plutôt qu'une liste en dur fait échouer ce
    test automatiquement si un futur niveau est ajouté sans mettre à jour ces
    deux maps JS.
    """

    @staticmethod
    def _bloc_accueil_js() -> str:
        js = _lire("accueil.js")
        m = re.search(r"const niveauLabel = \{(.*?)\}\[joueur\.niveau\]", js, re.DOTALL)
        assert m, "map niveauLabel introuvable dans accueil.js"
        return m.group(1)

    @staticmethod
    def _bloc_jeu_js() -> str:
        js = _lire("jeu.js")
        m = re.search(
            r"const niveauLabel = joueur\.niveau\s*\?\s*\(\{(.*?)\}\[joueur\.niveau\]",
            js,
            re.DOTALL,
        )
        assert m, "map niveauLabel introuvable dans jeu.js"
        return m.group(1)

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_accueil_js_couvre_tous_les_niveaux(self, niveau):
        bloc = self._bloc_accueil_js()
        assert re.search(rf"\b{niveau.name}\b", bloc), (
            f"{niveau.name} absent de la map niveauLabel d'accueil.js"
        )

    @pytest.mark.parametrize("niveau", list(Niveau))
    def test_jeu_js_couvre_tous_les_niveaux(self, niveau):
        bloc = self._bloc_jeu_js()
        assert re.search(rf"\b{niveau.name}\b", bloc), (
            f"{niveau.name} absent de la map niveauLabel de jeu.js "
            "(badge affiché derrière le prénom du joueur)"
        )

    def test_jeu_js_avance_correctement_accentue(self):
        """Défaut antérieur signalé par le rapport du lot D : « AVANCE » brut
        s'affichait faute d'entrée dans la map, au lieu de « Avancé »."""
        bloc = self._bloc_jeu_js()
        assert "AVANCE: 'Avancé'" in bloc or "AVANCE : 'Avancé'" in bloc


class TestDisponibiliteNiveauxConsommeeParJS:
    """`ApiAccueil.obtenir_disponibilite_niveaux` doit être consommée par accueil.js."""

    def test_accueil_js_appelle_obtenir_disponibilite_niveaux(self):
        js = _lire("accueil.js")
        assert "api.obtenir_disponibilite_niveaux()" in js

    def test_appel_a_lieu_a_l_affichage_pas_seulement_au_clic(self):
        """Le contrôle doit avoir lieu à l'affichage (issue #371), pas
        seulement être câblé dans le gestionnaire de clic."""
        js = _lire("accueil.js")
        assert "await appliquerDisponibiliteNiveaux()" in js

    def test_bouton_indisponible_reste_cliquable_avec_message(self):
        """Un <button disabled> natif ne reçoit aucun clic : le message
        « au clic » exigé par l'issue impose de NE PAS désactiver nativement
        le bouton indisponible (classe CSS dédiée à la place)."""
        js = _lire("accueil.js")
        assert "niveau-indisponible" in js
        assert "btn.title = message" in js

    def test_css_definit_le_style_indisponible(self):
        css = _lire("accueil.css")
        assert ".niveau-indisponible" in css
