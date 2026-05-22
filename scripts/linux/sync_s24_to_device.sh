#!/bin/bash
# ============================================================
# sync_s24_to_device.sh — Sincroniza carpetas del S24 a otro
# dispositivo Android vía ADB (streaming directo sin almacenamiento
# intermedio en el PC)
#
# Uso:
#   ./sync_s24_to_device.sh <SERIAL_DESTINO> [carpetas...]
#
# Ejemplos:
#   ./sync_s24_to_device.sh 34237840310037S
#   ./sync_s24_to_device.sh 34237840310037S crudos_pendientes teasers_pendientes
#   ./sync_s24_to_device.sh 34237840310037S --list
#
# Nota: El S24 (origen) debe estar conectado por ADB.
# ============================================================
set -euo pipefail

SERIAL_S24="RFCX91HV4GD"
STORAGE_ROOT="/sdcard/Antigravity"
DEST_DEVICE="${1:-}"
ESTIMATED_SPEED_MBs=30

# Carpetas prioritarias con tamaño estimado (GB)
declare -A FOLDERS
FOLDERS[teasers_pendientes]="10"
FOLDERS[crudos_pendientes]="30"
FOLDERS[agentes]="0.134"
FOLDERS[subidos_a_facebook]="11"
FOLDERS[videos_subidos_exitosamente]="0"

usage() {
    echo "Uso: $0 <SERIAL_DESTINO> [carpetas...]"
    echo ""
    echo "Carpetas disponibles:"
    for f in "${!FOLDERS[@]}"; do
        echo "  $f (~${FOLDERS[$f]} GB)"
    done
    echo ""
    echo "Ejemplo: $0 34237840310037S teasers_pendientes crudos_pendientes"
    exit 1
}

progress_report() {
    local folder="$1"
    local dest_device="$2"
    local start_time="$3"

    while true; do
        sleep 300  # 5 minutos
        local elapsed=$(( $(date +%s) - start_time ))
        local dest_size=$(adb -s "$dest_device" shell "du -sb /sdcard/Antigravity/$folder 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "0")
        local src_size=$(adb -s "$SERIAL_S24" shell "du -sb /sdcard/Antigravity/$folder 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "1")
        local src_size_mb=$(( src_size / 1048576 ))
        local dest_size_mb=$(( dest_size / 1048576 ))
        local pct=0
        [ "$src_size" -gt 0 ] && pct=$(( dest_size * 100 / src_size ))
        local elapsed_min=$(( elapsed / 60 ))

        echo "[$(date '+%H:%M:%S')] $folder: ${dest_size_mb}MB / ${src_size_mb}MB (${pct}%) — ${elapsed_min}min transcurridos"
    done
}

if [ -z "$DEST_DEVICE" ]; then
    echo "ERROR: Especifica el serial del dispositivo destino."
    echo ""
    usage
fi

if [ "$DEST_DEVICE" = "--list" ]; then
    echo "Carpetas en /sdcard/Antigravity del S24 ($SERIAL_S24):"
    adb -s "$SERIAL_S24" shell "du -sh /sdcard/Antigravity/*/ 2>/dev/null | sort -rh"
    exit 0
fi

# Verificar conexión S24
if ! adb devices | grep -q "$SERIAL_S24"; then
    echo "ERROR: S24 ($SERIAL_S24) no conectado"
    exit 1
fi

# Verificar conexión destino
if ! adb devices | grep -q "$DEST_DEVICE"; then
    echo "ERROR: Destino ($DEST_DEVICE) no conectado"
    exit 1
fi

# Verificar espacio en destino
DEST_SPACE=$(adb -s "$DEST_DEVICE" shell "df -k /sdcard 2>/dev/null | tail -1 | awk '{print \$4}'" 2>/dev/null || echo "0")
DEST_SPACE_GB=$(( DEST_SPACE / 1048576 ))
echo "=== S24 -> $DEST_DEVICE ==="
echo "Origen:  $SERIAL_S24 (/sdcard/Antigravity)"
echo "Destino: $DEST_DEVICE (${DEST_SPACE_GB} GB libres)"
echo ""

# Determinar carpetas a copiar
TARGETS=()
if [ $# -gt 1 ]; then
    shift
    TARGETS=("$@")
else
    for f in teasers_pendientes crudos_pendientes; do
        TARGETS+=("$f")
    done
fi

echo "Carpetas a copiar: ${TARGETS[*]}"
echo ""

for folder in "${TARGETS[@]}"; do
    # Saltar carpetas que no existen en origen
    SRC_EXISTS=$(adb -s "$SERIAL_S24" shell "test -d /sdcard/Antigravity/$folder && echo 1 || echo 0" 2>/dev/null || echo "0")
    if [ "$SRC_EXISTS" = "0" ]; then
        echo "[SKIP] $folder — no existe en origen"
        continue
    fi

    # Calcular tamaño
    SRC_SIZE_BYTES=$(adb -s "$SERIAL_S24" shell "du -sb /sdcard/Antigravity/$folder 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "0")
    SRC_SIZE_MB=$(( SRC_SIZE_BYTES / 1048576 ))
    SRC_SIZE_GB=$(( SRC_SIZE_MB / 1024 ))
    EST_SECONDS=$(( SRC_SIZE_BYTES / (ESTIMATED_SPEED_MBs * 1048576) ))
    EST_MIN=$(( EST_SECONDS / 60 ))

    echo "----------------------------------------"
    echo "Transferencia: $folder"
    echo "  Tamaño: ${SRC_SIZE_GB}GB (${SRC_SIZE_MB}MB)"
    echo "  ETA: ~${EST_MIN} minutos a ${ESTIMATED_SPEED_MBs}MB/s"
    echo "----------------------------------------"

    # Verificar espacio
    if [ "$SRC_SIZE_GB" -gt "$DEST_SPACE_GB" ]; then
        echo "[SKIP] $folder — requiere ${SRC_SIZE_GB}GB, solo hay ${DEST_SPACE_GB}GB libres"
        ESTIMATED_SPEED_MBs=$(( ESTIMATED_SPEED_MBs - 2 ))
        [ "$ESTIMATED_SPEED_MBs" -lt 5 ] && ESTIMATED_SPEED_MBs=5
        continue
    fi

    # Crear carpeta destino si no existe
    adb -s "$DEST_DEVICE" shell "mkdir -p /sdcard/Antigravity/$folder" 2>/dev/null || true

    # Iniciar reporte de progreso en background
    START_TIME=$(date +%s)
    progress_report "$folder" "$DEST_DEVICE" "$START_TIME" &
    PROGRESS_PID=$!

    # Transferir en streaming directo S24 -> PC -> Destino
    echo "  Iniciando transferencia..."
    adb -s "$SERIAL_S24" shell "tar cz -C /sdcard/Antigravity $folder 2>/dev/null" | \
        adb -s "$DEST_DEVICE" shell "cd /sdcard/Antigravity && tar xz 2>/dev/null; echo TRANSFER_DONE=\$?"

    kill "$PROGRESS_PID" 2>/dev/null || true

    # Verificar resultado
    DEST_SIZE=$(adb -s "$DEST_DEVICE" shell "du -sh /sdcard/Antigravity/$folder 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "0")
    echo "  $folder transferido: $DEST_SIZE"

    # Actualizar espacio disponible
    DEST_SPACE=$(adb -s "$DEST_DEVICE" shell "df -k /sdcard 2>/dev/null | tail -1 | awk '{print \$4}'" 2>/dev/null || echo "0")
    DEST_SPACE_GB=$(( DEST_SPACE / 1048576 ))
    echo "  Espacio restante: ${DEST_SPACE_GB}GB"

    # Ajustar velocidad estimada basado en tiempo real
    END_TIME=$(date +%s)
    ELAPSED=$(( END_TIME - START_TIME ))
    if [ "$ELAPSED" -gt 0 ]; then
        ACTUAL_SPEED=$(( SRC_SIZE_BYTES / ELAPSED / 1048576 ))
        [ "$ACTUAL_SPEED" -gt 0 ] && ESTIMATED_SPEED_MBs=$ACTUAL_SPEED
    fi

    echo ""
done

echo "=== Sincronización completada ==="
echo "Resumen final:"
for folder in "${TARGETS[@]}"; do
    DEST_SIZE=$(adb -s "$DEST_DEVICE" shell "du -sh /sdcard/Antigravity/$folder 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "N/A")
    echo "  $folder: $DEST_SIZE"
done
