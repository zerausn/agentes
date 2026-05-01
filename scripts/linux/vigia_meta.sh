#!/bin/bash

# AGENTE VIGIA META 3.0 - Versión Linux Parrot

echo -e "\e[36m=========================================================\e[0m"
echo -e "\e[36m       👁️ AGENTE VIGIA META 3.0: ACTIVADO 👁️ \e[0m"
echo -e "\e[36m=========================================================\e[0m"
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
cd "$BASE_DIR/meta_uploader" || exit

"$BASE_DIR/.venv/bin/python3" fb_to_ig_vigia.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "\e[31m[ERROR] El Agente se detuvo con un código de error.\e[0m"
    read -p "Presiona Enter para salir..."
fi
