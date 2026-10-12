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

Dictionnaire — retiré de l'archive (issue #154, revu issues #339, #460)
------------------------------------------------------------------------
Le dépôt du jeu est **public** et l'updater Actualise télécharge les mises à
jour (archive de Release GitHub) sans identifiant : tout ce qui est embarqué
dans l'archive est donc public. Depuis l'issue #460, ``data/dictionnaire/``
(dictionnaires tiers ODS8/Hunspell, définitions, mots courants, caches,
belgicismes, personnalisations) n'est **plus du tout embarqué** dans
l'archive produite par ce build, quel que soit son contenu sur le disque de
build — ``avertir_dictionnaires_non_embarques`` ci-dessous se contente d'un
message d'information dans le journal du build, aucune condition d'échec.

Ces données sont désormais déposées **à la main par Alain** dans
``{app}\\data\\`` sur chaque poste (voir ``data/dictionnaire/README.md``) :
une mise à jour Actualise extrait l'archive par-dessus le dossier
d'installation et ne supprime que les chemins listés dans le manifeste de
l'archive (``manifest.json``) — des données absentes de l'archive et du
manifeste survivent donc aux mises à jour. Sans dictionnaire déposé
manuellement, le jeu démarre normalement mais valide zéro mot.

Historique (issue #339, pour mémoire — le mécanisme décrit ci-dessous a
existé mais ne s'applique plus depuis l'issue #460) : jusqu'à l'issue #339,
le contenu de ``data/dictionnaire/`` était embarqué intégralement et sans
filtre (``collect_tree`` = ``os.walk`` récursif sur tout ce qui traîne sur le
disque local). Un dump de 8,2 Go déposé par erreur dans ce dossier
(``wiktionnaire-kaikki/``, matière première jamais lue à l'exécution) a ainsi
fini embarqué dans plusieurs builds Windows, produisant des installeurs de
~400 Mo en 25+ minutes au lieu de ~26 Mo. L'issue #339 avait alors introduit
une liste explicite de ce qui était embarqué, avec échec du build si aucun
dictionnaire tiers n'était trouvé sur le disque de build. L'issue #460 a
retiré cet embarquement entièrement : la question « que faire si le
dictionnaire est absent du disque de build » ne se pose donc plus — il n'est
de toute façon plus lu par ce script.

Le garde-fou de taille (``SEUIL_TAILLE_DATAS_OCTETS``/``verifier_taille_datas``)
reste en place : il continue de faire échouer le build si le total des
données embarquées (désormais ressources de l'interface + icône uniquement)
dépasse un seuil, avec le détail des plus gros contributeurs.
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


# Seuil d'alerte du garde-fou de taille (issue #339). Depuis l'issue #460,
# les données embarquées sont réduites aux ressources de l'interface +
# l'icône (plus aucun dictionnaire) : seuil conservé à 200 Mo, large marge
# pour cette croissance future, tout en détectant en quelques secondes un
# dépôt accidentel de fichier volumineux dans les dossiers encore embarqués.
SEUIL_TAILLE_DATAS_OCTETS = 200 * 1024 * 1024


def avertir_dictionnaires_non_embarques():
    """Rappelle dans le journal du build que ``data/dictionnaire`` n'est pas
    embarqué dans l'archive (issue #460) : le dépôt étant public, les
    dictionnaires et listes de mots sont déposés à la main par Alain dans
    ``{app}\\data\\`` sur chaque poste, indépendamment de ce build — voir
    ``data/dictionnaire/README.md``. Simple message d'information : plus
    aucune condition d'échec ici (contrairement à l'ancienne règle de
    l'issue #339, qui échouait le build si aucun dictionnaire tiers n'était
    trouvé sur le disque de build — ce script ne regarde même plus le
    contenu de ``data/dictionnaire``).
    """
    print(
        "[scrabble.spec] INFO : data/dictionnaire n'est pas embarqué dans "
        "cette archive (dépôt public, issue #460) — les dictionnaires et "
        "listes de mots sont installés à la main sur chaque poste, dans "
        "{app}\\data\\ (voir data/dictionnaire/README.md)."
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
# Icône du jeu, copiée à la racine de dist/Scrabble/ (aux côtés de Scrabble.exe) :
# le paramètre icon= de EXE() ci-dessous ne fait que l'intégrer comme ressource
# de l'exécutable, il ne la copie pas comme fichier de données. Or scrabble.iss
# référence "{app}\scrabble.ico" via IconFilename pour les raccourcis (issue
# #348) — sans cette entrée, ce fichier serait absent après installation
# (issue #349).
datas += [(os.path.join(RACINE, "assets", "scrabble.ico"), ".")]
# Assets web (HTML/CSS/JS/avatars SVG + images PNG comme web/images/sac.png)
# des fenêtres accueil (réglages intégrés)/jeu/chevalet. ``collect_tree`` marche
# via ``os.walk`` sans filtre d'extension : tout fichier de ``web/`` est embarqué
# (dossier suivi par git, pas de risque de dépôt local non versionné ici).
datas += collect_tree(os.path.join("src", "scrabble", "ui", "web"), os.path.join("scrabble", "ui", "web"))
# Dictionnaire(s), personnalisations, définitions, cache Trie : plus du tout
# embarqués depuis l'issue #460 (dépôt public, voir docstring en tête de
# fichier) — simple message d'information dans le journal du build.
avertir_dictionnaires_non_embarques()
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
    # Métadonnées Windows (clic droit -> Propriétés -> Détails -> Version du
    # fichier) du .exe produit, issue #389 : version_info.txt à la racine du
    # dépôt, dont build\rebuild_scrabble.bat substitue le numéro de build réel
    # avant cet appel PyInstaller.
    version=os.path.join(RACINE, "version_info.txt"),
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
