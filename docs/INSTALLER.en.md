# Windows installer (CP4)

Build a school installer: install → icon → open browser, no Python knowledge required.

Thai: [INSTALLER.md](INSTALLER.md)

## Outputs

| Artifact | Meaning |
|----------|---------|
| `dist/PDFFormMarker/` | Runnable PyInstaller one-folder build |
| `dist/installer/PDFFormMarker-Setup-0.1.9.exe` | Inno Setup installer (if ISCC is available) |

Bundled: civil-service fonts, demo, `formpacks/`, `locales/`, `license_public.pem`, UI from `static/`

**Not included:** `scripts/gen_license.py`, `keys/ed25519_private.pem`, `.env`

## Build machine requirements (vendor)

1. Windows + Python 3.11+
2. Node.js (frontend build)
3. [Inno Setup 6](https://jrsoftware.org/isinfo.php) — for Setup.exe (without it you only get `dist/PDFFormMarker/`)
   - Wizard: English always; Thai added automatically when `Languages\Thai.isl` is installed (`/DENABLE_THAI=1`)

## Build

From the repo root (script creates a `.venv` — avoid a global Python with torch/etc.):

```powershell
.\scripts\build_windows.ps1
```

Options:

```powershell
.\scripts\build_windows.ps1 -SkipInno       # PyInstaller only
.\scripts\build_windows.ps1 -SkipFrontend   # reuse existing static/
```

Result: `dist\PDFFormMarker\PDFFormMarker.exe` and (with Inno) `dist\installer\PDFFormMarker-Setup-0.1.9.exe`

## Test on the build PC

1. Run `dist\PDFFormMarker\PDFFormMarker.exe`
2. Expect a status window + browser at `http://127.0.0.1:5000`
3. Confirm demo-form and PDF creation work
4. Data under `%LOCALAPPDATA%\PDFFormMarker\`
5. Switch UI language Thai ↔ English in the header

## First-run behavior

- Creates `%LOCALAPPDATA%\PDFFormMarker\data` and `logs`
- Creates `secret_key` automatically
- Seeds demo for user `local`
- Does not load `.env` from the install folder (blocks `LICENSE_BYPASS`)

## Install at a school

1. Send `PDFFormMarker-Setup-*.exe`
2. Install (no admin required — `PrivilegesRequired=lowest`)
3. Pick wizard language (English / Thai) if prompted
4. Launch from Desktop / Start Menu
5. Copy the machine ID from the app → request a key from the vendor

If an older copy is still running, Setup **closes it automatically** before overwriting (also on uninstall).

If files are still locked, Setup may ask for a **reboot** (`restartreplace`) — after reboot, open the app and check the top-right version matches the Setup.

Uninstall does not delete the AppData folder — use the in-app backup before moving PCs.
