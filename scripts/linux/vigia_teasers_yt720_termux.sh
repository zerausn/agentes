#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 3_SUBIR_TEASERS_YT720 — Sube teasers a YouTube cada 720s
#
# METODO: reloj del sistema (date +%s) para evitar Doze.
# + termux-wake-lock activo.
# + chequeo cada 15s.
#
# PATRON: copia exacta del loop de vigia_facebook720_termux.sh
# + deteccion de limite diario de YouTube via log del uploader.
#
# Dos modos:
#   NORMAL  — 1 teaser cada 720s (12 min)
#   LIMITED — cuando YouTube rechaza por uploadLimitExceeded,
#             espera 3600s (1h) entre reintentos. Si una subida
#             es exitosa, vuelve a NORMAL automaticamente.
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
UPLOADER_PROOT="$PR_ROOT/root/agentes/youtube_uploader/teaser_uploader.py"
UL_LOG="$PR_ROOT/root/agentes/youtube_uploader/teaser_uploader.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/3_SUBIR_TEASERS_YT720.log"
TEASERS_DIR="/sdcard/Antigravity/teasers_pendientes"

INTERVALO_NORMAL=720
INTERVALO_LIMITED=3600
CHECK_INTERVAL=15

# ----------------------------------------------------------------
# Espera inteligente basada en reloj del sistema.
# Aunque Android pause el proceso, date +%s es siempre real.
# Si al despertar ya paso el tiempo objetivo, continua de
# inmediato sin perder el ciclo.
# ----------------------------------------------------------------
wait_until() {
    local target_epoch=$1
    local objetivo
    objetivo=$(date -d "@${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || date -r "${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || echo "??:??:??")
    echo "[ESPERA] Proxima subida a las: ${objetivo}"

    while true; do
        local now
        now=$(date +%s)
        local diff=$(( target_epoch - now ))

        if [ "$diff" -le 0 ]; then
            echo "[RELOJ] Hora alcanzada: $(date '+%H:%M:%S') — arrancando ciclo."
            return 0
        fi

        printf "\r[RELOJ] %3ds restantes (objetivo %s)..." "$diff" "$objetivo"
        sleep "$CHECK_INTERVAL"
    done
}

# ----------------------------------------------------------------
# Contar teasers pendientes (sin .uploaded)
# ----------------------------------------------------------------
count_pending_teasers() {
source "$(dirname "$0")/_proot_bind.sh"
    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- python3 -c "
from pathlib import Path
root = Path('/sdcard/Antigravity')
input_dir = root / 'teasers_pendientes'
state_dir = root / '.state'
exts = {'.mp4', '.mov', '.mkv'}
count = 0
if input_dir.exists():
    for f in input_dir.iterdir():
        if f.is_file() and f.suffix.lower() in exts and 'teaser' in f.name.lower():
            marker = state_dir / f'{f.name}.uploaded'
            if not marker.exists():
                count += 1
print(count)
"
}

find_first_teaser() {
    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- python3 -c "
from pathlib import Path
root = Path('/sdcard/Antigravity')
input_dir = root / 'teasers_pendientes'
state_dir = root / '.state'
exts = {'.mp4', '.mov', '.mkv'}
if input_dir.exists():
    files = sorted(
        [f for f in input_dir.iterdir()
         if f.is_file() and f.suffix.lower() in exts and 'teaser' in f.name.lower()],
        key=lambda p: p.name.lower()
    )
    for f in files:
        marker = state_dir / f'{f.name}.uploaded'
        if not marker.exists():
            print(str(f))
            break
"
}

# ----------------------------------------------------------------
# Limpiar la linea de progreso (\r) antes de escribir encima
# ----------------------------------------------------------------
clean_line() {
    printf "\r%s\n" "$1"
}

# ----------------------------------------------------------------
# Setup
# ----------------------------------------------------------------
mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  3_SUBIR_TEASERS_YT720 — reloj sistema"
echo "  Intervalo normal: ${INTERVALO_NORMAL}s | Limited: ${INTERVALO_LIMITED}s | Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

# Wake lock
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para habilitar wake-lock."
fi

trap 'clean_line "[SALIDA] $(date "+%H:%M:%S") — liberando wake-lock"; termux-wake-unlock 2>/dev/null || true; exit' INT TERM EXIT

# ----------------------------------------------------------------
# Verificaciones
# ----------------------------------------------------------------
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado: $PROOT"
    exit 1
fi

if [ ! -f "$UPLOADER_PROOT" ]; then
    echo "[ERROR] No existe teaser_uploader.py"
    echo "        Ruta: $UPLOADER_PROOT"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"
touch "$UL_LOG" 2>/dev/null || true

# ----------------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------------
CICLO=0
MODE="NORMAL"

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)
    UPLOAD_OK=false

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Modo: ${MODE}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # --------------------------------------------------------
    # Paso 1: Buscar el primer teaser pendiente
    # --------------------------------------------------------
    FIRST_TEASER=$(find_first_teaser)

    if [ -z "$FIRST_TEASER" ]; then
        echo "[SIN TEASERS] No hay teasers pendientes por subir."
    else
        echo "[TEASER] ${FIRST_TEASER}"
        echo "[UPLOAD] Lanzando teaser_uploader.py dentro de Debian..."
        echo "[UPLOAD] Log uploader: ${UL_LOG}"
        echo ""

        # --------------------------------------------------------
        # Paso 2: Subir 1 teaser — SIN timeout, output en vivo
        # --------------------------------------------------------
        "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
            "cd /root/agentes/youtube_uploader && \
             AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
             python3 teaser_uploader.py \
               --single-file '${FIRST_TEASER}' \
               --from-orchestrator"
        EXIT_CODE=$?

        # --------------------------------------------------------
        # Paso 3: Determinar resultado
        # --------------------------------------------------------
        if [ "$EXIT_CODE" -eq 0 ]; then
            UPLOAD_OK=true
            # Verificar si en modo LIMITED el limite se resetio
            if [ "$MODE" = "LIMITED" ]; then
                echo "[RECUPERADO] Limite diario reseteado. Volviendo a modo NORMAL."
                MODE="NORMAL"
            fi
        else
            # Revisar el log del uploader para LIMIT_EXCEEDED
            if [ -f "$UL_LOG" ] && tail -20 "$UL_LOG" 2>/dev/null | grep -qi "LIMIT_EXCEEDED\|uploadLimitExceeded"; then
                clean_line "[LIMITE] YouTube rechazo la subida: limite diario alcanzado. Cambiando a modo LIMITED."
                MODE="LIMITED"
            else
                echo "[ERROR] La subida fallo con codigo ${EXIT_CODE}."
            fi
        fi
    fi

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))

    # --------------------------------------------------------
    # Paso 4: Resumen del ciclo + pendientes
    # --------------------------------------------------------
    PENDIENTES=$(count_pending_teasers)
    if [ "$UPLOAD_OK" = true ]; then
        echo "[CICLO #${CICLO}] OK — subida completada en ${DURACION}s."
    elif [ -z "$FIRST_TEASER" ]; then
        echo "[CICLO #${CICLO}] Sin teasers pendientes (${DURACION}s)."
    elif [ "$MODE" = "LIMITED" ]; then
        echo "[CICLO #${CICLO}] LIMITE DIARIO — esperando ${INTERVALO_LIMITED}s (1h) antes de reintentar."
    else
        echo "[CICLO #${CICLO}] FALLO — error en subida (${DURACION}s)."
    fi
    echo "[PENDIENTES] ${PENDIENTES} teasers restantes en ${TEASERS_DIR}"

    # --------------------------------------------------------
    # Paso 5: Calcular proxima ejecucion segun modo
    # --------------------------------------------------------
    if [ "$MODE" = "LIMITED" ]; then
        NEXT_EPOCH=$(( T_FIN + INTERVALO_LIMITED ))
        echo "[RELOJ] Ciclo termino: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO_LIMITED}s (modo LIMITED)"
    else
        NEXT_EPOCH=$(( T_FIN + INTERVALO_NORMAL ))
        echo "[RELOJ] Ciclo termino: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO_NORMAL}s"
    fi

    wait_until "$NEXT_EPOCH"
    printf "\n"
done
