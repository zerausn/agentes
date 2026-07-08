#!/data/data/com.termux/files/usr/bin/bash
# 4_VIGIA_FACEBOOK — Evacúa videos a Facebook desde Debian (S24 Ultra)
# Widget Termux: ~/.shortcuts/4_VIGIA_FACEBOOK.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
EVACUADOR="$TERMUX_HOME/agentes/meta_uploader/subir_fb_evacuador.py"
LOG_FILE="$TERMUX_HOME/agentes/meta_uploader/fb_evacuador.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/4_VIGIA_FACEBOOK.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  4_VIGIA_FACEBOOK — Antigravity S24"
echo "=============================================="
echo ""

# Verificar proot-distro
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado en $PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Verificar script Python
if [ ! -f "$EVACUADOR" ]; then
    echo "[ERROR] No existe $EVACUADOR"
    echo "        Corre primero 0_RENOVAR_REPO para actualizar el repo."
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Cargar perfil de entorno si existe
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

echo "Iniciando subir_fb_evacuador.py dentro de Debian..."
echo "Log: $LOG_FILE"
echo ""

# Crear el log si no existe para que el seguimiento funcione
touch "$LOG_FILE"

# Lanzar en Debian: corre el evacuador y muestra la salida en tiempo real
source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc \
    "cd /root/agentes/meta_uploader && AGENTES_STORAGE_ROOT=/sdcard/Antigravity python3 subir_fb_evacuador.py 2>&1 | tee -a '$LOG_FILE'"

echo ""
echo "=============================================="
echo "  Facebook evacuador finalizado."
echo "  Log completo en: $LOG_FILE"
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
