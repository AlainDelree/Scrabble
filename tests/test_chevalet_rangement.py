"""Tests des boutons de rangement du chevalet « tout à gauche / tout à droite »
(issue #373, lot H).

Le réarrangement du chevalet — manuel (clic-clic, drag droit) comme celui de
ces deux nouveaux boutons — est une pure mécanique JS locale : Python ne
sérialise jamais d'ordre de chevalet (voir ``obtenir_chevalet``/
``serialiser_chevalet``, ``api_tirage_ordre.py``/``jeu.py``), seulement
l'ensemble des lettres. Il n'y a donc rien à tester côté Python pour cette
fonctionnalité ; on vérifie ici, comme pour le lot F (issue #371,
``test_accueil_niveaux_visuels.py``), le markup et la logique JS par lecture
statique des fichiers de ``ui/web/``.
"""

import re

from scrabble.ui.jeu import DOSSIER_WEB


def _lire(nom: str) -> str:
    return (DOSSIER_WEB / nom).read_text(encoding="utf-8")


class TestBoutonsPresents:
    """Les deux boutons existent dans le markup, avec un ``title`` explicite."""

    def test_bouton_gauche_present(self):
        html = _lire("jeu.html")
        assert 'id="btn-ranger-gauche"' in html

    def test_bouton_droite_present(self):
        html = _lire("jeu.html")
        assert 'id="btn-ranger-droite"' in html

    def test_boutons_ont_un_title_comprehensible(self):
        html = _lire("jeu.html")
        for id_bouton in ("btn-ranger-gauche", "btn-ranger-droite"):
            m = re.search(
                r'<button\b[^>]*\bid="' + id_bouton + r'"[^>]*>', html
            )
            assert m, f"{id_bouton} introuvable"
            balise = m.group(0)
            assert 'title="' in balise and 'title=""' not in balise, (
                f"{id_bouton} sans title exploitable au survol"
            )

    def test_boutons_reutilisent_la_classe_cible_accessible(self):
        """Cible de clic suffisamment grande (public senior, issue #373) :
        réutilise ``.btn-icone-seule`` (min 40px), déjà éprouvée pour
        « ↻ Resynchroniser »."""
        html = _lire("jeu.html")
        for id_bouton in ("btn-ranger-gauche", "btn-ranger-droite"):
            m = re.search(
                r'<button\b[^>]*\bid="' + id_bouton + r'"[^>]*>', html
            )
            assert "btn-icone-seule" in m.group(0)

    def test_css_min_width_40px_pour_cible_accessible(self):
        css = _lire("jeu.css")
        bloc = re.search(r"\.btn-icone-seule\s*\{([^}]+)\}", css)
        assert bloc, ".btn-icone-seule introuvable dans jeu.css"
        assert "min-width: 40px" in bloc.group(1)


class TestCablageJS:
    """Les boutons sont câblés à la fonction de rangement dans jeu.js."""

    def test_ecouteurs_de_clic_presents(self):
        js = _lire("jeu.js")
        assert "btnRangerGauche.addEventListener('click'" in js
        assert "btnRangerDroite.addEventListener('click'" in js

    def test_appel_avec_la_bonne_direction(self):
        js = _lire("jeu.js")
        assert "rangerChevalet('gauche')" in js
        assert "rangerChevalet('droite')" in js

    def test_fonction_rangerChevalet_definie(self):
        js = _lire("jeu.js")
        assert "function rangerChevalet(direction)" in js


class TestCompactageLogiqueJS:
    """Comportement attendu de ``rangerChevalet`` (lecture statique du corps).

    On ne peut pas exécuter le JS directement en pytest (pas de moteur JS
    dans la suite) : on vérifie donc, comme le lot F pour les maps de
    libellés, la PRÉSENCE des garde-fous attendus dans le corps de la
    fonction — chevalet vide, mode échange partiel, lettres déjà posées en
    attente (« utilisee ») laissées de côté, ordre relatif préservé.
    """

    @staticmethod
    def _corps() -> str:
        js = _lire("jeu.js")
        m = re.search(
            r"function rangerChevalet\(direction\) \{(.*?)\n    \}",
            js,
            re.DOTALL,
        )
        assert m, "corps de rangerChevalet introuvable"
        return m.group(1)

    def test_ignore_le_mode_echange_partiel(self):
        """Cas limite : pas de rangement pendant le marquage d'échange partiel
        (issue #138) — même restriction que le clic droit existant."""
        corps = self._corps()
        assert "enModeEchange()" in corps

    def test_ignore_chevalet_vide(self):
        corps = self._corps()
        assert "panneauLettres.length === 0" in corps

    def test_ne_deplace_pas_les_lettres_deja_posees(self):
        """Cas limite : une pose en cours (lettre « utilisee ») n'est jamais
        perturbée — seules les lettres RESTANTES du chevalet bougent (choix
        documenté dans le commentaire de la fonction, issue #373)."""
        corps = self._corps()
        assert "indexUtilises" in corps or "utilises" in corps
        assert "utilises.has(l.indexOrigine)" in corps

    def test_preserve_l_ordre_relatif_sans_trier(self):
        """Le compactage lit ``lettresLibres`` dans l'ordre d'apparition puis
        les replace dans ce même ordre — aucun ``.sort()`` n'intervient."""
        corps = self._corps()
        assert ".sort(" not in corps

    def test_decalage_nul_a_gauche_et_vers_la_fin_a_droite(self):
        corps = self._corps()
        assert "direction === 'droite'" in corps
        assert "positions.length - lettresLibres.length" in corps


class TestPersistanceChevaletCotePython:
    """Constat de l'issue (point 3) : l'ordre du chevalet est-il persisté ?

    Réponse : NON — ni pour le réarrangement manuel existant, ni pour ces
    nouveaux boutons. ``serialiser_chevalet``/``obtenir_chevalet`` ne
    sérialisent qu'un ENSEMBLE de lettres (dans l'ordre du modèle Python,
    inchangé par la réflexion JS) ; le réarrangement visuel ne vit que dans
    ``panneauLettres`` côté navigateur et est reconstruit dès que le contenu
    du chevalet change (nouveau tirage, échange) — voir
    ``reconstruirePanneau``/``appliquerEtatChevalet``. Les boutons de
    rangement suivent exactement le même mécanisme que le glisser au clic
    déjà en place : ni plus ni moins persistants que lui, donc aucune
    régression introduite. Ce test documente ce constat pour éviter qu'une
    future modification ne le suppose à tort persisté côté serveur.
    """

    def test_obtenir_chevalet_ne_renvoie_pas_de_champ_ordre(self):
        import inspect

        from scrabble.ui.api_tirage_ordre import MixinTirageOrdre

        source = inspect.getsource(MixinTirageOrdre.obtenir_chevalet)
        assert "ordre" not in source.lower()

    def test_reconstruction_du_panneau_efface_le_rangement_local(self):
        """``reconstruirePanneau`` reconstruit ``panneauLettres`` depuis
        ``etatChevalet.lettres`` (l'ordre Python) : tout rangement local —
        manuel ou via ces boutons — est perdu au tirage/échange suivant."""
        js = _lire("jeu.js")
        m = re.search(r"function reconstruirePanneau\(\) \{(.*?)\n    \}", js, re.DOTALL)
        assert m, "reconstruirePanneau introuvable"
        assert "etatChevalet.lettres" in m.group(1)
