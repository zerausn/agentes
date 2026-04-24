#!/bin/bash

# Agentes de Subida Automatizada (Meta y YouTube) - Versión Linux Parrot

echo "========================================================"
echo "   INICIANDO LOS AGENTES DIARIOS DE META Y YOUTUBE"
echo "========================================================"
echo ""

# Matar procesos anteriores si es necesario (equivalente al comando powershell)
# Buscamos procesos python que estén ejecutando nuestros agents
pkill -f "run_jornada1_supervisor.py"
pkill -f "uploader.py"

sleep 2

# Definir rutas
BASE_DIR="/home/zerausn/Documents/Antigravity/agentes"

echo "Iniciando Agente Meta..."
# Abrimos en una nueva terminal si es posible, o usamos nohup
if command -v qterminal >/dev/null 2>&1; then
    qterminal -e bash -c "cd $BASE_DIR && source .venv/bin/activate && bash scripts/linux/start_agent_meta.sh; exec bash" &
elif command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -c "cd $BASE_DIR && source .venv/bin/activate && bash scripts/linux/start_agent_meta.sh; exec bash" &
else
    nohup bash scripts/linux/start_agent_meta.sh > $BASE_DIR/meta_uploader/linux_agent.log 2>&1 &
fi

echo "Iniciando Agente YouTube..."
if command -v qterminal >/dev/null 2>&1; then
    qterminal -e bash -c "cd $BASE_DIR && source .venv/bin/activate && bash scripts/linux/start_agent_youtube.sh; exec bash" &
elif command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -c "cd $BASE_DIR && source .venv/bin/activate && bash scripts/linux/start_agent_youtube.sh; exec bash" &
else
    nohup bash scripts/linux/start_agent_youtube.sh > $BASE_DIR/youtube_uploader/linux_agent.log 2>&1 &
fi

echo ""
echo "========================================================"
echo " EXITO: Los agentes se están ejecutando."
echo " Puedes ver los logs en las nuevas ventanas o en los archivos .log"
echo "========================================================"
read -p "Presiona Enter para cerrar este lanzador..."
