@echo off
REM Lanceur interactif : appelle rebuild_scrabble.bat puis garde la fenetre
REM ouverte pour lecture du resultat. Ne jamais utiliser ce script en contexte
REM automatise (service CCW) : c'est rebuild_scrabble.bat qu'il faut appeler
REM directement dans ce cas (voir installeur\README.md).
call "%~dp0rebuild_scrabble.bat"
set "CODE_SORTIE=%errorlevel%"
echo.
pause
exit /b %CODE_SORTIE%
