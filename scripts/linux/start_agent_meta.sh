#!/bin/bash

# START_AGENT_META - Versión Linux Parrot

BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"
VENV_PYTHON="$BASE_DIR/.venv/bin/python3"
TARGET_DIR="/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/videos subidos exitosamente"

echo -e "\e[36m==========================================================\e[0m"
echo -e "\e[36m INICIANDO AGENTE DIARIO: SUBE VIDEOS A META \e[0m"
echo -e "\e[36m==========================================================\e[0m"

cd "$BASE_DIR" || exit

echo -e "\e[33mPaso 1: Reconciliando (Limpiando duplicados alojados en la nube)...\e[0m"
"$VENV_PYTHON" "meta_uploader/reconcile_meta_cloud.py"

echo -e "\e[33mPaso 2: Clasificando nuevos videos (Directorio Externo de ADM)...\e[0m"
"$VENV_PYTHON" "meta_uploader/classify_meta_videos.py" "$TARGET_DIR"

echo -e "\e[36mPaso 3: Lanzando Motor de Cascada Infinito (07:00 / 18:30)...\e[0m"
export META_ENABLE_UPLOAD=1
"$VENV_PYTHON" "meta_uploader/run_jornada1_supervisor.py" --days 28 --max-live-days 28 --rebuild-plan --restart-delay-seconds 10 --max-restarts 9999
