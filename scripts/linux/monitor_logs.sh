#!/bin/bash

# MONITOR_LOGS_REDES - Versión Linux Parrot

ROOT="/home/zerausn/Documents/Antigravity/agentes"
PYTHON="$ROOT/.venv/bin/python3"
SCRIPT="$ROOT/scripts/monitor_realtime.py"

if [ -f "$PYTHON" ]; then
    "$PYTHON" "$SCRIPT" "$@"
else
    python3 "$SCRIPT" "$@"
fi
