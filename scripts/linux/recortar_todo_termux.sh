#!/data/data/com.termux/files/usr/bin/bash
# RECORTAR_TODO — Corta todos los crudos desde cero (borra markers previos)
# Widget sugerido: ~/.shortcuts/RECORTAR_TODO.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/RECORTAR_TODO.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  RECORTAR_TODO - Antigravity S24"
echo "  Corta todos los crudos desde cero"
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

echo "Iniciando recorte completo dentro de Debian..."

source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc '
set -euo pipefail

PROJECT_DIR="/root/agentes/youtube_uploader"
PYTHON_BIN="python3"
STORAGE_ROOT="/sdcard/Antigravity"
STATE_DIR="$STORAGE_ROOT/.state"

echo "========================================"
echo " RECORTAR TODO - TEASERS FRESCOS"
echo " $(date "+%Y-%m-%d %H:%M:%S")"
echo "========================================"
echo ""

cd "$PROJECT_DIR"

echo "Paso 1: Limpiando markers de estado previos..."
rm -f "$STATE_DIR"/*.done "$STATE_DIR"/*.lock 2>/dev/null || true
echo "  -> .done y .lock eliminados de $STATE_DIR"

echo ""
echo "Paso 2: Escaneando base de datos..."
AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN video_scanner.py

echo ""
echo "Paso 3: Generando teasers desde cero (sin saltar ninguno)..."
AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN teaser_generator.py
'

echo ""
echo "=============================================="
echo "  Recorte completado."
echo "  Todos los crudos fueron procesados."
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
