# -*- mode: python ; coding: utf-8 -*-
# PyInstaller one-folder (Windows / Linux) + .app bundle (macOS)
# Run from repo root:
#   pyinstaller PDFFormMarker.spec --noconfirm
#
# Build in a clean venv with requirements-build.txt only.
import sys

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

try:
    from PyInstaller.building.osx import BUNDLE
except ImportError:  # pragma: no cover - non-mac PyInstaller
    BUNDLE = None  # type: ignore[misc, assignment]

from envutil import APP_VERSION

block_cipher = None
IS_DARWIN = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

datas = [
    ("third_party_licenses", "third_party_licenses"),
    ("THIRD_PARTY_NOTICES.txt", "."),
    ("templates", "templates"),
    ("static", "static"),
    ("fonts", "fonts"),
    ("demo", "demo"),
    ("formpacks", "formpacks"),
    ("locales", "locales"),
    ("license_public.pem", "."),
]

binaries = []
for pkg in ("pypdfium2", "pypdfium2_raw", "reportlab", "uharfbuzz"):
    datas += collect_data_files(pkg)
    binaries += collect_dynamic_libs(pkg)

# ReportLab ships unused DarkGarden fonts under the GPL — do not bundle them.
datas = [
    item for item in datas
    if "darkgarden" not in str(item[0]).replace("\\", "/").lower()
]

hiddenimports = [
    "waitress",
    "license_core",
    "envutil",
    "logging_setup",
    "library_core",
    "history_core",
    "backup_core",
    "update_core",
    "i18n_core",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "pdf_engine",
    "pypdfium2_raw",
    "uharfbuzz",
    "PIL",
    "PIL.Image",
]

excludes = [
    "fitz",
    "pymupdf",
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
    argv_emulation=IS_DARWIN,
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

# macOS .app (build on a Mac only)
if IS_DARWIN and BUNDLE is not None:
    app = BUNDLE(
        coll,
        name="PDFFormMarker.app",
        icon=None,
        bundle_identifier="app.pdfformmarker.desktop",
        version=APP_VERSION,
        info_plist={
            "CFBundleName": "PDF Form Marker",
            "CFBundleDisplayName": "PDF Form Marker",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
            "LSBackgroundOnly": False,
        },
    )
