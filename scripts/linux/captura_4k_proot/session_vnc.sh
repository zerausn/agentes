#!/bin/bash
# session_vnc.sh — sesion manual del perfil de captura visible por VNC (login de cuenta).
# Usa Xvnc (evita el shmget de x11vnc, bloqueado en el proot del S24).
# Conectarse con un cliente VNC (ej. VNC Viewer) a 127.0.0.1:5901 desde el propio S24.
# Sin contraseña (solo loopback, -localhost). Al cerrar la sesion, matar el script.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="/root"

pkill -f '[f]irefox' 2>/dev/null || true
pkill -f '[X]vnc' 2>/dev/null || true
pkill -f '[X]vfb' 2>/dev/null || true
pkill -f '[m]itmdump' 2>/dev/null || true
rm -rf /root/.vnc/passwd
sleep 2

Xvnc :1 -geometry 1440x900 -depth 24 -SecurityTypes None -localhost > /tmp/vnc_xvnc.log 2>&1 &
VNC=$!
sleep 3

export DISPLAY=:1
/usr/bin/firefox --no-remote --profile /root/captura_firefox_profile \
    "https://accounts.google.com/signin/v2/identifier?continue=https%3A%2F%2Fwww.youtube.com%2F&hl=es" \
    > /tmp/vnc_firefox.log 2>&1 &
FF=$!

echo "=== SESION VNC LISTA ==="
echo "Xvnc=$VNC firefox=$FF"
echo "Conecta tu cliente VNC a: 127.0.0.1:5901"

for i in $(seq 1 600); do
    sleep 30
    if ! kill -0 "$VNC" 2>/dev/null; then
        echo "Xvnc murio a los $((i * 30))s"
        tail -6 /tmp/vnc_xvnc.log
        break
    fi
done
echo "=== SESION VNC FIN ==="
pkill -f '[f]irefox' 2>/dev/null || true
kill "$VNC" 2>/dev/null || true