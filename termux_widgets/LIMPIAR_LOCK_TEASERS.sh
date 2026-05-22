#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# LIMPIAR_LOCK_TEASERS.sh — Limpia lock de teaser_uploader
# Mata procesos huerfanos y elimina el archivo .lock
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/bin:/system/bin:/system/xbin"

LOCK="/data/data/com.termux/files/home/agentes/youtube_uploader/teaser_uploader.lock"
PID_FILE="$LOCK"

echo "========================================"
echo " LIMPIAR LOCK TEASER UPLOADER"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 1. Matar procesos teaser_uploader colgados
TEASER_PIDS=$(pgrep -f "teaser_uploader.py" 2>/dev/null || true)
if [ -n "$TEASER_PIDS" ]; then
  echo "Matando proceso(s) teaser_uploader: $TEASER_PIDS"
  kill -9 $TEASER_PIDS 2>/dev/null || true
  sleep 1
  echo "  -> OK"
else
  echo "No hay procesos teaser_uploader activos."
fi

# 2. Eliminar lock file
if [ -f "$LOCK" ]; then
  rm -f "$LOCK"
  echo "Lock eliminado: $LOCK"
else
  echo "No existe archivo .lock."
fi

# 3. Verificar uploader.py (subida de crudos)
UPLOADER_PID=$(pgrep -f "uploader\.py" 2>/dev/null || true)
if [ -n "$UPLOADER_PID" ]; then
  echo "uploader.py activo (PID: $UPLOADER_PID) — OK"
else
  echo "uploader.py NO esta corriendo."
fi

# 4. Contar teasers pendientes
TEASERS=$(ls /sdcard/Antigravity/teasers_pendientes/*.mp4 2>/dev/null | wc -l || echo 0)
echo "Teasers pendientes: $TEASERS"

echo ""
echo "========================================"
echo " LISTO — cerrando en 10s..."
echo "========================================"
sleep 10
