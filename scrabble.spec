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

Dictionnaire (issue #154, revu issue #339)
--------------------------------------------
``data/dictionnaire/`` est gitignoré et les dictionnaires tiers (ODS8,
Hunspell) doivent être déposés manuellement (voir
``data/dictionnaire/README.md``) **avant** de lancer ``pyinstaller`` pour
obtenir un exécutable avec le dictionnaire complet — sans eux, le jeu démarre
normalement mais valide zéro mot.

Jusqu'à l'issue #339, le contenu de ce dossier était embarqué intégralement et
sans filtre (``collect_tree`` = ``os.walk`` récursif sur tout ce qui traîne
sur le disque local). Un dump de 8,2 Go déposé par erreur dans ce dossier
(``wiktionnaire-kaikki/``, matière première jamais lue à l'exécution) a ainsi
fini embarqué dans plusieurs builds Windows, produisant des installeurs de
~400 Mo en 25+ minutes au lieu de ~26 Mo — et deux clones du même commit
pouvaient produire deux installeurs différents selon l'état local non
versionné de la machine de build.

Depuis l'issue #339, ``ELEMENTS_DICTIONNAIRE``/``ELEMENTS_DICTIONNAIRE_TIERS``
ci-dessous énumèrent explicitement ce qui est embarqué : un fichier posé dans
``data/dictionnaire`` sans y être déclaré n'est plus embarqué, quelle que soit
sa taille. Un garde-fou (``SEUIL_TAILLE_DATAS_OCTETS``) fait en plus échouer
le build si le total dépasse un seuil, avec le détail des plus gros
contributeurs.
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


DOSSIER_DICTIONNAIRE_REL = os.path.join("data", "dictionnaire")

# Éléments de premier niveau de data/dictionnaire à embarquer (issue #339).
# Liste EXPLICITE volontairement : tout fichier/dossier présent sur le disque
# de build mais absent d'ici (dump de travail, brouillon, export temporaire...)
# n'est plus embarqué, quelle que soit sa taille. Les dossiers listés restent
# parcourus récursivement par ``collect_tree`` (leur propre arborescence n'a
# pas à être déclarée en détail).
#
# (nom, optionnel) — ``optionnel=True`` : absence tolérée à l'exécution (le
# code source dégrade proprement, cf. dictionnaire.py) donc un simple
# avertissement suffit au build. Caches régénérés automatiquement au premier
# lancement si absents (trie_cache.pkl/trie_ia_cache.pkl).
ELEMENTS_DICTIONNAIRE = [
    ("definitions.json", True),
    ("Lexique383.tsv", True),
    ("mots_courants.txt", True),
    ("mots_ajoutes.txt", True),
    ("mots_ajoutes_hunspell.txt", True),
    ("mots_ajoutes_ods.txt", True),
    ("mots_retires.txt", True),
    ("mots_retires_hunspell.txt", True),
    ("mots_retires_ods.txt", True),
    ("classiques_ajoutes.txt", True),
    ("classiques_retires.txt", True),
    ("belgicismes_a_revoir.csv", True),
    ("README.md", True),
    ("trie_cache.pkl", True),
    ("trie_ia_cache.pkl", True),
]

# Dictionnaires tiers (dossiers) : au moins l'un des deux doit être présent,
# faute de quoi le jeu valide zéro mot (voir data/dictionnaire/README.md) —
# traités à part de ELEMENTS_DICTIONNAIRE pour pouvoir échouer le build
# seulement si AUCUN des deux n'est trouvé (l'un ou l'autre suffit selon
# ``source_dictionnaire`` dans la config, cf. config.py).
ELEMENTS_DICTIONNAIRE_TIERS = [
    "French-Scrabble-ODS8-main",
    "hunspell-french-dictionaries-v7.7",
]

# Seuil d'alerte du garde-fou de taille (issue #339). Contenu légitime actuel
# (liste ci-dessus, mesuré le 31/07/2026) : ~88 Mo. Seuil fixé à 200 Mo pour
# laisser de la marge à une croissance légitime (nouvelles variantes de
# dictionnaire, etc.) tout en détectant en quelques secondes un dépôt
# accidentel de fichier volumineux — l'anomalie à l'origine de cette issue
# (8,2 Go) le dépasse de plus de 40x.
SEUIL_TAILLE_DATAS_OCTETS = 200 * 1024 * 1024


def ajouter_elements_dictionnaire(datas):
    """Ajoute à ``datas`` les entrées de ``data/dictionnaire`` déclarées
    ci-dessus (fichiers un par un, dossiers récursivement via
    ``collect_tree``). Avertit sur les éléments optionnels absents, échoue
    le build si AUCUN dictionnaire tiers (ODS8/Hunspell) n'est trouvé.
    """
    dico_abs = os.path.join(RACINE, DOSSIER_DICTIONNAIRE_REL)
    absents = []
    for nom, _optionnel in ELEMENTS_DICTIONNAIRE:
        chemin_abs = os.path.join(dico_abs, nom)
        if os.path.isfile(chemin_abs):
            datas.append((chemin_abs, DOSSIER_DICTIONNAIRE_REL))
        elif os.path.isdir(chemin_abs):
            datas.extend(collect_tree(
                os.path.join(DOSSIER_DICTIONNAIRE_REL, nom),
                os.path.join(DOSSIER_DICTIONNAIRE_REL, nom),
            ))
        else:
            absents.append(nom)

    tiers_presents = []
    for nom in ELEMENTS_DICTIONNAIRE_TIERS:
        chemin_abs = os.path.join(dico_abs, nom)
        if os.path.isdir(chemin_abs):
            datas.extend(collect_tree(
                os.path.join(DOSSIER_DICTIONNAIRE_REL, nom),
                os.path.join(DOSSIER_DICTIONNAIRE_REL, nom),
            ))
            tiers_presents.append(nom)
        else:
            absents.append(nom)

    if absents:
        print(
            "[scrabble.spec] AVERTISSEMENT : éléments de data/dictionnaire "
            "absents du disque, non embarqués (fonctionnalités réduites) : "
            + ", ".join(absents)
        )
    if not tiers_presents:
        raise SystemExit(
            "[scrabble.spec] ERREUR : aucun dictionnaire tiers trouvé dans "
            f"data/dictionnaire ({' ni '.join(ELEMENTS_DICTIONNAIRE_TIERS)}) "
            "— le jeu validerait zéro mot. Déposez-en au moins un avant de "
            "lancer PyInstaller (voir data/dictionnaire/README.md)."
        )


def verifier_taille_datas(datas, seuil_octets):
    """Échoue le build si le total des fichiers de ``datas`` dépasse
    ``seuil_octets`` (issue #339) — détecte en quelques secondes un dépôt
    accidentel de fichier volumineux, au lieu de le découvrir après 25+
    minutes de compression PyInstaller.
    """
    tailles = {}
    for source, _dest in datas:
        try:
            tailles[source] = tailles.get(source, 0) + os.path.getsize(source)
        except OSError:
            continue
    total = sum(tailles.values())
    print(
        f"[scrabble.spec] {total / 1_048_576:.1f} Mo de données embarquées "
        f"({len(datas)} fichiers), seuil {seuil_octets / 1_048_576:.0f} Mo."
    )
    if total > seuil_octets:
        plus_gros = sorted(tailles.items(), key=lambda kv: kv[1], reverse=True)[:10]
        detail = "\n".join(
            f"  {taille / 1_048_576:8.1f} Mo  {chemin}" for chemin, taille in plus_gros
        )
        raise SystemExit(
            f"[scrabble.spec] ERREUR : {total / 1_048_576:.1f} Mo de données "
            f"embarquées, seuil de {seuil_octets / 1_048_576:.0f} Mo dépassé. "
            "Un fichier volumineux traîne probablement dans data/dictionnaire "
            f"(ou un autre dossier source non filtré). Plus gros contributeurs :\n{detail}"
        )
    return total


datas = []
# Assets web (HTML/CSS/JS/avatars SVG + images PNG comme web/images/sac.png)
# des fenêtres accueil (réglages intégrés)/jeu/chevalet. ``collect_tree`` marche
# via ``os.walk`` sans filtre d'extension : tout fichier de ``web/`` est embarqué
# (dossier suivi par git, pas de risque de dépôt local non versionné ici).
datas += collect_tree(os.path.join("src", "scrabble", "ui", "web"), os.path.join("scrabble", "ui", "web"))
# Dictionnaire(s), personnalisations (issue #110), définitions, cache Trie —
# liste explicite (issue #339), plus dictionnaire(s) tiers ODS8/Hunspell.
ajouter_elements_dictionnaire(datas)
verifier_taille_datas(datas, SEUIL_TAILLE_DATAS_OCTETS)

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
