#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 2_SUBIR_CRUDOS_YT.sh — Subir crudos a YouTube
# Modo: PRIMER PLANO — logs visibles en terminal
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/bin:/system/bin:/system/xbin"

# IMPORTANTE: Usar el navegador nativo Android para OAuth
export BROWSER=/data/data/com.termux/files/home/bin/chrome-beta-open

# Pausa incondicional de 15s al salir (éxito o error)
trap 'echo ""; echo "========================================"; echo " PROCESO FINALIZADO — cerrando en 15s..."; echo "========================================"; sleep 15' EXIT

ENTRYPOINT="uploader.py"
PROJECT_DIR="/sdcard/Antigravity/agentes/youtube_uploader"
PYTHON_BIN="$PREFIX/bin/python3"

echo "========================================"
echo " SUBIR CRUDOS A YOUTUBE"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""
echo "Directorio: $PROJECT_DIR"
echo "Script:     $ENTRYPOINT"
echo ""

if [ ! -f "$PROJECT_DIR/$ENTRYPOINT" ]; then
  echo "ERROR: No se encontro $PROJECT_DIR/$ENTRYPOINT"
  exit 1
fi

if [ ! -f "$PYTHON_BIN" ]; then
  echo "ERROR: Python3 no encontrado en $PYTHON_BIN"
  exit 1
fi

cd "$PROJECT_DIR" || exit 1

# Ejecutar EN PRIMER PLANO para que los logs sean visibles
"$PYTHON_BIN" "$ENTRYPOINT"
