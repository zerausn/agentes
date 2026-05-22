#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/sincronizar_yt_a_fb_termux.sh"

echo "--- ACTIVANDO sincronizar_yt_a_fb ---"

if [ ! -f "$LAUNCHER" ]; then
  echo "ERROR: no existe $LAUNCHER"
  exit 1
fi

exec "$LAUNCHER"
