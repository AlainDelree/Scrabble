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
#define MyAppPublisher "Alain Delree"
#define MyAppExeName "Scrabble.exe"
#define MyDistDir "..\dist\Scrabble"
; Actualise (dépôt AlainDelree/Actualise) est l'updater autonome qui met
; Scrabble à jour depuis les GitHub Releases avant de le lancer (issue #344,
; architecture complète dans CONCEPTION.md du dépôt Actualise). Le raccourci
; utilisateur doit pointer vers lui, jamais directement vers Scrabble.exe.
; Version d'Actualise embarquée (Release GitHub AlainDelree/Actualise) :
; reflète le "build_installe" écrit dans config.json par CreerConfigActualise
; ci-dessous (issue #352 — évite la valeur figée en dur). Valeur reelle
; injectee par rebuild_scrabble.bat via /DActualiseVersion=<build lu dans
; manifest.json du zip Actualise telecharge> ; "3" n'est qu'un repli de
; secours pour une compilation manuelle isolee de ce script.
#ifndef ActualiseVersion
  #define ActualiseVersion "3"
#endif
#define MyActualiseExeName "Actualise.exe"
; Icône affichée sur les raccourcis (Bureau/menu Démarrer), déployée dans
; {app} par la section [Files] ci-dessous (embarquée par PyInstaller, cf.
; scrabble.spec) : sans elle, les raccourcis pointant vers Actualise.exe
; afficheraient l'icône générique d'Actualise.
#define MyAppIcoName "scrabble.ico"
; Déposé par build\rebuild_scrabble.bat avant l'appel à ISCC (Actualise.exe +
; son dossier _internal\, runtime Python + DLL, mode PyInstaller --onedir).
#define MyActualiseSrcDir "C:\Temp\ScrabbleBuild\Actualise_dist"
#define MyActualiseDir "{sd}\Actualise_Scrabble"
; Numero de build de Scrabble reellement embarque dans ce setup (lu dans
; version.json a la racine du depot par rebuild_scrabble.bat, injecte via
; /DScrabbleBuildInstalle=<build>) ; "1" n'est qu'un repli de secours pour
; une compilation manuelle isolee de ce script.
#ifndef ScrabbleBuildInstalle
  #define ScrabbleBuildInstalle "1"
#endif

[Setup]
; GUID fixe et unique à l'application : NE PAS régénérer (sert à Windows pour
; identifier les mises à jour vs. une nouvelle installation lors des futures
; versions).
AppId={{EC04D19C-69EA-4116-9EB8-C51A30E56EBA}
AppName={#MyAppName}
AppVersion={#ScrabbleBuildInstalle}
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
OutputDir=C:\Temp\ScrabbleOutput
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
; Actualise : updater autonome, installé à côté de Scrabble (pas dans {app})
; car il survit aux mises à jour/réinstallations de Scrabble lui-même. Copie
; récursive (Actualise.exe + _internal\, runtime Python + DLL, mode
; PyInstaller --onedir).
Source: "{#MyActualiseSrcDir}\*"; DestDir: "{#MyActualiseDir}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{#MyActualiseDir}"
Name: "{#MyActualiseDir}\attente"

[Icons]
; Les raccourcis pointent vers Actualise.exe (jamais directement vers
; Scrabble.exe) : Actualise met Scrabble à jour depuis les GitHub Releases
; avant de le lancer, à chaque démarrage.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; IconFilename: "{app}\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; IconFilename: "{app}\{#MyAppIcoName}"

[Code]
// Génère le config.json d'Actualise, consommé par Actualise.exe au
// lancement pour savoir quel dépôt GitHub surveiller, où est installé
// Scrabble et où stocker les archives téléchargées (issue #344).
function EchapperJSON(const Texte: String): String;
begin
  Result := Texte;
  StringChangeEx(Result, '\', '\\', True);
end;

procedure CreerConfigActualise();
var
  DossierActualise, RepertoireInstallation, ZoneAttente, Contenu: String;
begin
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  RepertoireInstallation := ExpandConstant('{app}') + '\';
  ZoneAttente := DossierActualise + 'attente\';

  Contenu :=
    '{' + #13#10 +
    '  "actualise": {' + #13#10 +
    '    "build_installe": {#ActualiseVersion},' + #13#10 +
    '    "depot_github": "AlainDelree/Actualise"' + #13#10 +
    '  },' + #13#10 +
    '  "application_cible": {' + #13#10 +
    '    "nom": "Scrabble",' + #13#10 +
    '    "depot_github": "AlainDelree/Scrabble",' + #13#10 +
    '    "build_installe": {#ScrabbleBuildInstalle},' + #13#10 +
    '    "repertoire_installation": "' + EchapperJSON(RepertoireInstallation) + '",' + #13#10 +
    '    "executable": "Scrabble.exe",' + #13#10 +
    '    "icone": "' + EchapperJSON(ExpandConstant('{app}') + '\scrabble.ico') + '"' + #13#10 +
    '  },' + #13#10 +
    '  "zone_attente": "' + EchapperJSON(ZoneAttente) + '",' + #13#10 +
    '  "topic_ntfy": "hippocampe-scrabble-y9htxM7q"' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config.json', Contenu, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    CreerConfigActualise();
end;

[UninstallDelete]
; Nettoyage des fichiers générés à l'usage par le jeu (config.json, logs/,
; data/parties.db, mots_ajoutes_*/mots_retires_*) qui ne font pas partie de
; [Files] et que le désinstalleur par défaut d'Inno Setup ne supprime donc pas.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\config.json"
