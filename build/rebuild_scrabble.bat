@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
pushd "%~dp0.."

echo ============================================
echo   Rebuild Scrabble.exe
echo ============================================
echo.

REM --- 0. Verifier les dependances externes non versionnees -----------------
echo [0/5] Verification des dependances externes (hors git)...
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

REM --- 1. Preparer l'environnement virtuel de build -------------------------
echo [1/5] Verification de l'environnement virtuel de build...
if not exist ".venv_build\Scripts\python.exe" (
    echo .venv_build introuvable : creation en cours...
    python -m venv .venv_build
    if errorlevel 1 (
        echo.
        echo ERREUR : impossible de creer .venv_build. Verifiez l'installation Python.
        popd
        exit /b 1
    )
    call ".venv_build\Scripts\python.exe" -m pip install --upgrade pip >nul
    call ".venv_build\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERREUR : l'installation de requirements.txt a echoue.
        popd
        exit /b 1
    )
    call ".venv_build\Scripts\pip.exe" install pyinstaller
    if errorlevel 1 (
        echo.
        echo ERREUR : l'installation de pyinstaller a echoue.
        popd
        exit /b 1
    )
) else (
    echo .venv_build present. OK.
)
echo.

REM --- 2. Fermer Scrabble.exe s'il tourne encore ---------------------------
echo [2/5] Fermeture de Scrabble.exe si necessaire...
tasklist /fi "imagename eq Scrabble.exe" 2>nul | find /i "Scrabble.exe" >nul
if not errorlevel 1 (
    echo Scrabble.exe est en cours d'execution : fermeture...
    taskkill /im Scrabble.exe /f >nul 2>&1
    timeout /t 2 >nul
) else (
    echo Aucune instance en cours. OK.
)
echo.

REM --- 3. Lancer le build PyInstaller ---------------------------------------
echo [3/5] Build PyInstaller en cours (peut prendre plusieurs minutes)...
call ".venv_build\Scripts\pyinstaller.exe" scrabble.spec -y
if errorlevel 1 (
    echo.
    echo ERREUR : le build PyInstaller a echoue. Voir les messages ci-dessus.
    popd
    exit /b 1
)
echo.
echo Build termine avec succes.
echo.

REM --- 4. Verifier le resultat ----------------------------------------------
echo [4/5] Verification du resultat...
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
    exit /b 1
)

REM --- 5. Compiler l'installeur Windows (Inno Setup) ------------------------
echo [5/5] Compilation de l'installeur Inno Setup...
if not exist ".tools\InnoSetup6\ISCC.exe" (
    echo.
    echo ERREUR : .tools\InnoSetup6\ISCC.exe introuvable. Verifiez l'installation
    echo portable d'Inno Setup sur cette machine ^(voir installeur\README.md^).
    popd
    exit /b 1
)
call ".tools\InnoSetup6\ISCC.exe" installeur\scrabble.iss
if errorlevel 1 (
    echo.
    echo ERREUR : la compilation Inno Setup a echoue. Voir les messages ci-dessus.
    popd
    exit /b 1
)
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
