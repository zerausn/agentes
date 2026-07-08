#!/data/data/com.termux/files/usr/bin/bash
# 3_SUBIR_TEASERS_YT — Sube teasers a YouTube desde Debian (S24 Ultra)
# Widget Termux: ~/.shortcuts/3_SUBIR_TEASERS_YT.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
UPLOADER="$TERMUX_HOME/agentes/youtube_uploader/teaser_uploader.py"
LOG_FILE="$TERMUX_HOME/agentes/youtube_uploader/teaser_uploader.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/3_SUBIR_TEASERS_YT.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  3_SUBIR_TEASERS_YT — Antigravity S24"
echo "=============================================="
echo ""

# Verificar proot-distro
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado en $PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Verificar script Python
if [ ! -f "$UPLOADER" ]; then
    echo "[ERROR] No existe $UPLOADER"
    echo "        Corre primero 0_RENOVAR_REPO para actualizar el repo."
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Cargar perfil de entorno si existe
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

echo "Iniciando teaser_uploader.py dentro de Debian..."
echo "Log: $LOG_FILE"
echo ""

# Crear el log si no existe para que tail funcione
touch "$LOG_FILE"

# Lanzar en Debian: corre el uploader y muestra la salida en tiempo real
source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
    "cd /root/agentes/youtube_uploader && AGENTES_STORAGE_ROOT=/sdcard/Antigravity python3 teaser_uploader.py 2>&1 | tee -a '$LOG_FILE'"

echo ""
echo "=============================================="
echo "  Teaser uploader finalizado."
echo "  Log completo en: $LOG_FILE"
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
