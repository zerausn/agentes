#!/bin/bash
# driver_captura_4k.sh — lógica del capturador 4K por navegador (corre DENTRO del proot Debian)
# Clon funcional de bajar_youtube_sin_limite_termux.sh usando la estrategia MITM-UMP:
#   Firefox (Xvfb) reproduce con su sesión confiable → mitmproxy captura el transporte
#   UMP → extract_4k.py reensambla cada epoch (video/calidad) como .mp4 AV1/VP9 4K.
#
# Invocado por: bajar_captura_4k_termux.sh (Termux) vía proot-distro login.

set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="/root"

CAP_BASE="/sdcard/Antigravity/captura_4k"
SEG_DIR="$CAP_BASE/segments"
OUT_DIR="$CAP_BASE/salidas"
LOG_DIR="$CAP_BASE/logs"
WIDGET_LOG="/sdcard/Antigravity/widget_logs/6_BAJAR_YOUTUBE_4K_CAPTURA.log"
DEST_DIR="/sdcard/Antigravity/crudos_4k_captura"
SRC_DIR="/root/agentes/scripts/linux/captura_4k_proot"
MITM_VENV="/root/venv-mitm"
PROFILE="/root/captura_firefox_profile"
SETUP_MARK="$CAP_BASE/.setup_done"

mkdir -p "$CAP_BASE" "$SEG_DIR" "$OUT_DIR" "$LOG_DIR" "$DEST_DIR"
exec > >(tee -a "$WIDGET_LOG") 2>&1

echo "============================================================"
echo " 6_BAJAR_YOUTUBE_4K_CAPTURA (driver proot)"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# ─── Setup idempotente (1ª ejecución) ─────────────────────────────
if [ ! -f "$SETUP_MARK" ] || [ ! -x "$MITM_VENV/bin/mitmdump" ]; then
    echo "[SETUP] Instalando dependencias (solo la primera vez)..."
    bash "$SRC_DIR/setup_captura_4k.sh"
    touch "$SETUP_MARK"
fi

FIREFOX="$(command -v firefox || true)"
if [ -z "$FIREFOX" ] || [ ! -x "$MITM_VENV/bin/mitmdump" ]; then
    echo "[ERROR] Firefox o mitmproxy no disponibles. Revisa $LOG_DIR/setup.log"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# ─── Mitmproxy ─────────────────────────────────────────────────────
start_mitm() {
    pkill -f "venv-mitm/bin/mitmdump" 2>/dev/null || true
    sleep 1
    export CAPTURE_SEG="$SEG_DIR" CAPTURE_LOGS="$LOG_DIR" PLAYBACK_RATE=0.5
    nohup "$MITM_VENV/bin/mitmdump" -q -s "$SRC_DIR/yt_capture_4k.py" \
        --listen-host 127.0.0.1 --listen-port 8080 >> "$LOG_DIR/mitmdump.log" 2>&1 &
    echo $! > "$LOG_DIR/mitmdump.pid"
    sleep 3
    if ! ss -tln 2>/dev/null | grep -q ':8080'; then
        echo "[ERROR] mitmdump no quedó escuchando en 8080. Log: $LOG_DIR/mitmdump.log"
        return 1
    fi
    echo "[MITM] mitmdump activo (PID $(cat "$LOG_DIR/mitmdump.pid"))"
}

stop_mitm() {
    pkill -f "venv-mitm/bin/mitmdump" 2>/dev/null || true
}

# ─── Captura de una URL (video o playlist) ─────────────────────────
run_capture() {
    local URL="$1"
    local LABEL="$2"
    local last_seen=0 last_sz=0 sz media_sz=0 deadline

    echo ""
    echo "[CAPTURA] $LABEL: $URL"
    echo "[CAPTURA] Limpiando segments previos..."
    rm -rf "$SEG_DIR"/* 2>/dev/null || true
    : > "$LOG_DIR/captura.csv"

    export DISPLAY=:99
    Xvfb :99 -screen 0 1280x720x24 > "$LOG_DIR/xvfb.log" 2>&1 &
    local XVFB_PID=$!
    sleep 2

    "$FIREFOX" --no-remote --profile "$PROFILE" "$URL" > "$LOG_DIR/firefox.log" 2>&1 &
    local FF_PID=$!
    echo "[CAPTURA] Firefox PID $FF_PID reproduciendo en Xvfb :99..."

    deadline=$(( $(date +%s) + 21600 ))   # tope de 6h por corrida
    while kill -0 "$FF_PID" 2>/dev/null && [ "$(date +%s)" -lt "$deadline" ]; do
        sleep 20
        sz="$(du -sb "$SEG_DIR" 2>/dev/null | cut -f1)"
        [ -z "$sz" ] && sz=0
        if [ "$sz" -gt "$last_sz" ]; then
            last_seen=$(date +%s)
        fi
        last_sz=$sz
        if [ "$media_sz" = 0 ] && [ "$sz" -gt 0 ]; then
            media_sz=1
        fi
        if [ "$media_sz" = 1 ] && [ $(( $(date +%s) - last_seen )) -gt 150 ]; then
            echo "[CAPTURA] 150s sin datos media nuevos → fin de reproducción ($(du -sb "$SEG_DIR" | cut -f1) bytes)."
            break
        fi
        echo "[CAPTURA] ...capturando $(du -sb "$SEG_DIR" | cut -f1) bytes (epochs: $(ls "$SEG_DIR" 2>/dev/null | grep -c epoch || true))"
    done

    kill -TERM "$FF_PID" 2>/dev/null || true
    sleep 3
    kill -9 "$FF_PID" 2>/dev/null || true
    kill "$XVFB_PID" 2>/dev/null || true
    rm -f "$PROFILE/.parentlock" 2>/dev/null || true
    echo "[CAPTURA] Reproducción terminada."
}

# ─── Extracción ────────────────────────────────────────────────────
do_extract() {
    echo ""
    echo "[EXTRACT] Reensamblando epochs..."
    python3 "$SRC_DIR/extract_4k.py" "$SEG_DIR" "$OUT_DIR" "$DEST_DIR"
    echo "[EXTRACT] Listo. Salidas en $OUT_DIR/ y copia en $DEST_DIR/"
    echo "[EXTRACT] Manifest: $OUT_DIR/manifest.csv"
}

# ─── Menú ──────────────────────────────────────────────────────────
start_mitm || true

while true; do
    echo ""
    echo "────────────────────────────────────────────"
    echo "  1) Descargar 1 video  (pega la URL)"
    echo "  2) Descargar playlist (pega la URL de la playlist)"
    echo "  3) Estado / salidas"
    echo "  4) Re-extraer los segments actuales"
    echo "  5) Salir"
    echo "────────────────────────────────────────────"
    read -r -p "Opción: " op
    case "$op" in
        1)
            read -r -p "URL del video: " URL
            if [ -n "$URL" ]; then
                run_capture "$URL" "video"
                do_extract
            fi
            ;;
        2)
            read -r -p "URL de la playlist: " URL
            if [ -n "$URL" ]; then
                run_capture "$URL" "playlist"
                do_extract
            fi
            ;;
        3)
            echo "─ salidas ─"
            ls -la "$OUT_DIR" 2>/dev/null || true
            echo "─ manifest ─"
            cat "$OUT_DIR/manifest.csv" 2>/dev/null || echo "(sin manifest)"
            echo "─ segments (epochs actuales) ─"
            ls "$SEG_DIR" 2>/dev/null || true
            echo "─ total capturado ─"
            du -sh "$SEG_DIR" 2>/dev/null || true
            ;;
        4)
            do_extract
            ;;
        5)
            stop_mitm
            echo "Adiós."
            exit 0
            ;;
        *)
            echo "Opción inválida."
            ;;
    esac
done