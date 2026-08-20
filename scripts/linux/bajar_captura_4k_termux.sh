#!/data/data/com.termux/files/usr/bin/bash
# bajar_captura_4k_termux.sh
# Script maestro del capturador 4K por navegador (Firefox headless/Xvfb + mitmproxy)
# Clon de bajar_youtube_sin_limite_termux.sh con la estrategia de captura MITM-UMP.
# Lanzado por: ~/.shortcuts/6_BAJAR_YOUTUBE_4K_CAPTURA.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
if [ -d "/data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs" ]; then
    PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs"
else
    PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian"
fi
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
SCRIPT_PROOT="$PR_ROOT/root/agentes/scripts/linux/captura_4k_proot/driver_captura_4k.sh"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/6_BAJAR_YOUTUBE_4K_CAPTURA.log"
LOCK_DIR="$TERMUX_HOME/.run/6_BAJAR_YOUTUBE_4K_CAPTURA.lock"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

mkdir -p "$TERMUX_HOME/.run"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "[ERROR] Ya hay una ejecución activa de 6_BAJAR_YOUTUBE_4K_CAPTURA (PID $old_pid)."
        echo "        Cierra esa sesión antes de lanzar otra."
        read -r -p "Enter para cerrar..."
        exit 1
    fi

    echo "[WARN] Lock anterior sin proceso activo; limpiando."
    rm -rf "$LOCK_DIR"
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "[ERROR] No se pudo crear el lock de ejecución."
        read -r -p "Enter para cerrar..."
        exit 1
    fi
fi
printf "%s\n" "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

echo "============================================================"
echo "  6_BAJAR_YOUTUBE_4K_CAPTURA — Capturador 4K por navegador"
echo "  (Firefox + mitmproxy · transporte UMP · sin cookies)"
echo "============================================================"
echo ""

# Verificar proot-distro
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado en $PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Verificar driver dentro del proot
if [ ! -f "$SCRIPT_PROOT" ]; then
    echo "[ERROR] No existe driver_captura_4k.sh en el proot de Debian."
    echo "        Ruta buscada: $SCRIPT_PROOT"
    echo "        Corre primero 0_RENOVAR_REPO para actualizar el repo."
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Cargar variables de entorno si existen (incluye AGENTES_DEVICE_NAME)
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

# Crear carpeta destino de crudos capturados si no existe
mkdir -p /sdcard/Antigravity/crudos_4k_captura 2>/dev/null || true

echo "Dispositivo : ${AGENTES_DEVICE_NAME:-$(hostname)}"
echo "Destino     : /sdcard/Antigravity/crudos_4k_captura/"
echo ""
echo "Lanzando capturador dentro de Debian..."
echo ""

# Construir lista de variables de entorno para pasar al proot explícitamente.
PROOT_ENV_ARGS=()
if [ -n "${AGENTES_DEVICE_NAME:-}" ]; then
    PROOT_ENV_ARGS+=(--env "AGENTES_DEVICE_NAME=${AGENTES_DEVICE_NAME}")
fi
if [ -n "${AGENTES_FFMPEG_PRESET:-}" ]; then
    PROOT_ENV_ARGS+=(--env "AGENTES_FFMPEG_PRESET=${AGENTES_FFMPEG_PRESET}")
fi
if [ -n "${AGENTES_FFMPEG_CRF:-}" ]; then
    PROOT_ENV_ARGS+=(--env "AGENTES_FFMPEG_CRF=${AGENTES_FFMPEG_CRF}")
fi
if [ -n "${AGENTES_FFMPEG_AUDIO_BITRATE:-}" ]; then
    PROOT_ENV_ARGS+=(--env "AGENTES_FFMPEG_AUDIO_BITRATE=${AGENTES_FFMPEG_AUDIO_BITRATE}")
fi

# Lanzar en modo interactivo dentro del proot (sin -lc para que el stdin funcione)
source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" "${BIND_ARGS[@]}" "${PROOT_ENV_ARGS[@]}" -- /bin/bash /root/agentes/scripts/linux/captura_4k_proot/driver_captura_4k.sh

echo ""
echo "============================================================"
echo "  Capturador finalizado."
echo "  Log en: $SESSION_LOG"
echo "============================================================"
echo ""
read -r -p "Presiona Enter para cerrar..."