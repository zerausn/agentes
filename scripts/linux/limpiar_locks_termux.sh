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
STATE_DIR="/sdcard/Antigravity/.state"
if [ -d "$STATE_DIR" ]; then
    COUNT=$(find "$STATE_DIR" -type f | wc -l)
    rm -f "$STATE_DIR"/*.lock "$STATE_DIR"/*.done 2>/dev/null || true
    echo "[OK] Borrados $COUNT archivo(s) en $STATE_DIR/.lock .done"
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
