#!/bin/bash
# setup_wireless_dex.sh
# Robust setup script: prepare Note9 for wireless DeX + TCP/IP ADB

set -euo pipefail

# Defaults - override by environment or arguments
SERIAL="${1:-29396e8c1e3f7ece}"
IP="${2:-10.141.112.171}"
ADB="${ADB:-adb}"

echo "Using ADB: $ADB"

echo "Configurando ADB TCP/IP en el Note 9 (serial=$SERIAL)..."
$ADB -s "$SERIAL" tcpip 5555
sleep 2

echo "Forzando modo escritorio y pantalla virtual..."
$ADB -s "$SERIAL" shell settings put global force_desktop_mode_on_external_displays 1 || true
$ADB -s "$SERIAL" shell settings put global enable_freeform_support 1 || true
$ADB -s "$SERIAL" shell settings put global overlay_display_devices '1920x1080/160' || true

echo "Conectando por WiFi a $IP:5555..."
$ADB connect "$IP:5555" || true

echo "Configuración completada. Now run launch_scrcpy_dex.sh or use scrcpy directly."
