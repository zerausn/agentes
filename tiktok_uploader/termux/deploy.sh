#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# deploy.sh - Script para copiar archivos TikTok desde /sdcard al home de Termux
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
HOME_DIR="/data/data/com.termux/files/home"
SDCARD_TIKTOK="/sdcard/Antigravity/agentes/tiktok_uploader"
SDCARD_SCRIPTS="/sdcard/Antigravity/scripts/linux"
DEST="$HOME_DIR/agentes/tiktok_uploader"
SCRIPTS_DEST="$HOME_DIR/agentes/scripts/linux"

mkdir -p "$DEST" "$SCRIPTS_DEST"

cp "$SDCARD_TIKTOK/tiktok_evacuador_720.py" "$DEST/tiktok_evacuador_720.py"
cp "$SDCARD_TIKTOK/config.py" "$DEST/config.py"
cp "$SDCARD_TIKTOK/app.py" "$DEST/app.py"
cp "$SDCARD_SCRIPTS/_proot_bind.sh" "$SCRIPTS_DEST/_proot_bind.sh"

chmod +x "$DEST/tiktok_evacuador_720.py"

echo "Deploy completado:"
ls -la "$DEST/tiktok_evacuador_720.py" "$DEST/config.py" "$DEST/app.py" "$SCRIPTS_DEST/_proot_bind.sh"
