#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# Widget Termux: REPARAR_ADB_VIVO.sh
# Reparar ADB TCP (127.0.0.1:5555) en el Vivo cuando se pierde
# tras un reinicio o desconexion de USB.
#
# Este widget se puede correr desde Termux:Widget o desde terminal.
# No requiere root.
# ================================================================
set -euo pipefail
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/system/bin:/system/xbin"
export TMPDIR="$PREFIX/tmp"

LOG_DIR="/sdcard/Antigravity/widget_logs"
LOG="$LOG_DIR/reparar_adb_vivo.log"
BOOT_SCRIPT="/data/data/com.termux/files/home/.termux/boot/start_adb_tcpip.sh"

mkdir -p "$LOG_DIR"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG"
}

echo ""
echo "=================================================="
echo "  REPARAR_ADB_VIVO — ADB TCP Auto-Repair"
echo "  Vivo V2058 | Puerto: 5555"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="
echo ""

log "=== REPARAR_ADB_VIVO iniciado ==="

# 1. Verificar si ADB ya esta activo
log "Verificando estado actual de ADB..."
adb start-server >> "$LOG" 2>&1 || true
sleep 2

if adb devices 2>>"$LOG" | grep -q "127.0.0.1:5555.*device"; then
    log "ADB TCP ya activo en 127.0.0.1:5555 — no se necesita reparacion."
    echo ""
    echo "[OK] ADB ya estaba activo. No se requiere accion."
    echo ""
    exit 0
fi

log "ADB no disponible. Iniciando reparacion..."

# 2. Reiniciar servidor ADB
log "Reiniciando servidor ADB..."
adb kill-server >> "$LOG" 2>&1 || true
sleep 2
adb start-server >> "$LOG" 2>&1 || true
sleep 3

# 3. Activar TCP via adb tcpip (sin root)
log "Activando modo TCP en puerto 5555..."
adb tcpip 5555 >> "$LOG" 2>&1 || true
sleep 3

# 4. Conectar
log "Conectando a 127.0.0.1:5555..."
adb connect 127.0.0.1:5555 >> "$LOG" 2>&1 || true
sleep 2

# 5. Verificar
if adb devices 2>>"$LOG" | grep -q "127.0.0.1:5555.*device"; then
    log "ADB TCP ACTIVO — Reparacion exitosa."
    echo ""
    echo "[OK] ADB reparado: 127.0.0.1:5555 disponible."
    echo "     El widget 6_SUBIR_TIKTOK720 puede continuar."
    echo ""
else
    # 6. Segundo intento con reinicio completo
    log "Primer intento fallido. Reintentando..."
    adb kill-server >> "$LOG" 2>&1 || true
    sleep 3
    adb start-server >> "$LOG" 2>&1 || true
    sleep 5
    adb tcpip 5555 >> "$LOG" 2>&1 || true
    sleep 5
    adb connect 127.0.0.1:5555 >> "$LOG" 2>&1 || true
    sleep 3

    if adb devices 2>>"$LOG" | grep -q "127.0.0.1:5555.*device"; then
        log "ADB TCP ACTIVO — Reparacion exitosa en segundo intento."
        echo ""
        echo "[OK] ADB reparado (2do intento). Listo para continuar."
        echo ""
    else
        log "ERROR: ADB TCP no disponible. Conecta el USB al PC y ejecuta:"
        log "  adb -s <SERIAL_USB> tcpip 5555"
        echo ""
        echo "[ERROR] ADB TCP no pudo activarse."
        echo ""
        echo "Opciones:"
        echo "  1. Conecta el USB al PC y ejecuta desde la PC:"
        echo "     adb -s 34237840310037S tcpip 5555"
        echo ""
        echo "  2. O habilita WiFi ADB desde:"
        echo "     Ajustes > Opciones desarrollador > Depuracion inalambrica"
        echo ""
        exit 1
    fi
fi

# 7. Mostrar estado final
echo "--- Estado ADB ---"
adb devices 2>/dev/null | tee -a "$LOG"
echo ""
log "=== REPARAR_ADB_VIVO terminado ==="
