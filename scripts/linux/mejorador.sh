#!/bin/bash

# Antigravity Mejorador - Versión Linux Parrot

echo "=========================================================="
echo "       INICIANDO INTERFAZ GRAFICA DE MEJORAMIENTO"
echo "=========================================================="
echo ""
echo "Requisitos: Se abrirá una pestaña en tu navegador (http://127.0.0.1:7860)"
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
UPSCALER_DIR="$BASE_DIR/video_enhancer_4k"

cd "$UPSCALER_DIR" || exit

# Ejecutar la aplicación
"$BASE_DIR/.venv/bin/python3" gui_upscaler.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "\e[31m[ERROR] La aplicación se detuvo inesperadamente.\e[0m"
    read -p "Presiona Enter para salir..."
fi
