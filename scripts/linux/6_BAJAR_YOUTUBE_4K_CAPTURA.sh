#!/data/data/com.termux/files/usr/bin/bash
# 6_BAJAR_YOUTUBE_4K_CAPTURA — Widget puente hacia el capturador 4K por navegador
# Termux Shortcut: ~/.shortcuts/6_BAJAR_YOUTUBE_4K_CAPTURA.sh
# Estrategia: Firefox + mitmproxy en el proot Debian captura el transporte UMP de
# YouTube (docs/CAPTURA_4K_MITMPROXY_NAVEGADOR.md)

set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/bajar_captura_4k_termux.sh"