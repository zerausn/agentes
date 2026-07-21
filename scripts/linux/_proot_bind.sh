#!/bin/bash
# _proot_bind.sh
# Detectar la ruta real del almacenamiento externo (varía según el dispositivo y versión de Android)
# y proveer PROOT_BIND_ARGS para montar correctamente dentro del proot como /sdcard.
#
# Uso en otros scripts:
#   source "$(dirname "$0")/_proot_bind.sh"
#   "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" ...

REAL_SDCARD=""
for _candidate in \
    "/storage/emulated/0" \
    "/data/media/0" \
    "/mnt/user/0/primary" \
    "/sdcard"; do
    if [ -d "$_candidate/Antigravity" ] || [ -d "$_candidate/DCIM" ] || [ -d "$_candidate/Download" ]; then
        REAL_SDCARD="$_candidate"
        break
    fi
done

PROOT_BIND_ARGS=()
if [ -n "$REAL_SDCARD" ] && [ "$REAL_SDCARD" != "/sdcard" ]; then
    PROOT_BIND_ARGS+=(--bind "${REAL_SDCARD}:/sdcard")
fi

# Bind mount ADB keys desde Termux hacia /root/.android del proot
# para que adb -s 127.0.0.1:5555 funcione sin re-autorizar.
TERMUX_HOME="/data/data/com.termux/files/home"
ADB_KEY_SRC="$TERMUX_HOME/.android"
ADB_KEY_DST="/root/.android"
if [ -d "$ADB_KEY_SRC" ]; then
    PROOT_BIND_ARGS+=(--bind "$ADB_KEY_SRC:$ADB_KEY_DST")
fi
