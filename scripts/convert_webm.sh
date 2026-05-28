#!/data/data/com.termux/files/usr/bin/bash
# convert_webm.sh - Corre en Note 9 (Termux)
# Convierte .webm a .mp4 en crudos_pendientes automáticamente
# Ejecutar con: bash convert_webm.sh

CRUDOS="/sdcard/Antigravity/crudos_pendientes"
FFMPEG="/data/data/com.termux/files/usr/bin/ffmpeg"
LOG="/sdcard/Antigravity/convert_webm.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG"; echo "$1"; }

for webm in "$CRUDOS"/*.webm; do
    [ -f "$webm" ] || continue
    basename=$(basename "$webm" .webm)
    # Quitar espacios del nombre
    safename=$(echo "$basename" | tr ' ' '_')
    out="$CRUDOS/${safename}.mp4"

    # Si el .mp4 ya existe, saltear
    [ -f "$out" ] && log "SKIP $out ya existe" && continue

    log "Convirtiendo: $(basename "$webm") -> $(basename "$out")"
    $FFMPEG -y -i "$webm" -c:v libx264 -preset ultrafast -crf 28 \
            -c:a aac -movflags +faststart "$out" 2>> "$LOG"

    if [ $? -eq 0 ] && [ -f "$out" ]; then
        log "OK: $(basename "$out") ($(du -h "$out" | cut -f1))"
        rm -f "$webm"
        log "Eliminado: $(basename "$webm")"
    else
        log "ERROR convirtiendo $(basename "$webm")"
    fi
done
log "---"
