#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/limpiar_locks_stale_termux.sh"
