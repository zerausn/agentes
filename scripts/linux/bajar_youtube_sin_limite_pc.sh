#!/usr/bin/env bash
# ============================================================
#  bajar_youtube_sin_limite_pc.sh
#  Script maestro del descargador SIN LÍMITE DE FECHA de YouTube
#  Versión PC — Parrot OS / Linux nativo (sin proot, sin Termux)
#
#  Equivalente a: bajar_youtube_sin_limite_termux.sh del S24
#  Lanzado por  : scripts/linux/5_BAJAR_YOUTUBE_SIN_LIMITE_PC.sh
#  o directamente desde terminal.
# ============================================================

set -euo pipefail

# ── Cargar NVM y PATH explícitamente ──────────
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="/home/zerausn/.local/bin:$PATH"

# ── Rutas PC ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
YOUTUBE_DIR="$AGENTES_DIR/youtube_uploader"
PYTHON_SCRIPT="$YOUTUBE_DIR/yt_downloader_lotes_sin_limite.py"
LOG_DIR="$AGENTES_DIR/logs"
SESSION_LOG="$LOG_DIR/5_BAJAR_YOUTUBE_SIN_LIMITE_PC.log"
LOCK_DIR="$HOME/.run/5_BAJAR_YOUTUBE_SIN_LIMITE_PC.lock"
VENV_DIR="$AGENTES_DIR/.venv"

# Destino de los crudos en el PC (disco duro local o NTFS)
# Prioridad: variable de entorno > disco de videos > home
if [ -n "${AGENTES_CRUDOS_DIR:-}" ]; then
    DEST_DIR="$AGENTES_CRUDOS_DIR"
elif [ -d "/mnt/Videos" ]; then
    DEST_DIR="/mnt/Videos/Antigravity/crudos"
elif [ -d "/media/zerausn/D69493CF9493B08B" ]; then
    DEST_DIR="/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/crudos"
else
    DEST_DIR="$HOME/Antigravity/crudos"
fi

mkdir -p "$LOG_DIR"
exec > >(tee -a "$SESSION_LOG") 2>&1

# ── Lock de instancia única ──────────────────────────────────
mkdir -p "$HOME/.run"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "[ERROR] Ya hay una ejecución activa de 5_BAJAR_YOUTUBE_SIN_LIMITE_PC (PID $old_pid)."
        echo "        Cierra esa sesión antes de lanzar otra."
        read -r -p "Enter para cerrar..."
        exit 1
    fi
    echo "[WARN] Lock anterior sin proceso activo; limpiando."
    rm -rf "$LOCK_DIR"
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "[ERROR] No se pudo crear el lock de ejecución."
        read -r -p "Enter para cerrar..."
        exit 1
    fi
fi
printf "%s\n" "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

echo "============================================================"
echo "  5_BAJAR_YOUTUBE_SIN_LIMITE — PC (Parrot OS)"
echo "  Todos los crudos públicos · Sin límite de fecha"
echo "============================================================"
echo ""

# ── Verificar dependencias ───────────────────────────────────
MISSING=0
for dep in python3 ffmpeg ffprobe yt-dlp node; do
    if ! command -v "$dep" &>/dev/null; then
        echo "[ERROR] Dependencia no encontrada: $dep"
        MISSING=1
    fi
done
if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "Instala las dependencias faltantes y vuelve a intentarlo."
    echo "  yt-dlp  → pip install yt-dlp"
    echo "  node    → https://nodejs.org"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# ── Verificar script Python ──────────────────────────────────
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "[ERROR] No existe el script Python:"
    echo "        $PYTHON_SCRIPT"
    echo "        Verifica que el repo esté correctamente clonado."
    read -r -p "Enter para cerrar..."
    exit 1
fi

# ── Activar entorno virtual Python ──────────────────────────
if [ -d "$VENV_DIR/bin" ]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    echo "[ENV] Usando venv: $VENV_DIR"
else
    echo "[WARN] No se encontró venv en $VENV_DIR"
    echo "       Usando Python del sistema. Si faltan paquetes:"
    echo "       cd $AGENTES_DIR && python3 -m venv .venv && source .venv/bin/activate"
    echo "       pip install -r $YOUTUBE_DIR/requirements.txt"
fi

# ── Variables de entorno para el script Python ───────────────
export AGENTES_DEVICE_NAME="${AGENTES_DEVICE_NAME:-PC_PARROT}"
export AGENTES_CRUDOS_DIR="$DEST_DIR"
export AGENTES_FFMPEG_PRESET="${AGENTES_FFMPEG_PRESET:-medium}"
export AGENTES_FFMPEG_CRF="${AGENTES_FFMPEG_CRF:-18}"
export AGENTES_FFMPEG_AUDIO_BITRATE="${AGENTES_FFMPEG_AUDIO_BITRATE:-192k}"

mkdir -p "$DEST_DIR"

echo "Dispositivo : $AGENTES_DEVICE_NAME"
echo "Destino     : $DEST_DIR"
echo "Log         : $SESSION_LOG"
echo ""
echo "Lanzando descargador..."
echo ""

# ── Ejecutar el downloader Python ────────────────────────────
python3 "$PYTHON_SCRIPT"

echo ""
echo "============================================================"
echo "  Descargador finalizado."
echo "  Log en: $SESSION_LOG"
echo "============================================================"
echo ""
read -r -p "Presiona Enter para cerrar..."
