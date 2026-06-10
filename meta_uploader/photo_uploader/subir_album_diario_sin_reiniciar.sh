#!/usr/bin/env bash
set -euo pipefail

# Apunta siempre al repo, sin importar desde donde se ejecute este .sh
REPO_DIR="/home/zerausn/Documents/Antigravity/agentes/meta_uploader/photo_uploader"
PHOTO_DIR="/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/Fotos"
ALBUM_CREATOR="$REPO_DIR/facebook_album_web_auto.py"
UPLOADER="$REPO_DIR/album_diario.py"

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
echo "FACEBOOK - ALBUMES + SUBIDA AUTOMATICA (sin reiniciar Edge)"
echo "============================================================"
echo "Carpeta fotos : $PHOTO_DIR"
echo "Navegador     : Microsoft Edge Flatpak (ya abierto)"
echo "Modo          : detecta albumes faltantes y sube fotos"
echo "============================================================"

if [[ ! -d "$PHOTO_DIR" ]]; then
  echo "ERROR: no existe la carpeta de fotos:"
  echo "$PHOTO_DIR"
  exit 1
fi

if [[ ! -f "$ALBUM_CREATOR" ]]; then
  echo "ERROR: no existe el creador web en el repo:"
  echo "$ALBUM_CREATOR"
  exit 1
fi

if [[ ! -f "$UPLOADER" ]]; then
  echo "ERROR: no existe el uploader en el repo:"
  echo "$UPLOADER"
  exit 1
fi

# Verificar si hay albumes faltantes antes de abrir Edge
echo ""
echo "[1/2] Verificando albumes faltantes..."
FALTANTES=$(python3 "$ALBUM_CREATOR" --dry-run 2>&1 | grep "Albumes faltantes:" | awk '{print $NF}')

if [[ "$FALTANTES" == "0" || -z "$FALTANTES" ]]; then
  echo "Todos los albumes ya existen en Facebook. No es necesario abrir Edge."
else
  echo "Faltan $FALTANTES albumes. Abriendo Edge para crearlos..."
  python3 "$ALBUM_CREATOR" \
    --browser edge \
    --placeholder \
    --continue-on-error
fi

echo ""
echo "[2/2] Subiendo fotos a los albumes confirmados..."
cd "$REPO_DIR"
python3 "$UPLOADER"
