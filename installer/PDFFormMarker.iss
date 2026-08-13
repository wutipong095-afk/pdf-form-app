; Inno Setup 6 — pack PyInstaller folder into Setup.exe
; Requires dist\PDFFormMarker\ first (scripts\build_windows.ps1)
; Compile: ISCC.exe installer\PDFFormMarker.iss

#define MyAppName "PDF Form Marker"
#define MyAppVersion "0.3.0"
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
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll
RestartApplications=no
; When Thai.isl is present, build_windows.ps1 passes /DENABLE_THAI=1
#ifndef ENABLE_THAI
  #define ENABLE_THAI 0
#endif
#if ENABLE_THAI
ShowLanguageDialog=yes
#else
ShowLanguageDialog=no
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if ENABLE_THAI
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"
#endif

[CustomMessages]
english.CreateDesktopIcon=Create a desktop icon
english.AdditionalIcons=Additional icons:
english.UninstallShortcut=Uninstall {#MyAppName}
english.LaunchApp=Launch {#MyAppName}
english.CannotCloseApp=Could not close a running PDF Form Marker.%n%nPlease close the app window and the "PDF Form Marker" status window, then click OK to try again.
english.UninstallNote=Form data and license remain in %LOCALAPPDATA%\PDFFormMarker%nUninstall does not delete this folder — back up first if you are moving to another PC.
#if ENABLE_THAI
thai.CreateDesktopIcon=สร้างไอคอนบนเดสก์ท็อป
thai.AdditionalIcons=ไอคอนเพิ่มเติม:
thai.UninstallShortcut=ถอนการติดตั้ง {#MyAppName}
thai.LaunchApp=เปิด {#MyAppName}
thai.CannotCloseApp=ไม่สามารถปิด PDF Form Marker ที่กำลังทำงานอยู่ได้%n%nกรุณาปิดหน้าต่างโปรแกรมและหน้าต่างสถานะ "PDF Form Marker" แล้วกด OK เพื่อลองอีกครั้ง
thai.UninstallNote=ข้อมูลฟอร์มและไลเซนต์อยู่ที่ %LOCALAPPDATA%\PDFFormMarker%nถอนการติดตั้งจะไม่ลบโฟลเดอร์นี้ — สำรองข้อมูลก่อนถ้าต้องการย้ายเครื่อง
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; restartreplace = if still locked, swap on reboot instead of Error code 5
Source: "..\dist\PDFFormMarker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs restartreplace

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallShortcut}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Code]
const
  AppExeName = 'PDFFormMarker.exe';
  AppProcessName = 'PDFFormMarker';

function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  { find returns 0 when the process name appears in tasklist }
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

    { 1) taskkill whole process tree }
    Exec(
      ExpandConstant('{cmd}'),
      '/C taskkill /F /IM ' + AppExeName + ' /T',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    { 2) PowerShell fallback }
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
    Result := CustomMessage('CannotCloseApp');
    Exit;
  end;
  { wait for file handles after process exit }
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
  MsgBox(CustomMessage('UninstallNote'), mbInformation, MB_OK);
end;
