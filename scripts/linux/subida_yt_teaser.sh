#!/bin/bash

# YOUTUBE TEASER UPLOADER - Versión Linux Parrot

echo "=========================================================="
echo "          YOUTUBE TEASER UPLOADER (RECICLAJE)             "
echo "=========================================================="
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
cd "$BASE_DIR/youtube_uploader" || exit

"$BASE_DIR/.venv/bin/python3" teaser_uploader.py

read -p "Presiona Enter para salir..."
