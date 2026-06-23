#!/bin/bash

# Matar procesos colgados anteriores
killall -9 python python3 ngrok 2>/dev/null

echo "=== INICIANDO SERVIDORES EN TU GALAXY NOTE 9 ==="

# 1. Iniciar Flask
echo "[1/2] Iniciando Flask local..."
cd ~/tiktok_uploader
source venv/bin/activate
nohup python3 app.py > ~/flask_android.log 2>&1 &

# 2. Iniciar Ngrok
echo "[2/2] Levantando túnel Ngrok..."
nohup ~/ngrok http 127.0.0.1:8080 --log=stdout > ~/ngrok_android.log 2>&1 &

# Esperar a que ngrok obtenga la dirección
sleep 5

echo "--------------------------------------------------------"
echo "¡SERVIDORES ONLINE EN SEGUNDO PLANO!"
echo "--------------------------------------------------------"
# Obtener URL pública desde la API local de Ngrok
URL=$(python3 -c "import urllib.request, json; print(json.loads(urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels').read())['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$URL" ]; then
    echo "Error: Ngrok no logró levantar la URL a tiempo."
    echo "Revisa el log con: cat ~/ngrok_android.log"
else
    echo "Tu nueva URL pública es:"
    echo "👉 $URL"
    echo ""
    echo "Recuerda actualizar esta URL en el portal de TikTok Developers"
    echo "añadiéndole '/callback' al final."
fi
echo "--------------------------------------------------------"
echo "Para ver si hay errores en Flask: cat ~/flask_android.log"
echo "Para apagar los servidores: killall ngrok python3"
echo "--------------------------------------------------------"
