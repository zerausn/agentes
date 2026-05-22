#!/data/data/com.termux/files/usr/bin/bash
set -e

export HOME="/data/data/com.termux/files/home"
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

mkdir -p "$HOME/.shortcuts"
cd "$HOME/.shortcuts"

clear
printf 'Directorio actual: %s\n\n' "$PWD"
ls -la
printf '\nYa estas dentro de ~/.shortcuts.\n'
printf 'Puedes revisar, editar o ejecutar scripts desde aqui.\n\n'

exec /data/data/com.termux/files/usr/bin/bash -l
