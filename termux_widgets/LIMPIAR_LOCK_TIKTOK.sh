#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# LIMPIAR_LOCK_TIKTOK.sh — Limpia lock zombie de tiktok_evacuador
# Mata procesos huerfanos, elimina .lock y relanza el vigia
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/bin:/system/bin:/system/xbin"

LOCK="/sdcard/Antigravity/.state/tiktok_evacuador.lock"
VIGIA_LOCK="$HOME/vigia_tiktok720.lock"
VIGIA="$HOME/agentes/scripts/linux/vigia_tiktok720_termux.sh"
LOG_DIR="/sdcard/Antigravity/widget_logs"
LAUNCH_LOG="$LOG_DIR/6_SUBIR_TIKTOK720_launcher.log"
SESSION_LOG="$LOG_DIR/6_SUBIR_TIKTOK720.log"

echo "========================================================"
echo "  LIMPIAR LOCK — TIKTOK EVACUADOR"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================"
echo ""

# 1. Matar todos los procesos tiktok_evacuador_720 colgados
PIDS=$(pgrep -f "tiktok_evacuador_720.py" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "[1] Matando proceso(s) zombie tiktok_evacuador: $PIDS"
  kill -9 $PIDS 2>/dev/null || true
  sleep 2
  # Verificar que murieron
  STILL=$(pgrep -f "tiktok_evacuador_720.py" 2>/dev/null || true)
  if [ -n "$STILL" ]; then
    echo "    [AVISO] Aun vivos: $STILL — reintentando con SIGKILL..."
    kill -9 $STILL 2>/dev/null || true
    sleep 1
  fi
  echo "    -> Procesos eliminados."
else
  echo "[1] No hay procesos tiktok_evacuador activos."
fi

# 2. Matar el vigia si esta corriendo (para relanzarlo limpio)
VIGIA_PID=$(pgrep -f "vigia_tiktok720_termux.sh" 2>/dev/null || true)
if [ -n "$VIGIA_PID" ]; then
  echo "[2] Matando vigia (PID: $VIGIA_PID)..."
  kill -9 $VIGIA_PID 2>/dev/null || true
  sleep 1
  echo "    -> Vigia detenido."
else
  echo "[2] Vigia no estaba corriendo."
fi

# 3. Eliminar lock del evacuador Python
if [ -f "$LOCK" ]; then
  echo "[3] Eliminando lock: $LOCK"
  rm -f "$LOCK"
  echo "    -> Lock eliminado."
else
  echo "[3] No existe lock del evacuador."
fi

# 4. Eliminar lock del vigia bash
if [ -f "$VIGIA_LOCK" ]; then
  echo "[4] Eliminando lock del vigia: $VIGIA_LOCK"
  rm -f "$VIGIA_LOCK"
  echo "    -> Lock del vigia eliminado."
else
  echo "[4] No existe lock del vigia."
fi

# 5. Verificar estado final
echo ""
echo "--- Estado final ---"
QUEDAN=$(pgrep -fl "tiktok_evacuador" 2>/dev/null || true)
if [ -n "$QUEDAN" ]; then
  echo "[!] Aun quedan procesos: $QUEDAN"
else
  echo "[OK] Sin procesos tiktok_evacuador colgados."
fi

PENDIENTES=$(find "/sdcard/Antigravity/subidos a facebbok" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \) 2>/dev/null | wc -l)
echo "[INFO] Videos pendientes en fuente: $PENDIENTES"

echo ""
echo "========================================================"
echo "  LISTO. Relanzando widget 6_SUBIR_TIKTOK720..."
echo "========================================================"
sleep 2

# 6. Relanzar el vigia desenganchado del terminal
if [ -f "$VIGIA" ]; then
  mkdir -p "$LOG_DIR"
  nohup setsid bash "$VIGIA" >> "$LAUNCH_LOG" 2>&1 &
  NUEVO_PID=$!
  echo "[OK] Vigia relanzado (PID $NUEVO_PID)."
  echo "     Viendo log en vivo (cerrar esta pantalla no mata el proceso)..."
  echo "--------------------------------------------------------"
  sleep 3
  tail -n 40 -f "$SESSION_LOG"
else
  echo "[ERROR] No existe: $VIGIA"
  echo "        Sincroniza el repo primero con 0_RENOVAR_REPO."
  sleep 10
fi
