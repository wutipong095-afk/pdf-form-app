; Inno Setup 6 — แพ็กโฟลเดอร์จาก PyInstaller เป็น Setup.exe
; ต้องมี dist\PDFFormMarker\ ก่อน (scripts\build_windows.ps1)
; คอมไพล์: ISCC.exe installer\PDFFormMarker.iss

#define MyAppName "PDF Form Marker"
#define MyAppVersion "0.1.0"
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

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "สร้างไอคอนบนเดสก์ท็อป"; GroupDescription: "ไอคอนเพิ่มเติม:"; Flags: checkedonce

[Files]
; ไม่รวม scripts/ keys/ .env — แพ็กเฉพาะผล PyInstaller
Source: "..\dist\PDFFormMarker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\ถอนการติดตั้ง {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "เปิด {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  MsgBox(
    'ข้อมูลฟอร์มและไลเซนต์อยู่ที่ %LOCALAPPDATA%\PDFFormMarker' + #13#10 +
    'ถอนการติดตั้งจะไม่ลบโฟลเดอร์นี้ — สำรองข้อมูลก่อนถ้าต้องการย้ายเครื่อง',
    mbInformation, MB_OK);
end;
