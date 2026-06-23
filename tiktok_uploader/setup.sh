#!/bin/bash
echo "=== INICIANDO INSTALACIÓN DE DEPENDENCIAS EN NOTE 9 ==="
apt update
apt install -y python wget tar

echo "=== CONFIGURANDO ENTORNO PYTHON ==="
cd ~/tiktok_uploader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== DESCARGANDO NGROK OFICIAL PARA PROCESADORES ARM64 (ANDROID) ==="
cd ~
wget -O ngrok.tgz https://bin.equinox.io/c/bNy8Qzbq7Pp/ngrok-v3-stable-linux-arm64.tgz
tar -xvzf ngrok.tgz
rm ngrok.tgz
chmod +x ngrok

echo "=== CONFIGURANDO AUTHTOKEN EN EL CELULAR ==="
./ngrok config add-authtoken 3EHMo9nRqGq5IJofkSJXvbc6Mcn_3moZCefH8BJcwTVtbApXc

echo "=== CONFIGURANDO ACCESO AL ACTIVADOR ==="
cp ~/tiktok_uploader/iniciar.sh ~/iniciar.sh
chmod +x ~/iniciar.sh

echo "=== INSTALACIÓN COMPLETADA ==="
echo "Ahora puedes iniciar el servidor con: bash ~/iniciar.sh"
