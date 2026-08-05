#!/data/data/com.termux/files/usr/bin/bash
# 0_RENOVAR_REPO — Actualiza el repo y recrea todos los shortcuts/widgets
# Widget Termux: ~/.shortcuts/0_RENOVAR_REPO.sh

set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
REPO_DIR="$TERMUX_HOME/agentes"
BOOTSTRAP="$REPO_DIR/scripts/linux/bootstrap_termux_arm64.sh"

echo "=============================================="
echo "  0_RENOVAR_REPO — Antigravity S24"
echo "=============================================="
echo ""

# 1. Verificar que el repo existe
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[ERROR] No existe el repo en $REPO_DIR"
    echo "        Clona primero: git clone -b linux-arm64 <URL> ~/agentes"
    read -r -p "Enter para cerrar..."
    exit 1
fi

# 2. Git pull
echo "[1/2] Actualizando repo desde GitHub..."
cd "$REPO_DIR"

# Auto-detectar la rama actual (funciona en cualquier dispositivo: vivo-tiktok, linux-arm64, etc.)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "linux-arm64")
echo "  Rama actual: $CURRENT_BRANCH"

# Guardar los cambios locales si los hay (credentials, .env, etc. están en .gitignore)
git fetch origin "$CURRENT_BRANCH"

# Verificar si hay commits nuevos
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$CURRENT_BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "  Ya estás al día ($(git rev-parse --short HEAD))."
else
    echo "  Aplicando cambios: $LOCAL -> $REMOTE"
    git pull --ff-only "origin" "$CURRENT_BRANCH"
    echo "  [OK] Repo actualizado a $(git rev-parse --short HEAD)"
fi

echo ""

# 3. Re-ejecutar bootstrap para recrear todos los shortcuts
echo "[2/2] Recreando shortcuts y configuración..."
if [ ! -x "$BOOTSTRAP" ]; then
    chmod +x "$BOOTSTRAP"
fi

bash "$BOOTSTRAP" generic

echo ""
echo "=============================================="
echo "  [LISTO] Repo renovado y widgets recreados"
echo "  Commit: $(git -C $REPO_DIR rev-parse --short HEAD)"
echo "  Shortcuts en ~/.shortcuts/"
echo "=============================================="
echo ""
read -r -p "Enter para cerrar..."
