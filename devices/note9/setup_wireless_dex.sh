#!/bin/bash
# setup_wireless_dex.sh

SERIAL="29396e8c1e3f7ece"
IP="10.141.112.171"

echo "Configurando ADB TCP/IP en el Note 9..."
adb -s $SERIAL tcpip 5555
sleep 2

echo "Forzando modo escritorio y pantalla virtual..."
adb -s $SERIAL shell settings put global force_desktop_mode_on_external_displays 1
adb -s $SERIAL shell settings put global enable_freeform_support 1
adb -s $SERIAL shell settings put global overlay_display_devices "1920x1080/160"

echo "Conectando por WiFi..."
adb connect $IP:5555

echo "Configuración completada. Ahora puedes usar launch_scrcpy_dex.sh"
