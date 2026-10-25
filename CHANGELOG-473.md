# Changelog — Issue #473

## Modifié

- **`build\rebuild_scrabble.bat` : correction des deux derniers blocs à
  `exit /b` imbriqué sur deux niveaux (même défaut que #472, commit
  24497b6).** Relecture complète du script (tous les `if` contenant un
  `exit /b`) : deux occurrences restantes, toutes deux corrigées avec la
  même technique (indicateur d'erreur renseigné par des `if` à un seul
  niveau sans `exit`, puis une seule vérification/`exit /b 1` hors de tout
  bloc parent) :
  - étape `[2/9]` (création de `.venv_build`) : les trois `exit /b 1`
    (création du venv, installation de `requirements.txt`, installation de
    `pyinstaller`) étaient chacun dans un `if errorlevel 1` imbriqué dans le
    `if not exist ".venv_build\Scripts\python.exe"`. Remplacés par
    l'indicateur `VENV_ERR`.
  - bloc `--publier` : les trois `exit /b 1` (archive introuvable, calcul du
    SHA-256 échoué, commit git échoué) étaient chacun dans un `if` imbriqué
    dans le `if "%PUBLIER%"=="1"`. Remplacés par l'indicateur `PUBLIER_ERR`.
  Aucune autre occurrence du motif trouvée dans le script (tous les autres
  `exit /b` sont déjà à un seul niveau d'imbrication). Aucun changement de
  comportement nominal : mêmes étapes, même ordre, mêmes messages, mêmes
  noms de fichiers, même logique `--publier` (écriture de `version.json`,
  commit local, jamais de push ni de Release).

## Essais

- Reproduction isolée (mini-scripts jetables, non commités) : la forme
  défectueuse (motif réel de #472 — pipe `findstr` + `if errorlevel 1`
  imbriqué dans un `if`) arrête bien le script mais ressort avec le code 0 ;
  la forme corrigée (indicateur + vérification à un seul niveau) ressort
  avec le code 1.
- Essai nominal `build\rebuild_scrabble.bat --build 99` (sans `--publier`,
  99 fictif) : build complet en 1 min 43 s, code de sortie 0, `version.json`
  inchangé, artefacts copiés et affichés dans le dossier fixe
  (`Scrabble-Setup-v99.exe` : 12 904 767 octets, `scrabble-v99.zip` :
  13 352 481 octets).
- Refus vérifié : `--build 13` (égal au build courant) → code de sortie 1,
  sans aucun fichier écrit, avant toute construction.
- Les chemins d'erreur réels du bloc venv et du bloc `--publier` n'ont pas
  été exercés en conditions réelles (effets de bord à éviter : écriture de
  `version.json`, commit git) ; seules la reproduction isolée du motif et la
  relecture du code couvrent ces deux blocs.
