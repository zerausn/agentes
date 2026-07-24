#!/bin/bash
# sync_to_vivo.sh — Sincroniza el codigo TikTok al VIVO V2058 via ADB USB
# CLON ESPECIFICO PARA VIVO — NO USAR EN NOTE9
# Android 13 (VIVO) restringe run-as com.termux para leer /sdcard/.
# Usa ADB forward + SSH para ejecutar comandos dentro de Termux.
# Uso: bash sync_to_vivo.sh [SERIAL]
# Ejemplo: bash sync_to_vivo.sh 34237840310037S
set -euo pipefail

VIVO_SERIAL="${1:-34237840310037S}"
SSH_PORT=8022
AGENTES_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
TIKTOK_DIR="$AGENTES_DIR/tiktok_uploader"
VIVO_DIR="$TIKTOK_DIR/vivo"
REMOTE_TIKTOK_DIR="/sdcard/Antigravity/agentes/tiktok_uploader"
ADB_CMD="adb -s $VIVO_SERIAL"
SSH_CMD="ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null localhost"

echo "=============================================="
echo "  SINCRONIZANDO TIKTOK UPLOADER → VIVO V2058"
echo "  Serial: $VIVO_SERIAL"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  CLON — NO AFECTA NOTE9"
echo "=============================================="

# Verificar conexion
echo ""
echo "[1/5] Verificando conexion VIVO..."
if ! $ADB_CMD get-state 2>/dev/null | grep -q "device"; then
    echo "ERROR: VIVO no conectado (serial: $VIVO_SERIAL)"
    echo "Dispositivos disponibles:"
    adb devices -l
    exit 1
fi
echo "  Conectado: $($ADB_CMD shell getprop ro.product.model 2>/dev/null || echo $VIVO_SERIAL)"
echo "  Android: $($ADB_CMD shell getprop ro.build.version.release 2>/dev/null || echo '?')"
echo "  Resolucion: $($ADB_CMD shell wm size 2>/dev/null || echo '?')"

# Push archivos a /sdcard/
echo ""
echo "[2/5] Copiando archivos a /sdcard/..."
$ADB_CMD shell mkdir -p "$REMOTE_TIKTOK_DIR" "$REMOTE_TIKTOK_DIR/docs" "$REMOTE_TIKTOK_DIR/termux" /sdcard/Antigravity/scripts/linux /sdcard/Antigravity/termux_widgets 2>/dev/null || true

echo "  Push: tiktok_evacuador_720.py"
$ADB_CMD push "$TIKTOK_DIR/tiktok_evacuador_720.py" "$REMOTE_TIKTOK_DIR/tiktok_evacuador_720.py" >/dev/null

echo "  Push: termux/deploy.sh"
$ADB_CMD push "$VIVO_DIR/termux/deploy.sh" "$REMOTE_TIKTOK_DIR/termux/deploy.sh" >/dev/null

echo "  Push: termux/vigia_vivo.sh"
$ADB_CMD push "$VIVO_DIR/termux/vigia_vivo.sh" "/sdcard/Antigravity/scripts/linux/vigia_vivo.sh" >/dev/null

echo "  Push: termux/widget_vivo.sh"
$ADB_CMD push "$VIVO_DIR/termux/widget_vivo.sh" "/sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh" >/dev/null

echo "  Push: SETUP.md + AGENTS.md + AI.md"
$ADB_CMD push "$VIVO_DIR/SETUP.md" "$REMOTE_TIKTOK_DIR/vivo/SETUP.md" >/dev/null 2>&1 || true
$ADB_CMD push "$VIVO_DIR/AGENTS.md" "$REMOTE_TIKTOK_DIR/vivo/AGENTS.md" >/dev/null 2>&1 || true
$ADB_CMD push "$VIVO_DIR/AI.md" "$REMOTE_TIKTOK_DIR/vivo/AI.md" >/dev/null 2>&1 || true

# ADB forward + SSH para deploy en Termux
echo ""
echo "[3/5] Configurando ADB forward para SSH..."
$ADB_CMD forward tcp:$SSH_PORT tcp:$SSH_PORT 2>/dev/null || true
if ! $SSH_CMD "echo OK" 2>/dev/null | grep -q OK; then
    echo "  SSH no disponible. Intentando deploy via /data/local/tmp..."
    # Fallback: copiar via /data/local/tmp
    $ADB_CMD shell cp "$REMOTE_TIKTOK_DIR/tiktok_evacuador_720.py" /data/local/tmp/tiktok_evacuador_720.py 2>/dev/null || true
    $ADB_CMD shell chmod 644 /data/local/tmp/tiktok_evacuador_720.py 2>/dev/null || true
    $ADB_CMD shell "run-as com.termux cp /data/local/tmp/tiktok_evacuador_720.py /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py" 2>/dev/null || true
    $ADB_CMD shell "run-as com.termux chmod +x /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py" 2>/dev/null || true
    echo "  Deploy via fallback completado."
else
    echo "  SSH conectado via ADB forward."
fi

# Deploy en Termux via SSH
echo ""
echo "[4/5] Ejecutando deploy en Termux VIVO..."
if $SSH_CMD "echo OK" 2>/dev/null | grep -q OK; then
    $SSH_CMD "export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin && \
        mkdir -p /data/data/com.termux/files/home/agentes/tiktok_uploader \
                /data/data/com.termux/files/home/agentes/scripts/linux && \
        cp /sdcard/Antigravity/agentes/tiktok_uploader/tiktok_evacuador_720.py \
           /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py && \
        cp /sdcard/Antigravity/scripts/linux/vigia_vivo.sh \
           /data/data/com.termux/files/home/agentes/scripts/linux/vigia_vivo.sh && \
        chmod +x /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py && \
        chmod +x /data/data/com.termux/files/home/agentes/scripts/linux/vigia_vivo.sh && \
        echo 'Deploy VIVO OK'" 2>&1
fi

# Verificar
echo ""
echo "[5/5] Verificando..."
echo "--- tiktok_uploader (sdcard) ---"
$ADB_CMD shell ls -la "$REMOTE_TIKTOK_DIR/tiktok_evacuador_720.py" 2>/dev/null || echo "  (no encontrado)"
echo "--- tiktok_uploader (termux home) ---"
$ADB_CMD shell "run-as com.termux ls -la /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py" 2>/dev/null || echo "  (no encontrado en termux home)"
echo "--- widget ---"
$ADB_CMD shell ls -la "/sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh" 2>/dev/null || echo "  (no encontrado)"
echo "--- vigia ---"
$ADB_CMD shell ls -la "/sdcard/Antigravity/scripts/linux/vigia_vivo.sh" 2>/dev/null || echo "  (no encontrado)"
echo ""
echo "=============================================="
echo "  SINCRONIZACION VIVO COMPLETADA"
echo "=============================================="
echo ""
echo "Para probar dry-run via SSH:"
echo "  adb -s $VIVO_SERIAL forward tcp:$SSH_PORT tcp:$SSH_PORT"
echo "  ssh -p $SSH_PORT localhost 'cd ~/agentes/tiktok_uploader && python3 tiktok_evacuador_720.py --dry-run --open-next'"
