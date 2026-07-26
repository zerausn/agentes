#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# 6_SUBIR_TIKTOK720 — Evacuador TikTok por app (sin API)
#
# Sube 1 video cada 720s desde:
#   /sdcard/Antigravity/subidos a facebbok
#
# Corre Python directo desde Termux (sin proot-distro).
# Usa ADB local (127.0.0.1:5555) para UI automation.
# ================================================================

export PREFIX="/data/data/com.termux/files/usr"
export HOME="/data/data/com.termux/files/home"
export PATH="/system/bin:/system/xbin:${PREFIX}/bin"
export TMPDIR="${PREFIX}/tmp"

TERMUX_HOME="$HOME"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
EVACUADOR="$TERMUX_HOME/agentes/tiktok_uploader/tiktok_evacuador_720.py"
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

ensure_adb_local() {
    if ! command -v adb >/dev/null 2>&1; then
        echo "[ERROR] Falta android-tools en Termux. Instala: pkg install android-tools"
        return 1
    fi
    adb connect 127.0.0.1:5555 >/dev/null 2>&1 || true
    if adb devices | awk '$1 == "127.0.0.1:5555" && $2 == "device" {found=1} END {exit(found ? 0 : 1)}'; then
        echo "[ADB] Local OK: 127.0.0.1:5555"
        return 0
    fi
    echo "[ADB] Reconectando..."
    adb kill-server >/dev/null 2>&1 || true
    sleep 1
    adb start-server >/dev/null 2>&1 || true
    sleep 2
    adb connect 127.0.0.1:5555 2>&1
    sleep 1
    if adb devices | awk '$1 == "127.0.0.1:5555" && $2 == "device" {found=1} END {exit(found ? 0 : 1)}'; then
        echo "[ADB] Local OK tras reconexion."
        return 0
    fi
    echo "[ERROR] ADB local no disponible. Revisa 'adb tcpip 5555' en Note9."
    return 1
}

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  6_SUBIR_TIKTOK720 — TikTok por app (Termux directo)"
echo "  Intervalo: ${INTERVALO}s | Check: ${CHECK_INTERVAL}s"
echo "  Fuente: ${SOURCE_DIR}"
echo "  ADB: local 127.0.0.1:5555"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[WAKE-LOCK] Activado."
else
    echo "[WAKE-LOCK] AVISO: instala termux-api para habilitar wake-lock."
fi

trap 'printf "\n"; echo "[SALIDA] $(date "+%H:%M:%S") — liberando wake-lock"; termux-wake-unlock 2>/dev/null || true; exit' INT TERM EXIT

if [ ! -f "$EVACUADOR" ]; then
    echo "[ERROR] No existe tiktok_evacuador_720.py"
    echo "        Ruta: $EVACUADOR"
    echo "        Copialo desde /sdcard:"
    echo "        cp /sdcard/Antigravity/agentes/... \$TERMUX_HOME/agentes/tiktok_uploader/"
    exit 1
fi

[ -f "$ENV_FILE" ] && . "$ENV_FILE"

ensure_adb_local || exit 1

echo "[MODO] Sin proot-distro. Python directo desde Termux + ADB local."

adb_wake() {
    adb connect 127.0.0.1:5555 >/dev/null 2>&1 || true
    if adb devices | awk '$1 == "127.0.0.1:5555" && $2 == "device" {found=1} END {exit(found ? 0 : 1)}'; then
        return 0
    fi
    echo "[ADB-WAKE] Caido. Reconectando..."
    adb kill-server >/dev/null 2>&1 || true
    sleep 1
    adb start-server >/dev/null 2>&1 || true
    sleep 2
    adb connect 127.0.0.1:5555 >/dev/null 2>&1
    sleep 1
    if adb devices | awk '$1 == "127.0.0.1:5555" && $2 == "device" {found=1} END {exit(found ? 0 : 1)}'; then
        return 0
    fi
    echo "[ADB-WAKE] AVISO: ADB no disponible. Intentando con accessibility fallback."
    return 1
}

CICLO=0

while true; do
    CICLO=$((CICLO + 1))
    T_INICIO=$(date +%s)

    printf "\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CICLO #${CICLO} — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if adb_wake; then
        UI_BACKEND_VAL="adb"
    else
        UI_BACKEND_VAL="accessibility"
        echo "[CICLO] Fallback a accessibility para inputs."
    fi

    PATH=$PATH TMPDIR=$TMPDIR \
    AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
    TIKTOK_UI_BACKEND=$UI_BACKEND_VAL \
    TIKTOK_ADB_SERIAL=127.0.0.1:5555 \
    TIKTOK_SHARE_METHOD=intent \
    TIKTOK_PUBLISH_MODE=direct \
    "$PREFIX/bin/python3" "$EVACUADOR" \
        --open-next 2>&1 | tee -a "$LOG_DIR/tiktok_evacuador.log"
    EXIT_CODE=${PIPESTATUS[0]}

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
