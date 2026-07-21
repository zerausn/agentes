#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 6_SUBIR_TIKTOK720_S24 — Evacuador TikTok app (S24 local)
#
# Sube 1 video cada 720s desde:
#   /sdcard/Antigravity/subidos a facebbok
#
# Sin proot-distro ni ADB. El evacuador usa UI_BACKEND=direct
# por defecto: ejecuta input tap/am start directamente en el shell.
# ================================================================

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
export PREFIX="/data/data/com.termux/files/usr"
export HOME="/data/data/com.termux/files/home"
export TMPDIR="$PREFIX/tmp"

TERMUX_HOME="/data/data/com.termux/files/home"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
EVACUADOR="$TERMUX_HOME/agentes/tiktok_uploader/tiktok_evacuador_720.py"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/6_SUBIR_TIKTOK720_S24.log"
SOURCE_DIR="/sdcard/Antigravity/subidos a facebbok"

INTERVALO=720
CHECK_INTERVAL=15

wait_until() {
    local target_epoch=$1
    local objetivo
    objetivo=$(date -d "@${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || date -r "${target_epoch}" '+%H:%M:%S' 2>/dev/null \
               || echo "??:??:??")
    echo "[ESPERA] Proxima revision a las: ${objetivo}"

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

count_pending() {
    "$PREFIX/bin/python3" -c "
from pathlib import Path
p = Path('$SOURCE_DIR')
if p.exists():
    print(sum(1 for f in p.iterdir() if f.is_file() and f.suffix.lower() in {'.mp4','.mov','.mkv'}))
else:
    print(0)
"
}

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  6_SUBIR_TIKTOK720_S24 — TikTok por app"
echo "  Intervalo: ${INTERVALO}s | Check: ${CHECK_INTERVAL}s"
echo "  Fuente: ${SOURCE_DIR}"
echo "  UI_BACKEND: direct (shell local)"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para wake-lock."
fi

trap 'printf "\n"; echo "[SALIDA] $(date "+%H:%M:%S") — liberando wake-lock"; termux-wake-unlock 2>/dev/null || true; exit' INT TERM EXIT

if [ ! -f "$EVACUADOR" ]; then
    echo "[ERROR] No existe tiktok_evacuador_720.py"
    echo "        Ruta: $EVACUADOR"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"

# UI_BACKEND=direct por defecto: el evacuador usa el shell local
# (input tap, am start via /system/bin/) sin pasar por ADB

CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    "$PREFIX/bin/python3" "$EVACUADOR" \
        --open-next 2>&1 | tee -a "$LOG_DIR/tiktok_evacuador_s24.log"
    EXIT_CODE=$?

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))
    PENDIENTES=$(count_pending)

    case "$EXIT_CODE" in
        0) echo "[CICLO #${CICLO}] OK — publicado/movido en ${DURACION}s. | Pendientes: ${PENDIENTES}" ;;
        2) echo "[CICLO #${CICLO}] Sin videos (${DURACION}s). | Pendientes: 0" ;;
        3) echo "[CICLO #${CICLO}] Otra instancia corriendo. | Pendientes: ${PENDIENTES}" ;;
        *) echo "[CICLO #${CICLO}] Error exit=$EXIT_CODE (${DURACION}s). | Pendientes: ${PENDIENTES}" ;;
    esac

    NEXT_EPOCH=$(( T_FIN + INTERVALO ))
    echo "[RELOJ] Ciclo termino: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO}s"
    wait_until "$NEXT_EPOCH"
    printf "\n"
done
