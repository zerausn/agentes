#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-8080}"
RUN_DIR="${SCRIPT_DIR}/.run"
PID_FILE="${RUN_DIR}/cloudflared.pid"
LOG_FILE="${RUN_DIR}/cloudflared.log"
URL_FILE="${RUN_DIR}/public_url.txt"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-/home/zerausn/.local/bin/cloudflared}"
CLOUDFLARED_PROTOCOL="${CLOUDFLARED_PROTOCOL:-http2}"

mkdir -p "${RUN_DIR}"

if [ ! -x "${CLOUDFLARED_BIN}" ]; then
    echo "No encuentro cloudflared en ${CLOUDFLARED_BIN}"
    exit 1
fi

if [ -f "${PID_FILE}" ]; then
    existing_pid="$(cat "${PID_FILE}")"
    if kill -0 "${existing_pid}" 2>/dev/null; then
        if [ -f "${URL_FILE}" ]; then
            url="$(cat "${URL_FILE}")"
            echo "Cloudflare Tunnel ya estaba activo: ${url}"
            echo "Redirect URI: ${url}/callback"
            exit 0
        fi
    else
        rm -f "${PID_FILE}"
    fi
fi

: > "${LOG_FILE}"
nohup "${CLOUDFLARED_BIN}" tunnel --url "http://127.0.0.1:${PORT}" --protocol "${CLOUDFLARED_PROTOCOL}" --no-autoupdate \
    > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

url=""
for _ in $(seq 1 60); do
    if grep -Eo 'https://[[:alnum:]-]+\.trycloudflare\.com' "${LOG_FILE}" >/dev/null 2>&1; then
        url="$(grep -Eo 'https://[[:alnum:]-]+\.trycloudflare\.com' "${LOG_FILE}" | tail -n 1)"
        break
    fi
    sleep 1
done

if [ -z "${url}" ]; then
    echo "No pude obtener la URL publica de Cloudflare Tunnel."
    echo "Revisa ${LOG_FILE}"
    exit 1
fi

host="${url#https://}"
for _ in $(seq 1 90); do
    if getent ahosts "${host}" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! getent ahosts "${host}" >/dev/null 2>&1; then
    echo "La URL publica no resolvio por DNS a tiempo: ${url}"
    echo "Revisa ${LOG_FILE}"
    exit 1
fi

printf '%s\n' "${url}" > "${URL_FILE}"
"${SCRIPT_DIR}/set_public_base_url.sh" "${url}" >/dev/null

echo "Cloudflare Tunnel activo: ${url}"
echo "Protocolo Cloudflare Tunnel: ${CLOUDFLARED_PROTOCOL}"
echo "Redirect URI: ${url}/callback"
