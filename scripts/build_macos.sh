#!/usr/bin/env bash
# Build macOS desktop package (PyInstaller .app + optional .dmg)
#
# Prerequisites: macOS, Python 3.11+, Node.js, Xcode CLT (for hdiutil)
# Usage (from repo root):
#   ./scripts/build_macos.sh
#   ./scripts/build_macos.sh --skip-frontend
#   ./scripts/build_macos.sh --skip-dmg
#   ./scripts/build_macos.sh --skip-pip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_FRONTEND=0
SKIP_PIP=0
SKIP_DMG=0
for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --skip-pip) SKIP_PIP=1 ;;
    --skip-dmg) SKIP_DMG=1 ;;
    -h|--help)
      echo "Usage: $0 [--skip-frontend] [--skip-pip] [--skip-dmg]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "build_macos.sh must run on macOS (current: $(uname -s))" >&2
  exit 1
fi

echo "== PDF Form Marker - macOS build =="
echo "Root: $ROOT"

VENV_PY="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi
PYTHON="$VENV_PY"
echo "Python: $PYTHON"

if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
  echo "tkinter missing — use the python.org installer or fix the framework build" >&2
  exit 1
fi

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
  echo ""
  echo "[1/4] Build frontend..."
  pushd frontend >/dev/null
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  npm run build
  popd >/dev/null
else
  echo ""
  echo "[1/4] Skip frontend build"
fi

if [[ "$SKIP_PIP" -eq 0 ]]; then
  echo ""
  echo "[2/4] Install build deps into .venv..."
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -r requirements-build.txt
else
  echo ""
  echo "[2/4] Skip pip install"
fi

echo ""
echo "[3/4] PyInstaller (.app bundle)..."
rm -rf dist/PDFFormMarker dist/PDFFormMarker.app build/PDFFormMarker
"$PYTHON" -m PyInstaller PDFFormMarker.spec --noconfirm

APP="$ROOT/dist/PDFFormMarker.app"
if [[ ! -d "$APP" ]]; then
  echo "PyInstaller failed — missing $APP" >&2
  echo "Expected BUNDLE output on macOS." >&2
  exit 1
fi

if find "$APP" \( -name 'ed25519_private.pem' -o -name 'gen_license.py' -o -name 'gen_keypair.py' \) | grep -q .; then
  echo "Forbidden files in bundle" >&2
  exit 1
fi

# Assets live under Contents/Frameworks or Resources/_internal depending on PyInstaller version
FOUND_FONT=0
if find "$APP" -type d -name fonts | grep -q .; then
  FOUND_FONT=1
fi
if [[ "$FOUND_FONT" -eq 0 ]]; then
  echo "Missing bundled fonts/ inside .app" >&2
  exit 1
fi

VERSION="$("$PYTHON" -c "from envutil import APP_VERSION; print(APP_VERSION)")"
mkdir -p "$ROOT/dist/installer"

echo ""
if [[ "$SKIP_DMG" -eq 1 ]]; then
  echo "[4/4] Skip DMG — app at $APP"
  exit 0
fi

echo "[4/4] Create DMG..."
DMG="$ROOT/dist/installer/PDFFormMarker-${VERSION}-macos.dmg"
rm -f "$DMG"
# UDZO = compressed read-only disk image
hdiutil create \
  -volname "PDF Form Marker" \
  -srcfolder "$APP" \
  -ov \
  -format UDZO \
  "$DMG"

echo ""
echo "OK: $APP"
echo "Done: $DMG"
echo "Note: Gatekeeper may block unsigned apps — right-click → Open the first time,"
echo "      or codesign/notarize for distribution outside your org."
