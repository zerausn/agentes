#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 7_SHIRABYOSHI_TEASERS — Evacuador Facebook TEASERS Seguro (S24 Termux)
# Sube 1 TEASER con intervalo ultralargo ALEATORIO entre 2 a 4 horas (7200-14400s).
# Diseñado específicamente para evitar el Code 368 de Meta y "calentar" la cuenta.
#
# TEASERS → Shirabyoshi Writings (ID: 1347014641828725)
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
EVACUADOR_PROOT="$PR_ROOT/root/agentes/meta_uploader/subir_teasers_shirabyoshi.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/fb_shirabyoshi_teasers.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/7_SHIRABYOSHI_TEASERS.log"

# Rango aleatorio ultralargo: 2-4 horas (7200 - 14400 segundos)
INTERVALO_MIN=7200
INTERVALO_MAX=14400

# Intervalo de chequeo del reloj (no sleep largo)
CHECK_INTERVAL=15

# ----------------------------------------------------------------
# Genera un intervalo aleatorio entre INTERVALO_MIN y INTERVALO_MAX
# ----------------------------------------------------------------
generar_intervalo_aleatorio() {
    # Usar $RANDOM (0-32767)
    local rango=$((INTERVALO_MAX - INTERVALO_MIN + 1))
    local intervalo=$((INTERVALO_MIN + RANDOM % rango))
    echo $intervalo
}

# ----------------------------------------------------------------
# Espera inteligente basada en reloj del sistema.
# ----------------------------------------------------------------
wait_until() {
    local target_epoch=$1
    local objetivo
    objetivo=$(date -d "@${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || date -r "${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || echo "??:??:??")
    echo "[SHIRABYOSHI ESPERA] Proxima subida a las: ${objetivo}"

    while true; do
        local now
        now=$(date +%s)
        local diff=$(( target_epoch - now ))

        if [ "$diff" -le 0 ]; then
            printf "\n"
            echo "[SHIRABYOSHI RELOJ] Hora alcanzada: $(date '+%H:%M:%S') — arrancando ciclo."
            return 0
        fi

        printf "\r[SHIRABYOSHI RELOJ] %4ds restantes (objetivo %s)..." "$diff" "$objetivo"
        sleep "$CHECK_INTERVAL"
    done
}

# ----------------------------------------------------------------
# Setup
# ----------------------------------------------------------------
mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  7_SHIRABYOSHI_TEASERS — Evasión Anti-Spam"
echo "  Intervalo: ALEATORIO ${INTERVALO_MIN}-${INTERVALO_MAX}s (2-4 horas)"
echo "  Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Destino: Shirabyoshi Writings (1347014641828725)"
echo "=============================================="

# Wake lock
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para habilitar wake-lock."
fi

trap 'printf "\n"; echo "[SALIDA SHIRABYOSHI] $(date '+%H:%M:%S') — liberando wake-lock"; termux-wake-unlock 2>/dev/null || true; exit' INT TERM EXIT

# Verificaciones
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado: $PROOT"
    exit 1
fi

if [ ! -f "$EVACUADOR_PROOT" ]; then
    echo "[ERROR] No existe subir_teasers_shirabyoshi.py"
    echo "        Ruta: $EVACUADOR_PROOT"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"
export META_FB_PAGE_ID_TEASER
export META_FB_PAGE_TOKEN_TEASER
export META_FB_PAGE_TOKEN
touch "$LOG_FILE"

# ----------------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------------
CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    # Generar intervalo aleatorio para ESTE ciclo
    INTERVALO_ALEATORIO=$(generar_intervalo_aleatorio)
    hr=$((INTERVALO_ALEATORIO / 3600))
    min=$(((INTERVALO_ALEATORIO % 3600) / 60))
    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO SHIRABYOSHI #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Próximo intervalo: ${INTERVALO_ALEATORIO}s (${hr}h ${min}m)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    source "/data/data/com.termux/files/home/agentes/scripts/linux/_proot_bind.sh"
    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- \
        META_FB_PAGE_ID_TEASER="${META_FB_PAGE_ID_TEASER}" \
        META_FB_PAGE_TOKEN_TEASER="${META_FB_PAGE_TOKEN_TEASER}" \
        META_FB_PAGE_TOKEN="${META_FB_PAGE_TOKEN}" \
        /bin/bash -lc \
        "set -o pipefail; cd /root/agentes/meta_uploader && AGENTES_STORAGE_ROOT=/sdcard/Antigravity python3 subir_teasers_shirabyoshi.py 2>&1 | tee -a '${LOG_FILE}'"
    EXIT_CODE=$?

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))

    SOURCE_DIR="/sdcard/Antigravity/videos subidos exitosamente"
    PENDIENTES=$(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \) 2>/dev/null | grep -i "_teaser_" | wc -l)

    case "$EXIT_CODE" in
        0)  echo "[SHIRABYOSHI CICLO #${CICLO}] OK — subida exitosa en ${DURACION}s. | Pendientes TEASERS: ${PENDIENTES}"
            ;;
        2)  echo "[SHIRABYOSHI CICLO #${CICLO}] Sin acción requerida / Backoff Activo (${DURACION}s). | Pendientes: ${PENDIENTES}"
            ;;
        *)  echo "[SHIRABYOSHI CICLO #${CICLO}] Error exit=$EXIT_CODE (${DURACION}s). | Pendientes TEASERS: ${PENDIENTES}"
            ;;
    esac

    NEXT_EPOCH=$(( T_FIN + INTERVALO_ALEATORIO ))
    hr=$((INTERVALO_ALEATORIO / 3600))
    min=$(((INTERVALO_ALEATORIO % 3600) / 60))
    echo "[SHIRABYOSHI RELOJ] Ciclo terminó: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO_ALEATORIO}s (${hr}h ${min}m)"

    wait_until "$NEXT_EPOCH"
    printf "\n"
done
