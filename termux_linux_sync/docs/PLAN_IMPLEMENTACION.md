# Plan de Migración de Código y Solución de Red en Dispositivo "Vivo" (Termux)

El objetivo de este plan es enviar el código limpio y refactorizado de Linux hacia el dispositivo Vivo (Android/Termux), asegurando su autonomía total e investigando la dependencia a la red WiFi.

## User Review Required
> [!IMPORTANT]
> Se instalará Parrot OS en el S24 Ultra (`RFCX91HV4GD`) para unificar el ecosistema con la tablet. Esto consumirá aproximadamente 2GB de almacenamiento.

## Proposed Changes

### 1. Diagnóstico de Red (El problema del WiFi)
- **Corrección:** Volver toda configuración de red agnóstica o dinámica para que no "reviente" al cambiar de router o dirección DHCP.

### 2. Sincronización del Código Base (`agentes/`)
- Utilizar `adb push` para enviar diferencialmente la carpeta `youtube_uploader/` y `meta_uploader/` al almacenamiento en Termux del celular.

### 5. Optimización de Escala y Limpieza
- **Cambio:** 
  - Subir la densidad a **480 DPI** (Escalado Master) para legibilidad masiva.
  - Implementar una subrutina de **Limpieza Total** (`pkill -9`) antes de cada arranque.
  - Asegurar la sincronización de `wm density 480` en el display virtual del S24.

### 11. Replicación y Hardening S24 Ultra
- **Contenedores:** Instalación de `parrot` vía `proot-distro`.
- **Ecosistema Visual:** Instalación de `mate-desktop-environment` y `kde-plasma-desktop` en Debian y Parrot.
- **Saneamiento de Librerías:** Aplicar el parche de eliminación de `LD_LIBRARY_PATH` contaminado para evitar el error "invalid ELF header".
- **Launchers:** Replicar `launch_*.sh` con soporte para `dbus-run-session` y desactivación de autolock.

## Verification Plan
### Automated Tests
- Ejecutar `adb -s RFCX91HV4GD shell "run-as com.termux proot-distro login parrot -- which mate-session"` para validar la instalación.
- Confirmar el inicio de sesión de Plasma en el S24.
### Manual Verification
- El usuario validará el acceso a KDE/MATE desde el S24 Ultra y el funcionamiento de la contraseña `debian`.
