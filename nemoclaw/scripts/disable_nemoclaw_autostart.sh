#!/usr/bin/env bash
set -euo pipefail

AUTOSTART_FILE="${HOME}/.config/autostart/nemoclaw-telegram-bridge.desktop"
ENV_FILE="${HOME}/.config/antigravity/nemoclaw.env"
PID_FILE="/tmp/nemoclaw-telegram-bridge.pid"
LOG_FILE="/tmp/nemoclaw-telegram-bridge.log"
BRIDGE_SCRIPT="/home/zerausn/NemoClaw/scripts/telegram-bridge.js"

REMOVE_SECRETS="${1:-}"

echo "[disable-nemoclaw] removing autostart entry"
rm -f "$AUTOSTART_FILE"

echo "[disable-nemoclaw] stopping running bridge if present"
pkill -f "$BRIDGE_SCRIPT" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"

if [ "$REMOVE_SECRETS" = "--remove-secrets" ]; then
  echo "[disable-nemoclaw] removing external secret file"
  rm -f "$ENV_FILE"
fi

echo "[disable-nemoclaw] done"
