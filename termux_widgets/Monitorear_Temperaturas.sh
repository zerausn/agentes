#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

echo "THERMAL SNAPSHOT"
echo "================"
if command -v termux-battery-status >/dev/null 2>&1; then
  battery_temp=$(termux-battery-status | grep -i temperature | awk '{print $2}' | sed 's/,//')
  echo "battery_c=${battery_temp:-unknown}"
fi
for tz in /sys/class/thermal/thermal_zone*; do
  type=$(cat "$tz/type" 2>/dev/null || true)
  temp=$(cat "$tz/temp" 2>/dev/null || true)
  if [ -n "$temp" ]; then
    if [ "$temp" -gt 1000 ] 2>/dev/null; then
      temp=$(("$temp" / 1000))
    fi
    echo "${type:-unknown}=${temp}C"
  fi
done | grep -Ei 'cpu|gpu|battery|tsens|quiet|skin' | head -n 12
echo "================"
read -r -p "Enter para cerrar..."
