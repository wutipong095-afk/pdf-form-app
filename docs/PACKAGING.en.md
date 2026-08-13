# Desktop packaging (Windows / Linux / macOS)

Thai: [PACKAGING.md](PACKAGING.md)

The primary product is still the **Windows school installer** (`Setup.exe`).  
Linux and macOS have separate desktop packages for users who want a frozen app without installing Python.

| Platform | Script | Main artifact |
|----------|--------|----------------|
| Windows | `scripts/build_windows.ps1` | `dist/installer/PDFFormMarker-Setup-<ver>.exe` |
| Linux | `scripts/build_linux.sh` | `dist/installer/PDFFormMarker-<ver>-linux-<arch>.tar.gz` |
| macOS | `scripts/build_macos.sh` | `dist/PDFFormMarker.app` + `dist/installer/PDFFormMarker-<ver>-macos.dmg` |

**Important:** build on the target OS (PyInstaller does not cross-compile).  
A Windows machine cannot produce `.dmg` or Linux tarballs.

---

## Data locations (frozen builds)

| OS | Path |
|----|------|
| Windows | `%LOCALAPPDATA%\PDFFormMarker\` |
| macOS | `~/Library/Application Support/PDFFormMarker/` |
| Linux | `~/.local/share/PDFFormMarker/` or `$XDG_DATA_HOME/PDFFormMarker/` |

Override with `DATA_DIR` if needed.

---

## Linux

Requirements: Linux, Python 3.11+ with venv + **tkinter**, Node.js.

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Options: `--skip-frontend` · `--skip-pip`

```bash
tar -xzf dist/installer/PDFFormMarker-*-linux-*.tar.gz
cd PDFFormMarker-*-linux-*
./PDFFormMarker
```

---

## macOS

Requirements: macOS, Python 3.11+ with tkinter, Node.js, Xcode CLT (for DMG).

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

Options: `--skip-frontend` · `--skip-pip` · `--skip-dmg`

Builds are **not codesigned/notarized**. First launch may need Right-click → Open.  
Sign and notarize before wide distribution outside your organization.

---

## Windows

See [INSTALLER.en.md](INSTALLER.en.md)

---

## Never bundled

- `keys/ed25519_private.pem`
- `scripts/gen_license.py` / `gen_keypair.py`
- `.env` (blocks accidental `LICENSE_BYPASS`)
