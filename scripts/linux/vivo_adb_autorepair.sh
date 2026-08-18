#!/usr/bin/env bash
# ==============================================================
# vivo_adb_autorepair.sh
#
# Detecta cuando el Vivo V2058 se conecta por USB y activa
# automáticamente el modo TCP (puerto 5555) para que Termux
# pueda usar ADB local (127.0.0.1:5555) sin necesidad de root.
#
# Uso:
#   - Ejecutar como servicio al iniciar sesión (ver systemd o autostart)
#   - Requiere: adb instalado en el PC, udev configurado
#
# Instalación automática del servicio (systemd --user):
#   bash vivo_adb_autorepair.sh --install
# ==============================================================

VIVO_SERIAL="34237840310037S"   # Ajusta si cambia al reconectar
ADB_PORT=5555
LOG="/tmp/vivo_adb_autorepair.log"
POLL_INTERVAL=10  # segundos entre checks

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

activate_tcpip() {
    local serial="$1"
    log "Vivo detectado: $serial — activando tcpip $ADB_PORT..."
    adb -s "$serial" tcpip "$ADB_PORT" >> "$LOG" 2>&1
    sleep 2
    local ip
    ip=$(adb -s "$serial" shell ip route | grep -oP '(?<=src )\S+' | head -1)
    if [ -n "$ip" ]; then
        log "IP del Vivo: $ip — conectando $ip:$ADB_PORT..."
        adb connect "$ip:$ADB_PORT" >> "$LOG" 2>&1
        log "ADB TCP activado: $ip:$ADB_PORT"
    else
        log "No se pudo obtener IP del Vivo. TCP activado en 127.0.0.1:$ADB_PORT vía USB."
    fi
}

install_service() {
    SCRIPT_PATH="$(realpath "$0")"
    SERVICE_DIR="$HOME/.config/systemd/user"
    SERVICE_FILE="$SERVICE_DIR/vivo-adb-autorepair.service"
    mkdir -p "$SERVICE_DIR"
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Vivo V2058 ADB TCP Auto-Repair
After=default.target

[Service]
Type=simple
ExecStart=/bin/bash $SCRIPT_PATH --watch
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable vivo-adb-autorepair.service
    systemctl --user start vivo-adb-autorepair.service
    echo "Servicio instalado y arrancado."
    echo "Ver logs: journalctl --user -u vivo-adb-autorepair -f"
    echo "O ver: tail -f $LOG"
}

watch_loop() {
    log "=== Vivo ADB Auto-Repair iniciado (poll cada ${POLL_INTERVAL}s) ==="
    declare -A ACTIVATED
    while true; do
        # Obtener dispositivos conectados por USB (no TCP)
        while IFS= read -r line; do
            serial=$(echo "$line" | awk '{print $1}')
            state=$(echo "$line" | awk '{print $2}')
            # Solo dispositivos USB (no contienen ":" en el serial = no son TCP)
            if [[ "$state" == "device" && "$serial" != *":"* ]]; then
                if [ -z "${ACTIVATED[$serial]+x}" ]; then
                    activate_tcpip "$serial"
                    ACTIVATED["$serial"]=1
                fi
            fi
        done < <(adb devices | tail -n +2 | grep -v "^$")

        # Limpiar dispositivos desconectados del map
        for serial in "${!ACTIVATED[@]}"; do
            if ! adb devices | grep -q "^$serial"; then
                log "Vivo desconectado ($serial) — reseteando estado."
                unset "ACTIVATED[$serial]"
            fi
        done

        sleep "$POLL_INTERVAL"
    done
}

# ---- Main ----
case "${1:-}" in
    --install)
        install_service
        ;;
    --watch)
        watch_loop
        ;;
    *)
        echo "Uso:"
        echo "  $0 --install    Instala el servicio systemd --user (se autoinicia al login)"
        echo "  $0 --watch      Corre en primer plano (modo manual)"
        ;;
esac
