#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${SCRIPT_DIR}/.run"
PID_FILE="${RUN_DIR}/flask.pid"
LOG_FILE="${RUN_DIR}/flask.log"
ENV_FILE="${SCRIPT_DIR}/.env.local"

if [ -f "${ENV_FILE}" ]; then
    set -a
    . "${ENV_FILE}"
    set +a
fi

PORT="${PORT:-8080}"
TUNNEL_PROVIDER="${TUNNEL_PROVIDER:-cloudflare}"

mkdir -p "${RUN_DIR}"

find_project_flask_pid() {
    while read -r pid args; do
        cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
        if [ "${cwd}" = "${SCRIPT_DIR}" ] && [[ "${args}" == *app.py* ]]; then
            echo "${pid}"
            return 0
        fi
    done < <(ps -eo pid=,args=)
    return 1
}

existing_pid="$(find_project_flask_pid || true)"
if [ -n "${existing_pid}" ]; then
    printf '%s\n' "${existing_pid}" > "${PID_FILE}"
fi

if [ -z "${existing_pid}" ]; then
    nohup "${SCRIPT_DIR}/run_flask.sh" > "${LOG_FILE}" 2>&1 &
    printf '%s\n' "$!" > "${PID_FILE}"
fi

for _ in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    echo "Flask no levanto correctamente. Revisa ${LOG_FILE}"
    exit 1
fi

echo "Flask activo en http://127.0.0.1:${PORT}"

case "${TUNNEL_PROVIDER}" in
    cloudflare)
        tunnel_script="${SCRIPT_DIR}/start_cloudflare_tunnel.sh"
        ;;
    ngrok)
        tunnel_script="${SCRIPT_DIR}/start_ngrok_tunnel.sh"
        ;;
    *)
        echo "Proveedor de tunel no soportado: ${TUNNEL_PROVIDER}"
        echo "Usa TUNNEL_PROVIDER=cloudflare o TUNNEL_PROVIDER=ngrok"
        exit 1
        ;;
esac

"${tunnel_script}" "${PORT}"
