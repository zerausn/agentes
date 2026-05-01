#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PREFIX="/data/data/com.termux/files/usr"
PROOT="$PREFIX/bin/proot-distro"
REPO_DIR="$TERMUX_HOME/agentes"
SHORTCUTS_DIR="$TERMUX_HOME/.shortcuts"
DISTRO_PLUGIN="$PREFIX/etc/proot-distro/debian-gui.sh"
START_SCRIPT="$REPO_DIR/scripts/linux/start_debian_gui_termux.sh"
STOP_SCRIPT="$REPO_DIR/scripts/linux/stop_debian_gui_termux.sh"
SESSION_SCRIPT="$REPO_DIR/scripts/linux/start_debian_gui_session_termux.sh"

if [ ! -d "$REPO_DIR" ]; then
  echo "ERROR: no existe $REPO_DIR"
  exit 1
fi

if [ ! -x "$PROOT" ]; then
  echo "ERROR: proot-distro no encontrado en $PROOT"
  exit 1
fi

echo "--- Instalando stack grafico local para Debian en Termux ---"
pkg install -y x11-repo termux-x11-nightly pulseaudio

if [ ! -f "$DISTRO_PLUGIN" ]; then
  cp "$PREFIX/etc/proot-distro/debian.sh" "$DISTRO_PLUGIN"
  printf '\n# Override local: evitar fallo del plugin oficial en dpkg-reconfigure locales\ndistro_setup() { :; }\n' >> "$DISTRO_PLUGIN"
fi

if ! "$PROOT" login debian-gui -- /bin/true >/dev/null 2>&1; then
  "$PROOT" install debian-gui
fi

read -r -d '' DEBIAN_SETUP_CMD <<'EOF' || true
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt update
apt install -y --no-install-recommends \
  locales \
  sudo \
  dbus-x11 \
  xfce4 \
  xfce4-terminal \
  xauth \
  x11-utils \
  xterm \
  tigervnc-standalone-server \
  tigervnc-tools \
  psmisc \
  wget \
  curl \
  git \
  ca-certificates

sed -i -E 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

if ! id -u tablet >/dev/null 2>&1; then
  useradd -m -s /bin/bash tablet
fi

mkdir -p /home/tablet/.vnc
cat > /home/tablet/.vnc/xstartup <<'VNC_EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
exec startxfce4
VNC_EOF

chmod +x /home/tablet/.vnc/xstartup
chown -R tablet:tablet /home/tablet
EOF

"$PROOT" login debian-gui --shared-tmp -- /bin/bash -lc "$DEBIAN_SETUP_CMD"

mkdir -p "$SHORTCUTS_DIR"

cat > "$SHORTCUTS_DIR/Debian_Grafico.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
exec "$TERMUX_HOME/agentes/scripts/linux/start_debian_gui_termux.sh"
EOF

cat > "$SHORTCUTS_DIR/Parar_Debian_Grafico.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
exec "$TERMUX_HOME/agentes/scripts/linux/stop_debian_gui_termux.sh"
EOF

chmod +x \
  "$START_SCRIPT" \
  "$STOP_SCRIPT" \
  "$SESSION_SCRIPT" \
  "$SHORTCUTS_DIR/Debian_Grafico.sh" \
  "$SHORTCUTS_DIR/Parar_Debian_Grafico.sh"

echo "Widget grafico listo:"
echo "  - $SHORTCUTS_DIR/Debian_Grafico.sh"
echo "  - $SHORTCUTS_DIR/Parar_Debian_Grafico.sh"
echo "Distribucion grafica lista: debian-gui"
