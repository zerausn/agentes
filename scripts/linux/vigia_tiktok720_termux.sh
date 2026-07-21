#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 6_SUBIR_TIKTOK720 — Evacuador TikTok por app (sin API aprobada)
#
# Sube/abre 1 video cada 720 segundos desde:
#   /sdcard/Antigravity/subidos a facebbok
#
# Metodo: comparte el video hacia la app TikTok y automatiza la UI
# con adb local + input tap. Al terminar la secuencia, mueve el archivo
# a /sdcard/Antigravity/subidos a tiktok.
# ================================================================

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
export PREFIX="/data/data/com.termux/files/usr"
export HOME="/data/data/com.termux/files/home"
export TMPDIR="$PREFIX/tmp"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
EVACUADOR_PROOT="$PR_ROOT/root/agentes/tiktok_uploader/tiktok_evacuador_720.py"
LOG_FILE="$PR_ROOT/root/agentes/tiktok_uploader/tiktok_evacuador.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/6_SUBIR_TIKTOK720.log"
SOURCE_DIR="/sdcard/Antigravity/subidos a facebbok"
ADB_SERIAL="127.0.0.1:5555"

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
    find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \) 2>/dev/null | wc -l
}

ensure_local_adb() {
    mkdir -p "$TMPDIR"

    if ! command -v adb >/dev/null 2>&1; then
        echo "[ERROR] Falta android-tools en Termux. Instala: pkg install android-tools"
        return 1
    fi

    adb connect "$ADB_SERIAL" >/dev/null 2>&1 || true

    if adb devices | awk -v serial="$ADB_SERIAL" '$1 == serial && $2 == "device" {found=1} END {exit(found ? 0 : 1)}'; then
        echo "[ADB] Local autorizado: $ADB_SERIAL"
        return 0
    fi

    echo "[ERROR] ADB local no autorizado: $ADB_SERIAL"
    echo "        Activa 'adb tcpip 5555' y acepta la huella RSA en el Note9."
    return 1
}

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  6_SUBIR_TIKTOK720 — TikTok por app"
echo "  Intervalo: ${INTERVALO}s | Check: ${CHECK_INTERVAL}s"
echo "  Fuente: ${SOURCE_DIR}"
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

if [ ! -f "$EVACUADOR_PROOT" ]; then
    echo "[ERROR] No existe tiktok_evacuador_720.py"
    echo "        Ruta: $EVACUADOR_PROOT"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"
touch "$LOG_FILE" 2>/dev/null || true

source "$(dirname "$0")/_proot_bind.sh"

ensure_local_adb || exit 1

CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
        "set -o pipefail; cd /root/agentes/tiktok_uploader && \
         AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
         TIKTOK_UI_BACKEND=adb \
         TIKTOK_ADB_SERIAL='${ADB_SERIAL}' \
         TIKTOK_PUBLISH_MODE='${TIKTOK_PUBLISH_MODE:-direct}' \
         python3 tiktok_evacuador_720.py --open-next 2>&1 | tee -a '${LOG_FILE}'"
    EXIT_CODE=$?

    T_FIN=$(date +%s)
    DURACION=$((T_FIN - T_INICIO))
    PENDIENTES=$(count_pending)

    case "$EXIT_CODE" in
        0) echo "[CICLO #${CICLO}] OK — TikTok publicado/movido en ${DURACION}s. | Pendientes: ${PENDIENTES}" ;;
        2) echo "[CICLO #${CICLO}] Sin videos pendientes (${DURACION}s). | Pendientes: 0" ;;
        3) echo "[CICLO #${CICLO}] Otra instancia esta corriendo. | Pendientes: ${PENDIENTES}" ;;
        *) echo "[CICLO #${CICLO}] Error exit=$EXIT_CODE (${DURACION}s). Archivo queda en cola. | Pendientes: ${PENDIENTES}" ;;
    esac

    NEXT_EPOCH=$(( T_FIN + INTERVALO ))
    echo "[RELOJ] Ciclo termino: $(date '+%H:%M:%S') | Siguiente en ${INTERVALO}s"
    wait_until "$NEXT_EPOCH"
    printf "\n"
done
