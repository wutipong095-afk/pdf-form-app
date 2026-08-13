#!/usr/bin/env bash
# Build Linux desktop package (PyInstaller one-folder + .tar.gz)
#
# Prerequisites: Linux x86_64, Python 3.11+, Node.js, tkinter
# Usage (from repo root):
#   ./scripts/build_linux.sh
#   ./scripts/build_linux.sh --skip-frontend
#   ./scripts/build_linux.sh --skip-pip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_FRONTEND=0
SKIP_PIP=0
for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --skip-pip) SKIP_PIP=1 ;;
    -h|--help)
      echo "Usage: $0 [--skip-frontend] [--skip-pip]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "build_linux.sh must run on Linux (current: $(uname -s))" >&2
  exit 1
fi

echo "== PDF Form Marker - Linux build =="
echo "Root: $ROOT"

VENV_PY="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi
PYTHON="$VENV_PY"
echo "Python: $PYTHON"

# tkinter required for folder picker / status window
if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
  echo "tkinter missing — install e.g. sudo apt install python3-tk" >&2
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
echo "[3/4] PyInstaller (one-folder)..."
rm -rf dist/PDFFormMarker build/PDFFormMarker
"$PYTHON" -m PyInstaller PDFFormMarker.spec --noconfirm

BIN="$ROOT/dist/PDFFormMarker/PDFFormMarker"
if [[ ! -x "$BIN" && ! -f "$BIN" ]]; then
  echo "PyInstaller failed — missing $BIN" >&2
  exit 1
fi
chmod +x "$BIN" || true

BUNDLE_ROOT="$ROOT/dist/PDFFormMarker"
if find "$BUNDLE_ROOT" \( -name 'ed25519_private.pem' -o -name 'gen_license.py' -o -name 'gen_keypair.py' \) | grep -q .; then
  echo "Forbidden files in bundle" >&2
  find "$BUNDLE_ROOT" \( -name 'ed25519_private.pem' -o -name 'gen_license.py' -o -name 'gen_keypair.py' \) >&2
  exit 1
fi

for rel in license_public.pem fonts demo templates static formpacks locales; do
  if [[ ! -e "$BUNDLE_ROOT/$rel" && ! -e "$BUNDLE_ROOT/_internal/$rel" ]]; then
    echo "Missing bundled asset: $rel" >&2
    exit 1
  fi
done

VERSION="$("$PYTHON" -c "from envutil import APP_VERSION; print(APP_VERSION)")"
ARCH="$(uname -m)"
STAGE="PDFFormMarker-${VERSION}-linux-${ARCH}"
STAGE_DIR="$ROOT/dist/$STAGE"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
cp -a "$BUNDLE_ROOT/." "$STAGE_DIR/"

# Desktop entry (user can copy to ~/.local/share/applications)
cat > "$STAGE_DIR/PDFFormMarker.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PDF Form Marker
Comment=Mark and fill PDF forms
Exec=PDFFormMarker
Path=
Terminal=false
Categories=Office;
EOF

cat > "$STAGE_DIR/README-LINUX.txt" <<EOF
PDF Form Marker ${VERSION} (Linux)

Run:
  ./PDFFormMarker

Data / license / logs:
  ~/.local/share/PDFFormMarker/   (or \$XDG_DATA_HOME/PDFFormMarker)

Optional desktop shortcut:
  Edit Exec= to the full path of this PDFFormMarker binary, then copy
  PDFFormMarker.desktop to ~/.local/share/applications/
EOF

echo ""
echo "[4/4] Pack tar.gz..."
mkdir -p "$ROOT/dist/installer"
ARCHIVE="$ROOT/dist/installer/PDFFormMarker-${VERSION}-linux-${ARCH}.tar.gz"
tar -C "$ROOT/dist" -czf "$ARCHIVE" "$STAGE"

echo ""
echo "OK: $BIN"
echo "Done: $ARCHIVE"
