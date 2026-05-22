#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
YT_LOG="$TERMUX_HOME/agentes/youtube_uploader/youtube_to_fb_sync.log"
META_LOG="$TERMUX_HOME/agentes/meta_uploader/fb_to_ig_vigia.log"

echo "YOUTUBE LOG"
echo "==========="
tail -n 40 "$YT_LOG" 2>/dev/null || echo "sin log de youtube"
echo
echo "META LOG"
echo "========"
tail -n 40 "$META_LOG" 2>/dev/null || echo "sin log de meta"
echo
read -r -p "Enter para cerrar..."
