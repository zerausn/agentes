#!/usr/bin/env bash
set -euo pipefail

NGROK_BIN="${NGROK_BIN:-/home/zerausn/.local/bin/ngrok}"

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 <ngrok_authtoken>"
    exit 1
fi

if [ ! -x "${NGROK_BIN}" ]; then
    echo "No encuentro ngrok en ${NGROK_BIN}"
    exit 1
fi

"${NGROK_BIN}" config add-authtoken "$1" >/dev/null
echo "Authtoken de ngrok configurado."
