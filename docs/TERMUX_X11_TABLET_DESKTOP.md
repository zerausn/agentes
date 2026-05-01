# Debian Grafico Local en Tablet ARM64

## Alcance

Este documento describe el carril grafico local agregado sobre la rama
`linux-arm64` para usar Debian en una tablet Android "como si fuera un PC",
sin escribir comandos manuales en Termux para cada arranque.

Objetivo operativo:

- Termux como host local
- Debian dentro de `proot-distro`
- `XFCE` como escritorio
- `Termux:X11` como salida grafica local
- `Termux:Widget` como punto de entrada directo
- `TigerVNC` como fallback

## Componentes

### Android

- `Termux`
- `Termux:API`
- `Termux:Widget`
- `Termux:X11` app (`com.termux.x11/.MainActivity`)

### Termux

- `x11-repo`
- `termux-x11-nightly`
- `pulseaudio`
- `proot-distro`

### Debian (`debian-gui`)

- `xfce4`
- `xfce4-terminal`
- `dbus-x11`
- `xauth`
- `x11-utils`
- `xterm`
- `tigervnc-standalone-server`
- `tigervnc-tools`
- `psmisc`
- `curl`, `wget`, `git`, `ca-certificates`
- locale `en_US.UTF-8`
- usuario de escritorio `tablet`

## Scripts versionados

Todos los scripts viven en `scripts/linux/`:

- `install_debian_gui_termux.sh`
  - instala el stack grafico del lado Termux
  - crea el alias `debian-gui` para evitar el fallo del plugin oficial
    `debian` de `proot-distro` en `dpkg-reconfigure locales`
  - instala `XFCE` dentro de Debian
  - genera locale
  - crea el usuario `tablet`
  - crea widgets en `~/.shortcuts/`
- `start_debian_gui_termux.sh`
  - activa wakelock si existe
  - reinicia `pulseaudio`
  - abre la app `Termux:X11`
  - levanta `termux-x11 :1`
  - encadena la sesion Debian por `-xstartup`
- `start_debian_gui_session_termux.sh`
  - entra a `debian-gui` con `--shared-tmp`
  - exporta `DISPLAY=:1`
  - exporta `PULSE_SERVER=127.0.0.1`
  - crea `XDG_RUNTIME_DIR`
  - abre `xfce4-session` como usuario `tablet`
- `stop_debian_gui_termux.sh`
  - detiene `xfce4-session`, `xfwm4`, `xfdesktop4`, `termux-x11`,
    `tigervnc` y `pulseaudio`

## Widgets creados

El instalador deja estos accesos directos en `~/.shortcuts/`:

- `Debian_Grafico.sh`
- `Parar_Debian_Grafico.sh`

Flujo diario esperado:

1. tocar `Debian_Grafico`
2. se abre `Termux:X11`
3. sube `pulseaudio`
4. sube `termux-x11 :1`
5. entra `xfce4-session`

No hace falta abrir Termux ni escribir nada.

## Fallback por VNC

Tambien queda configurado:

- paquete `tigervnc-standalone-server`
- `~/.vnc/xstartup` para el usuario `tablet`

No es el camino principal, pero sirve como rescate si `Termux:X11` falla en un
modelo concreto o si se prefiere abrir el escritorio desde un viewer externo.

## Validacion realizada en tablet

Estado observado durante la configuracion real:

- `termux-x11-nightly` instalado en Termux
- `pulseaudio` instalado en Termux
- `debian-gui` instalado via `proot-distro`
- `xfce4`, `xfce4-session`, `xfce4-terminal`, `dbus-x11`,
  `tigervnc-standalone-server` instalados en Debian
- locale `en_US.UTF-8` generado
- usuario `tablet` creado
- widgets `Debian_Grafico.sh` y `Parar_Debian_Grafico.sh` creados

Prueba de arranque validada:

- `Termux:X11` tomó el foco en Android
- `pulseaudio` quedó vivo
- dentro de Debian aparecieron procesos:
  - `su - tablet`
  - `dbus-launch --exit-with-session xfce4-session`
  - `xfce4-session`

## Notas operativas

- El alias `debian-gui` existe porque el plugin oficial `debian` de
  `proot-distro` falló en el paso final de locales durante la instalacion en la
  tablet probada.
- El escritorio usa `DISPLAY=:1` para alinearse con el flujo documentado por
  `termux/termux-x11`.
- La parte de audio depende de `module-native-protocol-tcp` en `pulseaudio`.
- Si se quiere reiniciar limpio el escritorio, usar `Parar_Debian_Grafico`
  antes de volver a lanzar `Debian_Grafico`.

## Comando de instalacion recomendado

En la tablet:

```bash
cd ~/agentes
bash scripts/linux/install_debian_gui_termux.sh
```

## Criterio de exito

- `proot-distro login debian-gui -- /bin/bash -lc 'command -v xfce4-session'`
  funciona
- `~/.shortcuts/Debian_Grafico.sh` existe
- `~/.shortcuts/Parar_Debian_Grafico.sh` existe
- `Termux:X11` abre al lanzar el script de inicio
- `xfce4-session` aparece vivo dentro del `proot`
