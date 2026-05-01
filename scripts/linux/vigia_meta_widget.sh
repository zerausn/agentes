#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/vigia_meta_termux.sh"
LOG_FILE="$TERMUX_HOME/agentes/meta_uploader/fb_to_ig_vigia.log"

echo "--- ACTIVANDO vigia_meta ---"

if [ ! -x "$PROOT" ]; then
  echo "ERROR: proot-distro no encontrado en $PROOT"
  exit 1
fi

if [ ! -f "$LAUNCHER" ]; then
  echo "ERROR: no existe $LAUNCHER"
  exit 1
fi

exec "$PROOT" login debian -- /bin/bash -lc "$LAUNCHER & sleep 3; tail -f '$LOG_FILE'"
