#!/data/data/com.termux/files/usr/bin/bash
# 0_PIPELINE_COMPLETO - Orquestador del S24 Ultra (corre dentro de Debian)
# Widget Termux: ~/.shortcuts/0_PIPELINE_COMPLETO.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/0_PIPELINE_COMPLETO.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  0_PIPELINE_COMPLETO - Antigravity S24"
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

echo "Iniciando pipeline en Debian..."

source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -c '
set -euo pipefail

PROJECT_DIR="/root/agentes/youtube_uploader"
PYTHON_BIN="python3"
META_DIR="/root/agentes/meta_uploader"
FB_SCRIPT="$META_DIR/subir_fb_evacuador.py"
STORAGE_ROOT="/sdcard/Antigravity"
STATE_DIR="$STORAGE_ROOT/.state"
TEASER_DIR="$STORAGE_ROOT/teasers_pendientes"
TEASER_WAIT_TIMEOUT_SEC="${AGENTES_TEASER_WAIT_TIMEOUT_SEC:-1800}"

count_matches() {
  local dir="$1"
  local pattern="$2"
  find "$dir" -maxdepth 1 -type f -name "$pattern" | wc -l | tr -d "[:space:]"
}

fb() {
  sleep 2
  if [ -f "$FB_SCRIPT" ]; then
    echo "[FB] Subiendo a Facebook lo nuevo..."
    cd "$META_DIR" && AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN subir_fb_evacuador.py
  fi
}

echo "========================================"
echo " PIPELINE COMPLETO v8 (Debian)"
echo " $(date "+%Y-%m-%d %H:%M:%S")"
echo "========================================"

cd "$PROJECT_DIR" || exit 1

echo ""
echo "--- FASE 1: Escaneando base de datos ---"
$PYTHON_BIN video_scanner.py

echo ""
echo "--- FASE 2: Limpiando estado anterior y cortando teasers ---"
echo "  Borrando markers .done y .lock previos..."
rm -f "$STATE_DIR"/*.done "$STATE_DIR"/*.lock 2>/dev/null || true
AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN teaser_generator.py
echo "  -> Corte completado"

echo ""
echo "--- FASE 3: Streaming uploader (subida concurrente + evacuacion) ---"
AGENTES_STORAGE_ROOT="$STORAGE_ROOT" $PYTHON_BIN /root/agentes/scripts/linux/streaming_uploader.py --skip-facebook
echo ""
echo "--- FASE FINAL: Facebook (barrido) ---"
fb

echo ""
echo "========================================"
echo " PIPELINE COMPLETADO v8"
echo " $(date "+%Y-%m-%d %H:%M:%S")"
echo "========================================"
'

echo ""
read -r -p "Enter para cerrar..."
