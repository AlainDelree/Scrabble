"""Synchronisation dynamique de la hauteur du tour IA — logique pure (issue #96).

Point A de l'issue #96 : la hauteur de la zone d'attente du tour IA
(``.zone-attente-ia``) n'est plus une constante de pixels figée (échecs #92/#94,
Chromium ≠ WebKitGTK) mais est calée dynamiquement, au moteur de rendu courant,
sur la hauteur RÉELLEMENT mesurée de la zone interactive du tour humain.

L'arithmétique de cette synchronisation est isolée, PURE (sans DOM), dans
``src/scrabble/ui/web/hauteur_attente.js`` afin d'être testable sans vrai moteur
de rendu. Ce test l'exécute sous Node avec des hauteurs de DOM **simulées** et
vérifie que le ``min-height`` appliqué suit bien la plus grande hauteur observée
(et non une valeur figée). C'est exactement le comportement que les constantes
figées ne pouvaient pas offrir : suivre les différences de rendu entre moteurs.

Le test se termine de lui-même (Node, ``timeout`` explicite) : il n'ouvre aucune
fenêtre graphique et ne dépend d'aucune fermeture manuelle. Il est ignoré (skip)
si Node.js n'est pas installé.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE_JS = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "scrabble"
    / "ui"
    / "web"
    / "hauteur_attente.js"
)


def _executer_scenarios(scenarios: dict) -> dict:
    """Exécute ``hauteur_attente.js`` sous Node sur des séquences de hauteurs.

    ``scenarios`` associe un nom à une liste de hauteurs mesurées successives
    (des nombres, ou ``null`` pour une mesure absente). Pour chaque scénario, on
    rejoue la logique de chevalet.js : on part d'un maximum ``null`` (aucune mesure
    encore, repli CSS) puis on cumule chaque hauteur via ``cumulerHauteur`` et on
    calcule le ``min-height`` correspondant via ``minHeightAttente``. Renvoie, par
    scénario, la liste des ``{max, minHeight}`` après chaque étape.
    """
    node = shutil.which("node")
    if node is None:  # pragma: no cover - dépend de l'environnement CI
        pytest.skip("Node.js indisponible : logique JS de synchronisation non testée.")
    driver = (
        "const H = require(process.argv[1]);\n"
        "const scenarios = JSON.parse(process.argv[2]);\n"
        "const sortie = {};\n"
        "for (const [nom, hauteurs] of Object.entries(scenarios)) {\n"
        "  let max = null;\n"
        "  const etapes = [];\n"
        "  for (const h of hauteurs) {\n"
        "    max = H.cumulerHauteur(max, h);\n"
        "    etapes.push({ max: max, minHeight: H.minHeightAttente(max) });\n"
        "  }\n"
        "  sortie[nom] = etapes;\n"
        "}\n"
        "process.stdout.write(JSON.stringify(sortie));\n"
    )
    resultat = subprocess.run(
        [node, "-e", driver, str(MODULE_JS), json.dumps(scenarios)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultat.returncode == 0, resultat.stderr
    return json.loads(resultat.stdout)


def test_le_module_existe() -> None:
    """Garde-fou : le module de synchronisation est bien présent (wiring HTML)."""
    assert MODULE_JS.is_file()


def test_premier_tour_ia_avant_tout_tour_humain_utilise_le_repli() -> None:
    """Aucune mesure encore : ``min-height`` reste ``null`` → repli CSS en vigueur."""
    sortie = _executer_scenarios({"repli": [None]})
    etape = sortie["repli"][0]
    assert etape["max"] is None
    assert etape["minHeight"] is None


def test_min_height_suit_la_hauteur_mesuree() -> None:
    """Une hauteur mesurée devient le ``min-height`` (arrondi au pixel)."""
    sortie = _executer_scenarios({"mesure": [280]})
    assert sortie["mesure"][0] == {"max": 280, "minHeight": "280px"}


def test_min_height_cumule_le_maximum_et_ne_redescend_pas() -> None:
    """Le tour humain le plus haut fixe le plancher ; une mesure plus courte
    ensuite ne rabaisse pas la zone d'attente (empreinte stable)."""
    sortie = _executer_scenarios({"cumul": [280, 300, 250]})
    etapes = sortie["cumul"]
    assert [e["minHeight"] for e in etapes] == ["280px", "300px", "300px"]
    # Le maximum ne redescend jamais sous la plus grande valeur vue.
    assert etapes[-1]["max"] == 300


def test_mesure_nulle_ou_absente_est_ignoree() -> None:
    """Une hauteur 0 (zone masquée) ou ``null`` laisse le maximum inchangé."""
    sortie = _executer_scenarios(
        {
            "zero_puis_mesure": [0, 288],
            "mesure_puis_zero": [288, 0],
            "mesure_puis_null": [288, None],
        }
    )
    # Une mesure nulle initiale ne fige rien : repli CSS jusqu'à une vraie mesure.
    assert sortie["zero_puis_mesure"][0] == {"max": None, "minHeight": None}
    assert sortie["zero_puis_mesure"][1] == {"max": 288, "minHeight": "288px"}
    # Une mesure nulle APRÈS coup ne détruit pas le maximum déjà acquis.
    assert sortie["mesure_puis_zero"][1] == {"max": 288, "minHeight": "288px"}
    assert sortie["mesure_puis_null"][1] == {"max": 288, "minHeight": "288px"}


def test_sous_pixels_arrondis() -> None:
    """Les sous-pixels de getBoundingClientRect sont arrondis à l'entier CSS."""
    sortie = _executer_scenarios({"arrondi": [280.6]})
    assert sortie["arrondi"][0]["minHeight"] == "281px"


def test_suit_le_moteur_courant_et_non_une_constante_figee() -> None:
    """Cœur de l'issue #96 : simulant une mesure « Chromium » (221 px, la constante
    figée de #94) suivie de la mesure du moteur réel (WebKitGTK, plus haute), le
    ``min-height`` s'aligne sur le moteur COURANT — jamais bloqué sur la valeur figée."""
    sortie = _executer_scenarios({"moteurs": [221, 280]})
    etapes = sortie["moteurs"]
    # La zone d'attente adopte la hauteur réelle du rendu courant (280), pas 221.
    assert etapes[-1]["minHeight"] == "280px"
    assert etapes[-1]["max"] == 280
