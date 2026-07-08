#!/data/data/com.termux/files/usr/bin/bash
# 2_SUBIR_CRUDOS_YT — Subir crudos a YouTube desde Debian (S24 Ultra)
# Widget Termux: ~/.shortcuts/2_SUBIR_CRUDOS_YT.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
LOG_FILE="$TERMUX_HOME/agentes/youtube_uploader/uploader.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/2_SUBIR_CRUDOS_YT.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  2_SUBIR_CRUDOS_YT — Antigravity S24"
echo "=============================================="
echo ""

if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado en $PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

touch "$LOG_FILE"

echo "[1/2] Escaneando videos en crudos_pendientes..."
source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
    "cd /root/agentes/youtube_uploader && python3 video_scanner.py 2>&1 | tee -a '$LOG_FILE'"
echo ""

echo "[2/2] Subiendo crudos a YouTube..."
echo "Log: $LOG_FILE"
echo ""
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
    "cd /root/agentes/youtube_uploader && python3 uploader.py 2>&1 | tee -a '$LOG_FILE'"

echo ""
echo "=============================================="
echo "  YouTube crudos uploader finalizado."
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
