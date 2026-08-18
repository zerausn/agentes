#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# VIGIA_META720 — Crossposteador FB->IG (S24 Termux)
# Crosspostea 1 post de Facebook a Instagram cada 720 segundos.
#
# METODO: reloj del sistema (date +%s) para determinar cuándo
# es el siguiente ciclo. Si Android pausa el proceso por Doze,
# cuando despierte date +%s devuelve la hora REAL — si ya
# pasaron 720s, crosspostea inmediatamente sin esperar más.
#
# + termux-wake-lock activo para minimizar pausas.
# + chequeo cada 15s (no sleep largo que Doze pueda congelar).
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
VIGIA_PROOT="$PR_ROOT/root/agentes/meta_uploader/fb_to_ig_vigia_720.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/fb_to_ig_vigia.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/VIGIA_META720.log"

INTERVALO=720
CHECK_INTERVAL=15

wait_until() {
    local target_epoch=$1
    local objetivo
    objetivo=$(date -d "@${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || date -r "${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || echo "??:??:??")
    echo "[ESPERA] Proxima ejecucion a las: ${objetivo}"

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

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  VIGIA_META720 — reloj sistema"
echo "  Intervalo: ${INTERVALO}s | Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para habilitar wake-lock."
fi

trap 'printf "\n"; echo "[SALIDA] $(date "+%H:%M:%S") — liberando wake-lock"; termux-wake-unlock 2>/dev/null || true; exit' INT TERM EXIT

if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado: $PROOT"
    exit 1
fi

if [ ! -f "$VIGIA_PROOT" ]; then
    echo "[ERROR] No existe fb_to_ig_vigia_720.py"
    echo "        Ruta: $VIGIA_PROOT"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"
touch "$LOG_FILE"

CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

source "$(dirname "$0")/_proot_bind.sh"
    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
        "set -o pipefail; cd /root/agentes/meta_uploader && \
         AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
         python3 fb_to_ig_vigia_720.py 2>&1 | tee -a '${LOG_FILE}'"
    EXIT_CODE=$?

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))

    case "$EXIT_CODE" in
        0)  echo "[CICLO #${CICLO}] OK — crosspost exitoso en ${DURACION}s."
            ;;
        2)  echo "[CICLO #${CICLO}] Sin posts nuevos para crosspostear (${DURACION}s)."
            ;;
        *)  echo "[CICLO #${CICLO}] Error exit=$EXIT_CODE (${DURACION}s)."
            ;;
    esac

    NEXT_EPOCH=$(( T_FIN + INTERVALO ))
    echo "[RELOJ] Ciclo termino: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO}s"

    wait_until "$NEXT_EPOCH"
    printf "\n"
done
