; Inno Setup 6 — แพ็กโฟลเดอร์จาก PyInstaller เป็น Setup.exe
; ต้องมี dist\PDFFormMarker\ ก่อน (scripts\build_windows.ps1)
; คอมไพล์: ISCC.exe installer\PDFFormMarker.iss

#define MyAppName "PDF Form Marker"
#define MyAppVersion "0.1.7"
#define MyAppPublisher "PDF Form Marker"
#define MyAppExeName "PDFFormMarker.exe"
#define MyAppId "{{A8E3C2B1-4F5D-4A9E-9C1B-7D6E5F4A3B2C}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PDFFormMarker
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=PDFFormMarker-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
InfoBeforeFile=info-before.txt
LicenseFile=
; ปิดโปรแกรมที่ล็อกไฟล์ในโฟลเดอร์ติดตั้งอัตโนมัติ (ไม่ถาม)
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "สร้างไอคอนบนเดสก์ท็อป"; GroupDescription: "ไอคอนเพิ่มเติม:"; Flags: checkedonce

[Files]
; restartreplace = ถ้ายังถูกล็อก ให้สลับไฟล์ตอนรีสตาร์ท แทน Error code 5
Source: "..\dist\PDFFormMarker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs restartreplace

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\ถอนการติดตั้ง {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "เปิด {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  AppExeName = 'PDFFormMarker.exe';
  AppProcessName = 'PDFFormMarker';

function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  { find คืน 0 เมื่อเจอชื่อโปรเซสใน tasklist }
  Result :=
    Exec(
      ExpandConstant('{cmd}'),
      '/C tasklist /FI "IMAGENAME eq ' + AppExeName + '" | find /I "' + AppExeName + '" >nul',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

procedure KillRunningApp();
var
  ResultCode: Integer;
  i: Integer;
begin
  for i := 1 to 6 do
  begin
    if not IsAppRunning() then
      Exit;

    { 1) taskkill บังคับทั้งต้นไม้โปรเซส }
    Exec(
      ExpandConstant('{cmd}'),
      '/C taskkill /F /IM ' + AppExeName + ' /T',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    { 2) PowerShell สำรอง — บางเครื่อง taskkill ไม่พอ }
    Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -ExecutionPolicy Bypass -Command ' +
        '"Get-Process -Name ''' + AppProcessName + ''' -ErrorAction SilentlyContinue | Stop-Process -Force"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    Sleep(1000);
  end;
end;

function InitializeSetup(): Boolean;
begin
  KillRunningApp();
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillRunningApp();
  NeedsRestart := False;
  if IsAppRunning() then
  begin
    Result :=
      'ไม่สามารถปิด PDF Form Marker ที่กำลังทำงานอยู่ได้' + #13#10 + #13#10 +
      'กรุณาปิดหน้าต่างโปรแกรมและหน้าต่างสถานะ "PDF Form Marker" แล้วกด OK เพื่อลองอีกครั้ง';
    Exit;
  end;
  { รอปล่อยไฟล์หลังโปรเซสตาย — กัน DeleteFile code 5 }
  Sleep(1500);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    KillRunningApp();
    Sleep(500);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  KillRunningApp();
  Sleep(1000);
  Result := True;
  MsgBox(
    'ข้อมูลฟอร์มและไลเซนต์อยู่ที่ %LOCALAPPDATA%\PDFFormMarker' + #13#10 +
    'ถอนการติดตั้งจะไม่ลบโฟลเดอร์นี้ — สำรองข้อมูลก่อนถ้าต้องการย้ายเครื่อง',
    mbInformation, MB_OK);
end;
