#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"

if [ ! -x "$PROOT" ]; then
  echo "ERROR: proot-distro no encontrado en $PROOT"
  exit 1
fi

read -r -d '' DEBIAN_CMD <<'EOF' || true
set -euo pipefail
export DISPLAY=:1
export PULSE_SERVER=127.0.0.1
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

mkdir -p /tmp/runtime-tablet
chmod 700 /tmp/runtime-tablet
export XDG_RUNTIME_DIR=/tmp/runtime-tablet

exec su - tablet -c 'export DISPLAY=:1 PULSE_SERVER=127.0.0.1 LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 XDG_RUNTIME_DIR=/tmp/runtime-tablet; exec dbus-launch --exit-with-session xfce4-session'
EOF

exec "$PROOT" login debian-gui --shared-tmp -- /bin/bash -lc "$DEBIAN_CMD"
