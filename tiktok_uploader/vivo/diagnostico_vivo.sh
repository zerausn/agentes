#!/bin/bash
# diagnostico_vivo.sh
# Diagnostico del clon TikTok VIVO V2058
# CLON ESPECIFICO PARA VIVO — NO USAR EN NOTE9
# Uso: bash diagnostico_vivo.sh [SERIAL]
set -euo pipefail

VIVO_SERIAL="${1:-34237840310037S}"
ADB_CMD="adb -s $VIVO_SERIAL"

echo "=============================================="
echo "  DIAGNOSTICO TIKTOK — VIVO V2058 (CLON)"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

echo ""
echo "[1/8] Conexion ADB..."
if $ADB_CMD get-state 2>/dev/null | grep -q "device"; then
    echo "  OK: $($ADB_CMD shell getprop ro.product.model 2>/dev/null) ($VIVO_SERIAL)"
    echo "  Android: $($ADB_CMD shell getprop ro.build.version.release 2>/dev/null)"
    echo "  Resolucion: $($ADB_CMD shell wm size 2>/dev/null)"
else
    echo "  FALLO: VIVO no conectado"
    adb devices -l
    exit 1
fi

echo ""
echo "[2/8] TikTok app..."
TIKTOK_PKG=$(adb -s "$VIVO_SERIAL" shell "pm list packages com.zhiliaoapp.musically" 2>/dev/null || echo "")
if echo "$TIKTOK_PKG" | grep -q "com.zhiliaoapp.musically"; then
    echo "  OK: TikTok instalado"
else
    echo "  FALTA: TikTok no instalado"
    adb -s "$VIVO_SERIAL" shell "pm list packages | grep -i tiktok" 2>/dev/null || echo "  (ninguno)"
fi

echo ""
echo "[3/8] Directorios Antigravity..."
for d in "/sdcard/Antigravity" "/sdcard/Antigravity/.state" "/sdcard/Antigravity/subidos a facebbok" "/sdcard/Antigravity/subidos a tiktok" "/sdcard/Antigravity/widget_logs"; do
    if $ADB_CMD shell "[ -d '$d' ]" 2>/dev/null; then
        echo "  OK: $d"
    else
        echo "  FALTA: $d"
    fi
done

echo ""
echo "[4/8] TikTok script en sdcard..."
if $ADB_CMD shell "ls /sdcard/Antigravity/agentes/tiktok_uploader/tiktok_evacuador_720.py" 2>/dev/null >/dev/null; then
    SIZE=$($ADB_CMD shell "stat -c%s /sdcard/Antigravity/agentes/tiktok_uploader/tiktok_evacuador_720.py" 2>/dev/null || echo "?")
    echo "  OK: tiktok_evacuador_720.py (${SIZE} bytes)"
else
    echo "  FALTA: no encontrado en sdcard"
fi

echo ""
echo "[5/8] TikTok script en Termux home..."
if $ADB_CMD shell run-as com.termux "ls /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py" 2>/dev/null >/dev/null; then
    echo "  OK: deployado en termux home"
else
    echo "  FALTA: no deployado en termux home"
fi

echo ""
echo "[6/8] Widget y vigia..."
$ADB_CMD shell "ls -la /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh" 2>/dev/null && echo "  Widget: OK" || echo "  Widget: FALTA"
$ADB_CMD shell "ls -la /sdcard/Antigravity/scripts/linux/vigia_vivo.sh" 2>/dev/null && echo "  Vigia: OK" || echo "  Vigia: FALTA"

echo ""
echo "[7/8] Videos pendientes..."
PENDING=$($ADB_CMD shell "find /sdcard/Antigravity/subidos\ a\ facebbok -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' \) 2>/dev/null | wc -l" 2>/dev/null || echo 0)
echo "  Pendientes: $PENDING"
PUBLISHED=$($ADB_CMD shell "find /sdcard/Antigravity/subidos\ a\ tiktok -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' \) 2>/dev/null | wc -l" 2>/dev/null || echo 0)
echo "  Publicados: $PUBLISHED"

echo ""
echo "[8/8] Dry-run (coordenadas)..."
$ADB_CMD shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "
    export TMPDIR=/data/data/com.termux/files/usr/tmp
    export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin
    export AGENTES_STORAGE_ROOT=/sdcard/Antigravity
    export TIKTOK_UI_BACKEND=adb
    export TIKTOK_ADB_SERIAL=$VIVO_SERIAL
    export TIKTOK_SHARE_METHOD=intent
    export TIKTOK_PUBLISH_MODE=direct
    export TIKTOK_POST_SETTLE_SECONDS=30
    timeout 30 python3 /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py --open-next --dry-run 2>&1 | grep -E 'MediaStore|Dry.run|Coordenadas|tap_scaled|Publicar|Editor|Siguiente'
" 2>/dev/null || echo "  (dry-run no ejecutado — puede ser primer deploy)"

echo ""
echo "=============================================="
echo "  DIAGNOSTICO VIVO COMPLETADO"
echo "=============================================="
echo ""
echo "Para ejecutar ciclo real:"
echo "  adb -s $VIVO_SERIAL shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \\"
echo "    'cd /data/data/com.termux/files/home/agentes/tiktok_uploader \\"
echo "     && export TIKTOK_POST_SETTLE_SECONDS=30 \\"
echo "     && timeout 180 python3 tiktok_evacuador_720.py --open-next'"
