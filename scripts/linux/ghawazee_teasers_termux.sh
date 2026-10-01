#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 9_GHAWAZEE_TEASERS — Evacuador Facebook TEASERS (S24 Termux)
# Sube 1 TEASER cada 2880 segundos (aprox 48 minutos) -> 30 diarios
#
# TEASERS -> Ghawazee Writings (ID: 1288381367700799)
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
EVACUADOR_PROOT="$PR_ROOT/root/agentes/meta_uploader/subir_teasers_ghawazee.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/fb_ghawazee_teasers.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/9_GHAWAZEE_TEASERS.log"

# Intervalo objetivo en segundos entre subidas (30 videos/dia = 2880s)
INTERVALO=2880

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
    echo "[SALIDA GHAWAZEE] $(date +%H:%M:%S) — liberando wake-lock" >> "$SESSION_LOG"
    echo "" >> "$SESSION_LOG"
}

trap liberar_wake_lock EXIT

wait_until() {
    local target_time=$1
    echo "[GHAWAZEE ESPERA] Proxima subida a las: $(date -d @$target_time +'%H:%M:%S')" >> "$SESSION_LOG"
    
    while true; do
        local current_time=$(date +%s)
        if [ "$current_time" -ge "$target_time" ]; then
            break
        fi
        local remaining=$((target_time - current_time))
        echo -ne "\r[GHAWAZEE RELOJ] ${remaining}s restantes (objetivo $(date -d @$target_time +'%H:%M:%S'))...\033[K"
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
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  9_GHAWAZEE_TEASERS — Evasión Anti-Spam (30/día)"
echo "  Intervalo: ${INTERVALO}s"
echo "  Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date +'%Y-%m-%d %H:%M:%S')"
echo "  Destino: Ghawazee Writings (1288381367700799)"
echo "=============================================="

adquirir_wake_lock

# ----------------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------------
CICLO=1
while true; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO GHAWAZEE #$CICLO — $(date +'%Y-%m-%d %H:%M:%S')"
    echo "  Destino: Ghawazee Writings"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Invocamos a proot-distro
    set +e
    $PROOT login debian --bind /sdcard:/sdcard -- bash -c "source /root/.bashrc 2>/dev/null; cd /root/agentes/meta_uploader && python3 subir_teasers_ghawazee.py"
    STATUS=$?
    set -e

    if [ $STATUS -eq 0 ]; then
        echo "[GHAWAZEE CICLO #$CICLO] Video subido OK."
    elif [ $STATUS -eq 2 ]; then
        echo "[GHAWAZEE CICLO #$CICLO] Sin TEASERS pendientes / Backoff Activo."
    else
        echo "[GHAWAZEE CICLO #$CICLO] Error exit=$STATUS."
    fi

    # Calculamos el objetivo exacto
    CURRENT_TS=$(date +%s)
    NEXT_TARGET=$((CURRENT_TS + INTERVALO))
    
    echo "[GHAWAZEE RELOJ] Ciclo terminó: $(date +%H:%M:%S) | Siguiente en ${INTERVALO}s"
    wait_until "$NEXT_TARGET"

    CICLO=$((CICLO + 1))
done
