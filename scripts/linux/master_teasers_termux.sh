#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 10_MASTER_TEASERS_ROTATIVO — Evacuador Rotativo de 4 Paginas
# Sube 1 TEASER cada 12 minutos (720s) saltando de pagina en pagina.
# Cada pagina recibe 1 video cada 48 minutos -> Exactamente 30 al dia por pagina.
#
# Orden: Seanchai -> Ghawazee -> Shirabyoshi -> Performatic
# ================================================================

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/10_MASTER_TEASERS.log"

# Array con los scripts de python a ejecutar en orden
SCRIPTS=(
    "subir_teasers_seanchai.py"
    "subir_teasers_ghawazee.py"
    "subir_teasers_shirabyoshi.py"
    "subir_fb_evacuador_teasers.py"
)

# Nombres legibles para el log
NOMBRES=(
    "Seanchai Writings"
    "Ghawazee Writings"
    "Shirabyoshi Writings"
    "Performatic Writings"
)

# Intervalo entre CADA publicacion en segundos (12 minutos)
INTERVALO=720
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
    echo "[SALIDA MASTER] $(date +%H:%M:%S) — liberando wake-lock" >> "$SESSION_LOG"
    echo "" >> "$SESSION_LOG"
}

trap liberar_wake_lock EXIT

wait_until() {
    local target_time=$1
    echo "[MASTER ESPERA] Proxima subida a las: $(date -d @$target_time +'%H:%M:%S')" >> "$SESSION_LOG"
    
    while true; do
        local current_time=$(date +%s)
        if [ "$current_time" -ge "$target_time" ]; then
            break
        fi
        local remaining=$((target_time - current_time))
        echo -ne "\r[MASTER RELOJ] ${remaining}s restantes (objetivo $(date -d @$target_time +'%H:%M:%S'))...\033[K"
        sleep "$CHECK_INTERVAL"
    done
    echo ""
}

# ----------------------------------------------------------------
# Setup y Logging
# ----------------------------------------------------------------
mkdir -p "$LOG_DIR"
touch "$SESSION_LOG"
tail -n 1000 "$SESSION_LOG" > "${SESSION_LOG}.tmp" && mv "${SESSION_LOG}.tmp" "$SESSION_LOG"

exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  10_MASTER_TEASERS_ROTATIVO (Anti-Spam Warmup)"
echo "  Publica cada ${INTERVALO}s rotando entre 4 paginas."
echo "  (Resulta en 30 videos exactos por pagina al dia)"
echo "  Inicio: $(date +'%Y-%m-%d %H:%M:%S')"
echo "=============================================="

adquirir_wake_lock

# ----------------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------------
CICLO=1
IDX=0
TOTAL_PAGINAS=${#SCRIPTS[@]}

while true; do
    SCRIPT_ACTUAL="${SCRIPTS[$IDX]}"
    NOMBRE_ACTUAL="${NOMBRES[$IDX]}"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO GLOBAL #$CICLO — $(date +'%Y-%m-%d %H:%M:%S')"
    echo "  Turno de: $NOMBRE_ACTUAL"
    echo "  Script: $SCRIPT_ACTUAL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Invocamos a proot-distro con el script que toca
    set +e
    $PROOT login debian --bind /sdcard:/sdcard -- bash -c "source /root/.bashrc 2>/dev/null; cd /root/agentes/meta_uploader && python3 $SCRIPT_ACTUAL"
    STATUS=$?
    set -e

    if [ $STATUS -eq 0 ]; then
        echo "[$NOMBRE_ACTUAL] Video subido OK."
    elif [ $STATUS -eq 2 ]; then
        echo "[$NOMBRE_ACTUAL] Sin TEASERS / Backoff Activo."
    else
        echo "[$NOMBRE_ACTUAL] Error exit=$STATUS."
    fi

    # Calculamos el objetivo exacto para la SIGUIENTE pagina
    CURRENT_TS=$(date +%s)
    NEXT_TARGET=$((CURRENT_TS + INTERVALO))
    
    # Avanzamos al siguiente indice circularmente
    IDX=$(( (IDX + 1) % TOTAL_PAGINAS ))
    SIGUIENTE_NOMBRE="${NOMBRES[$IDX]}"
    
    echo "[MASTER RELOJ] Ciclo terminó: $(date +%H:%M:%S) | Proximo turno ($SIGUIENTE_NOMBRE) en ${INTERVALO}s"
    wait_until "$NEXT_TARGET"

    CICLO=$((CICLO + 1))
done
