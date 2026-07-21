@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d C:\CCW\Scrabble

echo ============================================
echo   Rebuild Scrabble.exe
echo ============================================
echo.

REM --- 1. Fermer Scrabble.exe s'il tourne encore ---------------------------
echo [1/4] Fermeture de Scrabble.exe si necessaire...
tasklist /fi "imagename eq Scrabble.exe" 2>nul | find /i "Scrabble.exe" >nul
if not errorlevel 1 (
    echo Scrabble.exe est en cours d'execution : fermeture...
    taskkill /im Scrabble.exe /f >nul 2>&1
    timeout /t 2 >nul
) else (
    echo Aucune instance en cours. OK.
)
echo.

REM --- 2. Lancer le build PyInstaller ---------------------------------------
echo [2/4] Build PyInstaller en cours (peut prendre plusieurs minutes)...
call ".venv_build\Scripts\pyinstaller.exe" scrabble.spec -y
if errorlevel 1 (
    echo.
    echo ERREUR : le build PyInstaller a echoue. Voir les messages ci-dessus.
    pause
    exit /b 1
)
echo.
echo Build termine avec succes.
echo.

REM --- 3. Verifier le resultat ----------------------------------------------
echo [3/4] Verification du resultat...
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
    pause
    exit /b 1
)

REM --- 4. Compiler l'installeur Windows (Inno Setup) ------------------------
echo [4/4] Compilation de l'installeur Inno Setup...
if not exist ".tools\InnoSetup6\ISCC.exe" (
    echo.
    echo ERREUR : .tools\InnoSetup6\ISCC.exe introuvable. Verifiez l'installation
    echo portable d'Inno Setup sur cette machine ^(voir installeur\README.md^).
    pause
    exit /b 1
)
call ".tools\InnoSetup6\ISCC.exe" installeur\scrabble.iss
if errorlevel 1 (
    echo.
    echo ERREUR : la compilation Inno Setup a echoue. Voir les messages ci-dessus.
    pause
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
pause
