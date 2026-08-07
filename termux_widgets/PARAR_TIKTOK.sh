#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

STOPPER="/data/data/com.termux/files/home/agentes/scripts/linux/parar_tiktok_termux.sh"

if [ ! -f "$STOPPER" ]; then
  echo "[ERROR] no existe $STOPPER"
  echo "        Sincroniza el repo primero."
  exit 1
fi

exec bash "$STOPPER"
