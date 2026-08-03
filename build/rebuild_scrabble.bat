@echo off
setlocal enabledelayedexpansion
pushd "%~dp0.."
set "ORIGDIR=%CD%"

echo ============================================
echo   Rebuild Scrabble.exe
echo ============================================
echo.

REM --- 0. Verifier les dependances externes non versionnees -----------------
echo [0/9] Verification des dependances externes (hors git)...
if not exist ".tools\InnoSetup6\ISCC.exe" (
    echo.
    echo ERREUR : .tools\InnoSetup6\ISCC.exe introuvable.
    echo Deposez l'installation portable d'Inno Setup 6 a cet emplacement exact
    echo ^(.tools\InnoSetup6\^) avant de lancer ce script ^(voir installeur\README.md,
    echo section Prerequis^).
    popd
    exit /b 1
)
if not exist "data\dictionnaire\French-Scrabble-ODS8-main" (
    echo.
    echo ERREUR : data\dictionnaire\French-Scrabble-ODS8-main introuvable.
    echo Deposez le dictionnaire ODS8 a cet emplacement exact
    echo ^(data\dictionnaire\French-Scrabble-ODS8-main\^) avant de lancer ce script
    echo ^(voir data\dictionnaire\README.md^).
    popd
    exit /b 1
)
echo Dependances externes presentes. OK.
echo.

REM --- 1. Copier les sources vers un repertoire local de la VM ---------------
REM Contournement temporaire (~10 jours, avant migration vers PC Windows
REM physique) : PyInstaller et ISCC produisent des fichiers tronques quand le
REM build tourne directement sur le partage VirtualBox (\\VBOXSVR\...). On
REM copie donc tout ce qui est necessaire au build vers un dossier local
REM (C:\Temp\ScrabbleBuild), on construit entierement la-bas, puis on recopie
REM uniquement l'installeur final vers le partage.
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
robocopy "%ORIGDIR%" "%LOCALBUILD%" /E /XD ".git" "venv" ".venv_build" "dist" "build" "__pycache__" ".pytest_cache" "logs" "Exemples plateau" "issue-attachments" /NFL /NDL /NJH /NJS /NC /NS /NP >nul
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
    if errorlevel 1 (
        echo.
        echo ERREUR : impossible de creer .venv_build. Verifiez l'installation Python.
        popd
        popd
        exit /b 1
    )
    call ".venv_build\Scripts\python.exe" -m pip install --upgrade pip >nul
    call ".venv_build\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERREUR : l'installation de requirements.txt a echoue.
        popd
        popd
        exit /b 1
    )
    call ".venv_build\Scripts\pip.exe" install pyinstaller
    if errorlevel 1 (
        echo.
        echo ERREUR : l'installation de pyinstaller a echoue.
        popd
        popd
        exit /b 1
    )
) else (
    echo .venv_build present. OK.
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
echo [4/9] Build PyInstaller en cours (peut prendre plusieurs minutes)...
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

REM --- 6. Telecharger et extraire Actualise (issue #345, issue #346) ---------
REM Actualise.exe + son dossier _internal\ (runtime Python + DLL, mode
REM PyInstaller --onedir) sont l'updater embarque dans l'installeur (cf.
REM scrabble.iss, Source attendue : C:\Temp\ScrabbleBuild\Actualise_dist\).
REM Recupere depuis la Release v3 du depot AlainDelree/Actualise.
echo [6/9] Telechargement d'Actualise (updater)...
set "ACTUALISE_URL=https://github.com/AlainDelree/Actualise/releases/download/v3/actualise.zip"
set "ACTUALISE_ZIP=%LOCALBUILD%\actualise.zip"
set "ACTUALISE_EXTRACT=%LOCALBUILD%\actualise_extract"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ACTUALISE_URL%' -OutFile '%ACTUALISE_ZIP%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo ERREUR : le telechargement d'actualise.zip a echoue ^(%ACTUALISE_URL%^).
    popd
    popd
    exit /b 1
)
powershell -NoProfile -Command "try { Expand-Archive -Path '%ACTUALISE_ZIP%' -DestinationPath '%ACTUALISE_EXTRACT%' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo ERREUR : l'extraction d'actualise.zip a echoue.
    popd
    popd
    exit /b 1
)
robocopy "%ACTUALISE_EXTRACT%" "%LOCALBUILD%\Actualise_dist" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul
if %errorlevel% geq 8 (
    echo.
    echo ERREUR : la copie de %ACTUALISE_EXTRACT% vers %LOCALBUILD%\Actualise_dist a echoue.
    popd
    popd
    exit /b 1
)
echo Actualise pret : %LOCALBUILD%\Actualise_dist
echo.

REM --- 7. Compiler l'installeur Windows (Inno Setup) ------------------------
echo [7/9] Compilation de l'installeur Inno Setup...
if not exist ".tools\InnoSetup6\ISCC.exe" (
    echo.
    echo ERREUR : .tools\InnoSetup6\ISCC.exe introuvable. Verifiez l'installation
    echo portable d'Inno Setup sur cette machine ^(voir installeur\README.md^).
    popd
    popd
    exit /b 1
)
call ".tools\InnoSetup6\ISCC.exe" installeur\scrabble.iss
if errorlevel 1 (
    echo.
    echo ERREUR : la compilation Inno Setup a echoue. Voir les messages ci-dessus.
    popd
    popd
    exit /b 1
)
if not exist "installeur\output" mkdir "installeur\output"
copy "C:\Temp\ScrabbleOutput\Scrabble-Setup.exe" "installeur\output\Scrabble-Setup.exe"
echo [OK] Installeur copié vers installeur\output\ ^(local^)
echo.

REM --- 8. Creer manifest.json et zipper vers scrabble.zip (issue #345) ------
REM scrabble.zip = dist\Scrabble\ + manifest.json, sans dossier englobant
REM (l'updater Actualise l'extrait directement par-dessus le dossier installe).
REM Nom fixe (pas de numero de version) : le numero vit dans le tag de la
REM Release GitHub, pas dans le nom de fichier.
echo [8/9] Creation de manifest.json et de scrabble.zip...
echo {"build": 1, "supprimer": []}>manifest.json
if not exist "installeur\output" mkdir "installeur\output"
if exist "installeur\output\scrabble.zip" del /f /q "installeur\output\scrabble.zip"
powershell -NoProfile -Command "try { Compress-Archive -Path 'dist\Scrabble\*','manifest.json' -DestinationPath 'installeur\output\scrabble.zip' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo ERREUR : la creation de scrabble.zip a echoue.
    popd
    popd
    exit /b 1
)
if not exist "installeur\output\scrabble.zip" (
    echo.
    echo ERREUR : installeur\output\scrabble.zip introuvable apres compression.
    popd
    popd
    exit /b 1
)
for /f "usebackq" %%s in (`powershell -NoProfile -Command "'{0:N2} Mo' -f ((Get-Item 'installeur\output\scrabble.zip').Length / 1MB)"`) do (
    echo [OK] scrabble.zip genere, taille : %%s
)
echo.

REM --- 9. Recopier l'installeur et le zip vers le partage, nettoyer le local -
echo [9/9] Recopie vers le partage et nettoyage du local...
if not exist "%ORIGDIR%\installeur\output" mkdir "%ORIGDIR%\installeur\output"
copy /y "installeur\output\Scrabble-Setup.exe" "%ORIGDIR%\installeur\output\Scrabble-Setup.exe"
if errorlevel 1 (
    echo.
    echo ERREUR : la recopie de l'installeur vers le partage a echoue.
    popd
    popd
    exit /b 1
)
echo [OK] Installeur copié vers %ORIGDIR%\installeur\output\
copy /y "installeur\output\scrabble.zip" "%ORIGDIR%\installeur\output\scrabble.zip"
if errorlevel 1 (
    echo.
    echo ERREUR : la recopie de scrabble.zip vers le partage a echoue.
    popd
    popd
    exit /b 1
)
echo [OK] scrabble.zip copié vers %ORIGDIR%\installeur\output\

popd
rmdir /s /q "%LOCALBUILD%"
echo [OK] Repertoire de build local nettoye ^(%LOCALBUILD%^)
echo.
echo installeur\output\Scrabble-Setup.exe et installeur\output\scrabble.zip generes.
echo.
echo ============================================
echo   REBUILD TERMINE AVEC SUCCES
echo ============================================
echo.
echo Rappel : lancez Scrabble.exe vous-meme depuis cette session
echo interactive pour verifier que tout fonctionne bien
echo ^(WebView2, dictionnaire, interface^).
echo.
echo Nettoyage du clone CCW (reset commits locaux)...
git -C Z:\CCW\scrabble reset --hard origin/master
echo Clone CCW propre.
echo.
popd
exit /b 0
