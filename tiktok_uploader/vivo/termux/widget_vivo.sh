#!/data/data/com.termux/files/usr/bin/bash
# widget_vivo.sh — Widget Termux para subir 1 video a TikTok en VIVO V2058
# CLON ESPECIFICO PARA VIVO — NO USAR EN NOTE9
# Colocar en ~/.shortcuts/6_SUBIR_TIKTOK720.sh

set -euo pipefail
export TMPDIR=/data/data/com.termux/files/usr/tmp
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
PYTHON="/data/data/com.termux/files/usr/bin/python3"
export AGENTES_STORAGE_ROOT=/sdcard/Antigravity
export TIKTOK_UI_BACKEND=adb
export TIKTOK_ADB_SERIAL=34237840310037S
export TIKTOK_SHARE_METHOD=intent
export TIKTOK_PUBLISH_MODE=direct
export TIKTOK_POST_SETTLE_SECONDS=30
SCRIPT="/data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py"
LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Widget VIVO: inicio" >> "$LOG"

# Despertar
/system/bin/input keyevent KEYCODE_WAKEUP 2>/dev/null || true
sleep 2
/system/bin/input swipe 500 1700 500 500 350 2>/dev/null || true
sleep 2

timeout 180 "$PYTHON" "$SCRIPT" --open-next >> "$LOG" 2>&1

/system/bin/input keyevent KEYCODE_HOME 2>/dev/null || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Widget VIVO: fin" >> "$LOG"
