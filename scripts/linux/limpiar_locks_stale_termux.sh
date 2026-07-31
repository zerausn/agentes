#!/data/data/com.termux/files/usr/bin/bash
# LIMPIAR_LOCKS_STALE — Borra solo locks cuyo PID ya no existe (stale)
# A diferencia de LIMPIAR_LOCKS, NO toca locks de procesos vivos.
# Widget: ~/.shortcuts/LIMPIAR_LOCKS_STALE.sh

set -uo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

STATE_DIR="/sdcard/Antigravity/.state"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/LIMPIAR_LOCKS_STALE.log"

mkdir -p "$LOG_DIR" "$STATE_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  LIMPIAR_LOCKS_STALE - $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Borra solo locks con PID muerto (stale)"
echo "=============================================="

ELIMINADOS=0
MANTENIDOS=0

for lock in "$STATE_DIR"/*.lock; do
    [ -e "$lock" ] || continue
    LOCK_NAME=$(basename "$lock")
    LOCK_PID=$(awk '{print $1}' "$lock" 2>/dev/null)

    if [ -z "$LOCK_PID" ] || ! echo "$LOCK_PID" | grep -qE '^[0-9]+$'; then
        rm -f "$lock"
        echo "[STALE] Sin PID valido -> borrado: $LOCK_NAME"
        ELIMINADOS=$((ELIMINADOS + 1))
        continue
    fi

    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[VIVO ] PID $LOCK_PID activo, se mantiene: $LOCK_NAME"
        MANTENIDOS=$((MANTENIDOS + 1))
    else
        rm -f "$lock"
        echo "[STALE] PID $LOCK_PID muerto -> borrado: $LOCK_NAME"
        ELIMINADOS=$((ELIMINADOS + 1))
    fi
done

echo ""
echo "  Resumen: $ELIMINADOS stale eliminados | $MANTENIDOS locks vivos mantenidos"
echo "=============================================="
