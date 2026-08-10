#!/usr/bin/env bash
# Install Claude Desktop (macOS, Universal — works on Intel x86_64 and Apple Silicon)
# into /Applications. Safe to re-run.
#
# Usage:
#   bash install_claude_desktop.sh
# If copying to /Applications fails with "Permission denied", run with sudo:
#   sudo bash install_claude_desktop.sh
set -euo pipefail

URL="https://claude.ai/api/desktop/darwin/universal/dmg/latest/redirect"
WORK="$(mktemp -d)"
DMG="$WORK/Claude.dmg"
MNT="$WORK/mnt"
trap 'hdiutil detach "$MNT" -quiet >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

echo "==> Downloading Claude Desktop (universal, Intel + Apple Silicon)..."
curl -fSL "$URL" -o "$DMG"
echo "    $(du -h "$DMG" | awk '{print $1}') downloaded"

echo "==> Mounting DMG..."
mkdir -p "$MNT"
hdiutil attach "$DMG" -nobrowse -mountpoint "$MNT" -quiet

APP="$(find "$MNT" -maxdepth 2 -iname 'Claude.app' | head -1)"
if [ -z "${APP:-}" ]; then
  echo "!! Could not find Claude.app inside the DMG. Volume contents:" >&2
  ls -la "$MNT" >&2
  exit 1
fi

echo "==> Installing $APP -> /Applications/Claude.app ..."
rm -rf "/Applications/Claude.app"
cp -R "$APP" "/Applications/Claude.app"

echo "==> Verifying..."
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "/Applications/Claude.app/Contents/Info.plist" 2>/dev/null \
  && echo "    version: $(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "/Applications/Claude.app/Contents/Info.plist" 2>/dev/null)" \
  || true

echo "==> Done. Claude.app is in /Applications."
echo "    Launch with:  open -a Claude"
