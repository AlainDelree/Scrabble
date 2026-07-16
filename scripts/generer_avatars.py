"""Générateur ponctuel des avatars SVG de joueur (issue #34).

Produit une bibliothèque d'avatars ORIGINAUX, simples et stylisés : des
portraits de visages caricaturaux (aucune reproduction d'œuvre protégée),
chacun combinant quelques traits distinctifs (couleur de peau, coiffure,
lunettes, chapeau, moustache, barbe, boucles d'oreilles…) afin de rester
reconnaissable même en petite taille (panneaux joueur de 160px, bandeau bas).

Ce script est un outil de fabrication ponctuel : il n'est pas importé par
l'application. Les fichiers .svg qu'il génère (avatar-01.svg … avatar-15.svg)
sont la véritable livraison et sont versionnés ; on peut le relancer pour
régénérer la bibliothèque à l'identique (rendu déterministe, aucun aléa).
"""

from pathlib import Path

DEST = Path(__file__).parent.parent / "src/scrabble/ui/web/avatars"

# Traits de la peau, de la coiffure et du bas de vêtement (couleurs).
SKINS = {
    "clair": "#f6d3b0",
    "hale": "#e0ac69",
    "mat": "#c68642",
    "brun": "#8d5524",
    "fonce": "#6b4226",
}


def _hair(top_only=True, color="#2b2b2b"):
    """Casquette de cheveux couvrant le haut du crâne."""
    return (
        f'<path d="M16 30 Q16 11 32 11 Q48 11 48 30 '
        f'Q48 20 32 20 Q16 20 16 30 Z" fill="{color}"/>'
    )


def _hair_long(color):
    """Cheveux longs tombant de part et d'autre du visage."""
    return (
        f'<path d="M15 44 Q13 16 32 12 Q51 16 49 44 '
        f'L45 44 Q47 22 32 21 Q17 22 19 44 Z" fill="{color}"/>'
    )


def _bun(color):
    """Chignon : petite coiffe + boule au sommet."""
    return (
        f'<circle cx="32" cy="10" r="5" fill="{color}"/>'
        + _hair(color=color)
    )


def _curly(color):
    """Cheveux bouclés : chapelet de cercles sur le haut du crâne."""
    cercles = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}"/>'
        for cx, cy in [(18, 24), (24, 16), (32, 13), (40, 16), (46, 24), (20, 30), (44, 30)]
    )
    return cercles


def _bald_sides(color):
    """Crâne dégarni : cheveux uniquement sur les côtés."""
    return (
        f'<path d="M16 34 Q15 24 20 22 L20 30 Q17 32 17 34 Z" fill="{color}"/>'
        f'<path d="M48 34 Q49 24 44 22 L44 30 Q47 32 47 34 Z" fill="{color}"/>'
    )


def _glasses(color="#333"):
    return (
        f'<g fill="none" stroke="{color}" stroke-width="1.6">'
        f'<circle cx="25" cy="30" r="4.2"/><circle cx="39" cy="30" r="4.2"/>'
        f'<line x1="29.2" y1="30" x2="34.8" y2="30"/>'
        f'<line x1="20.8" y1="30" x2="17" y2="28.5"/>'
        f'<line x1="43.2" y1="30" x2="47" y2="28.5"/></g>'
    )


def _mustache(color):
    return (
        f'<path d="M25 37.5 Q28.5 36 32 37.8 Q35.5 36 39 37.5 '
        f'Q35.5 40 32 38.6 Q28.5 40 25 37.5 Z" fill="{color}"/>'
    )


def _beard(color):
    return (
        f'<path d="M18 32 Q18 49 32 49 Q46 49 46 32 '
        f'Q46 41 32 41 Q18 41 18 32 Z" fill="{color}"/>'
    )


def _hat_cap(color, visor="#00000033"):
    """Casquette à visière."""
    return (
        f'<path d="M15 22 Q32 6 49 22 Q40 17 32 17 Q24 17 15 22 Z" fill="{color}"/>'
        f'<path d="M15 22 Q10 22 9 25 L24 24 Q20 22 15 22 Z" fill="{visor}"/>'
    )


def _hat_top(color):
    """Chapeau haut-de-forme stylisé."""
    return (
        f'<rect x="21" y="4" width="22" height="14" rx="2" fill="{color}"/>'
        f'<rect x="14" y="17" width="36" height="4" rx="2" fill="{color}"/>'
    )


def _beret(color):
    return (
        f'<path d="M15 22 Q16 12 32 12 Q48 12 49 22 '
        f'Q40 18 32 18 Q24 18 15 22 Z" fill="{color}"/>'
        f'<circle cx="46" cy="12" r="2.5" fill="{color}"/>'
    )


def _earrings(color="#f1c40f"):
    return (
        f'<circle cx="17" cy="36" r="1.8" fill="{color}"/>'
        f'<circle cx="47" cy="36" r="1.8" fill="{color}"/>'
    )


def _bow(color):
    return (
        f'<path d="M28 12 L24 9 L24 15 Z" fill="{color}"/>'
        f'<path d="M36 12 L40 9 L40 15 Z" fill="{color}"/>'
        f'<circle cx="32" cy="12" r="2" fill="{color}"/>'
    )


def avatar(bg, skin, shirt, features):
    """Assemble un avatar : fond circulaire, épaules, visage et traits."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'width="64" height="64" role="img">',
        '<defs><clipPath id="cadre"><circle cx="32" cy="32" r="32"/></clipPath></defs>',
        '<g clip-path="url(#cadre)">',
        f'<rect width="64" height="64" fill="{bg}"/>',
        # Épaules (buste) et cou.
        f'<path d="M9 64 Q9 49 22 46 L42 46 Q55 49 55 64 Z" fill="{shirt}"/>',
        f'<rect x="28" y="40" width="8" height="8" fill="{skin}"/>',
        # Oreilles + visage.
        f'<circle cx="17" cy="32" r="3.4" fill="{skin}"/>',
        f'<circle cx="47" cy="32" r="3.4" fill="{skin}"/>',
        f'<circle cx="32" cy="30" r="15" fill="{skin}"/>',
    ]
    # Ordre d'empilement : cheveux d'abord (derrière visage déjà posé), puis
    # traits du visage, puis accessoires par-dessus. Les helpers gèrent le placement.
    parts.extend(features.get("arriere", []))
    # Yeux + bouche par défaut (sauf si masqués par des lunettes gérées à part).
    parts.append('<circle cx="25" cy="30" r="1.9" fill="#3a2a20"/>')
    parts.append('<circle cx="39" cy="30" r="1.9" fill="#3a2a20"/>')
    parts.append(
        '<path d="M27 38 Q32 41.5 37 38" fill="none" stroke="#9c4a37" '
        'stroke-width="1.7" stroke-linecap="round"/>'
    )
    parts.extend(features.get("avant", []))
    parts.append("</g></svg>")
    return "\n".join(parts)


# 15 avatars, chacun avec une combinaison de traits distincte. bg/shirt variés
# pour renforcer la reconnaissance à petite taille.
BG = [
    "#a8d5e2", "#f6c1c1", "#c3e6cb", "#ffe4a3", "#d4c5f9",
    "#b8e0d2", "#f9d5b7", "#cfd8dc", "#e2c1e6", "#bcd4e6",
    "#f5b7b1", "#a3d5c5", "#f7dc6f", "#aed6f1", "#d7bde2",
]
SHIRT = [
    "#34495e", "#c0392b", "#2980b9", "#27ae60", "#8e44ad",
    "#d35400", "#16a085", "#7f8c8d", "#2c3e50", "#e67e22",
    "#1abc9c", "#9b59b6", "#e74c3c", "#3498db", "#f39c12",
]

# (peau, config des traits) — pensé pour que chaque avatar soit nettement
# différent des autres (coiffure + accessoire + pilosité).
CONFIGS = [
    ("clair", dict(arriere=[_hair(color="#2b2b2b")], avant=[])),
    ("hale", dict(arriere=[_hair_long("#5a3825")], avant=[_earrings()])),
    ("mat", dict(arriere=[_hair(color="#3a2a1a")], avant=[_glasses()])),
    ("clair", dict(arriere=[_bald_sides("#7a7a7a")], avant=[_mustache("#7a7a7a"), _beard("#8a8a8a")])),
    ("brun", dict(arriere=[_curly("#1e1e1e")], avant=[])),
    ("hale", dict(arriere=[_hair(color="#a55728")], avant=[_glasses("#5a3825"), _beard("#a55728")])),
    ("fonce", dict(arriere=[_hair(color="#111")], avant=[_hat_cap("#c0392b")])),
    ("clair", dict(arriere=[_bun("#d9b36b")], avant=[_bow("#e74c3c")])),
    ("mat", dict(arriere=[_hair(color="#2b2b2b")], avant=[_mustache("#2b2b2b")])),
    ("clair", dict(arriere=[_hair_long("#d9b36b")], avant=[_earrings("#e74c3c")])),
    ("brun", dict(arriere=[_bald_sides("#2b2b2b")], avant=[_glasses("#111")])),
    ("hale", dict(arriere=[], avant=[_hat_top("#2c3e50")])),
    ("clair", dict(arriere=[_curly("#a55728")], avant=[_glasses("#8e44ad")])),
    ("fonce", dict(arriere=[_hair(color="#111")], avant=[_beard("#111")])),
    ("clair", dict(arriere=[_hair(color="#c0c0c0")], avant=[_beret("#8e44ad")])),
]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for i, (skin_key, feats) in enumerate(CONFIGS, start=1):
        svg = avatar(BG[i - 1], SKINS[skin_key], SHIRT[i - 1], feats)
        (DEST / f"avatar-{i:02d}.svg").write_text(svg + "\n", encoding="utf-8")
    print(f"{len(CONFIGS)} avatars écrits dans {DEST}")


if __name__ == "__main__":
    main()
