# Desktop packaging (Windows / Linux / macOS)

ผลิตภัณฑ์หลักยังเป็น **Windows โรงเรียน** (`Setup.exe`)  
Linux และ macOS มีแพ็กเกจแยกสำหรับผู้ที่ต้องการรันแบบ desktop โดยไม่ต้องติดตั้ง Python เอง

| แพลตฟอร์ม | สคริปต์ | ผลลัพธ์หลัก |
|-----------|---------|-------------|
| Windows | `scripts/build_windows.ps1` | `dist/installer/FormDD-Setup-<ver>.exe` |
| Linux | `scripts/build_linux.sh` | `dist/installer/PDFFormMarker-<ver>-linux-<arch>.tar.gz` |
| macOS | `scripts/build_macos.sh` | `dist/PDFFormMarker.app` + `dist/installer/PDFFormMarker-<ver>-macos.dmg` |

**สำคัญ:** ต้อง build บน OS เป้าหมาย (PyInstaller ไม่ cross-compile)  
เครื่อง Windows สร้างแค่ Setup.exe — ไม่สร้าง `.dmg` / Linux tarball ได้

English: [PACKAGING.en.md](PACKAGING.en.md)

---

## Dependency lock (reproducible build)

`requirements.txt` เป็น **lockfile ที่ pin exact ทุกตัว** (รวม transitive) สร้างจาก
`requirements.in` (ช่วงเวอร์ชัน = เจตนา) ด้วย `scripts/lock_requirements.py`
ซึ่ง pin ไปที่ **เวอร์ชันที่ติดตั้ง/ทดสอบแล้วจริง** ไม่ใช่ resolve ล่าสุดที่ยังไม่เทส

อัปเกรด/เพิ่ม dependency:

```bash
# 1) แก้ requirements.in (ช่วงเวอร์ชัน) แล้วติดตั้ง+ทดสอบใน venv
python scripts/lock_requirements.py     # 2) pin ไป requirements.txt
python scripts/collect_notices.py        # 3) รีเฟรช notices ให้ตรงเวอร์ชันใหม่
# 4) commit requirements.txt + THIRD_PARTY_NOTICES.txt ด้วยกัน
```

Docker และทุกสคริปต์ build ใช้ `requirements.txt` (locked) → build reproducible

## ใบอนุญาตบุคคลที่สาม (compliance gate)

ทุกสคริปต์ build (Windows / Linux / macOS) จะรัน `scripts/collect_notices.py`
**หลังติดตั้ง deps และก่อน PyInstaller** เพื่อสร้าง `THIRD_PARTY_NOTICES.txt`
ใหม่จากเวอร์ชัน dependency ที่กำลังแพ็กจริง — ไม่ใช่ไฟล์ที่ commit ไว้ล่วงหน้า

- ถ้ามี component ที่ต้องแจกแต่หา license text ไม่เจอ **สคริปต์ล้ม build หยุด**
  จึงไม่มีทางออก installer ที่ notice ขาดโดยไม่รู้ตัว
- ขั้นตรวจ asset หลัง build ยืนยันว่า `THIRD_PARTY_NOTICES.txt` อยู่ในบันเดิลจริง
- CI รัน `collect_notices.py --check` เป็น completeness gate — ผ่านเฉพาะเมื่อทุก
  component สร้าง license text ได้ครบ (ไม่เทียบไบต์กับไฟล์ที่ commit เพราะ wheel
  แต่ละแพลตฟอร์มแนบไฟล์ license ต่างกันเล็กน้อย และ build สร้าง notices ใหม่เองอยู่แล้ว)

รายละเอียดแหล่งที่มาของ notice: [COMMERCIAL_DISTRIBUTION.md](COMMERCIAL_DISTRIBUTION.md)

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

- Linux x86_64 (หรือสถาปัตยกรรมที่ PyInstaller/pypdfium2 รองรับ)
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
