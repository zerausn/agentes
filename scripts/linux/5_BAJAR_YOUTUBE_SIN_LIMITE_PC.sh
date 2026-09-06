#!/usr/bin/env bash
# 5_BAJAR_YOUTUBE_SIN_LIMITE_PC — Shortcut lanzador para el PC
# Equivalente al widget del S24 pero para Parrot OS nativo.
# Puedes poner un alias en tu ~/.bashrc:
#   alias bajar-youtube="bash ~/Documents/Antigravity/agentes/scripts/linux/5_BAJAR_YOUTUBE_SIN_LIMITE_PC.sh"

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/bajar_youtube_sin_limite_pc.sh"
