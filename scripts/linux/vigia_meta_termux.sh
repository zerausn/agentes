#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
META_DIR="$TERMUX_HOME/agentes/meta_uploader"

cd "$META_DIR" || exit 1
exec /usr/bin/python3 fb_to_ig_vigia.py "$@"
