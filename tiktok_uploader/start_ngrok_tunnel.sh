#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.local"
RUN_DIR="${SCRIPT_DIR}/.run"
PID_FILE="${RUN_DIR}/ngrok.pid"
LOG_FILE="${RUN_DIR}/ngrok.log"
URL_FILE="${RUN_DIR}/public_url.txt"
PORT="${1:-8080}"
NGROK_BIN="${NGROK_BIN:-/home/zerausn/.local/bin/ngrok}"
NGROK_API_URL="${NGROK_API_URL:-http://127.0.0.1:4040/api/tunnels}"
NGROK_CONFIG_FILE="${NGROK_CONFIG_FILE:-/home/zerausn/.config/ngrok/ngrok.yml}"
NGROK_CA_FILE="${NGROK_CA_FILE:-/etc/ssl/certs/ca-certificates.crt}"
NGROK_CA_DIR="${NGROK_CA_DIR:-/etc/ssl/certs}"

if [ -f "${ENV_FILE}" ]; then
    set -a
    . "${ENV_FILE}"
    set +a
fi

mkdir -p "${RUN_DIR}"

if [ ! -x "${NGROK_BIN}" ]; then
    echo "No encuentro ngrok en ${NGROK_BIN}"
    exit 1
fi

if [ -n "${NGROK_AUTHTOKEN:-}" ]; then
    "${NGROK_BIN}" config add-authtoken "${NGROK_AUTHTOKEN}" >/dev/null
fi

if [ ! -f "${NGROK_CONFIG_FILE}" ] || ! grep -q 'authtoken:' "${NGROK_CONFIG_FILE}" 2>/dev/null; then
    echo "Falta configurar ngrok."
    echo "Exporta NGROK_AUTHTOKEN o ejecuta: ${NGROK_BIN} config add-authtoken <tu_token>"
    exit 1
fi

if [ -f "${PID_FILE}" ]; then
    existing_pid="$(cat "${PID_FILE}")"
    if kill -0 "${existing_pid}" 2>/dev/null; then
        if [ -f "${URL_FILE}" ]; then
            url="$(cat "${URL_FILE}")"
            echo "ngrok ya estaba activo: ${url}"
            echo "Redirect URI: ${url}/callback"
            exit 0
        fi
    else
        rm -f "${PID_FILE}"
    fi
fi

: > "${LOG_FILE}"
nohup env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
    SSL_CERT_FILE="${NGROK_CA_FILE}" SSL_CERT_DIR="${NGROK_CA_DIR}" \
    "${NGROK_BIN}" http "http://127.0.0.1:${PORT}" --log stdout > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

url=""
for _ in $(seq 1 60); do
    if ! kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
        break
    fi
    api_json="$(curl -fsS "${NGROK_API_URL}" 2>/dev/null || true)"
    if [ -n "${api_json}" ]; then
        url="$(printf '%s' "${api_json}" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(next((t.get("public_url","") for t in data.get("tunnels", []) if t.get("public_url","").startswith("https://")), ""))' 2>/dev/null || true)"
        if [ -n "${url}" ]; then
            break
        fi
    fi
    sleep 1
done

if [ -z "${url}" ]; then
    echo "No pude obtener la URL publica de ngrok."
    echo "Revisa ${LOG_FILE}"
    exit 1
fi

printf '%s\n' "${url}" > "${URL_FILE}"
"${SCRIPT_DIR}/set_public_base_url.sh" "${url}" >/dev/null

echo "ngrok activo: ${url}"
echo "Redirect URI: ${url}/callback"
