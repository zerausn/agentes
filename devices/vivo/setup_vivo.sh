#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# setup_vivo.sh — Configuración completa para Vivo V2058
# Ejecutar dentro de Termux en el Vivo
# ============================================================
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PREFIX="/data/data/com.termux/files/usr"
PROOT="$PREFIX/bin/proot-distro"
REPO_DIR="$TERMUX_HOME/agentes"

echo "========================================"
echo " SETUP VIVO V2058"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 1. Dependencias Termux
echo ""
echo "=== 1. Dependencias Termux ==="
pkg update -y
pkg upgrade -y
pkg install -y git openssh proot-distro termux-api python3 ffmpeg

# 2. Dependencias Python
echo ""
echo "=== 2. Dependencias Python ==="
pip3 install google-auth-oauthlib google-api-python-client httplib2 requests python-dotenv

# 3. Crear carpetas
echo ""
echo "=== 3. Carpetas de datos ==="
mkdir -p /sdcard/Antigravity/{crudos_pendientes,teasers_pendientes,subidos_a_facebook,videos_subidos_exitosamente,bench}
mkdir -p "$REPO_DIR/youtube_uploader/downloads"

# 4. Configurar SSH
echo ""
echo "=== 4. SSH ==="
mkdir -p "$TERMUX_HOME/.ssh"
chmod 700 "$TERMUX_HOME/.ssh"

# 5. Bootstrap del repo
echo ""
echo "=== 5. Bootstrap ==="
if [ -f "$REPO_DIR/scripts/linux/bootstrap_termux_arm64.sh" ]; then
  bash "$REPO_DIR/scripts/linux/bootstrap_termux_arm64.sh" generic
else
  echo "ERROR: bootstrap no encontrado. Asegúrate de tener el repo en $REPO_DIR"
  exit 1
fi

# 6. Instalar widgets desde staging
echo ""
echo "=== 6. Widgets ==="
STAGING_DIR="/sdcard/Download/codex_termux_widgets"
if [ -d "$STAGING_DIR" ]; then
  bash "$REPO_DIR/agentes/termux_widgets/install_shortcuts.sh"
else
  echo "AVISO: $STAGING_DIR no existe. Copia los widgets manualmente."
fi

# 7. Perfil Vivo
echo ""
echo "=== 7. Perfil Vivo ==="
cat > "$TERMUX_HOME/.agentes_termux_env" <<'EOF'
export AGENTES_FFMPEG_PRESET=medium
export AGENTES_FFMPEG_CRF=20
export AGENTES_FFMPEG_AUDIO_BITRATE=160k
export AGENTES_SYNC_SEARCH_LIMIT=5000
export AGENTES_SYNC_SLEEP_SECONDS=10
export AGENTES_YTDLP_CONCURRENT_FRAGMENTS=1
EOF

echo ""
echo "========================================"
echo " SETUP VIVO COMPLETADO"
echo "========================================"
echo ""
echo "Próximos pasos:"
echo "  1. Copiar credenciales: scp -P 38022 credentials/* u0_a289@127.0.0.1:~/agentes/youtube_uploader/credentials/"
echo "  2. Copiar .env: scp -P 38022 .env u0_a289@127.0.0.1:~/agentes/meta_uploader/.env"
echo "  3. Copiar datos: adb push crudos_pendientes/ /sdcard/Antigravity/crudos_pendientes/"
echo "  4. Verificar: ssh -p 38022 u0_a289@127.0.0.1 whoami"
