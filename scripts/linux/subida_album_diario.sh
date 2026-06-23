#!/bin/bash

echo "=========================================================="
echo "   ANTIGRAVITY - ALBUM DIARIO FACEBOOK + TEASER INMEDIATO"
echo "=========================================================="
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
cd "$BASE_DIR/meta_uploader/photo_uploader" || exit

read -p "Presiona Enter para INICIAR... (o Ctrl+C para cancelar)"

"$BASE_DIR/.venv/bin/python3" album_diario.py

echo ""
echo "Proceso terminado."
read -p "Presiona Enter para salir..."
