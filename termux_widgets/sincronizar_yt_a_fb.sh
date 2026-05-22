#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/sincronizar_yt_a_fb_termux.sh"
exec "$LAUNCHER"
