#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/vigia_meta_termux.sh"
LOG_FILE="$TERMUX_HOME/agentes/meta_uploader/fb_to_ig_vigia.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/VIGIA_META.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  VIGIA META — Antigravity S24"
echo "=============================================="
echo ""

if [ ! -x "$PROOT" ]; then
  echo "[ERROR] proot-distro no encontrado en $PROOT"
  read -r -p "Enter para cerrar..."
  exit 1
fi

if [ ! -f "$LAUNCHER" ]; then
  echo "[ERROR] no existe $LAUNCHER"
  echo "        Corre primero 0_RENOVAR_REPO para actualizar el repo."
  read -r -p "Enter para cerrar..."
  exit 1
fi

# Crear el log si no existe para que tail -f no falle de inmediato
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

echo "Iniciando vigia_meta dentro de Debian..."
echo "Log: $LOG_FILE"
echo ""

LAUNCH_CMD="bash $(printf '%q' "$LAUNCHER")"
if [ "$#" -gt 0 ]; then
  for arg in "$@"; do
    LAUNCH_CMD="$LAUNCH_CMD $(printf '%q' "$arg")"
  done
fi

# Lanzar el agente dentro de Debian en background y seguir el log
source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
  "touch '$LOG_FILE'; $LAUNCH_CMD >> '$LOG_FILE' 2>&1 &
   sleep 2
   tail -f '$LOG_FILE'"
