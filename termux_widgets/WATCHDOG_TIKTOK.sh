#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# WATCHDOG_TIKTOK.sh — Supervisor de supervivencia del Vigia
#
# Se asegura de que el vigia de TikTok siga corriendo. Si el 
# sistema mata el vigia por OOM, el watchdog lo resucita.
# ================================================================

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
VIGIA="/data/data/com.termux/files/home/agentes/scripts/linux/vigia_tiktok720_termux.sh"
SESSION_LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log"

echo "=============================================="
echo "  SUPERVISOR (WATCHDOG) TIKTOK ACTIVADO"
echo "  PID: $$"
echo "=============================================="

# Desvincular de la terminal para que sobreviva al cierre del widget
if [ "$1" != "--daemon" ]; then
    nohup setsid bash "$0" --daemon > /dev/null 2>&1 &
    echo "[OK] Watchdog corriendo en background."
    sleep 2
    exit 0
fi

# Modo Daemon
while true; do
    if ! pgrep -f "vigia_tiktok720_termux.sh" > /dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] Vigia muerto. Relanzando..." >> "$SESSION_LOG"
        
        # Limpiar locks por precaucion
        rm -f "/data/data/com.termux/files/home/vigia_tiktok720.lock" 2>/dev/null
        rm -f "/sdcard/Antigravity/.state/tiktok_evacuador.lock" 2>/dev/null
        
        # Lanzar vigia
        nohup setsid bash "$VIGIA" >> "$SESSION_LOG" 2>&1 &
    fi
    sleep 120 # Chequear cada 2 minutos
done
