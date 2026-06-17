#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${SCRIPT_DIR}/.run"

find_project_pid() {
    local pattern="$1"
    while read -r pid args; do
        local cwd
        cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
        if [ "${cwd}" = "${SCRIPT_DIR}" ] && [[ "${args}" == *"${pattern}"* ]]; then
            echo "${pid}"
            return 0
        fi
    done < <(ps -eo pid=,args=)
    return 1
}

stop_pid_file() {
    local pid_file="$1"
    if [ -f "${pid_file}" ]; then
        local pid
        pid="$(cat "${pid_file}")"
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
        rm -f "${pid_file}"
    fi
}

stop_pid_file "${RUN_DIR}/cloudflared.pid"
stop_pid_file "${RUN_DIR}/ngrok.pid"
stop_pid_file "${RUN_DIR}/flask.pid"
rm -f "${RUN_DIR}/public_url.txt"

extra_flask_pid="$(find_project_pid "app.py" || true)"
if [ -n "${extra_flask_pid}" ]; then
    kill "${extra_flask_pid}" 2>/dev/null || true
fi

echo "Stack detenido."
