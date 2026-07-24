# -*- mode: python ; coding: utf-8 -*-
# PyInstaller one-folder — รันจากรากโปรเจกต์:
#   pyinstaller PDFFormMarker.spec --noconfirm
#
# แนะนำ: build ใน venv ที่ติดตั้งแค่ requirements-build.txt
# (site-packages ใหญ่ เช่น torch จะถูก exclude ด้านล่าง)
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("fonts", "fonts"),
    ("demo", "demo"),
    ("formpacks", "formpacks"),
    ("license_public.pem", "."),
]

# ตรวจว่า PyMuPDF ใช้ได้ตอน build — ไม่ให้ผ่านแล้วไปพังตอนเปิด exe
try:
    import fitz  # noqa: F401
except ImportError as e:
    raise SystemExit(
        f"PDFFormMarker.spec: cannot import fitz (install PyMuPDF in the build venv): {e}"
    ) from e

# native libs + package data ของ PyMuPDF — ห้ามกลืน exception ทั้งคู่
binaries = []
pymupdf_ok = False
for pkg in ("pymupdf", "fitz"):
    try:
        libs = collect_dynamic_libs(pkg)
        binaries += libs
        if libs:
            pymupdf_ok = True
            print(f"PDFFormMarker.spec: collect_dynamic_libs({pkg}) -> {len(libs)}")
    except Exception as e:
        print(f"PDFFormMarker.spec: WARN collect_dynamic_libs({pkg}): {e}")

try:
    pm_data = collect_data_files("pymupdf")
    datas += pm_data
    if pm_data:
        pymupdf_ok = True
        print(f"PDFFormMarker.spec: collect_data_files(pymupdf) -> {len(pm_data)}")
except Exception as e:
    raise SystemExit(
        f"PDFFormMarker.spec: collect_data_files(pymupdf) failed: {e}"
    ) from e

if not pymupdf_ok:
    raise SystemExit(
        "PDFFormMarker.spec: no PyMuPDF binaries/data collected — "
        "frozen app would crash on import fitz"
    )

hiddenimports = [
    "waitress",
    "license_core",
    "envutil",
    "logging_setup",
    "library_core",
    "backup_core",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "fitz",
    "pymupdf",
]

# แพ็กเกจที่มักมีในเครื่องนักพัฒนา แต่ไม่เกี่ยวกับแอปนี้
# อย่า exclude unittest (stdlib) — dependency อาจ lazy-import unittest.mock
excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "keras",
    "pandas",
    "scipy",
    "sklearn",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "scripts",
    "gen_license",
    "gen_keypair",
    "cv2",
    "numba",
    "llvmlite",
    "pyarrow",
    "imageio",
    "sympy",
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFFormMarker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PDFFormMarker",
)
