#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PREFIX="/data/data/com.termux/files/usr"
TMPDIR="$PREFIX/tmp"
STARTUP_SCRIPT="$TERMUX_HOME/agentes/scripts/linux/start_debian_gui_session_termux.sh"
STOP_SCRIPT="$TERMUX_HOME/agentes/scripts/linux/stop_debian_gui_termux.sh"

if [ ! -x "$STARTUP_SCRIPT" ]; then
  echo "ERROR: no existe o no es ejecutable $STARTUP_SCRIPT"
  exit 1
fi

if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

"$STOP_SCRIPT" >/dev/null 2>&1 || true

mkdir -p "$TMPDIR"
chmod 700 "$TMPDIR"
export TMPDIR
export XDG_RUNTIME_DIR="$TMPDIR"

pulseaudio --kill >/dev/null 2>&1 || true
pulseaudio --start --exit-idle-time=-1 \
  --load="module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1" \
  >/dev/null 2>&1

am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 || true
sleep 2

exec termux-x11 :1 -ac -xstartup "$STARTUP_SCRIPT"
