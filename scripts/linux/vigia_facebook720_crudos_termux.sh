#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 4_VIGIA_FACEBOOK720_CRUDOS — Evacuador Facebook CRUDOS (Note9 Termux)
# Sube 1 video CRUDO cada 720 segundos. Timer INDEPENDIENTE.
#
# CRUDOS → Performatic Writings Cali (ID: 803559979506784)
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
EVACUADOR_PROOT="$PR_ROOT/root/agentes/meta_uploader/subir_fb_evacuador_crudos.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/fb_evacuador_crudos.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/4_VIGIA_FACEBOOK720_CRUDOS.log"

# Intervalo objetivo en segundos entre subidas
INTERVALO=720

# Intervalo de chequeo del reloj (no sleep largo)
CHECK_INTERVAL=15

# ----------------------------------------------------------------
# Espera inteligente basada en reloj del sistema.
# Aunque Android pause el proceso, date +%s es siempre real.
# Si al despertar ya pasó el tiempo objetivo, continúa de
# inmediato sin perder el ciclo.
# ----------------------------------------------------------------
wait_until() {
    local target_epoch=$1
    local objetivo
    objetivo=$(date -d "@${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || date -r "${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || echo "??:??:??")
    echo "[CRUDOS ESPERA] Proxima subida a las: ${objetivo}"

    while true; do
        local now
        now=$(date +%s)
        local diff=$(( target_epoch - now ))

        if [ "$diff" -le 0 ]; then
            echo "[CRUDOS RELOJ] Hora alcanzada: $(date '+%H:%M:%S') — arrancando ciclo."
            return 0
        fi

        printf "\r[CRUDOS RELOJ] %3ds restantes (objetivo %s)..." "$diff" "$objetivo"
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
echo "  4_VIGIA_FACEBOOK720_CRUDOS — reloj sistema"
echo "  Intervalo: ${INTERVALO}s | Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Destino: Performatic Writings Cali (803559979506784)"
echo "=============================================="

# Wake lock
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para habilitar wake-lock."
fi

trap 'printf "\n"; echo "[SALIDA CRUDOS] $(date '+%H:%M:%S') — liberando wake-lock"; termux-wake-unlock 2>/dev/null || true; exit' INT TERM EXIT

# Verificaciones
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado: $PROOT"
    exit 1
fi

if [ ! -f "$EVACUADOR_PROOT" ]; then
    echo "[ERROR] No existe subir_fb_evacuador_crudos.py"
    echo "        Ruta: $EVACUADOR_PROOT"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"
touch "$LOG_FILE"

# ----------------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------------
CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO CRUDOS #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Destino: Performatic Writings Cali (803559979506784)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Lanzar evacuador: sube 1 video CRUDO y retorna
source "$(dirname "$0")/_proot_bind.sh"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
export META_FB_PAGE_ID_RAW
export META_FB_PAGE_TOKEN_RAW
export META_FB_PAGE_TOKEN
    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
        "set -o pipefail; cd /root/agentes/meta_uploader && AGENTES_STORAGE_ROOT=/sdcard/Antigravity python3 subir_fb_evacuador_crudos.py 2>&1 | tee -a '${LOG_FILE}'"
    EXIT_CODE=$?

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))

    # Contar cuántos videos CRUDOS quedan en la carpeta fuente
    SOURCE_DIR="/sdcard/Antigravity/videos subidos exitosamente"
    PENDIENTES=$(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \) 2>/dev/null | grep -v -i "_teaser_" | wc -l)

    case "$EXIT_CODE" in
        0)  echo "[CRUDOS CICLO #${CICLO}] OK — subida exitosa en ${DURACION}s. | Pendientes CRUDOS: ${PENDIENTES}"
            ;;
        2)  echo "[CRUDOS CICLO #${CICLO}] Sin videos CRUDOS pendientes (${DURACION}s). | Pendientes: 0"
            ;;
        *)  echo "[CRUDOS CICLO #${CICLO}] Error exit=$EXIT_CODE (${DURACION}s). | Pendientes CRUDOS: ${PENDIENTES}"
            ;;
    esac

    # Calcular próxima ejecución basada en reloj real
    NEXT_EPOCH=$(( T_FIN + INTERVALO ))
    echo "[CRUDOS RELOJ] Ciclo terminó: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO}s"

    wait_until "$NEXT_EPOCH"
    printf "\n"
done