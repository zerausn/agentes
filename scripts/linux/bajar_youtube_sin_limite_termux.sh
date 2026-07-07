#!/data/data/com.termux/files/usr/bin/bash
# bajar_youtube_sin_limite_termux.sh
# Script maestro del descargador SIN LÍMITE DE FECHA de YouTube
# Lanzado por: ~/.shortcuts/5_BAJAR_YOUTUBE_SIN_LIMITE.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
SCRIPT_PROOT="$PR_ROOT/root/agentes/youtube_uploader/yt_downloader_lotes_sin_limite.py"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/5_BAJAR_YOUTUBE_SIN_LIMITE.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "============================================================"
echo "  5_BAJAR_YOUTUBE_SIN_LIMITE — Descargador por Lotes"
echo "  (Todos los crudos públicos · Sin límite de fecha)"
echo "============================================================"
echo ""

# Verificar proot-distro
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado en $PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Verificar script Python dentro del proot
if [ ! -f "$SCRIPT_PROOT" ]; then
    echo "[ERROR] No existe yt_downloader_lotes_sin_limite.py en el proot de Debian."
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

# Crear carpeta destino de crudos si no existe
mkdir -p /sdcard/Antigravity/crudos 2>/dev/null || true

echo "Dispositivo : ${AGENTES_DEVICE_NAME:-$(hostname)}"
echo "Destino     : /sdcard/Antigravity/crudos/"
echo ""
echo "Lanzando descargador dentro de Debian..."
echo ""

# Lanzar en modo interactivo dentro del proot (sin -lc para que el stdin funcione)
"$PROOT" login debian -- /usr/bin/python3 /root/agentes/youtube_uploader/yt_downloader_lotes_sin_limite.py

echo ""
echo "============================================================"
echo "  Descargador finalizado."
echo "  Log en: $SESSION_LOG"
echo "============================================================"
echo ""
read -r -p "Presiona Enter para cerrar..."
