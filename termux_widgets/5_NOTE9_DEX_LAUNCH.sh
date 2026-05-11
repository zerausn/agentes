#!/bin/bash
# 5_NOTE9_DEX_LAUNCH.sh
# Widget para lanzar scrcpy (Note 9) desde el Debian de la tablet

# Intentar encontrar la IP del Note 9 que ya esté conectado a ADB
IP=$(adb devices | grep ":5555" | head -n 1 | awk '{print $1}' | cut -d: -f1)

if [ -z "$IP" ]; then
    echo "Note 9 no está conectado por WiFi. Ejecuta primero el script de configuración."
    exit 1
fi

echo "Lanzando DeX de Note 9 ($IP) en Debian..."

# Entrar a Debian y ejecutar scrcpy
# Se asume que el display virtual es el ID 6 tras el truco del monitor fantasma
proot-distro login debian -- bash -c "DISPLAY=:0 scrcpy -s $IP:5555 --display-id=6 --no-audio -f"
