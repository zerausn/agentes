#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 8_SEANCHAI_TEASERS — Evacuador Facebook TEASERS (S24 Termux)
# Sube 1 TEASER cada 720 segundos. Timer INDEPENDIENTE.
#
# TEASERS -> Seanchai Writings (ID: 824642984061807)
# ================================================================

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
if [ -d "/data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs" ]; then
    PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs"
else
    PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian"
fi
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
EVACUADOR_PROOT="$PR_ROOT/root/agentes/meta_uploader/subir_teasers_seanchai.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/fb_seanchai_teasers.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/8_SEANCHAI_TEASERS.log"

# Intervalo objetivo en segundos entre subidas (igual a 4_VIGIA_FACEBOOK720)
INTERVALO=720

# Intervalo de chequeo del reloj
CHECK_INTERVAL=15

# ----------------------------------------------------------------
# Funciones de Soporte
# ----------------------------------------------------------------
adquirir_wake_lock() {
    termux-wake-lock
    echo "[WAKE-LOCK] Activado." >> "$SESSION_LOG"
}

liberar_wake_lock() {
    termux-wake-unlock
    echo "[SALIDA SEANCHAI] $(date +%H:%M:%S) — liberando wake-lock" >> "$SESSION_LOG"
    echo "" >> "$SESSION_LOG"
}

trap liberar_wake_lock EXIT

wait_until() {
    local target_time=$1
    echo "[SEANCHAI ESPERA] Proxima subida a las: $(date -d @$target_time +'%H:%M:%S')" >> "$SESSION_LOG"
    
    while true; do
        local current_time=$(date +%s)
        if [ "$current_time" -ge "$target_time" ]; then
            break
        fi
        local remaining=$((target_time - current_time))
        echo -ne "\r[SEANCHAI RELOJ] ${remaining}s restantes (objetivo $(date -d @$target_time +'%H:%M:%S'))...\033[K"
        sleep "$CHECK_INTERVAL"
    done
    echo ""
}

# ----------------------------------------------------------------
# Setup y Logging
# ----------------------------------------------------------------
mkdir -p "$LOG_DIR"
touch "$SESSION_LOG"
# Solo mantenemos las ultimas 1000 lineas del log para no saturar memoria
tail -n 1000 "$SESSION_LOG" > "${SESSION_LOG}.tmp" && mv "${SESSION_LOG}.tmp" "$SESSION_LOG"

# Evitamos el flood redirigiendo solo stdout temporalmente
# y usando tee para guardar en archivo, excepto los echos con \r
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  8_SEANCHAI_TEASERS — Evasion Anti-Spam"
echo "  Intervalo: ${INTERVALO}s"
echo "  Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date +'%Y-%m-%d %H:%M:%S')"
echo "  Destino: Seanchai Writings (824642984061807)"
echo "=============================================="

adquirir_wake_lock

# ----------------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------------
CICLO=1
while true; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO SEANCHAI #$CICLO — $(date +'%Y-%m-%d %H:%M:%S')"
    echo "  Destino: Seanchai Writings"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Invocamos a proot-distro
    set +e
    $PROOT login debian --bind /sdcard:/sdcard -- bash -c "source /root/.bashrc 2>/dev/null; cd /root/agentes/meta_uploader && python3 subir_teasers_seanchai.py"
    STATUS=$?
    set -e

    if [ $STATUS -eq 0 ]; then
        echo "[SEANCHAI CICLO #$CICLO] Video subido OK."
    elif [ $STATUS -eq 2 ]; then
        echo "[SEANCHAI CICLO #$CICLO] Sin TEASERS pendientes / Backoff Activo."
    else
        echo "[SEANCHAI CICLO #$CICLO] Error exit=$STATUS."
    fi

    # Calculamos el objetivo exacto (Independiente del tiempo que tardo en subir)
    # Siempre sera: Hora Actual + INTERVALO
    CURRENT_TS=$(date +%s)
    NEXT_TARGET=$((CURRENT_TS + INTERVALO))
    
    echo "[SEANCHAI RELOJ] Ciclo terminó: $(date +%H:%M:%S) | Siguiente en ${INTERVALO}s"
    wait_until "$NEXT_TARGET"

    CICLO=$((CICLO + 1))
done
