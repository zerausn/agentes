#!/bin/bash
set -euo pipefail

SERIAL="${1:-34237840310037S}"
STATE_DIR="/sdcard/Antigravity/.state"
REQUEST_FILE="$STATE_DIR/share_request.txt"
LOG_DIR="/tmp/antigravity_adb_watch"
LOG="$LOG_DIR/adb_watch_vivo.log"
POLL_SECONDS=2

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

cleanup() {
    log "Watcher detenido."
    exit 0
}
trap cleanup INT TERM

log "ADB Watcher VIVO iniciado (serial: $SERIAL)"
log "Poll cada ${POLL_SECONDS}s: $REQUEST_FILE"

while true; do
    content=$(adb -s "$SERIAL" shell "cat '$REQUEST_FILE' 2>/dev/null" | tr -d '\r' | head -c 2000 || true)
    if [ -n "$content" ] && [ "$content" != " " ]; then
        log "Request encontrado: ${content:0:120}..."
        if echo "$content" | grep -q "^adb "; then
            cmd="${content/#adb /adb -s $SERIAL }"
            log "Ejecutando: $cmd"
            if eval "$cmd" >> "$LOG" 2>&1; then
                log "Comando ejecutado OK"
            else
                log "ERROR: comando fallo (RC=$?)"
            fi
        else
            log "ERROR: formato desconocido: $content"
        fi
        adb -s "$SERIAL" shell "rm -f '$REQUEST_FILE'" >> "$LOG" 2>&1 || true
        log "Request file eliminado"
    fi
    sleep "$POLL_SECONDS"
done
