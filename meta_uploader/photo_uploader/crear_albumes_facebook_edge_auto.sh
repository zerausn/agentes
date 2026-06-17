#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALBUM_CREATOR="$SCRIPT_DIR/facebook_album_web_auto.py"

python3 "$ALBUM_CREATOR" \
  --browser edge \
  --restart-edge \
  --placeholder \
  --continue-on-error
