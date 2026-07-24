# Build Windows installer (PyInstaller + Inno Setup)
#
# Prerequisites:
#   - Python 3.11+
#   - Node.js (frontend build)
#   - Inno Setup 6 (optional; for Setup.exe)
#
# Usage (from repo root):
#   .\scripts\build_windows.ps1
#   .\scripts\build_windows.ps1 -SkipInno
#   .\scripts\build_windows.ps1 -SkipFrontend

param(
    [switch]$SkipFrontend,
    [switch]$SkipInno,
    [switch]$SkipPip
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "== PDF Form Marker - Windows build ==" -ForegroundColor Cyan
Write-Host "Root: $Root"

# Prefer project venv so global packages (torch etc.) are not bundled
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv ..." -ForegroundColor Yellow
    python -m venv .venv
}
$Python = $VenvPython
Write-Host "Python: $Python"

if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "[1/4] Build frontend..." -ForegroundColor Yellow
    Push-Location (Join-Path $Root "frontend")
    if (-not (Test-Path "node_modules")) {
        npm install
    }
    npm run build
    Pop-Location
}
else {
    Write-Host ""
    Write-Host "[1/4] Skip frontend build" -ForegroundColor DarkGray
}

if (-not $SkipPip) {
    Write-Host ""
    Write-Host "[2/4] Install build deps into .venv..." -ForegroundColor Yellow
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements-build.txt
}
else {
    Write-Host ""
    Write-Host "[2/4] Skip pip install" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "[3/4] PyInstaller (one-folder)..." -ForegroundColor Yellow
if (Test-Path "dist\PDFFormMarker") {
    Remove-Item -Recurse -Force "dist\PDFFormMarker"
}
if (Test-Path "build\PDFFormMarker") {
    Remove-Item -Recurse -Force "build\PDFFormMarker"
}
& $Python -m PyInstaller PDFFormMarker.spec --noconfirm

$Exe = Join-Path $Root "dist\PDFFormMarker\PDFFormMarker.exe"
if (-not (Test-Path $Exe)) {
    throw "PyInstaller failed - missing $Exe"
}

# Reject private key / license tooling if they leaked into the bundle
$BundleRoot = Join-Path $Root "dist\PDFFormMarker"
$Leaks = @()
$Leaks += Get-ChildItem -Path $BundleRoot -Recurse -Filter "ed25519_private.pem" -ErrorAction SilentlyContinue
$Leaks += Get-ChildItem -Path $BundleRoot -Recurse -Filter "gen_license.py" -ErrorAction SilentlyContinue
$Leaks += Get-ChildItem -Path $BundleRoot -Recurse -Filter "gen_keypair.py" -ErrorAction SilentlyContinue
if ($Leaks.Count -gt 0) {
    $names = ($Leaks | ForEach-Object { $_.FullName }) -join ", "
    throw "Forbidden files in bundle: $names"
}

# Sanity: bundled assets (PyInstaller 6 onedir puts datas under _internal)
foreach ($rel in @("license_public.pem", "fonts", "demo", "templates", "static", "formpacks")) {
    $p = Join-Path $BundleRoot $rel
    $pInternal = Join-Path $BundleRoot "_internal\$rel"
    if (-not (Test-Path $p) -and -not (Test-Path $pInternal)) {
        throw "Missing bundled asset: $rel"
    }
}

Write-Host "OK: $Exe" -ForegroundColor Green

if ($SkipInno) {
    Write-Host ""
    Write-Host "[4/4] Skip Inno Setup (-SkipInno)" -ForegroundColor DarkGray
    Write-Host "Run dist\PDFFormMarker\PDFFormMarker.exe to smoke-test."
    exit 0
}

Write-Host ""
Write-Host "[4/4] Inno Setup..." -ForegroundColor Yellow
$IsccCandidates = @(
    (Get-Command iscc -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if (-not $IsccCandidates) {
    Write-Host "ISCC.exe not found - folder ready at dist\PDFFormMarker\" -ForegroundColor Yellow
    Write-Host "Install Inno Setup 6, then re-run without -SkipInno."
    exit 0
}

$Iscc = $IsccCandidates[0]
New-Item -ItemType Directory -Force -Path (Join-Path $Root "dist\installer") | Out-Null
& $Iscc (Join-Path $Root "installer\PDFFormMarker.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed (exit $LASTEXITCODE)"
}

$Setup = Get-ChildItem (Join-Path $Root "dist\installer\PDFFormMarker-Setup-*.exe") |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
Write-Host ""
Write-Host "Done: $($Setup.FullName)" -ForegroundColor Green
