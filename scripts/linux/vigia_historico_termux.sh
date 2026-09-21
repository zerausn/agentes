#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# VIGIA_HISTORICO — Evacuador del Backlog (S24 Termux)
# Sube 1 post faltante del historial a Instagram cada 1800 segundos (30m).
# Lee desde missing_crossposts_report.json
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
SCRIPT_PROOT="$PR_ROOT/root/agentes/meta_uploader/evacuador_historico.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/evacuador_historico.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/VIGIA_HISTORICO.log"

INTERVALO=1800
CHECK_INTERVAL=15

wait_until() {
    local target_epoch=$1
    local objetivo
    objetivo=$(date -d "@${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || date -r "${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || echo "??:??:??")
    echo "[HISTORICO ESPERA] Proxima ejecucion a las: ${objetivo}"

    while true; do
        local now diff
        now=$(date +%s)
        diff=$(( target_epoch - now ))
        if [ "$diff" -le 0 ]; then
            echo "[HISTORICO RELOJ] Hora alcanzada: $(date '+%H:%M:%S') — arrancando ciclo."
            return 0
        fi
        printf "\r[HISTORICO RELOJ] %3ds restantes (objetivo %s)..." "$diff" "$objetivo"
        sleep "$CHECK_INTERVAL"
    done
}

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  VIGIA HISTORICO — Evacuador FB→IG"
echo "  Intervalo: ${INTERVALO}s (30 mins) | Check: ${CHECK_INTERVAL}s"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para habilitar wake-lock."
fi

if [ ! -f "$SCRIPT_PROOT" ]; then
    echo "[ERROR] No existe evacuador_historico.py en: $SCRIPT_PROOT"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"
touch "$LOG_FILE"

source "$(dirname "$0")/_proot_bind.sh"

CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO HISTORICO #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
        "set -o pipefail; \
         export META_FB_PAGE_ID_TEASER='${META_FB_PAGE_ID_TEASER:-1347014641828725}'; \
         export META_FB_PAGE_TOKEN_TEASER='${META_FB_PAGE_TOKEN_TEASER}'; \
         cd /root/agentes/meta_uploader && \
         python3 evacuador_historico.py 2>&1 | tee -a '${LOG_FILE}'"
    EXIT_CODE=$?

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))

    case "$EXIT_CODE" in
        0) echo "[HISTORICO CICLO #${CICLO}] OK en ${DURACION}s." ;;
        *)  echo "[HISTORICO CICLO #${CICLO}] Fin con exit=$EXIT_CODE en ${DURACION}s." ;;
    esac

    T_NEXT=$((T_FIN + INTERVALO))
    echo "[HISTORICO RELOJ] Ciclo termino: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO}s"
    wait_until "$T_NEXT"
done
