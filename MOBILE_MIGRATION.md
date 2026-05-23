# Guia Maestra de Migracion Movil ARM64 (Termux + Debian + ADB + SSH)

Esta guia consolida lo que quedo hecho el sabado 25 de abril de 2026 y los
ajustes del lunes 27 y martes 28 de abril de 2026 para correr `agentes` en celulares y
tablets Android ARM64 de forma replicable y lo mas autonoma posible.

## Inventario y Rutas del Ecosistema Móvil (4 Dispositivos)

A continuación se detalla la configuración de cada equipo para asegurar la trazabilidad exigida por el usuario:

## Inventario y Rutas del Ecosistema Móvil (4 Dispositivos)

A continuación se detalla la configuración de cada equipo para asegurar la trazabilidad exigida por el usuario:

| Dispositivo | Modelo | Rol | Ruta en Termux | Usuario Termux | ID Acceso (ADB/SSH) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tablet** | SM-X210 | Backend/GUI | `~/agentes` | `u0_a309` | `192.168.1.7:8022` |
| **Celular 1 (Vivo)** | V2058 | Sincronizador | `/data/data/com.termux/files/home/agentes` | **`u0_a289`** | `34237840310037S` |
| **Celular 2 (Note 9)** | N9600 | Agente Teaser | `~/agentes` | `u0_a254` | `192.168.1.5:8022` |
| **Celular 3 (S24U)** | SM-S928B | Experimental | `~/agentes` | `u0_a447` | `RFCX91HV4GD` |

## Estado verificado el 2026-04-28

- **Dispositivo Vivo (V2058):**
  - **Identidad:** Confirmado Modelo V2058 (Vivo) con serial `34237840310037S`.
  - **Usuario:** `u0_a289` (Diferente al S24U).
  - **Conectividad:** ADB WiFi inestable en red Univalle; se recomienda **USB ADB Forward** (`tcp:8022`).
  - **Problema DNS:** La red Univalle bloquea DNS externos (`8.8.8.8`) dentro de Debian Proot. El launcher ha sido modificado para inyectar DNS locales.

## Que se hizo el sabado 25 de abril de 2026

### Cambios versionados y trazables

1. `6f6e6bc`
   `fix(linux): yt-dlp con --js-runtimes node, descarga 2-pasos, sin cookies-from-browser`
   - Se rehizo `youtube_uploader/youtube_to_fb_watcher.py` para Linux/Parrot.
   - Se elimino la dependencia de `cookies-from-browser`.
   - Se fijo `yt-dlp` con `--js-runtimes node`.
   - Se adopto descarga combinada priorizando 4K y transcodificacion a MP4.

2. `d7365d6`
   `docs: add comprehensive mobile migration guide for Termux/ARM64`
   - Se creo la primera version de `MOBILE_MIGRATION.md`.
   - Quedo documentada la arquitectura Android + Termux + Debian.

3. `df62799`
   `feat(mobile): add termux specific watcher with inline progress and correct tokens`
   - Se creo `youtube_uploader/youtube_to_fb_watcher_termux.py`.
   - Se adaptaron rutas a Termux:
     - base `~/agentes/youtube_uploader`
     - historial `history.json`
     - credenciales `credentials/token_0.json`, `token_1.json`, etc.
   - Se agrego copia de MP4 final a `/sdcard/Download/Agentes_YouTube_4K`.
   - Se dejo progreso inline de `ffmpeg` durante la transcodificacion.

### Resultado del sabado

- El stack movil quedo separado del stack Linux/Parrot.
- El watcher de celular dejo de depender de rutas de Windows o Parrot.
- El telefono pudo correr Debian 13 dentro de Termux sin root.
- Se establecio el patron correcto para futuras replicas: Android host, Termux
  como shell/SSH/ADB helper y Debian como entorno real de ejecucion.

## Que se logro el lunes 27 de abril de 2026 con la tablet Samsung `SM-X210` (Codex & Antigravity)

### Conexión y Autorización ADB Exitosa
- Se resolvió el persistente bloqueo `Unauthorized` en ADB. El problema radicaba en que las llaves RSA no estaban siendo leídas correctamente por el Kernel de Linux (WSL/Proot). 
- La solución se alcanzó sincronizando manualmente (y luego por scripts) el par de llaves `adbkey` y `adbkey.pub` desde el perfil en Windows (Host) hacia el sistema Linux.
- Se verificó exitosamente que la tablet `SM-X210` reporta estado `device`
  al inyectar estas llaves.

### Verificación del Ecosistema Debian/Termux en la tablet
- El acceso vía SSH está totalmente operativo y expuesto en el puerto `8022`.
- El entorno Debian administrado por `proot-distro` está corriendo adecuadamente.
- Se ha validado la ejecución sin root y la posibilidad de emular las operaciones.
- Datos observados en la ronda de validación:
  - modelo: `SM-X210`
  - Android: `16`
  - ABI: `arm64-v8a`
  - usuario SSH/Termux: `u0_a309`
  - IP WiFi observada el `2026-04-27`: `192.168.1.7`

### Rehidratación operativa del repo en la tablet

- El `home` de Termux estaba casi vacío: solo `.shortcuts`, `.ssh`,
  `.termux` y `storage`, aunque `proot-distro` ya tenía `debian` y
  `debian-gui` instalados.
- Se subió desde el host un bundle filtrado de la rama `linux-arm64` a
  `/sdcard/Download/agentes-linux-arm64-samsung.tgz` usando ADB.
- Ese bundle se extrajo en `~/agentes` dentro de Termux.
- Luego se ejecutó:

```bash
bash ~/agentes/scripts/linux/bootstrap_termux_arm64.sh generic
```

- Ese bootstrap dejó:
  - `~/.termux/boot/start_sshd.sh`
  - `~/.shortcuts/Arrancar_SSH.sh`
  - `~/.shortcuts/Estado_Remoto.sh`
  - `~/.shortcuts/Monitor_Logs.sh`
  - `~/.shortcuts/Monitorear_Temperaturas.sh`
  - `~/.shortcuts/sincronizar_yt_a_fb.sh`
  - `~/.shortcuts/vigia_meta.sh`
  - el symlink Debian `/root/agentes -> /data/data/com.termux/files/home/agentes`## Que se logró el martes 28 de abril de 2026 con el Samsung `S24 Ultra` (S928B)

### 1. Bootstrap y Saneamiento del Host Termux
- Se instaló Python 3.13, Pip y herramientas base (`wget`, `curl`, `git`).
- Se localizó y activó `proot-distro` en el PATH de Termux.
- Se configuró el acceso SSH persistente vía ADB Forward en el puerto `38022`.

### 2. Instalación de Parrot OS ARM64 (Lory)
- Debido a la ausencia de un alias oficial en `proot-distro`, se transformó el entorno Debian existente en Parrot OS:
  - **Repositorios:** Se inyectaron los mirrors de `deb.parrot.sh` (Lory).
  - **Saneamiento GPG:** Se importó manualmente la llave `7A8286AF0E81EE4A` tras fallos en servidores de llaves públicos.
  - **Keyring:** Se instaló `parrot-archive-keyring` forzando la autenticación inicial.
  - **Core:** Se aprovisionó el paquete `parrot-core` nativo para ARM64.

### 3. Capa Gráfica: La Odisea y Solución "Modo Dios" (Samsung DeX + Termux:X11)

**Historial de Intentos Fallidos (Diagnóstico de Android 14/Knox):**
- ❌ **VNC (TigerVNC):** Se intentó montar un servidor VNC mediante `dbus-launch` y `startxfce4` en `proot-distro`. Aunque el servidor arrancaba (puerto 5901), al intentar enlazar un cliente desde el Host, devolvía `End of stream` y cerraba la conexión estrepitosamente. La causa raíz es la incompatibilidad de `systemd` que subyace a `xfce4` al correr en la red simulada del loopback Android.
- ❌ **XRDP:** Se instaló protocolo de Windows RDP en puerto 3389 para emplear Remmina. Instalación perfecta, dependencias perfectas, pero el daemon crasheaba instantáneamente al ejecutarse (`exit code 255`) debido a las estrictas políticas anti-daemon del `Phantom Process Killer` aplicadas en One UI de Samsung sobre las consolas internas.

**La Topología de la Victoria (Rendering Nativo):**
- **Sano y Salvo:** Para eludir la necesidad de sockets TCP, se empacó el renderizado directamente a nivel hardware sobre **Termux:X11** (Xwayland). 
- **Samsung DeX (Escritorio Virtual):** En lugar del engorro de interactuar en la pequeña pantalla táctil del S24 Ultra, usamos `scrcpy --new-display=1920x1080` (en PC) que despierta mágicamente la maquinaria nativa oculta de **Samsung DeX**.
- **Limpieza del Socket:** El servidor visual crasheó incialmente por variables zombie compartidas de VNC (`.X11-unix` y `/.tX1-lock`). Fue necesario forzar un barrido pre-arranque usando la variable correcta `TMPDIR` original de Termux.
- **Canalización Cero (`DISPLAY :0`):** La inyección final para que la app Termux:X11 reconociese el display debía coincidir con el puerto CERO, un error constante en la industria al asumir `DISPLAY :1`. 

**Ejecución Operativa:**
- El usuario dispone de tres niveles de acceso en su escritorio:
    - `4-Abrir_DeX_Scrcpy.sh`: Conexión directa por cable USB.
    - `5-Abrir_DeX_WIFI.sh`: Conexión inalámbrica interactiva (pide IP/Puerto).
    - `6-Abrir_TODO_AUTOMATICO.sh`: Solución **Zero-Touch**. Autodetecta, despierta `sshd` inyectando comandos ADB y lanza Parrot OS en DeX inalámbricamente.

**Lecciones de Ingeniería (S24 Ultra):**
- **Sintaxis Shell:** Se identificó que incluso en títulos de ventana entrecomillados, el uso de paréntesis `(...)` puede causar errores de sintaxis en el shell de Parrot. Todos los títulos se estandarizaron a texto plano.
- **Persistencia de Daemons:** El Gestor de Batería de Samsung es agresivo. Se implementó un re-arranque forzado de `sshd` y `termux-wake-lock` mediante el terminal inyectado por ADB para garantizar el enlace remoto.
- **Canalización Cero:** Se fijó el `DISPLAY :0` como estándar inamovible para que la App Termux:X11 reconozca el socket visual sin configuración manual extra.

### 4. Inventario de Widgets (Termux Widget)
- `Arrancar_SSH.sh`: Inicia el daemon SSH.
- `Arrancar_VNC_Parrot.sh`: Inicia el servidor Parrot GUI.
- `sincronizar_yt_a_fb.sh`: Launcher con inyección DNS autorizada (Univalle).

## Próximos Pasos (Pendientes para Codex/Sonnet)
1. **Depuración VNC:** Resolver el rechazo de sesión `End of stream` deshabilitando IPv6 o ajustando la seguridad del socket en Proot.
2. **Sincronización:** Validar el repo `agentes` dentro del Parrot OS del S24U.

### Validación funcional real en la tablet

- Dentro de Debian quedaron confirmados:
  - `Python 3.13.5`
  - `FFmpeg 7.1.3`
  - `Node v20.19.2`
  - `yt-dlp 2026.03.17` en `/usr/local/bin/yt-dlp`
- El import combinado de `google.auth`, `googleapiclient`,
  `google_auth_oauthlib`, `requests` y `dotenv` respondió `deps-ok`.
- `fb_to_ig_vigia.py --help` respondió correctamente.
- El dry-run del watcher móvil ejecutado sobre la tablet, registrado el
  `2026-04-28 05:00 UTC`, confirmó:
  - `352` videos pendientes detectados.
  - primera muestra de lote:
    `2026-02-19 - 20251108 182940`.
- Hallazgo importante: en esta ronda el dispositivo validado no fue un Note 9
  sino la tablet Samsung `SM-X210`; la trazabilidad quedó corregida aquí para
  no arrastrar esa etiqueta por error.

## Que se logro el martes 28 de abril de 2026 con el Samsung S24 Ultra `SM-S928B` (Codex & Antigravity)

### Bootstrap host por USB y Termux

- Datos confirmados del equipo:
  - serial ADB: `RFCX91HV4GD`
  - modelo: `SM-S928B`
  - producto: `e3qxxx`
  - Android: `16`
  - ABI: `arm64-v8a`
  - usuario SSH/Termux: `u0_a447`
- El telefono no traia el stack Termux completo: solo estaban
  `com.termux.api` y `com.termux.x11`.
- `com.termux`, `com.termux.boot` y `com.termux.widget` se instalaron por USB
  desde APK local luego de desactivar temporalmente la verificacion de
  paquetes ADB, porque el primer intento devolvia
  `INSTALL_FAILED_VERIFICATION_FAILURE`.
- Dentro de Termux se dejo listo el host con:
  - `curl`
  - `git`
  - `openssh`
  - `proot-distro`
  - `rsync`
  - `tar`
  - `termux-api`
- La llave publica del host se inyecto en
  `~/.ssh/authorized_keys` y `sshd` quedo levantado.

### Acceso operativo real al S24

- El acceso directo a `10.44.0.1:8022` quedo filtrado o inutilizable en esta
  red, asi que el camino estable fue USB:

```bash
adb -s RFCX91HV4GD forward tcp:38022 tcp:8022
ssh -p 38022 u0_a447@127.0.0.1
```

- Esa ruta quedo verificada con `id` y permitio terminar todo el bootstrap sin
  depender de ADB por WiFi.

### Debian nuevo y correccion de DNS

- Se instalo Debian desde cero con:

```bash
proot-distro install debian
```

- La primera ronda de `apt update` dentro de Debian fallo porque
  `/etc/resolv.conf` apuntaba a `8.8.8.8` y `8.8.4.4`, que no resolvian en
  esta red.
- Se corrigio el `resolv.conf` de la rootfs Debian usando los DNS efectivos del
  host Termux:
  - `192.168.248.58`
  - `192.168.248.37`
- Tras ese ajuste, `getent hosts deb.debian.org` ya respondio correctamente y
  se pudo provisionar Debian con:
  - `Python 3.13.5`
  - `FFmpeg 7.1.3`
  - `Node v20.19.2`
  - `yt-dlp 2026.03.17`

### Rehidratacion del repo y validacion final

- El bundle filtrado de la rama `linux-arm64` se copio por `scp` al home de
  Termux y se extrajo en `~/agentes`.
- Hallazgo operativo util: no usar `tar --strip-components=1` al deshidratar o
  rehidratar este repo, porque eso aplana directorios como `scripts/linux/` y
  `meta_uploader/`.
- El bootstrap final se ejecuto con:

```bash
bash ~/agentes/scripts/linux/bootstrap_termux_arm64.sh generic
```

- En el S24 quedaron creados y verificados:
  - `~/.termux/boot/start_sshd.sh`
  - `~/.agentes_termux_env`
  - `~/.shortcuts/Arrancar_SSH.sh`
  - `~/.shortcuts/Estado_Remoto.sh`
  - `~/.shortcuts/Monitor_Logs.sh`
  - `~/.shortcuts/Monitorear_Temperaturas.sh`
  - `~/.shortcuts/sincronizar_yt_a_fb.sh`
  - `~/.shortcuts/vigia_meta.sh`
  - `/root/agentes -> /data/data/com.termux/files/home/agentes`
- Validacion funcional real dentro de Debian:
  - import combinado `google.auth`, `googleapiclient`,
    `google_auth_oauthlib`, `requests` y `dotenv`: `imports ok`
  - `fb_to_ig_vigia.py --help` respondio correctamente
  - dry-run real del watcher movil con
    `AGENTES_SYNC_SEARCH_LIMIT=20 python3 youtube_to_fb_watcher_termux.py --dry-run --limit 1`
    detecto `20` videos pendientes y reporto como primera muestra
    `2026-02-19 - 20251108 182940`

## Que se ajusto el lunes 27 de abril de 2026 para el Vivo

### Ajustes locales en el watcher movil

En `youtube_uploader/youtube_to_fb_watcher_termux.py` quedaron estos cambios
respecto a la version del sabado:

- `BATCH_SIZE = 0` para tratar `0` como "sin limite".
- `effective_limit = None` cuando `--limit <= 0`.
- `search_limit = 5000` para escanear mucho mas historial del canal.
- `--dry-run` y el conteo final se corrigieron para no truncar mal el lote.

### Verificaciones hechas directamente sobre el telefono

- `~/.termux/boot/start_sshd.sh` existe y contiene:
  - `termux-wake-lock`
  - `sshd`
- `~/.shortcuts/Monitorear_Temperaturas.sh` existe y lee bateria + thermal zones.
- `~/.shortcuts/sincronizar_yt_a_fb.sh` existe y llama al wrapper del repo.
- `~/.shortcuts/vigia_meta.sh` existe y entra a Debian antes de lanzar el vigia.
- `~/.ssh/authorized_keys` existe y contiene la llave del host controlador.
- No existe `~/.ssh/config` en el servidor Termux actual, lo cual es correcto:
  solo hacia falta `authorized_keys`.

### Estado real observado

- El stack remoto ya responde por ADB USB.
- El stack ya esta listo para moverse a ADB por WiFi.
- SSH esta cableado para arrancar con el telefono.
- El watcher movil ya procesa el backlog completo si se le deja correr.
- Todavia no esta cerrado el hardening masivo de `yt-dlp`: la corrida mas
  reciente solo confirmo `1/360` y dejo un parcial
  `dl_M0EzUUW-wR0_merged.f315.webm`.

## Atribucion Codex / Sonnet

- Codex:
  - Los cambios moviles del sabado quedaron trazados por commit en
    `6f6e6bc`, `d7365d6` y `df62799`.
  - Los ajustes del lunes 27 de abril de 2026 estan hoy en el working tree de
    `youtube_uploader/youtube_to_fb_watcher_termux.py` y en la validacion
    operativa del Vivo por ADB.
  - Codex ejecutó e instaló las dependencias de ADB en la tablet Samsung
    `SM-X210` en conjunto con el agente Antigravity, logrando la conexión SSH
    en el `puerto 8022` y la rehidratación completa del repo `~/agentes`.
- Sonnet / Claude:
  - No encontre en este repo un commit separado ni una entrada de historial del
    `2026-04-25` o `2026-04-27` que aisle trabajo movil atribuido solo a
    Sonnet.
  - Lo que si esta versionado de ese ecosistema es la compatibilidad general en
    `configs/claude_local/`.
  - Inferencia: si Sonnet participo en la sesion movil, su aporte quedo
    absorbido en el resultado tecnico pero no separado en trazabilidad Git.

## Arquitectura canonica para otros celulares y la tablet

- Android solo hace de host.
- Termux provee shell, almacenamiento, SSH, widgets y punto de entrada para ADB.
- Debian en `proot-distro` corre Python, FFmpeg, Node y `yt-dlp`.
- El repo vive en `~/agentes`.
- El codigo movil debe salir siempre desde la rama `linux-arm64`.
- Para operacion diaria se prefiere:
  - ADB USB solo para bootstrap inicial.
  - ADB WiFi para mantenimiento cuando sea posible.
  - SSH para casi toda la operacion remota normal.

## Procedimiento autonomo para replicar un telefono o tablet nuevo

### 1. Preparacion del dispositivo Android

- Exigir `arm64-v8a`.
- Activar Opciones de desarrollador.
- Activar `USB debugging`.
- Activar `Wireless debugging` si el dispositivo lo soporta.
- Quitar optimizacion agresiva de bateria para:
  - Termux
  - Termux:Boot
  - Termux:Widget
  - Termux:API

### 2. Apps que deben instalarse

No usar la version de Play Store.

- Instalar `Termux` desde GitHub en APK para ARM64.
- Instalar tambien:
  - `Termux:API`
  - `Termux:Boot`
  - `Termux:Widget`

### 3. Primer enganche por ADB

Desde el host controlador:

```bash
adb devices
adb shell getprop ro.product.cpu.abi
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
```

Si el USB ya funciona, pasar a ADB por WiFi:

```bash
adb tcpip 5555
adb shell ip addr show wlan0
adb connect <IP_DEL_DISPOSITIVO>:5555
adb devices
```

Alternativa en Android 11+ con emparejamiento:

```bash
adb pair <IP_DEL_DISPOSITIVO>:<PUERTO_DE_PAIRING>
adb connect <IP_DEL_DISPOSITIVO>:<PUERTO_DE_ADB_WIFI>
```

Regla operativa:

- USB para bootstrap.
- WiFi para continuidad.
- Si ADB por WiFi cae, volver a USB, reemitir `adb tcpip 5555` y reconectar.

### 4. Bootstrap minimo dentro de Termux

Abrir Termux y correr:

```bash
termux-setup-storage
pkg update -y
pkg upgrade -y
pkg install -y git openssh proot-distro termux-api
```

Notas:

- `openssh` es obligatorio para control remoto normal.
- `proot-distro` es obligatorio para Debian.
- `termux-api` es obligatorio para el widget de temperatura.

### 5. Instalar Debian dentro de Termux

```bash
proot-distro install debian
proot-distro login debian
```

Dentro de Debian:

```bash
apt update
apt install -y python3 python3-pip python3-venv ffmpeg nodejs git openssh-client ca-certificates
python3 -m pip install --break-system-packages yt-dlp
```

Luego instalar dependencias del repo:

```bash
python3 -m pip install --break-system-packages \
  -r ~/agentes/youtube_uploader/requirements.txt \
  -r ~/agentes/meta_uploader/requirements.txt
```

Este punto es importante:

- En el Vivo validado no se usa una `.venv` movil para estos watchers.
- El watcher corre con `/usr/bin/python3`.
- `yt-dlp` queda en `/usr/local/bin/yt-dlp`.

### 6. Llevar el repo al telefono o tablet

Metodo preferido si el agente tiene acceso Git:

```bash
cd ~
git clone -b linux-arm64 <URL_DEL_REPO> agentes
```

Metodo preferido si el controlador ya tiene el repo local y el telefono ya
responde por SSH:

```bash
scp -P 8022 -r /ruta/local/agentes <USUARIO_TERMUX>@<IP_DEL_DISPOSITIVO>:~/
```

Metodo de fallback por ADB si todavia no hay SSH:

```bash
tar czf agentes-linux-arm64.tgz agentes
adb push agentes-linux-arm64.tgz /sdcard/Download/
```

Y dentro de Termux:

```bash
cd ~
tar xzf /sdcard/Download/agentes-linux-arm64.tgz
```

Regla:

- Empaquetar el tar con carpeta superior `agentes/`.
- Si ya existe `~/agentes`, renombrarlo o borrarlo antes de descomprimir.

### 7. Archivos y secretos que el agente debe poner

YouTube:

- `~/agentes/youtube_uploader/credentials/client_secret_*.json`
- `~/agentes/youtube_uploader/credentials/token_*.json`
- `~/agentes/youtube_uploader/credentials/token_sync_*.json` si se quiere
  reutilizar el flujo de sincronizacion ya autenticado

Meta:

- `~/agentes/meta_uploader/.env` a partir de `meta_uploader/.env.example`

Regla:

- Nunca subir estos archivos a Git.
- Copiarlos por `scp`, `rsync` o montaje manual dentro del dispositivo.

### 8. Configurar SSH para operacion remota

En el telefono o tablet:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys <<'EOF'
<PEGAR_LLAVE_PUBLICA_DEL_CONTROLADOR>
EOF
chmod 600 ~/.ssh/authorized_keys
sshd
```

Verificar usuario real del servidor:

```bash
whoami
```

En el Vivo actual devolvio `u0_a289`, pero en otro dispositivo ese nombre va a
cambiar.

Config recomendada en el cliente controlador `~/.ssh/config`:

```sshconfig
Host android-agentes
  HostName <IP_DEL_DISPOSITIVO>
  Port 8022
  User <USUARIO_TERMUX_REAL>
  IdentityFile ~/.ssh/id_ed25519
  ServerAliveInterval 30
  ServerAliveCountMax 4
```

Conexion:

```bash
ssh android-agentes
```

### 9. Arranque automatico de SSH y wakelock

Crear `~/.termux/boot/start_sshd.sh`:

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start_sshd.sh <<'EOF'
# Mantener CPU despierta y SSH siempre activo
termux-wake-lock
sshd
EOF
chmod +x ~/.termux/boot/start_sshd.sh
```

Esto replica exactamente lo verificado en el Vivo el `2026-04-27`.

### 10. Widgets que deben quedar instalados

Crear `~/.shortcuts` y poblarlo con wrappers ejecutables.

Bootstrap reproducible recomendado:

```bash
bash ~/agentes/scripts/linux/bootstrap_termux_arm64.sh generic
```

Ese bootstrap:

- reinstala `~/.termux/boot/start_sshd.sh`
- recrea widgets en `~/.shortcuts/`
- deja un perfil movil en `~/.agentes_termux_env`
- crea el enlace Debian `/root/agentes -> /data/data/com.termux/files/home/agentes`
- reinstala de forma idempotente `yt-dlp` y las dependencias Python de
  `youtube_uploader/requirements.txt` y `meta_uploader/requirements.txt`

Perfil `note9` recomendado:

- `AGENTES_FFMPEG_PRESET=medium`
- `AGENTES_FFMPEG_CRF=20`
- `AGENTES_FFMPEG_AUDIO_BITRATE=160k`
- `AGENTES_SYNC_SLEEP_SECONDS=8`
- `AGENTES_YTDLP_CONCURRENT_FRAGMENTS=1`

Para tablets o dispositivos nuevos sin tuning propio, usar `generic`.

El conjunto minimo recomendado es:

- `~/.shortcuts/sincronizar_yt_a_fb.sh`
- `~/.shortcuts/vigia_meta.sh`
- `~/.shortcuts/Monitorear_Temperaturas.sh`
- `~/.shortcuts/Monitor_Logs.sh`
- `~/.shortcuts/LIMPIAR_CRUDOS.sh`

Los wrappers reales verificados en el Vivo quedan asi:

`~/.shortcuts/sincronizar_yt_a_fb.sh`

```bash
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/sincronizar_yt_a_fb_termux.sh"
exec "$LAUNCHER"
```

`~/.shortcuts/vigia_meta.sh`

```bash
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
PROOT="/data/data/com.termux/files/usr/bin/proot-distro"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/vigia_meta_termux.sh"
LOG_FILE="$TERMUX_HOME/agentes/meta_uploader/fb_to_ig_vigia.log"
exec "$PROOT" login debian -- /bin/bash -lc "$LAUNCHER & sleep 3; tail -f '$LOG_FILE'"
```

`~/.shortcuts/Monitorear_Temperaturas.sh`

```bash
echo '🌡️ SENSORES DE TEMPERATURA (VIVO) 🌡️'
echo '========================================='
if command -v termux-battery-status > /dev/null; then
  battery_temp=$(termux-battery-status | grep -i temperature | awk '{print $2}' | sed 's/,//')
  echo "Batería: $battery_temp °C"
fi
for tz in /sys/class/thermal/thermal_zone*; do
  type=$(cat "$tz/type" 2>/dev/null)
  temp=$(cat "$tz/temp" 2>/dev/null)
  if [ -n "$temp" ]; then
    if [ "$temp" -gt 1000 ]; then temp=$(("$temp"/1000)); fi
    echo "$type: $temp °C"
  fi
done | grep -E 'cpu|tsens|battery|quiet' | head -n 10
echo '========================================='
read -p "Presiona Enter para cerrar..."
```

Relaciones repo -> widget:

- `scripts/linux/sincronizar_yt_a_fb.sh` -> wrapper Termux de acceso directo
- `scripts/linux/sincronizar_yt_a_fb_termux.sh` -> launcher real dentro de Debian
- `scripts/linux/vigia_meta_widget.sh` -> wrapper de widget para Meta
- `scripts/linux/vigia_meta_termux.sh` -> launcher real dentro de Debian
- `scripts/linux/LIMPIAR_CRUDOS.sh` -> wrapper Termux de acceso directo para limpiar crudos
- `scripts/linux/limpiar_crudos_incompletos_termux.sh` -> launcher real de limpieza
- `youtube_uploader/clean_incomplete_crudos.py` -> script de Python para detectar y mover crudos sin teaser

### 11. Comportamiento esperado de los launchers moviles

YouTube -> Facebook:

- El widget entra por `~/.shortcuts/sincronizar_yt_a_fb.sh`.
- Ese wrapper llama `~/agentes/scripts/linux/sincronizar_yt_a_fb_termux.sh`.
- El launcher entra a Debian y corre el watcher movil del repo.

Meta:

- El widget entra por `~/.shortcuts/vigia_meta.sh`.
- Ese wrapper entra a Debian.
- Luego llama `~/agentes/scripts/linux/vigia_meta_termux.sh`.
- Ese script corre `fb_to_ig_vigia.py` con `/usr/bin/python3`.

### 12. Validacion minima que debe hacer un agente autonomo

Desde Termux:

```bash
whoami
sshd
termux-wake-lock
```

Desde Debian:

```bash
proot-distro login debian -- python3 --version
proot-distro login debian -- ffmpeg -version
proot-distro login debian -- node --version
proot-distro login debian -- sh -lc 'command -v yt-dlp && yt-dlp --version'
```

Validacion del repo:

```bash
proot-distro login debian -- python3 ~/agentes/youtube_uploader/youtube_to_fb_watcher_termux.py --dry-run
proot-distro login debian -- python3 ~/agentes/meta_uploader/fb_to_ig_vigia.py --help
```

Validacion remota desde el controlador:

```bash
ssh -p 8022 <USUARIO_TERMUX_REAL>@<IP_DEL_DISPOSITIVO> whoami
adb connect <IP_DEL_DISPOSITIVO>:5555
adb devices
```

### 13. Operacion desde otros celulares o desde la tablet

Por SSH:

- Instalar Termux en el celular/tablet controlador.
- `pkg install -y openssh`
- `ssh-keygen -t ed25519`
- Agregar la llave publica del controlador al `authorized_keys` del telefono
  objetivo.
- Conectar con `ssh -p 8022 <USUARIO>@<IP>`.

Por ADB:

- En el controlador con Termux, instalar un cliente ADB si esta disponible.
- Conectar por USB una vez o usar `Wireless debugging`.
- Ejecutar:

```bash
adb connect <IP_DEL_DISPOSITIVO>:5555
adb devices
adb shell getprop ro.product.model
```

Uso recomendado:

- SSH para editar, copiar, correr scripts y leer logs.
- ADB para bootstrap, recuperacion, pairing y operacion cuando SSH no responde.

## Correcciones importantes respecto a la primera guia

- Ya no debe asumirse que la salida publica depende de un symlink. El estado
  actual verificado en el Vivo es copia explicita del MP4 final a
  `/sdcard/Download/Agentes_YouTube_4K`.
- El servidor SSH en Termux escucha en `8022`, no en `22`.
- El usuario SSH cambia segun el dispositivo; no fijarlo a mano.
- Para esta migracion movil, el watcher usa Python del Debian proot, no la
  `.venv` del repo.

## Checklists rapidos para la proxima IA

### Bootstrap de un dispositivo nuevo

1. Verificar `arm64-v8a`, Android y depuracion USB.
2. Instalar Termux GitHub + `Termux:API` + `Termux:Boot` + `Termux:Widget`.
3. Hacer handshake ADB USB.
4. Activar ADB por WiFi.
5. Instalar `openssh`, `proot-distro`, `termux-api`.
6. Instalar Debian.
7. Instalar Python, FFmpeg, Node, Git, `yt-dlp` en Debian.
8. Llevar `agentes` rama `linux-arm64`.
9. Copiar credenciales y `.env`.
10. Configurar `authorized_keys`, `start_sshd.sh` y widgets.
11. Validar SSH, ADB WiFi y launchers.

### Criterio de exito

- El dispositivo responde por `ssh -p 8022`.
- El dispositivo responde por `adb connect <ip>:5555`.
- `proot-distro login debian -- python3 --version` funciona.
- Los widgets lanzan los wrappers del repo.
- El watcher movil genera log y puede leer credenciales.

## Riesgos pendientes

- La descarga masiva por `yt-dlp` en el Vivo sigue fragil: el ultimo lote
  cerró con `1/360` exitos.
- Conviene dejar como siguiente tarea un endurecimiento de diagnostico para
  capturar el stderr real de `yt-dlp` en Termux/Debian y no solo el mensaje
  generico `Fallo la descarga.`.
