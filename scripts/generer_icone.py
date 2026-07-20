"""Générateur ponctuel de l'icône de l'application (issue #161).

Produit une TUILE DE SCRABBLE stylisée servant d'icône à l'application
(barre des tâches Windows, exécutable PyInstaller). L'icône reprend le style
visuel des tuiles du plateau (fond bois/beige, bordure dorée, lettre brun
foncé, valeur en points en bas à droite) : une tuile « S » valant 1 point,
cohérente avec la palette du front web (``commun.css`` : ``--tuile-fond``
#fbf9f3, ``--tuile-bordure`` #c9a961, ``--tuile-texte`` #3b2f1a).

Elle remplace l'icône « disquette » qui n'était que le défaut de PyInstaller
(aucune icône n'était fournie jusqu'ici).

Comme ``scripts/generer_avatars.py``, ce script est un OUTIL DE FABRICATION
ponctuel : il n'est pas importé par l'application. Les fichiers qu'il génère
dans ``assets/`` (le rendu déterministe) sont la véritable livraison et sont
versionnés :

- ``assets/scrabble.svg``      — source vectorielle (référence, réutilisable) ;
- ``assets/scrabble.ico``      — icône multi-résolutions pour Windows / PyInstaller
                                 (``icon='assets/scrabble.ico'`` dans scrabble.spec) ;
- ``assets/scrabble-256.png``  — aperçu / usage général (Linux, docs).

Relancer :  python scripts/generer_icone.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# --------------------------------------------------------------------------- #
# Paramètres de la tuile                                                       #
# --------------------------------------------------------------------------- #
LETTRE = "S"          # Lettre affichée (au centre).
VALEUR = "1"          # Valeur en points du « S » au Scrabble français.

# Palette reprise du front web (src/scrabble/ui/web/commun.css & jeu.css).
FOND_HAUT = (253, 247, 230)   # crème clair (haut : reflet du bois verni).
FOND_BAS = (233, 213, 168)    # beige/bois plus chaud (bas).
BORDURE = (201, 169, 97)      # #c9a961 — liseré doré des tuiles.
BORDURE_OMBRE = (176, 143, 74)  # arête inférieure/droite plus sombre (relief).
TEXTE = (59, 47, 26)          # #3b2f1a — brun foncé de la lettre.

DEST = Path(__file__).parent.parent / "assets"
POLICE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Tailles embarquées dans le .ico (Windows choisit la plus adaptée au contexte).
TAILLES_ICO = [16, 24, 32, 48, 64, 128, 256]

SS = 4  # facteur de suréchantillonnage (anticrénelage par réduction LANCZOS).


def _degrade_vertical(taille, haut, bas):
    """Image RGBA d'un dégradé vertical de ``haut`` (en haut) vers ``bas``."""
    grad = Image.new("RGB", (1, taille))
    for y in range(taille):
        t = y / max(1, taille - 1)
        grad.putpixel(
            (0, y),
            tuple(round(haut[c] + (bas[c] - haut[c]) * t) for c in range(3)),
        )
    return grad.resize((taille, taille)).convert("RGBA")


def _dessiner_tuile(n):
    """Rend la tuile de Scrabble sur un canevas RGBA carré de côté ``n`` px."""
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    marge = round(n * 0.055)          # petite respiration + place pour l'ombre.
    x0, y0 = marge, marge
    x1, y1 = n - marge, n - marge - round(n * 0.015)  # léger décalage pour l'ombre.
    cote = x1 - x0
    rayon = round(cote * 0.16)         # coins arrondis façon tuile.

    # 1) Ombre portée douce (profondeur dans la barre des tâches).
    ombre = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    dro = ImageDraw.Draw(ombre)
    dec = round(n * 0.02)
    dro.rounded_rectangle(
        [x0 + dec, y0 + dec, x1 + dec, y1 + dec],
        radius=rayon,
        fill=(40, 30, 15, 120),
    )
    ombre = ombre.filter(ImageFilter.GaussianBlur(round(n * 0.02)))
    img.alpha_composite(ombre)

    # 2) Corps de la tuile : dégradé bois/beige découpé aux coins arrondis.
    masque = Image.new("L", (n, n), 0)
    ImageDraw.Draw(masque).rounded_rectangle(
        [x0, y0, x1, y1], radius=rayon, fill=255
    )
    corps = _degrade_vertical(n, FOND_HAUT, FOND_BAS)
    img.paste(corps, (0, 0), masque)

    draw = ImageDraw.Draw(img)

    # 3) Bordure dorée + arête inférieure/droite plus sombre (relief).
    ep = max(2, round(cote * 0.045))
    draw.rounded_rectangle(
        [x0, y0, x1, y1], radius=rayon, outline=BORDURE_OMBRE, width=ep
    )
    draw.rounded_rectangle(
        [x0, y0, x1 - round(ep * 0.6), y1 - round(ep * 0.6)],
        radius=rayon,
        outline=BORDURE,
        width=max(1, round(ep * 0.6)),
    )

    # 4) Reflet clair en haut à gauche (biseau).
    reflet = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(reflet).rounded_rectangle(
        [x0 + ep, y0 + ep, x1 - ep, y1 - ep],
        radius=max(1, rayon - ep),
        outline=(255, 255, 255, 90),
        width=max(1, round(cote * 0.02)),
    )
    # On ne garde le reflet que sur la moitié haut-gauche.
    coupe = Image.new("L", (n, n), 0)
    ImageDraw.Draw(coupe).polygon(
        [(x0, y0), (x1, y0), (x0, y1)], fill=255
    )
    img.paste(reflet, (0, 0), Image.composite(reflet.getchannel("A"), coupe, coupe))

    # 5) Lettre centrale.
    police_lettre = ImageFont.truetype(POLICE, round(cote * 0.62))
    bb = draw.textbbox((0, 0), LETTRE, font=police_lettre)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]
    cx = x0 + (cote - lw) / 2 - bb[0]
    cy = y0 + (cote - lh) / 2 - bb[1] - cote * 0.04  # remonté pour loger la valeur.
    draw.text((cx, cy), LETTRE, font=police_lettre, fill=TEXTE)

    # 6) Valeur en points, en bas à droite.
    police_val = ImageFont.truetype(POLICE, round(cote * 0.22))
    bbv = draw.textbbox((0, 0), VALEUR, font=police_val)
    vw, vh = bbv[2] - bbv[0], bbv[3] - bbv[1]
    vx = x1 - ep - vw - bbv[0] - round(cote * 0.05)
    vy = y1 - ep - vh - bbv[1] - round(cote * 0.05)
    draw.text((vx, vy), VALEUR, font=police_val, fill=TEXTE)

    return img


def _rgb(c):
    return "#%02x%02x%02x" % c


def _ecrire_svg(chemin):
    """Écrit une source vectorielle équivalente (référence / réutilisation web)."""
    m, s = 6.0, 100.0  # viewBox 0..112, marge 6, côté 100.
    x0 = y0 = m
    x1 = y1 = m + s
    r = s * 0.16
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 112 112" width="112" height="112" role="img" aria-label="Tuile de Scrabble « {LETTRE} »">
  <defs>
    <linearGradient id="bois" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{_rgb(FOND_HAUT)}"/>
      <stop offset="1" stop-color="{_rgb(FOND_BAS)}"/>
    </linearGradient>
  </defs>
  <rect x="{x0 + 3}" y="{y0 + 4}" width="{s}" height="{s}" rx="{r}" fill="#281e0f" opacity="0.28"/>
  <rect x="{x0}" y="{y0}" width="{s}" height="{s}" rx="{r}" fill="url(#bois)"
        stroke="{_rgb(BORDURE)}" stroke-width="4"/>
  <text x="{x0 + s / 2}" y="{y0 + s * 0.56}" text-anchor="middle" dominant-baseline="central"
        font-family="DejaVu Sans, Arial, sans-serif" font-weight="700"
        font-size="{s * 0.62}" fill="{_rgb(TEXTE)}">{LETTRE}</text>
  <text x="{x1 - 8}" y="{y1 - 6}" text-anchor="end" dominant-baseline="alphabetic"
        font-family="DejaVu Sans, Arial, sans-serif" font-weight="700"
        font-size="{s * 0.22}" fill="{_rgb(TEXTE)}">{VALEUR}</text>
</svg>
"""
    chemin.write_text(svg, encoding="utf-8")


def main():
    DEST.mkdir(parents=True, exist_ok=True)

    # Rendu haute résolution suréchantillonné puis réduit (anticrénelage).
    base = _dessiner_tuile(256 * SS).resize((256, 256), Image.LANCZOS)

    png = DEST / "scrabble-256.png"
    base.save(png)

    ico = DEST / "scrabble.ico"
    base.save(ico, sizes=[(t, t) for t in TAILLES_ICO])

    svg = DEST / "scrabble.svg"
    _ecrire_svg(svg)

    for f in (svg, ico, png):
        print(f"écrit : {f.relative_to(DEST.parent)}")


if __name__ == "__main__":
    main()
