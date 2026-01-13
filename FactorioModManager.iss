[Setup]
AppName=Factorio Mod Manager
AppVersion=1.0.0
AppPublisher=Steve Musyoka
AppPublisherURL=https://example.com
AppSupportURL=https://example.com
AppUpdatesURL=https://example.com
DefaultDirName={autopf}\FactorioModManager
DefaultGroupName=Factorio Mod Manager
OutputBaseFilename=FactorioModManagerSetup
OutputDir=dist
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
LicenseFile=LICENSE
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\FactorioModManager.exe

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

[Icons]
Name: "{group}\Factorio Mod Manager"; Filename: "{app}\FactorioModManager.exe"; IconFilename: "{app}\FactorioModManager.exe"
Name: "{group}\{cm:UninstallProgram,Factorio Mod Manager}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Factorio Mod Manager"; Filename: "{app}\FactorioModManager.exe"; IconFilename: "{app}\FactorioModManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FactorioModManager.exe"; Description: "{cm:LaunchProgram,Factorio Mod Manager}"; Flags: nowait postinstall skipifsilent
