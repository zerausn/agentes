#!/data/data/com.termux/files/usr/bin/bash
# LIMPIAR_LOCKS — Borra todos los locks y done markers del sistema
# Widget: ~/.shortcuts/LIMPIAR_LOCKS.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/LIMPIAR_LOCKS.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  LIMPIAR_LOCKS - Antigravity S24"
echo "=============================================="
echo ""

# 1. Lock del teaser_uploader.py
LOCK1="$TERMUX_HOME/agentes/youtube_uploader/teaser_uploader.lock"
if [ -f "$LOCK1" ]; then
    rm -f "$LOCK1"
    echo "[OK] Borrado: $LOCK1"
else
    echo "[--] No existe: $LOCK1"
fi

# 2. Locks y done markers del .state/ (teaser_generator)
# El lock de TikTok se maneja aparte para no borrar una ejecucion viva.
STATE_DIR="/sdcard/Antigravity/.state"
if [ -d "$STATE_DIR" ]; then
    COUNT=$(find "$STATE_DIR" -maxdepth 1 -type f \( -name '*.lock' -o -name '*.done' \) ! -name 'tiktok_evacuador.lock' 2>/dev/null | wc -l)
    find "$STATE_DIR" -maxdepth 1 -type f \( -name '*.lock' -o -name '*.done' \) ! -name 'tiktok_evacuador.lock' -exec rm -f {} + 2>/dev/null || true
    echo "[OK] Borrados $COUNT archivo(s) .lock/.done no-TikTok en $STATE_DIR"

    TIKTOK_LOCK="$STATE_DIR/tiktok_evacuador.lock"
    if [ -f "$TIKTOK_LOCK" ]; then
        TIKTOK_PID=$(awk 'NR == 1 {print $1}' "$TIKTOK_LOCK" 2>/dev/null || true)
        if [ -n "$TIKTOK_PID" ] && kill -0 "$TIKTOK_PID" 2>/dev/null; then
            echo "[SKIP] TikTok activo (PID $TIKTOK_PID); no borro $TIKTOK_LOCK."
            echo "       Usa PARAR_TIKTOK si quieres detenerlo y limpiar sus locks."
        else
            rm -f "$TIKTOK_LOCK" 2>/dev/null || true
            echo "[OK] Borrado lock TikTok viejo: $TIKTOK_LOCK"
        fi
    fi
else
    echo "[--] No existe: $STATE_DIR"
fi

echo ""
echo "=============================================="
echo "  Limpieza completada."
echo "  Ahora los widgets deberian funcionar."
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
