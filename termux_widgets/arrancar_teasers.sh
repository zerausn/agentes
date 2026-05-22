#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
export AGENTES_STORAGE_ROOT="/sdcard/Antigravity"

cd /sdcard/Antigravity/agentes/youtube_uploader
exec nohup python3 teaser_uploader.py >> /sdcard/Antigravity/agentes/youtube_uploader/teaser_uploader.log 2>&1 &
