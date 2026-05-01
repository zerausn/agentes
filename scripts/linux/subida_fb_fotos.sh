#!/bin/bash

# Subidor de Fotos a Facebook (Reels) - Versión Linux Parrot

echo "=========================================================="
echo "   ANTIGRAVITY - SUBIDOR MASIVO DE FOTOS A FACEBOOK"
echo "=========================================================="
echo ""

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
cd "$BASE_DIR/meta_uploader/photo_uploader" || exit

# Entradas sugeridas (deberían ser validadas por el script python)
# Carpeta de entrada original: /media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\Fotos
# En Linux: /media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/FOTOs

echo "Modo: Foto -> Reel de 5 segundos"
echo ""

read -p "Presiona Enter para INICIAR... (o Ctrl+C para cancelar)"

echo "Iniciando agente..."
"$BASE_DIR/.venv/bin/python3" photo_uploader.py

echo ""
echo "El agente ha terminado o fue interrumpido."
read -p "Presiona Enter para salir..."
