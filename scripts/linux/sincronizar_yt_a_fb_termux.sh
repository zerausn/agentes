#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
WATCHER="$TERMUX_HOME/agentes/youtube_uploader/youtube_to_fb_watcher_termux.py"
LOG_FILE="$TERMUX_HOME/agentes/youtube_uploader/youtube_to_fb_sync.log"

echo "--- ACTIVANDO sincronizar_yt_a_fb ---"

if [ ! -x "$PROOT" ]; then
  echo "ERROR: proot-distro no encontrado en $PROOT"
  exit 1
fi

if [ ! -f "$WATCHER" ]; then
  echo "ERROR: no existe $WATCHER"
  exit 1
fi

if [ -f "$ENV_FILE" ]; then
  # Permite perfiles por dispositivo sin mutar el watcher del repo.
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /usr/bin/python3 "$WATCHER" "$@" 2>&1 | tee -a "$LOG_FILE"
