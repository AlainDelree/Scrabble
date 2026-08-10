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
; Scrabble à jour depuis les GitHub Releases avant de le lancer. Depuis
; l'issue #407, il n'est plus embarqué dans ce setup : il est distribué via
; son propre Actualise-Setup.exe indépendant. Le jeu le lance lui-même au
; démarrage s'il est présent (cf. main.py) ; le raccourci utilisateur pointe
; donc directement vers Scrabble.exe.
; Depuis l'issue #385, Actualise est une instance UNIQUE PARTAGEE
; (C:\Actualise\) entre toutes les applications qui l'utilisent (Scrabble,
; Rummikub, etc.), chacune avec son propre config_*.json ; on ne peut donc
; plus supposer que Scrabble est seul propriétaire de ce dossier.
; Icône affichée sur le raccourci (Bureau/menu Démarrer), déployée dans
; {app} par la section [Files] ci-dessous (embarquée par PyInstaller, cf.
; scrabble.spec).
#define MyAppIcoName "scrabble.ico"
#define MyActualiseDir "C:\Actualise"
; Ancien emplacement (une instance d'Actualise par application) : nettoyé
; avant installation si présent (issue #385, cf. [Code] ci-dessous).
#define MyOldActualiseDir "C:\Actualise_Scrabble"
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
; Numéro de build visible dans les métadonnées Windows de Scrabble-Setup.exe
; (clic droit -> Propriétés -> Détails -> Version du fichier), issue #389 :
; sans cela, impossible de distinguer visuellement deux exécutables sans les
; ouvrir.
VersionInfoVersion={#ScrabbleBuildInstalle}.0.0.0
VersionInfoProductName=Scrabble
VersionInfoDescription=Scrabble Setup build {#ScrabbleBuildInstalle}
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
OutputBaseFilename=Scrabble-Setup-v{#ScrabbleBuildInstalle}
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

[Dirs]
Name: "{#MyActualiseDir}"

[Icons]
; Les raccourcis pointent directement vers Scrabble.exe (issue #407) :
; Actualise n'est plus embarqué dans ce setup, il est distribué séparément
; via son propre Actualise-Setup.exe. Le jeu le lance lui-même au démarrage
; s'il est présent (cf. main.py).
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcoName}"

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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    SupprimerAncienneInstanceActualise();
  if CurStep = ssPostInstall then
    CreerConfigScrabble();
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
