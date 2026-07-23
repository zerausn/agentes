#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/vigia_meta720_termux.sh"
if [ ! -f "$LAUNCHER" ]; then
  echo "[ERROR] no existe $LAUNCHER"
  echo "        Corre primero 0_RENOVAR_REPO para actualizar el repo."
  exit 1
fi
exec bash "$LAUNCHER" "$@"
