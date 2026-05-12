#!/bin/bash
# 5_NOTE9_DEX_LAUNCH.sh
# Widget para lanzar scrcpy (Note 9) desde la tablet (Termux/proot)

set -euo pipefail

ADB="${ADB:-adb}"
SCRCPY="${SCRCPY:-scrcpy}"

# Detect device (tcpip preferred)
dev="$($ADB devices | awk '/:/ && /device/{print $1; exit}')"
if [ -z "$dev" ]; then
  dev="$($ADB devices | awk '/\tdevice$/{print $1; exit}')"
fi

if [ -z "$dev" ]; then
  echo "Note 9 no está conectado por ADB. Ejecuta primero la configuración." >&2
  exit 1
fi

echo "Usando dispositivo: $dev"

# Obtener display list y elegir el último (virtual/DeX)
displays=$($SCRCPY -s "$dev" --list-displays 2>&1 || true)
echo "$displays"
display_id=$(echo "$displays" | awk -F= '/--display-id=/{print $2}' | tail -n1)
[ -z "$display_id" ] && display_id=0

echo "Lanzando scrcpy en display $display_id (device $dev)..."

# Si scrcpy está disponible en Termux, usarlo; si no, invocar proot-distro
if command -v "$SCRCPY" >/dev/null 2>&1; then
  $SCRCPY -s "$dev" --display-id="$display_id" --no-audio -f
else
  proot-distro login debian -- bash -lc "scrcpy -s $dev --display-id=$display_id --no-audio -f"
fi
