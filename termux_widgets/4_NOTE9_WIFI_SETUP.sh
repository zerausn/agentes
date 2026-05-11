#!/bin/bash
# 4_NOTE9_WIFI_SETUP.sh
# Widget para configurar el Note 9 inalámbrico desde la tablet

# Detectar Note 9 por USB (Asegúrate de conectarlo a la tablet)
SERIAL=$(adb devices | grep -v "List" | grep "device$" | head -n 1 | awk '{print $1}')

if [ -z "$SERIAL" ]; then
    echo "No se detectó ningún dispositivo por USB."
    exit 1
fi

echo "Dispositivo detectado: $SERIAL"
adb -s $SERIAL tcpip 5555
sleep 3

# Obtener IP del Note 9
IP=$(adb -s $SERIAL shell ip route | grep "wlan0" | awk '{print $9}')
if [ -z "$IP" ]; then
    IP=$(adb -s $SERIAL shell ip addr show wlan0 | grep "inet " | awk '{print $2}' | cut -d/ -f1)
fi

echo "IP detectada: $IP"

# Truco del monitor fantasma
echo "Configurando pantalla virtual..."
adb -s $SERIAL shell settings put global force_desktop_mode_on_external_displays 1
adb -s $SERIAL shell settings put global overlay_display_devices "1920x1080/160"

# Conectar
adb connect $IP:5555
echo "Note 9 listo para usar sin cables en la IP $IP"
