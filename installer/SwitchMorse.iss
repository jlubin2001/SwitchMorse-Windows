; SwitchMorse Windows - the installer (Inno Setup 6, jrsoftware.org).
; Built by tools\build_exe.py, which passes VERSION and ROOT:
;   ISCC /DVERSION=0.9.1 /DROOT=<repo> installer\SwitchMorse.iss
; Installs for this Windows account only (no admin rights, no UAC prompt) into
; %LOCALAPPDATA%\Programs\SwitchMorse. Your own files - Documents\SwitchMorse
; and %APPDATA%\SwitchMorse - are never touched, and are kept on uninstall.

#ifndef VERSION
  #define VERSION "0.0"
#endif
#ifndef ROOT
  #define ROOT ".."
#endif

[Setup]
AppId={{6F1C2B7E-5A43-4D8E-9B2C-53574D4F5253}
AppName=SwitchMorse
AppVersion={#VERSION}
AppVerName=SwitchMorse {#VERSION}
AppPublisher=SwitchMorse
DefaultDirName={autopf}\SwitchMorse
DefaultGroupName=SwitchMorse
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#ROOT}\dist
OutputBaseFilename=SwitchMorse-Setup-{#VERSION}
SetupIconFile={#ROOT}\build\switchmorse.ico
UninstallDisplayIcon={app}\SwitchMorse.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
LicenseFile={#ROOT}\LICENSE

[Tasks]
Name: "startup"; Description: "Start SwitchMorse when I sign in to Windows"
Name: "desktopicon"; Description: "A SwitchMorse icon on the desktop"; Flags: unchecked

[Files]
Source: "{#ROOT}\dist\SwitchMorse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SwitchMorse"; Filename: "{app}\SwitchMorse.exe"
Name: "{group}\SwitchMorse Cheat Sheet"; Filename: "{app}\SwitchMorse Cheat Sheet.pdf"
Name: "{group}\My SwitchMorse files"; Filename: "{userdocs}\SwitchMorse"
Name: "{userstartup}\SwitchMorse"; Filename: "{app}\SwitchMorse.exe"; Tasks: startup
Name: "{autodesktop}\SwitchMorse"; Filename: "{app}\SwitchMorse.exe"; Tasks: desktopicon

[Dirs]
Name: "{userdocs}\SwitchMorse"; Flags: uninsneveruninstall

[Messages]
FinishedLabel=SwitchMorse is installed.%n%nThe first time it starts it opens a short guide: test your switches, pick a speed, then try typing and the mouse. To see the guide again, right-click the SwitchMorse window and choose "Start here (guide)...".%n%nYour codes and settings will be in Documents\SwitchMorse.

[Run]
Filename: "{app}\SwitchMorse.exe"; Description: "Start SwitchMorse now"; Flags: nowait postinstall skipifsilent
