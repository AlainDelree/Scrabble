# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller pour l'exécutable Windows du jeu Scrabble (issue #154).

Build : ``pyinstaller scrabble.spec`` (depuis la racine du dépôt, avec
l'environnement virtuel du projet activé — ``pywebview`` et ``pyinstaller``
installés). Sortie en mode ``--onedir`` (pas de ``--onefile`` : plus fiable
pour une appli pywebview/EdgeChromium, cf. corps de l'issue) dans
``dist/Scrabble/``.

Résolution des chemins une fois gelé
-------------------------------------
``scrabble.config.RACINE_PROJET`` bascule sur ``sys._MEIPASS`` quand
``sys.frozen`` est vrai (voir ``src/scrabble/config.py``). En mode
``--onedir``, ``sys._MEIPASS`` est le dossier de l'exécutable lui-même (pas un
dossier temporaire nettoyé à la sortie) : les données groupées ci-dessous sous
``data/dictionnaire`` restent donc lisibles ET les fichiers que le jeu écrit à
l'usage (``config.json``, ``logs/``, ``data/parties.db``,
``mots_ajoutes_*.txt``/``mots_retires_*.txt``) persistent d'un lancement à
l'autre au même endroit.

Les fenêtres accueil (réglages intégrés, issue #169)/jeu/chevalet résolvent leurs assets web via
``Path(__file__).parent / "web"`` (voir ``src/scrabble/ui/*.py``) : PyInstaller
préserve un ``__file__`` synthétique sous ``scrabble/ui/...`` pour les modules
gelés, donc placer le dossier ``web`` à la destination ``scrabble/ui/web``
(miroir exact du chemin du paquet) suffit à ce que ce calcul reste valable une
fois empaqueté — aucune adaptation de ce code n'est nécessaire.

Dictionnaire (issue #154 — point de vigilance)
------------------------------------------------
``data/dictionnaire/`` est intégralement embarqué tel quel (README, listes
ODS8/Hunspell si présentes, fichiers ``mots_ajoutes_*``/``mots_retires_*``,
``definitions.json``, cache ``trie_cache.pkl``) : quoi que contienne ce
dossier au moment du build est reflété dans l'exécutable. Ce dossier est
gitignoré et les dictionnaires tiers (ODS8, Hunspell) doivent être déposés
manuellement (voir ``data/dictionnaire/README.md``) **avant** de lancer
``pyinstaller`` pour obtenir un exécutable avec le dictionnaire complet — sans
ces fichiers, le jeu démarre normalement mais valide zéro mot.
"""

import os

block_cipher = None

RACINE = os.path.abspath(os.path.dirname(SPEC))


def collect_tree(src_relatif, dest_relatif):
    """Retourne les couples (fichier_source, dossier_dest) pour tout un arbre.

    Équivalent maison de ``datas=[(dossier, dest)]`` (non récursif nativement
    dans un ``.spec``) : préserve la structure de sous-dossiers de
    ``src_relatif`` sous ``dest_relatif`` dans le paquet final.
    """
    src_abs = os.path.join(RACINE, src_relatif)
    entrees = []
    if not os.path.isdir(src_abs):
        return entrees
    for dossier_courant, _sous_dossiers, fichiers in os.walk(src_abs):
        relatif = os.path.relpath(dossier_courant, src_abs)
        dest = dest_relatif if relatif == "." else os.path.join(dest_relatif, relatif)
        for nom_fichier in fichiers:
            entrees.append((os.path.join(dossier_courant, nom_fichier), dest))
    return entrees


datas = []
# Assets web (HTML/CSS/JS/avatars SVG) des fenêtres accueil (réglages intégrés)/jeu/chevalet.
datas += collect_tree(os.path.join("src", "scrabble", "ui", "web"), os.path.join("scrabble", "ui", "web"))
# Dictionnaire(s), personnalisations (issue #110), définitions, cache Trie —
# tout ce qui se trouve dans data/dictionnaire au moment du build.
datas += collect_tree(os.path.join("data", "dictionnaire"), os.path.join("data", "dictionnaire"))

a = Analysis(
    ["main.py"],
    pathex=[os.path.join(RACINE, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Scrabble",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Application graphique : pas de console visible.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(RACINE, "assets", "scrabble.ico"),
    # Désactive le sous-dossier "_internal" (nouveau défaut depuis PyInstaller
    # 6.0) : sys._MEIPASS reste alors le dossier de l'exe lui-même, à côté
    # duquel scrabble.config.RACINE_PROJET écrit config.json/logs/data en mode
    # gelé — évite de les enterrer dans un dossier nommé "interne".
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Scrabble",
)
