[Setup]
AppId={{D4A8E4F0-8B5C-4F9E-9C3A-7B2F1E8D6C4A}
AppName=Factorio Mod Manager
AppVersion=1.0.0
AppVerName=Factorio Mod Manager 1.0.0
AppPublisher=Steve Musyoka
AppPublisherURL=https://github.com/Musyoka2020-eng/FactorioManager
AppSupportURL=https://github.com/Musyoka2020-eng/FactorioManager/issues
AppUpdatesURL=https://github.com/Musyoka2020-eng/FactorioManager/releases
DefaultDirName={autopf}\FactorioModManager
DefaultGroupName=Factorio Mod Manager
AllowNoIcons=yes
OutputBaseFilename=FactorioModManagerSetup-1.0.0
OutputDir=dist
Compression=lzma2
SolidCompression=yes
SolidCompressionLevel=max
WizardStyle=modern
WizardSizePercent=100
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
CloseApplications=yes
RestartApplications=no
PrivilegesRequired=lowest
ShowComponentSizes=no
DisableProgramGroupPage=no
DisableReadyPage=no
DisableFinishedPage=no
LicenseFile=LICENSE
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\FactorioModManager.exe
VersionInfoVersion=1.0.0.0
VersionInfoCompany=Factorio Mod Manager Contributors
VersionInfoFileDescription=Factorio Mod Manager - Desktop Application for Managing Factorio Mods
VersionInfoProductName=Factorio Mod Manager
UninstallDisplayName=Factorio Mod Manager

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
Type: filesandordirs; Name: "{app}\ms-playwright"
Type: filesandordirs; Name: "{app}\.playwright"

[Files]
Source: "dist\FactorioModManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Factorio Mod Manager"; Filename: "{app}\FactorioModManager.exe"; WorkingDir: "{app}"; Comment: "Download and manage Factorio mods"; IconFilename: "{app}\FactorioModManager.exe"; IconIndex: 0
Name: "{group}\{cm:UninstallProgram,Factorio Mod Manager}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Factorio Mod Manager"; Filename: "{app}\FactorioModManager.exe"; WorkingDir: "{app}"; Comment: "Download and manage Factorio mods"; Tasks: desktopicon

[Run]
Filename: "{app}\FactorioModManager.exe"; Description: "{cm:LaunchProgram,Factorio Mod Manager}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create a shortcut to the app in the start menu
    CreateDirectory(ExpandConstant('{userprograms}\Factorio Mod Manager'));
  end;
end;
