# Desktop packaging (Windows / Linux / macOS)

ผลิตภัณฑ์หลักยังเป็น **Windows โรงเรียน** (`Setup.exe`)  
Linux และ macOS มีแพ็กเกจแยกสำหรับผู้ที่ต้องการรันแบบ desktop โดยไม่ต้องติดตั้ง Python เอง

| แพลตฟอร์ม | สคริปต์ | ผลลัพธ์หลัก |
|-----------|---------|-------------|
| Windows | `scripts/build_windows.ps1` | `dist/installer/FromDD-Setup-<ver>.exe` |
| Linux | `scripts/build_linux.sh` | `dist/installer/PDFFormMarker-<ver>-linux-<arch>.tar.gz` |
| macOS | `scripts/build_macos.sh` | `dist/PDFFormMarker.app` + `dist/installer/PDFFormMarker-<ver>-macos.dmg` |

**สำคัญ:** ต้อง build บน OS เป้าหมาย (PyInstaller ไม่ cross-compile)  
เครื่อง Windows สร้างแค่ Setup.exe — ไม่สร้าง `.dmg` / Linux tarball ได้

English: [PACKAGING.en.md](PACKAGING.en.md)

---

## ที่เก็บข้อมูลเมื่อรันแพ็กเกจ (frozen)

| OS | ตำแหน่ง |
|----|---------|
| Windows | `%LOCALAPPDATA%\PDFFormMarker\` |
| macOS | `~/Library/Application Support/PDFFormMarker/` |
| Linux | `~/.local/share/PDFFormMarker/` หรือ `$XDG_DATA_HOME/PDFFormMarker/` |

ตั้ง `DATA_DIR` ทับได้ผ่าน environment

---

## Linux

### ความต้องการเครื่องแพ็ก

- Linux x86_64 (หรือสถาปัตยกรรมที่ PyInstaller/PyMuPDF รองรับ)
- Python 3.11+ พร้อม `python3-venv` และ **tkinter** (`python3-tk` บน Debian/Ubuntu)
- Node.js

### สร้างแพ็ก

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

ตัวเลือก: `--skip-frontend` · `--skip-pip`

แตกและรัน:

```bash
tar -xzf dist/installer/PDFFormMarker-*-linux-*.tar.gz
cd PDFFormMarker-*-linux-*
./PDFFormMarker
```

---

## macOS

### ความต้องการเครื่องแพ็ก

- macOS + Python 3.11+ (แนะนำจาก python.org) พร้อม tkinter
- Node.js
- Xcode Command Line Tools (`hdiutil` สำหรับ DMG)

### สร้างแพ็ก

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

ตัวเลือก: `--skip-frontend` · `--skip-pip` · `--skip-dmg`

คัดลอก `dist/PDFFormMarker.app` ไป Applications หรือแจก `.dmg`

แอปยัง**ไม่ codesign / notarize** — ครั้งแรกอาจต้องคลิกขวา → Open  
สำหรับแจกนอกองค์กรควรเซ็นและ notarize เพิ่มเอง

---

## Windows

ดู [INSTALLER.md](INSTALLER.md)

---

## สิ่งที่ไม่รวมในทุกแพ็ก

- `keys/ed25519_private.pem`
- `scripts/gen_license.py` / `gen_keypair.py`
- `.env` (กัน `LICENSE_BYPASS`)
