#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TUNNEL_PROVIDER=ngrok "${SCRIPT_DIR}/start_demo_stack.sh" "$@"
