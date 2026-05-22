#!/bin/bash

# AGENTE VIGIA META 3.0 - Linux desktop / Termux bridge

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

case "$SCRIPT_DIR" in
    /data/data/com.termux/*|/data/user/0/com.termux/*)
        IN_TERMUX_SCRIPT_DIR=1
        ;;
    *)
        IN_TERMUX_SCRIPT_DIR=0
        ;;
esac

if [ "$IN_TERMUX_SCRIPT_DIR" = "1" ] || [ "${PREFIX:-}" = "/data/data/com.termux/files/usr" ] || [ "${HOME:-}" = "/data/data/com.termux/files/home" ]; then
    TERMUX_LAUNCHER="$SCRIPT_DIR/vigia_meta_widget.sh"
    TERMUX_BASH="/data/data/com.termux/files/usr/bin/bash"

    if [ ! -f "$TERMUX_LAUNCHER" ]; then
        echo "[ERROR] No existe $TERMUX_LAUNCHER"
        exit 1
    fi

    if [ ! -x "$TERMUX_BASH" ]; then
        TERMUX_BASH="$(command -v bash 2>/dev/null || true)"
    fi

    if [ -z "$TERMUX_BASH" ]; then
        echo "[ERROR] No se encontro bash dentro de Termux"
        exit 1
    fi

    # The repo can arrive on Android without execute bits; bash avoids depending on chmod.
    exec "$TERMUX_BASH" "$TERMUX_LAUNCHER" "$@"
fi

echo -e "\e[36m=========================================================\e[0m"
echo -e "\e[36m       AGENTE VIGIA META 3.0: ACTIVADO       \e[0m"
echo -e "\e[36m=========================================================\e[0m"
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
cd "$BASE_DIR/meta_uploader" || exit

"$BASE_DIR/.venv/bin/python3" fb_to_ig_vigia.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "\e[31m[ERROR] El Agente se detuvo con un codigo de error.\e[0m"
    read -p "Presiona Enter para salir..."
fi
