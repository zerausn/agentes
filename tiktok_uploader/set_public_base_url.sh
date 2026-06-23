#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 https://tu-url-publica"
    exit 1
fi

base_url="${1%/}"
env_file="${SCRIPT_DIR}/.env.local"

cat > "${env_file}" <<EOF
PUBLIC_BASE_URL=${base_url}
REDIRECT_URI=${base_url}/callback
PORT=8080
EOF

echo "Actualizado ${env_file}"
echo "Redirect URI: ${base_url}/callback"
