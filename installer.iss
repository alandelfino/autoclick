; Script do Inno Setup para compilar o instalador do AutoClick com suporte a Português e Inglês.
#define AppName "AutoClick"
#define AppVersion "1.0.0"
#define AppPublisher "AutoClick"
#define AppExeName "AutoClick.exe"

[Setup]
AppId={{5E4C0D43-4C0C-4A2D-BE4E-7C1C5220C4F6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Define privilégios mais baixos para permitir instalação de usuário sem UAC (instala em AppData se executado sem admin)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir=Output
OutputBaseFilename=AutoClickSetup
SetupIconFile=logo.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\AutoClick\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  LangCode: String;
  ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    if ActiveLanguage = 'portuguese' then
      LangCode := 'pt'
    else
      LangCode := 'en';
      
    ConfigContent := '{' + #13#10 +
                     '    "language": "' + LangCode + '"' + #13#10 +
                     '}';
                     
    if SaveStringToFile(ExpandConstant('{app}\config.json'), ConfigContent, False) then
      Log('Config.json written with language: ' + LangCode)
    else
      Log('Failed to write config.json.');
  end;
end;
