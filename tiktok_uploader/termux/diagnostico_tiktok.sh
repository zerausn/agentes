#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# Diagnostico TikTok Note9
# Verifica ADB local, TikTok app, UI dump, y permisos
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
ADB_SERIAL="127.0.0.1:5555"
TIKTOK_PKG="com.zhiliaoapp.musically"
STATE_DIR="/sdcard/Antigravity/.state"
SOURCE_DIR="/sdcard/Antigravity/subidos a facebbok"

echo "=============================================="
echo "  DIAGNOSTICO TIKTOK — NOTE9"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

# 1. Verificar ADB
echo ""
echo "[1/8] ADB local..."
if command -v adb >/dev/null 2>&1; then
    echo "  adb binario: OK ($(adb --version 2>&1 | head -1))"
else
    echo "  adb binario: FALTA — Instala: pkg install android-tools"
fi

adb connect "$ADB_SERIAL" >/dev/null 2>&1 || true
if adb devices | awk -v s="$ADB_SERIAL" '$1==s && $2=="device" {found=1} END{exit(found?0:1)}'; then
    echo "  ADB conectado: OK ($ADB_SERIAL)"
else
    echo "  ADB conectado: FALLO"
    echo "  Verifica que 'adb tcpip 5555' se ejecuto en el Note9"
fi

# 2. Verificar TikTok instalado
echo ""
echo "[2/8] TikTok app..."
TIKTOK_CHECK=$(adb shell "pm list packages $TIKTOK_PKG" 2>/dev/null || echo "")
if echo "$TIKTOK_CHECK" | grep -q "$TIKTOK_PKG"; then
    echo "  TikTok instalado: OK"
else
    echo "  TikTok instalado: FALTA — package $TIKTOK_PKG no encontrado"
    echo "  Buscando packages TikTok..."
    adb shell "pm list packages | grep -i tiktok" 2>/dev/null || echo "  (ninguno)"
fi

# 3. Verificar screen size
echo ""
echo "[3/8] Resolucion pantalla..."
SCREEN_INFO=$(adb shell wm size 2>/dev/null || echo "fallo")
echo "  $SCREEN_INFO"
SCREEN_OVERRIDE=$(adb shell wm size 2>/dev/null | grep "Override" || echo "sin override")
echo "  $SCREEN_OVERRIDE"

# 4. Verificar wake + unlock
echo ""
echo "[4/8] Pantalla activa..."
SCREEN_STATE=$(adb shell dumpsys power 2>/dev/null | grep "mScreenOn\|Display Power" | head -1 || echo "desconocido")
echo "  Estado: $SCREEN_STATE"
adb shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true
sleep 1
adb shell input swipe 500 1700 500 500 350 2>/dev/null || true
sleep 1
SCREEN_STATE2=$(adb shell dumpsys power 2>/dev/null | grep "mScreenOn\|Display Power" | head -1 || echo "")
echo "  Despues de wake+swipe: $SCREEN_STATE2"

# 5. Verificar uiautomator dump
echo ""
echo "[5/8] uiautomator dump..."
mkdir -p "$STATE_DIR"
adb shell rm -f "$STATE_DIR/tiktok_ui.xml" 2>/dev/null || true
DUMP_RESULT=$(adb shell uiautomator dump "$STATE_DIR/tiktok_ui.xml" 2>&1 || echo "fallo")
echo "  dump: $DUMP_RESULT"
sleep 1
DUMP_SIZE=$(adb shell stat -c%s "$STATE_DIR/tiktok_ui.xml" 2>/dev/null || echo 0)
echo "  XML size: ${DUMP_SIZE} bytes"
if [ "$DUMP_SIZE" -gt 100 ]; then
    echo "  UI dump: FUNCIONAL"
else
    echo "  UI dump: FALLO (XML muy pequeno o vacio)"
fi

# 6. Verificar MediaStore query
echo ""
echo "[6/8] MediaStore query..."
echo "  Source dir: $SOURCE_DIR"
MS_RESULT=$(adb shell "content query --uri content://media/external/video/media --projection _data --where \"_data LIKE '%subidos a facebbok%'\" --sort \"date_added DESC, _id DESC\" 2>&1" || echo "fallo")
echo "  Resultado:"
echo "$MS_RESULT" | head -10
MS_COUNT=$(echo "$MS_RESULT" | grep -c "_data=" 2>/dev/null || echo 0)
echo "  Videos encontrados: $MS_COUNT"

# 7. Videos pendientes
echo ""
echo "[7/8] Videos pendientes..."
if [ -d "$SOURCE_DIR" ]; then
    PENDING=$(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \) 2>/dev/null | wc -l)
    echo "  Pendientes: $PENDING"
    find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \) -printf "%T@ %s %f\n" 2>/dev/null | sort -rn | head -5 || ls -lt "$SOURCE_DIR" 2>/dev/null | head -5
else
    echo "  Directorio $SOURCE_DIR: NO EXISTE"
fi

# 8. Directorios de estado
echo ""
echo "[8/8] Directorios de estado..."
for d in "/sdcard/Antigravity" "/sdcard/Antigravity/.state" "/sdcard/Antigravity/subidos a facebbok" "/sdcard/Antigravity/subidos a tiktok"; do
    if [ -d "$d" ]; then
        echo "  OK: $d"
    else
        echo "  FALTA: $d"
    fi
done

echo ""
echo "=============================================="
echo "  DIAGNOSTICO COMPLETADO"
echo "=============================================="
