#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PHOTO_DIR="/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/Fotos"
ALBUM_CREATOR="$SCRIPT_DIR/facebook_album_web_auto.py"
UPLOADER_DIR="$SCRIPT_DIR"
UPLOADER="$UPLOADER_DIR/album_diario.py"
UPLOADER_PYTHON="python3"
WEB_PYTHON="python3"

finish() {
  local exit_code=$?
  echo ""
  if [[ $exit_code -eq 0 ]]; then
    echo "Proceso terminado correctamente."
  else
    echo "Proceso detenido con error: $exit_code"
  fi
  read -r -p "Presiona Enter para salir..."
  exit "$exit_code"
}
trap finish EXIT

echo "============================================================"
echo "FACEBOOK - ALBUMES + SUBIDA AUTOMATICA"
echo "============================================================"
echo "Carpeta unica : $PHOTO_DIR"
echo "Navegador     : Microsoft Edge Flatpak"
echo "Modo          : crea albumes por web y luego sube fotos"
echo "============================================================"

if [[ ! -d "$PHOTO_DIR" ]]; then
  echo "ERROR: no existe la carpeta de fotos:"
  echo "$PHOTO_DIR"
  exit 1
fi

if [[ ! -f "$ALBUM_CREATOR" ]]; then
  echo "ERROR: no existe el creador web:"
  echo "$ALBUM_CREATOR"
  exit 1
fi

if [[ ! -f "$UPLOADER" ]]; then
  echo "ERROR: no existe el uploader:"
  echo "$UPLOADER"
  exit 1
fi

echo ""
echo "[1/2] Creando albumes faltantes en Facebook por Edge..."
"$WEB_PYTHON" "$ALBUM_CREATOR" \
  --browser edge \
  --placeholder \
  --continue-on-error

echo ""
echo "[2/2] Subiendo fotos a los albumes confirmados..."
cd "$UPLOADER_DIR"
"$UPLOADER_PYTHON" "$UPLOADER"
