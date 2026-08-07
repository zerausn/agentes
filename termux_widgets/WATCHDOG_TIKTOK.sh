#!/data/data/com.termux/files/usr/bin/bash
# WATCHDOG_TIKTOK - modo seguro.
#
# Antes este widget relanzaba automaticamente 6_SUBIR_TIKTOK720 cuando no veia
# vigia_tiktok720_termux.sh. Eso podia dejar un proceso fantasma tocando TikTok
# mientras se usaba Shirabyoshi o Ghawazee.

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/WATCHDOG_TIKTOK.log"
TERMUX_HOME="/data/data/com.termux/files/home"
GLOBAL_LOCK="$TERMUX_HOME/vigia_tiktok_global.lock"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  WATCHDOG_TIKTOK - modo seguro"
echo "=============================================="
echo ""
echo "Este watchdog ya no relanza 6_SUBIR_TIKTOK720 automaticamente."
echo "Motivo: evitar procesos fantasma al cambiar entre 720, Shirabyoshi y Ghawazee."
echo ""

if [ -f "$GLOBAL_LOCK" ]; then
    echo "[LOCK] Lock global actual:"
    cat "$GLOBAL_LOCK" 2>/dev/null || true
else
    echo "[LOCK] No hay lock global TikTok activo."
fi

echo ""
echo "Usa un widget 6_SUBIR_TIKTOK... para iniciar."
echo "Usa PARAR_TIKTOK para detener procesos activos y limpiar locks."
echo ""
read -r -p "Enter para cerrar..." || true
