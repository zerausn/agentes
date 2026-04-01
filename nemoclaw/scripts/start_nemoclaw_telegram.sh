#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${HOME}/.config/antigravity/nemoclaw.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "[nemoclaw-telegram] missing env file: $ENV_FILE" >&2
  echo "[nemoclaw-telegram] copy nemoclaw/nemoclaw.env.example to that path and fill the real secrets there." >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[nemoclaw-telegram] node not found" >&2
  exit 1
fi

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "[nemoclaw-telegram] nemoclaw not found" >&2
  exit 1
fi

if ! command -v openshell >/dev/null 2>&1; then
  echo "[nemoclaw-telegram] openshell not found" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

: "${NVIDIA_API_KEY:?NVIDIA_API_KEY missing in $ENV_FILE}"
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN missing in $ENV_FILE}"
: "${SANDBOX_NAME:=nemoclaw-main}"
: "${NEMOCLAW_CHECKOUT:=/home/zerausn/NemoClaw}"

BRIDGE_SCRIPT="${NEMOCLAW_CHECKOUT}/scripts/telegram-bridge.js"
PID_FILE="/tmp/nemoclaw-telegram-bridge.pid"
LOG_FILE="/tmp/nemoclaw-telegram-bridge.log"

if [ ! -f "$BRIDGE_SCRIPT" ]; then
  echo "[nemoclaw-telegram] bridge script not found: $BRIDGE_SCRIPT" >&2
  exit 1
fi

echo "[nemoclaw-telegram] starting telegram bridge for sandbox: $SANDBOX_NAME"
nohup env SANDBOX_NAME="$SANDBOX_NAME" node "$BRIDGE_SCRIPT" >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 2
ps -p "$(cat "$PID_FILE")" -o pid=,user=,cmd=
sed -n '1,40p' "$LOG_FILE"
