#!/data/data/com.termux/files/usr/bin/bash
# 4_VIGIA_FACEBOOK720 — Evacúa videos a Facebook cada 12 min (S24 Ultra)
# Widget Termux: ~/.shortcuts/4_VIGIA_FACEBOOK720.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
PR_ROOT="/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
EVACUADOR_PROOT="$PR_ROOT/root/agentes/meta_uploader/subir_fb_evacuador_720.py"
LOG_FILE="$PR_ROOT/root/agentes/meta_uploader/fb_evacuador.log"
LOG_DIR="/sdcard/Antigravity/widget_logs"
SESSION_LOG="$LOG_DIR/4_VIGIA_FACEBOOK720.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

echo "=============================================="
echo "  4_VIGIA_FACEBOOK720 — Evacuador cada 12min"
echo "=============================================="
echo ""

# Verificar proot-distro
if [ ! -x "$PROOT" ]; then
    echo "[ERROR] proot-distro no encontrado en $PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Verificar script Python dentro del proot
if [ ! -f "$EVACUADOR_PROOT" ]; then
    echo "[ERROR] No existe subir_fb_evacuador_720.py en el proot de Debian."
    echo "        Ruta buscada: $EVACUADOR_PROOT"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# Cargar perfil de entorno si existe
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

echo "Iniciando subir_fb_evacuador_720.py dentro de Debian..."
echo "Log: $LOG_FILE"
echo ""

# Crear el log si no existe para que el seguimiento funcione
touch "$LOG_FILE"

# Lanzar en Debian: corre el evacuador con pausa de 720s entre videos
"$PROOT" login debian -- /bin/bash -lc \
    "cd /root/agentes/meta_uploader && AGENTES_STORAGE_ROOT=/sdcard/Antigravity python3 subir_fb_evacuador_720.py 2>&1 | tee -a '$LOG_FILE'"

echo ""
echo "=============================================="
echo "  Facebook evacuador 720 finalizado."
echo "  Log completo en: $LOG_FILE"
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
