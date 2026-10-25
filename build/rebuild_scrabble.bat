@echo off
setlocal enabledelayedexpansion
pushd "%~dp0.."
set "ORIGDIR=%CD%"

REM --- Analyse des parametres -------------------------------------------------
REM Syntaxe : build\rebuild_scrabble.bat [--publier] [--build N]
REM Les deux options sont acceptees dans n'importe quel ordre.
REM   --publier : apres un build reussi, calcule le SHA-256 de l'archive,
REM               ecrit version.json et fait un commit local du resultat
REM               (jamais de push ni de Release GitHub, toujours manuels).
REM   --build N : impose le numero de build N a utiliser. N doit toujours
REM               etre un entier strictement superieur au build actuel de
REM               version.json (garde-fou, issue #472), publie ou non.
REM               Sans --build, N = build actuel de version.json + 1, dans
REM               tous les modes, y compris sans --publier.
REM L'ancienne forme "--publier N" (numero accole a --publier) n'est plus
REM acceptee : utiliser desormais "--publier --build N".
set "PUBLIER=0"
set "BUILD_ARG="
set "ARG_ERR="
set "VENV_ERR="
set "PUBLIER_ERR="

:parse_args
if "%~1"=="" goto parse_done
if /i "%~1"=="--publier" goto arg_publier
if /i "%~1"=="--build" goto arg_build
set "ARG_ERR=argument inconnu : %~1"
goto parse_done

:arg_publier
if "%PUBLIER%"=="1" (
    set "ARG_ERR=--publier specifie plusieurs fois"
    goto parse_done
)
set "PUBLIER=1"
shift
goto parse_args

:arg_build
if not "%BUILD_ARG%"=="" (
    set "ARG_ERR=--build specifie plusieurs fois"
    goto parse_done
)
if "%~2"=="" (
    set "ARG_ERR=--build necessite une valeur (numero de build)"
    goto parse_done
)
set "BUILD_ARG=%~2"
shift
shift
goto parse_args

:parse_done
if defined ARG_ERR (
    echo.
    echo ERREUR : !ARG_ERR!
    echo Syntaxe attendue : build\rebuild_scrabble.bat [--publier] [--build N]
    popd
    exit /b 1
)

echo ============================================
echo   Rebuild Scrabble.exe
echo ============================================
echo.

REM --- 0. Verifier les dependances externes non versionnees -----------------
REM Inno Setup est cherche hors du depot (emplacement stable du poste,
REM partage par tous les clones/worktrees), puis a defaut dans l'ancien
REM emplacement .tools\InnoSetup6 du depot (build manuel du clone principal).
echo [0/9] Verification des dependances externes (hors git)...
set "ISCC_EXE=C:\CCW\tools\InnoSetup6\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%ORIGDIR%\.tools\InnoSetup6\ISCC.exe"
if not exist "%ISCC_EXE%" (
    echo.
    echo ERREUR : ISCC.exe introuvable. Emplacements recherches :
    echo   - C:\CCW\tools\InnoSetup6\ISCC.exe
    echo   - %ORIGDIR%\.tools\InnoSetup6\ISCC.exe
    echo Deposez l'installation portable d'Inno Setup 6 a l'un de ces
    echo emplacements avant de lancer ce script ^(voir installeur\README.md,
    echo section Prerequis^).
    popd
    exit /b 1
)
echo Inno Setup trouve : %ISCC_EXE%
echo.
echo INFO : data\dictionnaire n'est plus requis pour ce build ^(issue #460^) --
echo le depot etant public, les dictionnaires et listes de mots ne sont plus
echo embarques dans l'archive/l'installeur. Ils sont deposes a la main par
echo Alain sur chaque poste, apres installation ^(voir data\dictionnaire\README.md^).
echo.

REM --- 0bis. Determiner et valider le numero de build (garde-fou, issue #472)
REM Lu AVANT toute copie/construction/ecriture. N (fourni via --build, ou
REM build actuel + 1 par defaut) doit toujours etre strictement superieur
REM au build actuel de version.json, publie ou non.
echo Determination et validation du numero de build...
set "ANCIEN_BUILD="
for /f "usebackq" %%b in (`powershell -NoProfile -Command "try { (Get-Content 'version.json' -Raw | ConvertFrom-Json).build } catch { '' }"`) do set "ANCIEN_BUILD=%%b"
if "!ANCIEN_BUILD!"=="" (
    echo.
    echo ERREUR : impossible de lire le champ build de version.json a la racine du clone.
    popd
    exit /b 1
)
echo Build actuel dans version.json : !ANCIEN_BUILD!

set "BUILD_FORMAT_OK=1"
if not "%BUILD_ARG%"=="" echo %BUILD_ARG%| findstr /r "^[1-9][0-9]*$" >nul || set "BUILD_FORMAT_OK=0"
if "%BUILD_FORMAT_OK%"=="0" (
    echo.
    echo ERREUR : --build "%BUILD_ARG%" n'est pas un numero de build valide ^(entier positif attendu^).
    popd
    exit /b 1
)

if not "%BUILD_ARG%"=="" (
    set "BUILD_CANDIDATE=%BUILD_ARG%"
    echo Numero de build demande ^(--build^) : !BUILD_CANDIDATE!
) else (
    set /a BUILD_CANDIDATE=!ANCIEN_BUILD!+1
    echo Pas de --build fourni : build par defaut = build actuel + 1 = !BUILD_CANDIDATE!
)

if not !BUILD_CANDIDATE! gtr !ANCIEN_BUILD! (
    echo.
    echo ERREUR : numero de build demande ^(!BUILD_CANDIDATE!^) invalide.
    echo Build courant de version.json : !ANCIEN_BUILD!.
    echo Regle : le numero de build doit toujours etre strictement superieur
    echo au build courant de version.json.
    popd
    exit /b 1
)

set "SCRABBLE_BUILD=!BUILD_CANDIDATE!"
set "NOUVEAU_BUILD=!SCRABBLE_BUILD!"
echo Numero de build retenu : !SCRABBLE_BUILD!
set "ZIP_NAME=scrabble-v!SCRABBLE_BUILD!.zip"
echo Nom du zip : !ZIP_NAME!
set "SETUP_NAME=Scrabble-Setup-v!SCRABBLE_BUILD!.exe"
echo Nom de l'installeur : !SETUP_NAME!
echo.

REM --- 1. Copier les sources vers un repertoire local -------------------------
REM Sur le PC fixe physique, PyInstaller et ISCC produisent des fichiers
REM tronques quand le build tourne directement sur le partage local
REM (C:\CCW_Share\...). On copie donc tout ce qui est necessaire au build vers
REM un dossier local (C:\Temp\ScrabbleBuild), on construit entierement la-bas,
REM puis on recopie uniquement l'installeur final vers le partage.
echo [1/9] Copie des sources vers le repertoire de build local...
set "LOCALBUILD=C:\Temp\ScrabbleBuild"
if exist "%LOCALBUILD%" (
    echo Nettoyage de l'ancien repertoire de build local...
    rmdir /s /q "%LOCALBUILD%"
)
mkdir "%LOCALBUILD%"
if errorlevel 1 (
    echo.
    echo ERREUR : impossible de creer %LOCALBUILD%.
    popd
    exit /b 1
)
REM data\dictionnaire exclu (issue #460) : plus lu par scrabble.spec (plus
REM embarque dans l'archive), inutile de le copier vers le repertoire de
REM build local -- chemin complet pour ne pas confondre avec
REM src\scrabble\dictionnaire\ (code source, lui necessaire au build).
REM .tools exclu (issue #467) : Inno Setup est appele depuis %ISCC_EXE%,
REM pas besoin de le recopier vers le repertoire de build local.
robocopy "%ORIGDIR%" "%LOCALBUILD%" /E /XD ".git" "venv" ".venv_build" "dist" "build" "__pycache__" ".pytest_cache" "logs" "Exemples plateau" "issue-attachments" ".tools" "%ORIGDIR%\data\dictionnaire" /NFL /NDL /NJH /NJS /NC /NS /NP >nul
if %errorlevel% geq 8 (
    echo.
    echo ERREUR : la copie des sources vers %LOCALBUILD% a echoue.
    popd
    exit /b 1
)
echo Sources copiees vers %LOCALBUILD%. OK.
echo.

pushd "%LOCALBUILD%"

REM --- 2. Preparer l'environnement virtuel de build -------------------------
echo [2/9] Verification de l'environnement virtuel de build...
if not exist ".venv_build\Scripts\python.exe" (
    echo .venv_build introuvable : creation en cours...
    python -m venv .venv_build
    if errorlevel 1 set "VENV_ERR=impossible de creer .venv_build. Verifiez l'installation Python."
    if not defined VENV_ERR (
        call ".venv_build\Scripts\python.exe" -m pip install --upgrade pip >nul
        call ".venv_build\Scripts\pip.exe" install -r requirements.txt
        if errorlevel 1 set "VENV_ERR=l'installation de requirements.txt a echoue."
    )
    if not defined VENV_ERR (
        call ".venv_build\Scripts\pip.exe" install pyinstaller
        if errorlevel 1 set "VENV_ERR=l'installation de pyinstaller a echoue."
    )
) else (
    echo .venv_build present. OK.
)
if defined VENV_ERR (
    echo.
    echo ERREUR : !VENV_ERR!
    popd
    popd
    exit /b 1
)
echo.

REM --- 3. Fermer Scrabble.exe s'il tourne encore ---------------------------
echo [3/9] Fermeture de Scrabble.exe si necessaire...
tasklist /fi "imagename eq Scrabble.exe" 2>nul | find /i "Scrabble.exe" >nul
if not errorlevel 1 (
    echo Scrabble.exe est en cours d'execution : fermeture...
    taskkill /im Scrabble.exe /f >nul 2>&1
    timeout /t 2 >nul
) else (
    echo Aucune instance en cours. OK.
)
echo.

REM --- 4. Lancer le build PyInstaller ---------------------------------------
echo [4/9] Injection du numero de build dans version_info.txt...
powershell -NoProfile -Command "(Get-Content 'version_info.txt' -Raw) -replace 'BUILD', '!SCRABBLE_BUILD!' | Set-Content 'version_info.txt' -NoNewline"
if errorlevel 1 (
    echo.
    echo ERREUR : l'injection du numero de build dans version_info.txt a echoue.
    popd
    popd
    exit /b 1
)
echo Numero de build !SCRABBLE_BUILD! injecte dans version_info.txt. OK.
echo.
echo Build PyInstaller en cours (peut prendre plusieurs minutes)...
call ".venv_build\Scripts\pyinstaller.exe" scrabble.spec -y
if errorlevel 1 (
    echo.
    echo ERREUR : le build PyInstaller a echoue. Voir les messages ci-dessus.
    popd
    popd
    exit /b 1
)
echo.
echo Build termine avec succes.
echo.

REM --- 5. Verifier le resultat ----------------------------------------------
echo [5/9] Verification du resultat...
if exist "dist\Scrabble\Scrabble.exe" (
    echo.
    echo dist\Scrabble\ genere :
    dir "dist\Scrabble" | find "Scrabble.exe"
    echo.
    for /f "usebackq" %%s in (`powershell -NoProfile -Command "'{0:N2} Mo' -f ((Get-ChildItem -Recurse 'dist\Scrabble' | Measure-Object -Property Length -Sum).Sum / 1MB)"`) do (
        echo Taille totale du dossier dist\Scrabble : %%s
    )
    echo.
) else (
    echo.
    echo ERREUR : Scrabble.exe introuvable dans dist\Scrabble apres le build.
    popd
    popd
    exit /b 1
)

REM --- 6. Compiler l'installeur Windows (Inno Setup) ------------------------
echo [6/9] Compilation de l'installeur Inno Setup...
if not exist "%ISCC_EXE%" (
    echo.
    echo ERREUR : %ISCC_EXE% introuvable. Verifiez l'installation portable
    echo d'Inno Setup sur cette machine ^(voir installeur\README.md^).
    popd
    popd
    exit /b 1
)
call "%ISCC_EXE%" /DScrabbleBuildInstalle=!SCRABBLE_BUILD! installeur\scrabble.iss
if errorlevel 1 (
    echo.
    echo ERREUR : la compilation Inno Setup a echoue. Voir les messages ci-dessus.
    popd
    popd
    exit /b 1
)
if not exist "installeur\output" mkdir "installeur\output"
copy "C:\Temp\ScrabbleOutput\!SETUP_NAME!" "installeur\output\!SETUP_NAME!"
echo [OK] Installeur copié vers installeur\output\ ^(local^)
echo.

REM --- 7. Creer manifest.json et zipper vers scrabble-vN.zip (issue #345, issue #396)
REM scrabble-vN.zip = dist\Scrabble\ + manifest.json, sans dossier englobant
REM (l'updater Actualise l'extrait directement par-dessus le dossier installe).
REM N = SCRABBLE_BUILD/NOUVEAU_BUILD, determine plus haut (etape 0bis), pour
REM que le nom du zip soit coherent avec le tag de la Release GitHub (vN).
echo [7/9] Creation de manifest.json et de %ZIP_NAME%...
echo {"build": 1, "supprimer": []}>manifest.json
if not exist "installeur\output" mkdir "installeur\output"
if exist "installeur\output\%ZIP_NAME%" del /f /q "installeur\output\%ZIP_NAME%"
powershell -NoProfile -Command "try { Compress-Archive -Path 'dist\Scrabble\*','manifest.json' -DestinationPath 'installeur\output\%ZIP_NAME%' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo ERREUR : la creation de %ZIP_NAME% a echoue.
    popd
    popd
    exit /b 1
)
if not exist "installeur\output\%ZIP_NAME%" (
    echo.
    echo ERREUR : installeur\output\%ZIP_NAME% introuvable apres compression.
    popd
    popd
    exit /b 1
)
for /f "usebackq" %%s in (`powershell -NoProfile -Command "'{0:N2} Mo' -f ((Get-Item 'installeur\output\%ZIP_NAME%').Length / 1MB)"`) do (
    echo [OK] %ZIP_NAME% genere, taille : %%s
)
echo.

REM --- 8. Recopier l'installeur et le zip vers le partage, nettoyer le local -
echo [8/9] Recopie vers le partage et nettoyage du local...
if not exist "%ORIGDIR%\installeur\output" mkdir "%ORIGDIR%\installeur\output"
copy /y "installeur\output\!SETUP_NAME!" "%ORIGDIR%\installeur\output\!SETUP_NAME!"
if errorlevel 1 (
    echo.
    echo ERREUR : la recopie de l'installeur vers le partage a echoue.
    popd
    popd
    exit /b 1
)
echo [OK] Installeur copié vers %ORIGDIR%\installeur\output\
copy /y "installeur\output\%ZIP_NAME%" "%ORIGDIR%\installeur\output\%ZIP_NAME%"
if errorlevel 1 (
    echo.
    echo ERREUR : la recopie de %ZIP_NAME% vers le partage a echoue.
    popd
    popd
    exit /b 1
)
echo [OK] %ZIP_NAME% copié vers %ORIGDIR%\installeur\output\

popd
rmdir /s /q "%LOCALBUILD%"
echo [OK] Repertoire de build local nettoye ^(%LOCALBUILD%^)
echo.
echo installeur\output\%SETUP_NAME% et installeur\output\%ZIP_NAME% generes.
echo.

REM --- 9. Copier les artefacts vers le dossier fixe hors worktree (issue #472)
REM installeur\output est ignore par git : il disparait avec le worktree quand
REM on le supprime. On copie donc aussi les artefacts dans un dossier fixe hors
REM worktree, comme le fait deja le script de build d'Actualise pour le meme
REM probleme (perte de l'installeur Rummikub v13).
echo [9/9] Copie des artefacts vers le dossier fixe hors worktree...
set "FIXED_DIR=C:\CCW_Share\_derniers_builds\scrabble"
if not exist "%FIXED_DIR%" mkdir "%FIXED_DIR%"
if not exist "%FIXED_DIR%" (
    echo.
    echo ERREUR : impossible de creer %FIXED_DIR%.
    popd
    exit /b 1
)
copy /y "%ORIGDIR%\installeur\output\!SETUP_NAME!" "%FIXED_DIR%\!SETUP_NAME!"
if errorlevel 1 (
    echo.
    echo ERREUR : la copie de !SETUP_NAME! vers %FIXED_DIR% a echoue.
    popd
    exit /b 1
)
copy /y "%ORIGDIR%\installeur\output\%ZIP_NAME%" "%FIXED_DIR%\%ZIP_NAME%"
if errorlevel 1 (
    echo.
    echo ERREUR : la copie de %ZIP_NAME% vers %FIXED_DIR% a echoue.
    popd
    exit /b 1
)
for /f "usebackq" %%s in (`powershell -NoProfile -Command "(Get-Item '%FIXED_DIR%\!SETUP_NAME!').Length"`) do (
    echo [OK] %FIXED_DIR%\!SETUP_NAME! : %%s octets
)
for /f "usebackq" %%s in (`powershell -NoProfile -Command "(Get-Item '%FIXED_DIR%\%ZIP_NAME%').Length"`) do (
    echo [OK] %FIXED_DIR%\%ZIP_NAME% : %%s octets
)
echo.

echo ============================================
echo   REBUILD TERMINE AVEC SUCCES
echo ============================================
echo.
echo Rappel : lancez Scrabble.exe vous-meme depuis cette session
echo interactive pour verifier que tout fonctionne bien
echo ^(WebView2, dictionnaire, interface^).
echo.
echo Rappel : artefacts egalement copies hors worktree dans %FIXED_DIR%
echo (issue #472).
echo.

if "%PUBLIER%"=="1" (
    echo ============================================
    echo   PUBLICATION ^(--publier^)
    echo ============================================
    echo.
    echo [Publier 1/3] Calcul du SHA-256 de installeur\output\%ZIP_NAME%...
    if not exist "installeur\output\%ZIP_NAME%" set "PUBLIER_ERR=installeur\output\%ZIP_NAME% introuvable, publication annulee."
    if not defined PUBLIER_ERR (
        set "ZIP_SHA256="
        for /f "usebackq" %%h in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 'installeur\output\%ZIP_NAME%').Hash.ToLower()"`) do set "ZIP_SHA256=%%h"
        if "!ZIP_SHA256!"=="" set "PUBLIER_ERR=le calcul du SHA-256 de %ZIP_NAME% a echoue."
    )
    if not defined PUBLIER_ERR (
        echo SHA-256 : !ZIP_SHA256!
        echo.

        echo [Publier 2/3] Ecriture de version.json ^(build !NOUVEAU_BUILD!^)...
        echo {"build": !NOUVEAU_BUILD!, "sha256": "!ZIP_SHA256!"}>version.json
        type version.json
        echo.
        echo.

        echo [Publier 3/3] Commit git de version.json...
        git add version.json
        git commit -m "version.json : build !NOUVEAU_BUILD!, sha256 !ZIP_NAME!"
        if errorlevel 1 set "PUBLIER_ERR=le commit git de version.json a echoue."
    )
    if not defined PUBLIER_ERR (
        echo.
        echo ============================================
        echo   RAPPEL : git push et gh release create restent MANUELS.
        echo   Ce script ne les execute JAMAIS automatiquement.
        echo ============================================
        echo.
    )
)
if defined PUBLIER_ERR (
    echo.
    echo ERREUR : !PUBLIER_ERR!
    popd
    exit /b 1
)

if "%PUBLIER%"=="1" (
    echo Mode --publier : clone CCW conserve tel quel ^(commit version.json en
    echo place^), aucun reset. Push et release restent MANUELS.
    echo.
) else (
    echo Verification des commits locaux non pousses dans %ORIGDIR%...
    set "UNPUSHED_COUNT="
    for /f "usebackq" %%c in (`git -C %ORIGDIR% rev-list --count origin/master..HEAD 2^>nul`) do set "UNPUSHED_COUNT=%%c"
    if "!UNPUSHED_COUNT!"=="" set "UNPUSHED_COUNT=0"
    if not "!UNPUSHED_COUNT!"=="0" (
        echo.
        echo ****************************************************************
        echo *  ATTENTION : RESET IGNORE - COMMITS LOCAUX NON POUSSES       *
        echo ****************************************************************
        echo !UNPUSHED_COUNT! commit^(s^) present^(s^) dans %ORIGDIR%
        echo ^(HEAD^) ne sont pas encore pousses sur origin/master. Le reset --hard
        echo a ete saute pour ne pas les ecraser. Poussez ou sauvegardez ces
        echo commits avant de relancer un build.
        echo ****************************************************************
        echo.
    ) else (
        echo Aucun commit local non pousse : nettoyage du clone CCW ^(reset^)...
        git -C %ORIGDIR% reset --hard origin/master
        echo Clone CCW propre.
        echo.
    )
)

popd
exit /b 0
