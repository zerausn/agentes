#!/bin/bash

# Procesamiento Masivo Antigravity - Versión Linux Parrot

echo "=========================================================="
echo "        AUTOMATIZACION: MEJORA DE FOTOS Y VIDEOS"
echo "=========================================================="
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
UPSCALER_DIR="$BASE_DIR/video_enhancer_4k"
VENV_PYTHON="$BASE_DIR/.venv/bin/python3"

echo "Se van a abrir DOS (2) ventanas separadas (si hay entorno gráfico):"
echo "- Una para Fotos."
echo "- Otra para Videos."
echo ""

read -p "Presiona Enter para ABRIR LAS VENTANAS... (o Ctrl+C para cancelar)"

launch_term() {
    local title=$1
    local cmd=$2
    if command -v qterminal >/dev/null 2>&1; then
        qterminal -e bash -c "echo $title; $cmd; exec bash" &
    elif command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator -e bash -c "echo $title; $cmd; exec bash" &
    else
        echo "Lanzando $title en segundo plano..."
        nohup $cmd > "$UPSCALER_DIR/masivo_$(echo $title | tr ' ' '_').log" 2>&1 &
    fi
}

launch_term "MASIVO: FOTOS" "cd $UPSCALER_DIR && $VENV_PYTHON auto_batch_upscale.py --fotos"
launch_term "MASIVO: VIDEOS" "cd $UPSCALER_DIR && $VENV_PYTHON auto_batch_upscale.py --videos"

echo ""
echo "Las dos interfaces han sido lanzadas."
read -p "Presiona Enter para cerrar este lanzador principal..."
