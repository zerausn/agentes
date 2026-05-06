#!/data/data/com.termux/files/usr/bin/bash
echo "[MATE] 1. Limpieza de procesos..."
pkill -9 -f termux-x11 2>/dev/null || true
pkill -9 -f proot-distro 2>/dev/null || true
rm -rf /data/data/com.termux/files/usr/tmp/.X11-unix/X0 2>/dev/null || true

echo "[MATE] 2. Servidor X11..."
termux-x11 :0 -ac &
while [ ! -e /data/data/com.termux/files/usr/tmp/.X11-unix/X0 ]; do sleep 1; done
am start -n com.termux.x11/com.termux.x11.MainActivity
sleep 2

echo "[MATE] 3. Iniciando Debian (Premium Polish)..."
proot-distro login debian --user root --shared-tmp -- /bin/bash -c "
  export DISPLAY=:0
  export HOME=/root
  export XCURSOR_THEME=Adwaita
  export XCURSOR_SIZE=24
  # Optimización de SHM (Evita errores de adjunto en logs)
  export QT_X11_NO_MITSHM=1
  export _X11_NO_MITSHM=1
  export MITSHM=OFF
  
  unset LD_PRELOAD
  unset LD_LIBRARY_PATH
  
  # Inicialización robusta de DBus
  if [ -z \"\$DBUS_SESSION_BUS_ADDRESS\" ]; then
    eval \$(dbus-launch --sh-syntax)
  fi
  
  xsetroot -cursor_name left_ptr || true
  
  echo \"[MATE] Lanzando sesión...\"
  /usr/bin/mate-session
"
echo "=== SESIÓN FINALIZADA ==="
sleep 15
