#!/usr/bin/env bash
# Build dist/Claude_Usage_Widget-<version>-x86_64.AppImage from the project venv.
# Needs: the dev venv (.venv with pyinstaller), curl, and sha256sum.
set -euo pipefail

cd "$(dirname "$0")/.."

# Pinned appimagetool (the upstream release is a rolling "continuous" build).
TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
TOOL_SHA256="95cbe7cce9717fce90c484e34052ee7c7f1d7635b33c12525b4776826a7d29b6"

PY=./.venv/bin/python
VERSION=$("$PY" -c "import claude_usage_widget as m; print(m.__version__)")
APPDIR=build/AppDir
TOOL=build/tools/appimagetool-x86_64.AppImage
OUT="dist/Claude_Usage_Widget-${VERSION}-x86_64.AppImage"

echo "==> Freezing the app with PyInstaller"
./.venv/bin/pyinstaller --noconfirm --onedir --name claude-usage-widget --paths src \
  --distpath build/dist --workpath build/pyinstaller --specpath build packaging/launcher.py \
  > build/pyinstaller.log 2>&1 || { tail -40 build/pyinstaller.log; exit 1; }

echo "==> Assembling AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -r build/dist/claude-usage-widget/. "$APPDIR/usr/bin/"
install -m755 packaging/AppRun "$APPDIR/AppRun"
install -m644 packaging/claude-usage-widget.desktop "$APPDIR/"
QT_QPA_PLATFORM=offscreen "$PY" packaging/make_icon.py "$APPDIR/claude-usage-widget.png"

echo "==> Checking appimagetool"
mkdir -p build/tools
if [ ! -x "$TOOL" ] || ! echo "$TOOL_SHA256  $TOOL" | sha256sum -c --status 2>/dev/null; then
  curl -fL -o "$TOOL" "$TOOL_URL"
  chmod +x "$TOOL"
  echo "$TOOL_SHA256  $TOOL" | sha256sum -c -
fi

echo "==> Building AppImage"
mkdir -p dist
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "$OUT"
echo "Built $OUT"
