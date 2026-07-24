#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# deploy.sh (VIVO V2058) — Copia archivos TikTok desde /sdcard al home de Termux
# CLON ESPECIFICO PARA VIVO — NO USAR EN NOTE9
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
HOME_DIR="/data/data/com.termux/files/home"
SDCARD_TIKTOK="/sdcard/Antigravity/agentes/tiktok_uploader"
SDCARD_SCRIPTS="/sdcard/Antigravity/scripts/linux"
DEST="$HOME_DIR/agentes/tiktok_uploader"
SCRIPTS_DEST="$HOME_DIR/agentes/scripts/linux"

mkdir -p "$DEST" "$SCRIPTS_DEST"

cp "$SDCARD_TIKTOK/tiktok_evacuador_720.py" "$DEST/tiktok_evacuador_720.py"

for f in vigia_vivo.sh widget_vivo.sh; do
    [ -f "$SDCARD_SCRIPTS/$f" ] && cp "$SDCARD_SCRIPTS/$f" "$SCRIPTS_DEST/$f" && chmod +x "$SCRIPTS_DEST/$f"
done

chmod +x "$DEST/tiktok_evacuador_720.py"

echo "Deploy VIVO completado:"
ls -la "$DEST/tiktok_evacuador_720.py"
echo "Scripts:"
ls -la "$SCRIPTS_DEST/"vigia_vivo.sh "$SCRIPTS_DEST/"widget_vivo.sh 2>/dev/null || true
