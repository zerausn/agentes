#!/data/data/com.termux/files/usr/bin/bash
# vigia_vivo.sh — Loop 720s para TikTok Uploader en VIVO V2058
# CLON ESPECIFICO PARA VIVO — NO USAR EN NOTE9
set -euo pipefail

LOCK="/data/data/com.termux/files/home/vigia_vivo.lock"
LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log"
STATE_DIR="/sdcard/Antigravity/.state"
PYTHON="/data/data/com.termux/files/usr/bin/python3"
SCRIPT="/data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py"

# Prevenir duplicados
if [ -f "$LOCK" ]; then
    LOCK_PID=$(cat "$LOCK" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Otra instancia de vigia_vivo esta corriendo (PID $LOCK_PID)" >> "$LOG"
        exit 0
    fi
fi
echo $$ > "$LOCK"

mkdir -p "$STATE_DIR"
export TMPDIR=/data/data/com.termux/files/usr/tmp
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
export AGENTES_STORAGE_ROOT=/sdcard/Antigravity
export TIKTOK_UI_BACKEND=adb
export TIKTOK_ADB_SERIAL=127.0.0.1:5555
export TIKTOK_SHARE_METHOD=intent
export TIKTOK_PUBLISH_MODE=direct
export TIKTOK_POST_SETTLE_SECONDS=30

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== INICIO CICLO VIVO =====" >> "$LOG"

    termux-wake-lock 2>/dev/null || true

    timeout 180 "$PYTHON" "$SCRIPT" --open-next >> "$LOG" 2>&1

    am broadcast -a com.antigravity.KEYEVENT --ei key 1 \
        -n com.antigravity.touchhelper/.TapReceiver 2>/dev/null || true
    termux-wake-unlock 2>/dev/null || true

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== FIN CICLO VIVO (sleep 720s) =====" >> "$LOG"

    # Esperar 720s pero con chequeo de lock cada 30s
    for i in $(seq 1 24); do
        sleep 30
        if ! kill -0 "$$" 2>/dev/null; then exit 0; fi
    done
done
