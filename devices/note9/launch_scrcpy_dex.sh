#!/bin/bash
# launch_scrcpy_dex.sh
# Robust launcher: detect device/IP and open DeX display in fullscreen

set -euo pipefail

ADB="${ADB:-adb}"
SCRCPY="${SCRCPY:-scrcpy}"

# Prefer a tcpip device if present
dev="$($ADB devices | awk '/:/ && /device/{print $1; exit}')"
if [ -z "$dev" ]; then
  # fallback to first usb device
  dev="$($ADB devices | awk '/\tdevice$/{print $1; exit}')"
fi

if [ -z "$dev" ]; then
  echo "No ADB device available." >&2
  exit 1
fi

echo "Using device: $dev"

# List displays and pick the last (commonly the DeX/virtual display)
displays="$($SCRCPY -s "$dev" --list-displays 2>&1 || true)"
echo "$displays"
display_id=$(echo "$displays" | awk -F= '/--display-id=/{print $2}' | tail -n1)
if [ -z "$display_id" ]; then
  display_id=0
fi

echo "Lanzando scrcpy en display $display_id for device $dev..."
$SCRCPY -s "$dev" --display-id="$display_id" --no-audio -f --window-title "Samsung DeX - Note 9"
