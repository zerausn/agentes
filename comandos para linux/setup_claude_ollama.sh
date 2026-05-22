#!/bin/bash
# =============================================================================
# setup_claude_ollama.sh
# Configura el puente entre Claude Code y Ollama en Linux Parrot OS 7
# =============================================================================

set -e

echo "[+] Verificando dependencias en Parrot OS 7..."
if ! command -v python3 &> /dev/null; then
    echo "    Instalando Python3 y venv..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

VENV_DIR="$HOME/.claude_ollama_venv"
PORT=4000
MODEL="ollama_chat/qwen2.5-coder:7b" # Puedes cambiar este nombre por el modelo exacto que descargues de la nube de Ollama

echo "[+] Creando entorno virtual seguro en $VENV_DIR..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

echo "[+] Activando entorno e instalando LiteLLM Proxy..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip litellm[proxy] >/dev/null 2>&1
echo "    OK: LiteLLM instalado correctamente"

echo ""
echo "==================================================================="
echo " INICIANDO SERVIDOR PROXY Y ENLAZANDO CLAUDE CODE"
echo "==================================================================="
echo " Modelo base: $MODEL"
echo " Puerto:      $PORT"
echo " API Key:     sk-local-ollama"
echo "==================================================================="
echo ""
echo "[!] Deja esta terminal abierta. El proxy estara corriendo."
echo ""
echo "-> EN UNA NUEVA TERMINAL, EJECUTA ESTO ANTES DE USAR CLAUDE:"
echo "-------------------------------------------------------------------"
echo "export ANTHROPIC_API_KEY=\"sk-local-ollama\""
echo "export ANTHROPIC_BASE_URL=\"http://127.0.0.1:$PORT\""
echo "claude"
echo "-------------------------------------------------------------------"
echo ""

# Iniciar el proxy de LiteLLM para traducir Anthropic a Ollama
litellm --model "$MODEL" --port "$PORT" --drop_params
