#!/bin/bash
# session_vnc.sh — sesion manual del perfil de captura visible por VNC (login de cuenta).
# Uso: bash session_vnc.sh   (dentro del proot)
#   Abre Xvfb :99 + Firefox (perfil captura) + x11vnc en el loopback del telefono.
#   Conectarse con un cliente VNC a 127.0.0.1:5900 desde el propio S24.
#   Al terminar: cerrar el firefox por VNC y matar el script (Ctrl-C / pkill).
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="/root"

pkill -f '[f]irefox' 2>/dev/null || true
pkill -f '[X]vfb' 2>/dev/null || true
pkill -f '[x]11vnc' 2>/dev/null || true
pkill -f '[m]itmdump' 2>/dev/null || true
sleep 2

export DISPLAY=:99
Xvfb :99 -screen 0 1440x900x24 > /tmp/vnc_xvfb.log 2>&1 &
XVFB=$!
sleep 2

x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 > /tmp/vnc_x11vnc.log 2>&1 &
VNC=$!
sleep 2

/usr/bin/firefox --no-remote --profile /root/captura_firefox_profile \
    "https://accounts.google.com/signin/v2/identifier?continue=https%3A%2F%2Fwww.youtube.com%2F&hl=es" \
    > /tmp/vnc_firefox.log 2>&1 &
FF=$!

echo "=== SESION VNC LISTA ==="
echo "Xvfb=$XVFB x11vnc=$VNC firefox=$FF"
echo "Conecta tu cliente VNC a 127.0.0.1:5900 (mismo telefono)"
echo "Cuando termines de loguear, cierra la pestana de firefox"

trap 'pkill -f "[f]irefox" 2>/dev/null; pkill -f "[x]11vnc" 2>/dev/null; kill $XVFB 2>/dev/null' EXIT
for i in $(seq 1 600); do
    sleep 30
    ! kill -0 "$VNC" 2>/dev/null && echo "x11vnc murio" && break
done
echo "=== SESION VNC FIN ==="