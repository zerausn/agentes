#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
VIGIA="/data/data/com.termux/files/home/agentes/scripts/linux/vigia_tiktok_shirabyoshi_termux.sh"
SESSION_LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK_SHIRABYOSHI.log"
LAUNCH_LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK_SHIRABYOSHI_launcher.log"
STOPPER="/data/data/com.termux/files/home/agentes/scripts/linux/parar_tiktok_termux.sh"
if [ ! -f "$VIGIA" ]; then
  echo "[ERROR] no existe $VIGIA"
  echo "        Sincroniza el repo primero."
  exit 1
fi

_stop_tiktok_on_ctrl_c() {
  echo ""
  echo "[STOP] Ctrl+C detectado; deteniendo vigias TikTok activos..."
  if [ -f "$STOPPER" ]; then
    PARAR_TIKTOK_NO_PROMPT=1 bash "$STOPPER"
  else
    pkill -f "vigia_tiktok.*termux.sh" 2>/dev/null || true
    pkill -f "tiktok_evacuador_720.py" 2>/dev/null || true
  fi
  exit 130
}
trap _stop_tiktok_on_ctrl_c INT

# Lanzar desenganchado del terminal del widget: sobrevive a SIGHUP/cierre
mkdir -p "$(dirname "$LAUNCH_LOG")"
nohup setsid bash "$VIGIA" >> "$LAUNCH_LOG" 2>&1 &
echo "[OK] Vigia lanzado en segundo plano (PID $!)."
echo "    Viendo log en vivo... (cerrar esta pantalla no mata el proceso)"
echo "    Ctrl+C ejecuta PARAR_TIKTOK."
echo "--------------------------------------------------------------"
sleep 2
tail -n 50 -f "$SESSION_LOG"
