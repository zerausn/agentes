#!/bin/bash

# START_AGENT_YOUTUBE - Versión Linux Parrot

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
VENV_PYTHON="$BASE_DIR/.venv/bin/python3"

echo -e "\e[31m==========================================================\e[0m"
echo -e "\e[31m INICIANDO AGENTE DIARIO: SUBE VIDEOS A YOUTUBE \e[0m"
echo -e "\e[31m==========================================================\e[0m"

cd "$BASE_DIR" || exit

while true; do
    currentTime=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "\n\e[32m[$currentTime] --- INICIANDO NUEVO CICLO DIARIO (YOUTUBE) ---\e[0m"

    echo -e "\e[33mPaso 1: Limpiando tu carpeta externa (Moviendo videos ya subidos)...\e[0m"
    "$VENV_PYTHON" "youtube_uploader/periodic_mover.py" --run-once

    echo -e "\e[33mPaso 1.5: Purgando memoria vieja...\e[0m"
    rm -f "youtube_uploader/scanned_videos.json"

    echo -e "\e[33mPaso 2: Escaneando en busca de nuevos videos...\e[0m"
    "$VENV_PYTHON" "youtube_uploader/video_scanner.py"

    echo -e "\e[33mPaso 3: Lanzando el archivo que sube videos a YouTube (Borradores)...\e[0m"
    "$VENV_PYTHON" "youtube_uploader/uploader.py"

    echo -e "\e[33mPaso 4: Recreando el calendario de YouTube...\e[0m"
    "$VENV_PYTHON" "youtube_uploader/schedule_drafts.py"

    currentTime=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "\n\e[32m[$currentTime] --- CICLO TERMINADO: ESPERANDO 24 HORAS ---\e[0m"
    
    sleep 86400
done
