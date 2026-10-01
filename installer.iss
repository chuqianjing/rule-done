; Inno Setup 脚本 — 入档 (RuleDone)
; 在 CI 中通过 iscc /DMyAppVersion=<tag> 传入版本号

#define MyAppName "入档"
#define MyAppDirName "RuleDone"
#define MyAppPublisher "楚乾靖"
#define MyAppURL "https://github.com/chuqianjing/rule-done"
#define MyAppExeName "RuleDone.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.2.1"
#endif

[Setup]
; 刻意不设置 AppId：Inno Setup 的默认值就是 AppName（"入档"），
; 已发布版本的卸载注册表项因此是「入档_is1」。一旦显式改成别的值，
; 老用户的升级会被当成「另一个应用」而变成并行安装，原有数据目录也不会沿用。
; 若将来要改名，必须同时把 AppId 固定为当前这个隐式值。
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppDirName}
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=RuleDone-{#MyAppVersion}-windows-setup
SetupIconFile=resources\icons\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 自动静默升级依赖下面两项（均为 Inno 默认值，此处显式声明以防将来变更）：
; 静默模式下 Setup 会通过 Restart Manager 关闭正在运行的程序，
; 装完后自动把它重新启动，因此 [Run] 段的 skipifsilent 不会影响升级后自启。
CloseApplications=yes
RestartApplications=yes

[Languages]
; 使用项目目录下的语言文件（CI 中会自动下载，本地构建需手动放置）
Name: "chinesesimplified"; MessagesFile: "Languages\ChineseSimplified.isl"

[Files]
Source: "dist\RuleDone\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "resources\icons\logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式选项："

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "运行 {#MyAppName}"; Flags: postinstall nowait skipifsilent
