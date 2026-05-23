#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# limpiar_crudos_incompletos_termux.sh
# Mueve los crudos que no tengan sus teasers completos
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/bin:/system/bin:/system/xbin"

# Pausa incondicional de 10s al salir (éxito o error)
trap 'echo ""; echo "========================================"; echo " PROCESO FINALIZADO — cerrando en 10s..."; echo "========================================"; sleep 10' EXIT

ENTRYPOINT="clean_incomplete_crudos.py"
PROJECT_DIR="/data/data/com.termux/files/home/agentes/youtube_uploader"
PYTHON_BIN="$PREFIX/bin/python3"

echo "========================================"
echo " LIMPIANDO CRUDOS INCOMPLETOS"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

if [ ! -d "$PROJECT_DIR" ]; then
  # Fallback si el repositorio solo está en sdcard
  PROJECT_DIR="/sdcard/Antigravity/agentes/youtube_uploader"
fi

if [ ! -f "$PROJECT_DIR/$ENTRYPOINT" ]; then
  echo "ERROR: No se encontro $PROJECT_DIR/$ENTRYPOINT"
  exit 1
fi

cd "$PROJECT_DIR" || exit 1

# Ejecutar el script de limpieza
"$PYTHON_BIN" "$ENTRYPOINT"
