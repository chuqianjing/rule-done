; Inno Setup 脚本 — 入档 (RuleDone)
; 在 CI 中通过 iscc /DMyAppVersion=<tag> 传入版本号

#define MyAppName "入档"
#define MyAppPublisher "楚乾靖"
#define MyAppURL "https://github.com/chuqianjing/rule-done"
#define MyAppExeName "RuleDone.exe"

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=RuleDone-{#MyAppVersion}-windows-setup
SetupIconFile=resources\icons\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "dist\RuleDone\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "resources\icons\logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "运行 {#MyAppName}"; Flags: postinstall nowait skipifsilent
