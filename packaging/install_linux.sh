#!/usr/bin/env bash
# Install the AppImage for the current user: copy it to ~/Applications, add an icon,
# and add an application-menu entry. Needs no root.
# Usage: packaging/install_linux.sh path/to/Claude_Usage_Widget-*.AppImage
set -euo pipefail

SRC="${1:?Usage: install_linux.sh path/to/AppImage}"
[ -f "$SRC" ] || { echo "No such file: $SRC" >&2; exit 1; }

APPS="$HOME/Applications"
BIN="$APPS/Claude_Usage_Widget.AppImage"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS" "$ICON_DIR" "$DESKTOP_DIR"

install -m755 "$SRC" "$BIN"

# Pull the icon out of the AppImage itself so the install stays self-contained.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
(cd "$TMP" && "$BIN" --appimage-extract claude-usage-widget.png >/dev/null 2>&1) || true
if [ -f "$TMP/squashfs-root/claude-usage-widget.png" ]; then
  install -m644 "$TMP/squashfs-root/claude-usage-widget.png" "$ICON_DIR/claude-usage-widget.png"
fi

cat > "$DESKTOP_DIR/claude-usage-widget.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Claude Usage Widget
Comment=Compact desktop widget for Claude usage
Exec="$BIN"
Icon=claude-usage-widget
Terminal=false
Categories=Utility;
DESKTOP

command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" || true
echo "Installed to $BIN"
echo "Find \"Claude Usage Widget\" in your application menu, or run: $BIN"
