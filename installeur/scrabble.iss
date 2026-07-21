; Script Inno Setup pour l'installeur Windows du jeu Scrabble (issue #217, issue A).
;
; Compilation : depuis Inno Setup Compiler (ISCC.exe), à la racine du dépôt ou
; depuis ce dossier :
;   ISCC.exe installeur\scrabble.iss
; Produit : installeur\output\Scrabble-Setup.exe (non commité, voir README.md
; de ce dossier).
;
; Prérequis : le contenu de dist\Scrabble\ doit déjà exister (généré par
; ``pyinstaller scrabble.spec`` depuis la racine du dépôt, cf. scrabble.spec).
; Cette issue ne s'occupe pas de déclencher ce build PyInstaller ; l'intégration
; au pipeline (rebuild_scrabble.bat) est traitée dans l'Issue B, à venir.

#define MyAppName "Scrabble"
#define MyAppVersion "1.0"
#define MyAppPublisher "Alain Delree"
#define MyAppExeName "Scrabble.exe"
#define MyDistDir "..\dist\Scrabble"

[Setup]
; GUID fixe et unique à l'application : NE PAS régénérer (sert à Windows pour
; identifier les mises à jour vs. une nouvelle installation lors des futures
; versions).
AppId={{EC04D19C-69EA-4116-9EB8-C51A30E56EBA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Aucun droit administrateur requis : installation dans le profil utilisateur
; courant. Avec PrivilegesRequired=lowest, {autopf}/{autodesktop}/{autoprograms}
; résolvent respectivement vers %LOCALAPPDATA%\Programs, le Bureau et le menu
; Démarrer de l'utilisateur courant (pas les emplacements "tous les
; utilisateurs", qui nécessiteraient des droits admin).
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
SetupIconFile=..\assets\scrabble.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
OutputDir=output
OutputBaseFilename=Scrabble-Setup
; Application graphique volumineuse (~90 Mo) : pas de mode "onefile", on
; installe le contenu tel quel (cf. [Files] ci-dessous).
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
; Copie récursive de tout dist\Scrabble\ (généré par PyInstaller, dictionnaire
; déjà embarqué) vers le dossier d'installation.
;
; Exclusions volontaires : config.json, data\parties.db et logs\* sont des
; fichiers générés à l'usage (préférences utilisateur, historique de parties,
; journaux) que scrabble.config.RACINE_PROJET recrée tout seul au premier
; lancement (mode gelé : à côté de Scrabble.exe, cf. scrabble.spec). S'ils
; traînent dans dist\Scrabble\ au moment du build (reliquat d'un lancement de
; test de l'exe gelé sur la machine de build), il ne faut PAS les embarquer
; dans l'installeur : un nouvel utilisateur hériterait sinon des préférences/
; de l'historique de parties de quelqu'un d'autre dès la première ouverture.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Excludes: "config.json,logs\*,data\parties.db,data\*.db"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[UninstallDelete]
; Nettoyage des fichiers générés à l'usage par le jeu (config.json, logs/,
; data/parties.db, mots_ajoutes_*/mots_retires_*) qui ne font pas partie de
; [Files] et que le désinstalleur par défaut d'Inno Setup ne supprime donc pas.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\config.json"
