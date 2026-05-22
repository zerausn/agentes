#!/data/data/com.termux/files/usr/bin/bash
set -e

export HOME="/data/data/com.termux/files/home"
TARGET="$HOME/launch_debian_mate.sh"

if [ ! -x "$TARGET" ]; then
  echo "No existe o no es ejecutable: $TARGET"
  exit 1
fi

exec "$TARGET"
