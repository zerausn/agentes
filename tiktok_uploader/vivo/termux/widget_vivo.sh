#!/data/data/com.termux/files/usr/bin/bash
# widget_vivo.sh — Widget Termux para VIGIA TikTok 720 en VIVO V2058
# Colocar en ~/.shortcuts/6_SUBIR_TIKTOK720.sh
# Llama al vigía estándar que maneja el ciclo de 720s.

set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
VIGIA="/data/data/com.termux/files/home/agentes/scripts/linux/vigia_tiktok720_termux.sh"
if [ ! -f "$VIGIA" ]; then
  echo "[ERROR] no existe $VIGIA"
  echo "        Corre 0_RENOVAR_REPO para actualizar el repo."
  exit 1
fi
exec bash "$VIGIA" "$@"
