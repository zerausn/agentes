#!/bin/bash
# sync_to_note9.sh
# Sincroniza el codigo TikTok mas reciente al Note9 via ADB
# Uso: bash sync_to_note9.sh [IP_DEL_NOTE9]
# Ejemplo: bash sync_to_note9.sh 192.168.0.100
set -euo pipefail

NOTE9_IP="${1:-}"
if [ -z "$NOTE9_IP" ]; then
    # Intentar detectar Note9 en la red
    echo "Buscando Note9 en la red..."
    NOTE9_IP=$(arp -a 2>/dev/null | grep -i "samsung\|sm-n960\|n960" | head -1 | grep -oP '\(\K[^)]+' || true)
    if [ -z "$NOTE9_IP" ]; then
        echo "Uso: bash sync_to_note9.sh <IP_DEL_NOTE9>"
        echo "Ejemplo: bash sync_to_note9.sh 192.168.0.100"
        exit 1
    fi
    echo "Note9 detectado en: $NOTE9_IP"
fi

echo "=============================================="
echo "  SINCRONIZANDO TIKTOK UPLOADER → NOTE9"
echo "  IP: $NOTE9_IP"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

AGENTES_DIR="/home/zerausn/Documents/Antigravity/agentes"
TIKTOK_DIR="$AGENTES_DIR/tiktok_uploader"
REMOTE_TIKTOK_DIR="/sdcard/Antigravity/agentes/tiktok_uploader"
REMOTE_HOME="/data/data/com.termux/files/home/agentes/tiktok_uploader"

# 1. Conectar ADB
echo ""
echo "[1/5] Conectando ADB a $NOTE9_IP:5555..."
adb connect "$NOTE9_IP:5555" 2>&1 || true
sleep 2
if ! adb devices | grep -q "$NOTE9_IP"; then
    echo "ERROR: No se pudo conectar a $NOTE9_IP"
    echo "Verifica que el Note9 tiene ADB WiFi activado:"
    echo "  1. Conecta via USB: adb tcpip 5555"
    echo "  2. Desconecta USB y ejecuta este script de nuevo"
    exit 1
fi
echo "  Conectado."

# 2. Push archivos al sdcard
echo ""
echo "[2/5] Copiando archivos a /sdcard/..."
adb shell mkdir -p "$REMOTE_TIKTOK_DIR" "$REMOTE_TIKTOK_DIR/docs" "$REMOTE_TIKTOK_DIR/templates" "$REMOTE_TIKTOK_DIR/termux" 2>/dev/null || true

ARCHIVOS_PY=(
    "tiktok_evacuador_720.py"
    "app.py"
    "config.py"
    "requirements.txt"
    ".env.local"
)

for f in "${ARCHIVOS_PY[@]}"; do
    if [ -f "$TIKTOK_DIR/$f" ]; then
        echo "  Push: $f"
        adb push "$TIKTOK_DIR/$f" "$REMOTE_TIKTOK_DIR/$f" >/dev/null
    fi
done

# Templates
echo "  Push: templates/"
for tmpl in "$TIKTOK_DIR/templates"/*.html; do
    adb push "$tmpl" "$REMOTE_TIKTOK_DIR/templates/" >/dev/null 2>&1 || true
done

# Termux scripts
echo "  Push: termux/"
for f in "$TIKTOK_DIR/termux"/*.sh; do
    name=$(basename "$f")
    adb push "$f" "$REMOTE_TIKTOK_DIR/termux/$name" >/dev/null 2>&1 || true
done

# Docs
echo "  Push: docs/"
for f in "$TIKTOK_DIR/docs"/*.md "$TIKTOK_DIR/docs"/*.sh 2>/dev/null; do
    [ -f "$f" ] || continue
    adb push "$f" "$REMOTE_TIKTOK_DIR/docs/" >/dev/null 2>&1 || true
done

# Widget y vigil
WIDGETS_DIR="$AGENTES_DIR/termux_widgets"
if [ -f "$WIDGETS_DIR/6_SUBIR_TIKTOK720.sh" ]; then
    echo "  Push: widget"
    adb push "$WIDGETS_DIR/6_SUBIR_TIKTOK720.sh" "/sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh" >/dev/null 2>&1 || true
fi

SCRIPTS_LINUX_DIR="$AGENTES_DIR/scripts/linux"
for f in "vigia_tiktok720_termux.sh" "_proot_bind.sh"; do
    if [ -f "$SCRIPTS_LINUX_DIR/$f" ]; then
        echo "  Push: scripts/linux/$f"
        adb push "$SCRIPTS_LINUX_DIR/$f" "/sdcard/Antigravity/scripts/linux/$f" >/dev/null 2>&1 || true
    fi
done

# 3. Copiar desde sdcard al home de Termux
echo ""
echo "[3/5] Copiando a Termux home..."
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "
    mkdir -p '$REMOTE_HOME' '$REMOTE_HOME/docs' '$REMOTE_HOME/templates' '$REMOTE_HOME/termux'
    cp -r '$REMOTE_TIKTOK_DIR/'* '$REMOTE_HOME/' 2>/dev/null || cp -r '$REMOTE_TIKTOK_DIR/.' '$REMOTE_HOME/' 2>/dev/null

    # Copiar widget al shortcut
    mkdir -p ~/.shortcuts
    if [ -f '$REMOTE_TIKTOK_DIR/../termux_widgets/6_SUBIR_TIKTOK720.sh' ]; then
        cp '$REMOTE_TIKTOK_DIR/../termux_widgets/6_SUBIR_TIKTOK720.sh' ~/.shortcuts/6_SUBIR_TIKTOK720.sh
    elif [ -f /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh ]; then
        cp /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh ~/.shortcuts/6_SUBIR_TIKTOK720.sh
    fi

    # Copiar scripts/linux
    mkdir -p ~/agentes/scripts/linux
    for f in vigia_tiktok720_termux.sh _proot_bind.sh; do
        [ -f /sdcard/Antigravity/scripts/linux/\$f ] && cp /sdcard/Antigravity/scripts/linux/\$f ~/agentes/scripts/linux/\$f
    done

    chmod +x ~/.shortcuts/6_SUBIR_TIKTOK720.sh ~/agentes/scripts/linux/vigia_tiktok720_termux.sh
    echo '  Copiado a Termux home: OK'
"

# 4. Verificar
echo ""
echo "[4/5] Verificando archivos en Note9..."
echo "--- tiktok_uploader/ ---"
adb shell run-as com.termux ls -la "$REMOTE_HOME/" 2>/dev/null || echo "  (error listando)"
echo "--- termux_widgets/ ---"
adb shell ls -la /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh 2>/dev/null || echo "  (widget no encontrado)"
echo "--- scripts/linux/ ---"
adb shell ls -la /sdcard/Antigravity/scripts/linux/ 2>/dev/null || echo "  (scripts no encontrados)"

# 5. Ejecutar diagnostico
echo ""
echo "[5/5] Ejecutando diagnostico..."
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "
    bash /sdcard/Antigravity/agentes/tiktok_uploader/termux/diagnostico_tiktok.sh \
        2>&1 | tee /sdcard/Antigravity/widget_logs/diagnostico_tiktok.log
" || adb shell "bash /data/data/com.termux/files/home/agentes/tiktok_uploader/termux/diagnostico_tiktok.sh 2>&1" || true

echo ""
echo "=============================================="
echo "  SINCRONIZACION COMPLETADA"
echo "  Log: /sdcard/Antigravity/widget_logs/diagnostico_tiktok.log"
echo "=============================================="
echo ""
echo "Para iniciar el widget TikTok manualmente:"
echo "  adb shell monkey -p com.termux -c android.intent.category.LAUNCHER 1"
echo "  (luego ejecutar el widget 6_SUBIR_TIKTOK720 desde Termux Widget)"
echo ""
echo "Para probar dry-run directamente:"
echo "  adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \\"
echo "    'cd ~/agentes/tiktok_uploader && python3 tiktok_evacuador_720.py --dry-run --open-next'"
