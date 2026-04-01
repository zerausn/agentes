#!/usr/bin/env bash
set -euo pipefail

SOURCE_DESKTOP="/home/zerausn/Documents/Antigravity/agentes/nemoclaw/startup/nemoclaw-telegram-bridge.desktop"
TARGET_DIR="${HOME}/.config/autostart"
TARGET_DESKTOP="${TARGET_DIR}/nemoclaw-telegram-bridge.desktop"

if [ ! -f "$SOURCE_DESKTOP" ]; then
  echo "[enable-nemoclaw] source desktop file not found: $SOURCE_DESKTOP" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
install -m 644 "$SOURCE_DESKTOP" "$TARGET_DESKTOP"

echo "[enable-nemoclaw] autostart installed at: $TARGET_DESKTOP"
echo "[enable-nemoclaw] start a new login session to verify autostart"
