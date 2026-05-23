#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 2_SUBIR_CRUDOS_YT.sh — Escanea + Sube crudos a YouTube
# Modo: PRIMER PLANO — logs visibles en terminal
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/bin:/system/bin:/system/xbin"

export BROWSER=/data/data/com.termux/files/home/bin/chrome-beta-open

LOG="/sdcard/Antigravity/widget_logs/2_SUBIR_CRUDOS_YT.log"

trap 'echo ""; echo "========================================"; echo " PROCESO FINALIZADO — cerrando en 15s..."; echo "========================================"; sleep 15' EXIT

PROJECT_DIR="/sdcard/Antigravity/agentes/youtube_uploader"
PYTHON_BIN="$PREFIX/bin/python3"

{
echo "========================================"
echo " ESCANEAR + SUBIR CRUDOS A YOUTUBE"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

if [ ! -f "$PYTHON_BIN" ]; then
  echo "ERROR: Python3 no encontrado en $PYTHON_BIN"
  exit 1
fi

cd "$PROJECT_DIR" || { echo "ERROR: no se pudo acceder a $PROJECT_DIR"; exit 1; }

echo "[1/2] Escaneando videos en crudos_pendientes..."
"$PYTHON_BIN" video_scanner.py 2>&1
echo ""

echo "[2/2] Subiendo crudos a YouTube..."
"$PYTHON_BIN" uploader.py 2>&1
} 2>&1 | tee "$LOG"
