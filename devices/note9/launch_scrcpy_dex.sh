#!/bin/bash
# launch_scrcpy_dex.sh

IP="10.141.112.171"
PORT="5555"

# Intentar conectar por si acaso
adb connect $IP:$PORT

# Buscar el display virtual (suele ser el 6 tras el truco del monitor fantasma)
DISPLAY_ID=$(adb -s $IP:$PORT shell dumpsys display | grep "mDisplayId=" | tail -n 1 | cut -d= -f2)

echo "Lanzando scrcpy en display $DISPLAY_ID..."
scrcpy -s $IP:$PORT --display-id=$DISPLAY_ID --no-audio -f --window-title "Samsung DeX - Note 9"
