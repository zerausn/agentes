#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# ~/.termux/boot/start_adb_tcpip.sh
#
# Se ejecuta automaticamente por Termux:Boot al arrancar el dispositivo.
#
# ESTRATEGIA (sin root):
#   - Espera a que el sistema arranque y haya red WiFi.
#   - Activa ADB TCP via "adb tcpip 5555" usando el adb de Termux
#     que se conecta al adbd LOCAL del mismo dispositivo via loopback.
#   - El PC luego puede conectarse via USB o WiFi: adb connect <IP>:5555
#
# Requiere: Termux:Boot instalado, android-tools en Termux (pkg install android-tools)
# =====================================================================

PREFIX=/data/data/com.termux/files/usr
PATH="$PREFIX/bin:/system/bin:/system/xbin"
TMPDIR="$PREFIX/tmp"
export PATH TMPDIR
LOG="/sdcard/Antigravity/widget_logs/boot_adb_tcpip.log"

mkdir -p /sdcard/Antigravity/widget_logs

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

log "=== start_adb_tcpip.sh arrancando (Termux:Boot) ==="

# Dar tiempo al sistema para terminar de arrancar (WiFi, adbd, etc.)
log "Esperando 35s para que el sistema termine de arrancar..."
sleep 35

log "Iniciando adb server local..."
adb start-server >> "$LOG" 2>&1 || true
sleep 3

# Metodo 1: adb tcpip via loopback (requiere que adbd ya este corriendo)
log "Intentando activar TCP via adb tcpip 5555..."
adb tcpip 5555 >> "$LOG" 2>&1
sleep 3

# Verificar
if adb connect 127.0.0.1:5555 >> "$LOG" 2>&1; then
    if adb devices 2>>"$LOG" | grep -q "127.0.0.1:5555.*device"; then
        log "ADB TCP 127.0.0.1:5555 ACTIVO — OK (primer intento)"
        exit 0
    fi
fi

# Reintento 1
log "Reintento 1 en 20s..."
sleep 20
adb kill-server >> "$LOG" 2>&1 || true
sleep 2
adb start-server >> "$LOG" 2>&1 || true
sleep 3
adb tcpip 5555 >> "$LOG" 2>&1 || true
sleep 3
adb connect 127.0.0.1:5555 >> "$LOG" 2>&1 || true
sleep 2

if adb devices 2>>"$LOG" | grep -q "127.0.0.1:5555.*device"; then
    log "ADB TCP ACTIVO — OK (reintento 1)"
    exit 0
fi

# Reintento 2
log "Reintento 2 en 30s..."
sleep 30
adb tcpip 5555 >> "$LOG" 2>&1 || true
sleep 5
adb connect 127.0.0.1:5555 >> "$LOG" 2>&1 || true
sleep 2

if adb devices 2>>"$LOG" | grep -q "127.0.0.1:5555.*device"; then
    log "ADB TCP ACTIVO — OK (reintento 2)"
    exit 0
fi

log "AVISO: ADB TCP no disponible tras boot. Conecta el USB al PC y el vigia intentara reconectar automaticamente."
log "=== start_adb_tcpip.sh terminado ==="
