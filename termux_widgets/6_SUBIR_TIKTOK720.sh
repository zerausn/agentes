#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
VIGIA="/data/data/com.termux/files/home/agentes/scripts/linux/vigia_tiktok720_termux.sh"
SESSION_LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log"
LAUNCH_LOG="/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720_launcher.log"
if [ ! -f "$VIGIA" ]; then
  echo "[ERROR] no existe $VIGIA"
  echo "        Sincroniza el repo primero."
  exit 1
fi
# Lanzar desenganchado del terminal del widget: sobrevive a SIGHUP/cierre
mkdir -p "$(dirname "$LAUNCH_LOG")"
nohup setsid bash "$VIGIA" >> "$LAUNCH_LOG" 2>&1 &
echo "[OK] Vigia lanzado en segundo plano (PID $!)."
echo "    Viendo log en vivo... (cerrar esta pantalla no mata el proceso)"
echo "--------------------------------------------------------------"
sleep 2
tail -n 50 -f "$SESSION_LOG"
