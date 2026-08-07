#!/data/data/com.termux/files/usr/bin/bash
# Detiene vigias TikTok lanzados en segundo plano por Termux Widget.

set -euo pipefail

export PREFIX="/data/data/com.termux/files/usr"
export HOME="/data/data/com.termux/files/home"
export PATH="/system/bin:/system/xbin:${PREFIX}/bin"
export TMPDIR="${PREFIX}/tmp"

TERMUX_HOME="$HOME"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/PARAR_TIKTOK.log"
STATE_DIR="/sdcard/Antigravity/.state"
ADB_SERIAL="${TIKTOK_ADB_SERIAL:-127.0.0.1:5555}"

mkdir -p "$LOG_DIR" "$TMPDIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo ""
echo "=============================================="
echo "  PARAR_TIKTOK - detener vigias y automatizador"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

PID_FILE="$TMPDIR/parar_tiktok_pids.$$"
PID_LIST="$TMPDIR/parar_tiktok_pid_list.$$"
: > "$PID_FILE"

add_matches() {
    local pattern="$1"
    local label="$2"
    local matches=""
    local pid=""

    if command -v pgrep >/dev/null 2>&1; then
        matches="$(pgrep -f "$pattern" 2>/dev/null || true)"
    else
        matches="$(ps -ef 2>/dev/null | awk -v pat="$pattern" '$0 ~ pat {print $2}' || true)"
    fi
    for pid in $matches; do
        case "$pid" in
            ''|*[!0-9]*) continue ;;
        esac
        if [ "$pid" = "$$" ] || [ "$pid" = "${PPID:-}" ]; then
            continue
        fi
        printf '%s %s\n' "$pid" "$label" >> "$PID_FILE"
    done
}

add_matches "tiktok_evacuador_720.py" "python_tiktok_evacuador"
add_matches "vigia_tiktok720_termux.sh" "vigia_720"
add_matches "vigia_tiktok_shirabyoshi_termux.sh" "vigia_shirabyoshi"
add_matches "vigia_tiktok_shirabyoshi_180_termux.sh" "vigia_shirabyoshi_180"
add_matches "vigia_tiktok_ghawazee_termux.sh" "vigia_ghawazee"
add_matches "vigia_tiktok_ghawazee_180_termux.sh" "vigia_ghawazee_180"
add_matches "WATCHDOG_TIKTOK.sh" "watchdog_tiktok"
add_matches "tail -n 50 -f /sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK" "tail_widget_tiktok"

sort -n "$PID_FILE" | awk '!seen[$1]++ {print $1}' > "$PID_LIST"

if [ ! -s "$PID_LIST" ]; then
    echo "[STOP] No encontre procesos TikTok de widgets/vigias corriendo."
else
    echo "[STOP] Procesos detectados:"
    while read -r pid; do
        ps -p "$pid" -o pid= -o args= 2>/dev/null || echo "  $pid"
    done < "$PID_LIST"

    echo "[STOP] Enviando TERM..."
    while read -r pid; do
        kill "$pid" 2>/dev/null || true
    done < "$PID_LIST"

    sleep 2

    echo "[STOP] Forzando KILL solo a remanentes vivos..."
    while read -r pid; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done < "$PID_LIST"
fi

echo "[LOCK] Limpiando locks TikTok locales..."
rm -f "$TERMUX_HOME"/vigia_tiktok*.lock "$TERMUX_HOME/vigia_tiktok_global.lock" 2>/dev/null || true
rm -f "$STATE_DIR/tiktok_evacuador.lock" 2>/dev/null || true

if command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock 2>/dev/null || true
fi

if command -v adb >/dev/null 2>&1; then
    adb connect "$ADB_SERIAL" >/dev/null 2>&1 || true
    adb -s "$ADB_SERIAL" shell 'am kill com.zhiliaoapp.musically' >/dev/null 2>&1 || true
    echo "[ADB] TikTok liberado de memoria si ADB estaba disponible."
fi

rm -f "$PID_FILE" "$PID_LIST" 2>/dev/null || true

echo "=============================================="
echo "  TikTok detenido. Ya puedes iniciar otro widget."
echo "=============================================="

if [ "${PARAR_TIKTOK_NO_PROMPT:-0}" != "1" ]; then
    read -r -p "Enter para cerrar..." || true
fi
