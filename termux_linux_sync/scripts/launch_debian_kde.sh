#!/data/data/com.termux/files/usr/bin/bash
echo "[KDE] 1. Purgando procesos..."
pkill -9 -f termux-x11 2>/dev/null || true
pkill -9 -f proot-distro 2>/dev/null || true
rm -rf /data/data/com.termux/files/usr/tmp/.X11-unix/X0 2>/dev/null || true

echo "[KDE] 2. Servidor X11..."
termux-x11 :0 -ac &
while [ ! -e /data/data/com.termux/files/usr/tmp/.X11-unix/X0 ]; do sleep 1; done
am start -n com.termux.x11/com.termux.x11.MainActivity
sleep 2

echo "[KDE] 3. Iniciando Debian (Extreme KDE Hardening)..."
proot-distro login debian --user root --shared-tmp -- /bin/bash -c "
  export DISPLAY=:0
  export HOME=/root
  # Saneado de Rutas de Socket Qt6/Plasma6
  export XDG_RUNTIME_DIR=/tmp/runtime-root
  mkdir -p \$XDG_RUNTIME_DIR
  chmod 700 \$XDG_RUNTIME_DIR
  
  export XCURSOR_THEME=Adwaita
  export XCURSOR_SIZE=24
  
  # Desactivación de SHM para evitar inundación de logs y latencia
  export QT_X11_NO_MITSHM=1
  export _X11_NO_MITSHM=1
  
  unset LD_PRELOAD
  unset LD_LIBRARY_PATH
  
  xsetroot -cursor_name left_ptr || true
  
  echo \"[KDE] Lanzando dbus-run-session con Plasma...\"
  dbus-run-session -- /usr/bin/startplasma-x11
"
echo "=== SESIÓN FINALIZADA ==="
sleep 15
