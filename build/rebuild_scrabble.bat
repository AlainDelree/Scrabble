@echo off
setlocal enabledelayedexpansion
pushd "%~dp0.."
set "ORIGDIR=%CD%"

echo ============================================
echo   Rebuild Scrabble.exe
echo ============================================
echo.

REM --- 0. Verifier les dependances externes non versionnees -----------------
echo [0/7] Verification des dependances externes (hors git)...
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
echo [1/7] Copie des sources vers le repertoire de build local...
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
echo [2/7] Verification de l'environnement virtuel de build...
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
echo [3/7] Fermeture de Scrabble.exe si necessaire...
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
echo [4/7] Build PyInstaller en cours (peut prendre plusieurs minutes)...
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
echo [5/7] Verification du resultat...
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
echo [6/7] Compilation de l'installeur Inno Setup...
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

REM --- 7. Recopier l'installeur vers le partage et nettoyer le local --------
echo [7/7] Recopie de l'installeur vers le partage et nettoyage du local...
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

popd
rmdir /s /q "%LOCALBUILD%"
echo [OK] Repertoire de build local nettoye ^(%LOCALBUILD%^)
echo.
echo installeur\output\Scrabble-Setup.exe genere.
echo.
echo ============================================
echo   REBUILD TERMINE AVEC SUCCES
echo ============================================
echo.
echo Rappel : lancez Scrabble.exe vous-meme depuis cette session
echo interactive pour verifier que tout fonctionne bien
echo ^(WebView2, dictionnaire, interface^).
echo.
popd
exit /b 0
