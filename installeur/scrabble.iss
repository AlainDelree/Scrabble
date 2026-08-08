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
; Depuis l'issue #385, Actualise est une instance UNIQUE PARTAGEE
; (C:\Actualise\) entre toutes les applications qui l'utilisent (Scrabble,
; Rummikub, etc.), chacune avec son propre config_*.json ; on ne peut donc
; plus supposer que Scrabble est seul propriétaire de ce dossier.
; Version d'Actualise embarquée (Release GitHub AlainDelree/Actualise) :
; reflète le "build_installe" écrit dans config_actualise.json par
; CreerConfigActualiseSiAbsent ci-dessous (issue #352 — évite la valeur
; figée en dur). Valeur reelle injectee par rebuild_scrabble.bat via
; /DActualiseVersion=<build lu dans manifest.json du zip Actualise
; telecharge> ; "3" n'est qu'un repli de secours pour une compilation
; manuelle isolee de ce script.
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
#define MyActualiseDir "{sd}\Actualise"
; Ancien emplacement (une instance d'Actualise par application) : nettoyé
; avant installation si présent (issue #385, cf. [Code] ci-dessous).
#define MyOldActualiseDir "{sd}\Actualise_Scrabble"
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
; Droits administrateur requis (issue #388) : nécessaire pour écrire dans
; C:\Actualise\ (racine du disque système, protégée pour les utilisateurs
; standard). Avec PrivilegesRequired=admin, {autopf}/{autodesktop}/
; {autoprograms} résolvent respectivement vers C:\Program Files\, le Bureau
; commun et le menu Démarrer commun (emplacements "tous les utilisateurs").
PrivilegesRequired=admin
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
; Actualise : updater autonome, installé dans l'instance partagée
; C:\Actualise\ (pas dans {app}) car il survit aux mises à jour/
; réinstallations de Scrabble lui-même, et peut déjà être présent si une
; autre application (Rummikub, etc.) l'a installé avant. Copie récursive
; (Actualise.exe + _internal\, runtime Python + DLL, mode PyInstaller
; --onedir). Pas de "ignoreversion" ici (issue #385) : on laisse Inno Setup
; comparer nativement la version du fichier embarqué à celle déjà présente
; et ne remplacer que si elle est plus récente, pour ne pas écraser une
; version plus à jour installée entretemps par une autre application
; partageant cette même instance.
Source: "{#MyActualiseSrcDir}\*"; DestDir: "{#MyActualiseDir}"; Flags: recursesubdirs createallsubdirs

[Dirs]
Name: "{#MyActualiseDir}"
Name: "{#MyActualiseDir}\attente"

[Icons]
; Les raccourcis pointent vers Actualise.exe (jamais directement vers
; Scrabble.exe) : Actualise met Scrabble à jour depuis les GitHub Releases
; avant de le lancer, à chaque démarrage. L'instance C:\Actualise\ étant
; partagée entre plusieurs applications (issue #385), l'argument
; "--config scrabble" indique à Actualise.exe de lire config_scrabble.json
; plutôt que celui d'une autre application installée à côté.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; Parameters: "--config scrabble"; IconFilename: "{app}\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; Parameters: "--config scrabble"; IconFilename: "{app}\{#MyAppIcoName}"

[Code]
function EchapperJSON(const Texte: String): String;
begin
  Result := Texte;
  StringChangeEx(Result, '\', '\\', True);
end;

// Instance unique partagée C:\Actualise\ (issue #385) : avant l'installation
// des fichiers, on supprime entièrement l'ancien emplacement par-application
// C:\Actualise_Scrabble\ s'il subsiste d'une installation antérieure.
procedure SupprimerAncienneInstanceActualise();
var
  DossierAncien: String;
begin
  DossierAncien := ExpandConstant('{#MyOldActualiseDir}');
  if DirExists(DossierAncien) then
    DelTree(DossierAncien, True, True, True);
end;

// Génère config_scrabble.json dans l'instance partagée C:\Actualise\,
// consommé par Actualise.exe (lancé avec "--config scrabble") pour savoir
// quel dépôt GitHub surveiller, où est installé Scrabble et quelle icône
// afficher (issue #344, adapté à l'instance partagée par l'issue #385).
procedure CreerConfigScrabble();
var
  DossierActualise, RepertoireInstallation, Contenu: String;
begin
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  RepertoireInstallation := ExpandConstant('{app}') + '\';

  Contenu :=
    '{' + #13#10 +
    '  "nom": "Scrabble",' + #13#10 +
    '  "depot_github": "AlainDelree/Scrabble",' + #13#10 +
    '  "build_installe": {#ScrabbleBuildInstalle},' + #13#10 +
    '  "repertoire_installation": "' + EchapperJSON(RepertoireInstallation) + '",' + #13#10 +
    '  "executable": "Scrabble.exe",' + #13#10 +
    '  "icone": "' + EchapperJSON(ExpandConstant('{app}') + '\scrabble.ico') + '",' + #13#10 +
    '  "topic_ntfy": "hippocampe-scrabble-y9htxM7q"' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config_scrabble.json', Contenu, False);
end;

// Génère config_actualise.json dans l'instance partagée, mais seulement s'il
// n'existe pas déjà : une autre application (Rummikub, etc.) partageant la
// même instance C:\Actualise\ a pu le créer avant nous ; il ne faut pas
// écraser ses réglages (issue #385).
procedure CreerConfigActualiseSiAbsent();
var
  DossierActualise, ZoneAttente, Contenu: String;
begin
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  if FileExists(DossierActualise + 'config_actualise.json') then
    Exit;

  ZoneAttente := DossierActualise + 'attente\';

  Contenu :=
    '{' + #13#10 +
    '  "build_installe": {#ActualiseVersion},' + #13#10 +
    '  "depot_github": "AlainDelree/Actualise",' + #13#10 +
    '  "zone_attente": "' + EchapperJSON(ZoneAttente) + '"' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config_actualise.json', Contenu, False);
end;

// Dépose le chemin de l'instance partagée d'Actualise dans un emplacement
// fixe, indépendant du dossier d'installation de Scrabble : consommé dans
// un chantier ultérieur par Scrabble pour localiser ActualiseUI (issue #385).
procedure CreerActualisePathTxt();
var
  DossierScrabble: String;
begin
  DossierScrabble := 'C:\Scrabble\';
  ForceDirectories(DossierScrabble);
  SaveStringToFile(DossierScrabble + 'actualise_path.txt', ExpandConstant('{#MyActualiseDir}') + '\', False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    SupprimerAncienneInstanceActualise();
  if CurStep = ssPostInstall then
  begin
    CreerConfigScrabble();
    CreerConfigActualiseSiAbsent();
    CreerActualisePathTxt();
  end;
end;

// Indique si un autre config_*.json (une autre application partageant
// l'instance C:\Actualise\) subsiste après la suppression de config_scrabble.json.
function ExisteAutreConfigActualise(): Boolean;
var
  DossierActualise: String;
  FindRec: TFindRec;
begin
  Result := False;
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  if FindFirst(DossierActualise + 'config_*.json', FindRec) then
  begin
    try
      Result := True;
    finally
      FindClose(FindRec);
    end;
  end;
end;

// À la désinstallation, on ne retire que ce qui appartient à Scrabble dans
// l'instance partagée : config_scrabble.json. Le dossier C:\Actualise\
// lui-même (et son contenu partagé, Actualise.exe compris) n'est supprimé
// que si plus aucun autre config_*.json n'y subsiste, c'est-à-dire si
// aucune autre application ne partage plus cette instance (issue #385).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DossierActualise, FichierConfigScrabble: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
    FichierConfigScrabble := DossierActualise + 'config_scrabble.json';
    if FileExists(FichierConfigScrabble) then
      DeleteFile(FichierConfigScrabble);
    if not ExisteAutreConfigActualise() then
      DelTree(DossierActualise, True, True, True);
  end;
end;

[UninstallDelete]
; Nettoyage des fichiers générés à l'usage par le jeu (config.json, logs/,
; data/parties.db, mots_ajoutes_*/mots_retires_*) qui ne font pas partie de
; [Files] et que le désinstalleur par défaut d'Inno Setup ne supprime donc pas.
; La suppression de config_scrabble.json (instance partagée C:\Actualise\)
; est traitée séparément par CurUninstallStepChanged ci-dessus, car elle est
; conditionnelle au partage avec d'autres applications.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\config.json"
