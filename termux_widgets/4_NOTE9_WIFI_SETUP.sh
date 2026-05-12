#!/bin/bash
# 4_NOTE9_WIFI_SETUP.sh
# Widget para configurar el Note 9 inalámbrico desde la tablet
# Ahora con intento automático de aceptar el diálogo de depuración (si es posible)

set -euo pipefail

ADB="${ADB:-adb}"

# Detectar Note 9 por USB (Asegúrate de conectarlo a la tablet)
SERIAL=$($ADB devices | grep -v "List" | grep "device$" | head -n 1 | awk '{print $1}')

if [ -z "$SERIAL" ]; then
    echo "No se detectó ningún dispositivo por USB."
    exit 1
fi

echo "Dispositivo detectado: $SERIAL"

# Helper: está autorizado?
is_authorized() {
  state=$($ADB devices | awk -v s="$SERIAL" '$1==s {print $2}') || state=""
  [ "$state" = "device" ]
}

# Parse bounds helper (recibe la línea XML con bounds)
parse_bounds_center() {
  local line="$1"
  # extract bounds="[l,t][r,b]"
  b=$(printf '%s' "$line" | awk -F'bounds="' '{if (NF>1) {split($2,a,"\""); print a[1]}}') || b=""
  if [ -z "$b" ]; then
    return 1
  fi
  coords=$(printf '%s' "$b" | sed 's/\]\[/ /g' | tr -d '[]')
  l=$(printf '%s' "$coords" | awk '{split($1,A,","); print A[1]}')
  t=$(printf '%s' "$coords" | awk '{split($1,A,","); print A[2]}')
  r=$(printf '%s' "$coords" | awk '{split($2,B,","); print B[1]}')
  btm=$(printf '%s' "$coords" | awk '{split($2,B,","); print B[2]}')
  cx=$(( (l + r)/2 ))
  cy=$(( (t + btm)/2 ))
  printf "%d %d" "$cx" "$cy"
  return 0
}

# Intento automático de aceptar el diálogo USB (si aparece)
auto_accept_dialog() {
  local serial="$1"
  local tries=${2:-12}
  echo "Intentando aceptar diálogo (hasta $tries intentos)..."
  for i in $(seq 1 $tries); do
    # Dump UI
    $ADB -s "$serial" shell uiautomator dump /sdcard/window_dump.xml >/dev/null 2>&1 || true
    dump=$($ADB -s "$serial" shell cat /sdcard/window_dump.xml 2>/dev/null || true)

    # Buscar checkbox "Always allow" / "Permitir siempre"
    checkbox_line=$(printf '%s' "$dump" | grep -iE 'class="[^"]*CheckBox|text="(Always allow|Permitir siempre|Remember auth|Recordar|Permitir siempre desde este equipo)"' | head -n1 || true)
    # Buscar botón Allow/Permitir/OK
    allow_line=$(printf '%s' "$dump" | grep -iE 'text="(Allow|Permitir|OK|Aceptar)"|resource-id="(android:id/button1|com.android.packageinstaller:id/permission_allow_button|android:id/button_once)"' | head -n1 || true)

    if [ -n "$checkbox_line" ]; then
      coords=$(parse_bounds_center "$checkbox_line" 2>/dev/null || true)
      if [ -n "$coords" ]; then
        cx=$(printf '%s' "$coords" | awk '{print $1}')
        cy=$(printf '%s' "$coords" | awk '{print $2}')
        echo "Tocando checkbox en $cx,$cy"
        $ADB -s "$serial" shell input tap $cx $cy || true
        sleep 0.4
      fi
    fi

    if [ -n "$allow_line" ]; then
      coords=$(parse_bounds_center "$allow_line" 2>/dev/null || true)
      if [ -n "$coords" ]; then
        cx=$(printf '%s' "$coords" | awk '{print $1}')
        cy=$(printf '%s' "$coords" | awk '{print $2}')
        echo "Tocando botón Allow en $cx,$cy"
        $ADB -s "$serial" shell input tap $cx $cy || true
        sleep 1
      fi
    else
      # fallback: tap bottom-right area
      size=$($ADB -s "$serial" shell wm size 2>/dev/null | awk -F': ' '{print $2}') || size=""
      if [ -n "$size" ]; then
        width=$(printf '%s' "$size" | cut -d'x' -f1)
        height=$(printf '%s' "$size" | cut -d'x' -f2)
        cx=$(( width*75/100 ))
        cy=$(( height*90/100 ))
        echo "Fallback tap at $cx,$cy"
        $ADB -s "$serial" shell input tap $cx $cy || true
        sleep 1
      fi
    fi

    # Verificar si ahora está autorizado
    if is_authorized; then
      echo "Device autorizado"
      return 0
    fi

    sleep 1
  done
  return 1
}

# Si no está autorizado, intentar auto-aceptar
if ! is_authorized; then
  echo "El dispositivo no está autorizado. Intentando auto-aceptar..."
  if auto_accept_dialog "$SERIAL" 18; then
    echo "Auto-aceptado OK"
  else
    echo "Auto-aceptado falló: revisa el Note9 y acepta manualmente."
  fi
fi

# Si está autorizado, continuar con tcpip y monitor fantasma
if is_authorized; then
  echo "Activando adb tcpip y configurando pantalla virtual..."
  $ADB -s $SERIAL tcpip 5555 || true
  sleep 2

  IP=$($ADB -s $SERIAL shell ip route | grep "wlan0" | awk '{print $9}' || true)
  if [ -z "$IP" ]; then
      IP=$($ADB -s $SERIAL shell ip addr show wlan0 | grep "inet " | awk '{print $2}' | cut -d/ -f1 | tr -d '\r' | head -n1 || true)
  fi

  echo "IP detectada: $IP"

  echo "Configurando pantalla virtual..."
  $ADB -s $SERIAL shell settings put global force_desktop_mode_on_external_displays 1 || true
  $ADB -s $SERIAL shell settings put global overlay_display_devices "1920x1080/160" || true

  if [ -n "$IP" ]; then
    echo "Conectando por WiFi..."
    $ADB connect $IP:5555 || true
    echo "Note 9 listo para usar sin cables en la IP $IP"
  else
    echo "No se pudo obtener IP. Verifica Wi‑Fi en el Note9."
  fi
fi
