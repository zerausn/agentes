#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

pkill -f "xfce4-session" >/dev/null 2>&1 || true
pkill -f "xfce4-panel" >/dev/null 2>&1 || true
pkill -f "xfdesktop4" >/dev/null 2>&1 || true
pkill -f "xfwm4" >/dev/null 2>&1 || true
pkill -f "tigervncserver" >/dev/null 2>&1 || true
pkill -f "Xtigervnc" >/dev/null 2>&1 || true
pkill -f "/data/data/com.termux/files/usr/bin/termux-x11" >/dev/null 2>&1 || true
pulseaudio --kill >/dev/null 2>&1 || true

echo "Debian grafico detenido."
