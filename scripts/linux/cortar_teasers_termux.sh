#!/data/data/com.termux/files/usr/bin/bash
# 1_CORTAR_TEASERS — Generar teasers usando FFmpeg desde Debian (S24 Ultra)
# Widget Termux: ~/.shortcuts/1_CORTAR_TEASERS.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/1_CORTAR_TEASERS.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  1_CORTAR_TEASERS — Antigravity S24"
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

echo "Iniciando teaser_generator.py dentro de Debian..."

"$PROOT" login debian -- /bin/bash -lc '
set -euo pipefail

PROJECT_DIR="/root/agentes/youtube_uploader"
PYTHON_BIN="python3"
STORAGE_ROOT="/sdcard/Antigravity"

echo "========================================"
echo " CORTANDO TEASERS"
echo " $(date "+%Y-%m-%d %H:%M:%S")"
echo "========================================"
echo ""

cd "$PROJECT_DIR"

echo "Paso 1: Escaneando base de datos antes de cortar..."
AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN video_scanner.py

echo ""
echo "Paso 2: Generando recortes de avance..."
AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN teaser_generator.py
'

echo ""
echo "=============================================="
echo "  Generador de teasers finalizado."
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
