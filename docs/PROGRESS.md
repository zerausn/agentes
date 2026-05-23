# Estado de Progreso - Repo agentes

## Infraestructura del repo
- Se resolvio la parte de hibernacion de una incidencia operativa de dual boot
  Windows 11 + Parrot OS en esta maquina: Windows quedo con hibernacion
  desactivada, `HiberbootEnabled` confirmado en `0` y sin `hiberfil.sys`.
- En el mismo diagnostico se confirmo que `C:` sigue con BitLocker
  `FullyEncrypted` (`XTS-AES 128`) aunque la proteccion esta en `Off`; por eso
  el acceso transparente desde Parrot sigue requiriendo una decision aparte:
  descifrar completamente `C:` o usar una ruta Linux compatible con BitLocker.
- Se dejo trazabilidad local de la correccion en
  `workspace-local/fix_dualboot_windows_access.ps1` y su log asociado.
- **Ecosistema Dual-Boot Consolidado:** Se construyo una suite paralela de scripts Bash ubicados en `scripts/linux/` para proveer paridad operativa en Parrot OS frente a los scripts PowerShell originales de Windows.
  - Scripts generados: `iniciar_agentes.sh`, `mejorador.sh`, `monitor_logs.sh`, `procesamiento_masivo.sh`, `start_agent_meta.sh`, `start_agent_youtube.sh`, `subida_fb_fotos.sh`, `subida_yt_teaser.sh`, `vigia_meta.sh`.
  - El sistema detecta y activa automaticamente los entornos virtuales correctos para ambos ecosistemas.
- `youtube_uploader/` ya vive en la raiz del repo contenedor.
- Se eliminaron las referencias operativas al nesting accidental
  `agentes/agentes/youtube_uploader`.
- La automatizacion raiz ahora valida `youtube_uploader/`, `meta_uploader/` y
  `scripts/init-agents.ps1`.
- `meta_uploader/` ya tiene contexto local minimo y setup base, aunque su
  implementacion funcional sigue en desarrollo.
- Se agrego un monitor de logs en tiempo real para Meta y YouTube en
  `scripts/monitor_realtime.py`, con launcher `.bat` y nota para futuras IAs.
- La convencion operativa de Meta quedo unificada en documentacion: "sube
  videos a Meta" significa usar `schedule_jornada1_supervisor.py`, y el carril
  previo de Meta pasa a llamarse "videos optimizados" en los docs.

## Sincronizador Vigía: YouTube -> Facebook (Linux/4K)
- Se implemento `youtube_to_fb_watcher.py` en `youtube_uploader/` especificamente para el entorno **Linux (Parrot OS)**.
- **Filtrado:** Identifica videos publicos subidos antes del 1 de marzo de 2026 que aun no estan en `sync_history.json`.
- **Estrategia Anti-403 (SABR Streaming):** Para evadir los bloqueos persistentes de YouTube al descargar fragmentos (HLS/m3u8), se implemento una arquitectura de descargas de 3 pasos usando `yt-dlp` y `ffmpeg`:
  1. Descarga del video 4K (solo video) rotando clientes (`ios`, `tv`, `web`).
  2. Descarga del audio usando los mismos clientes con cookies de Microsoft Edge.
  3. Fusión (`ffmpeg -movflags +faststart`).
- **Resiliencia:** Reintentos limitados por fragmento (`--fragment-retries`, `--retries`) para permitir `fail-fast` y saltar al siguiente cliente `yt-dlp` disponible.
- **Archivos de control:** Trabaja de la mano con `checklist_sincronizacion.md` (como backup visual del lote) y guarda en el disco dual (`D69493CF9493B08B`).

## YouTube Teaser Uploader (Nuevo Agente)
- Se implemento `teaser_uploader.py` como un agente independiente y aislado.
- **Funcionalidad:** Recicla material de descarte de IG (60s slices) y los sube a YouTube.
- **Avances del 2026-04-27:** Se creó adicionalmente `teaser_generator.py` que fragmenta de manera programática en teasers objetivo de `16s` usando `ffmpeg` sin recodificar.
- **Aislamiento:** No interactua con el sistema de playlists de los crudos largos en metadatos, pero sí corren de forma secuencial (`Teaser` -> `Crudo`).
- **Nomenclatura (2026-04-27):** Detecta la secuencia numérica del archivo `_teaser_000`, `_teaser_001`, etc. para crear el sufijo final (ej. `#teaser #1`, `#teaser #2`).
- **Orden (2026-04-27):** La cola de teasers quedó ordenada por serie y número, evitando que un `#teaser #3` salga antes que su `#teaser #1`.
- **Monitoreo Cero Zombies (2026-04-27):** Ambos scripts de subida detienen la secuencia bash completamente usando `.join()` en sus verificadores paralelos. Ninguno cerrará el proceso hasta que YouTube API `processingDetails` reporte éxito, impidiendo generar colas de videos zombies en el fondo.
- **Programación Rígida (2026-04-27):** Ahora está configurado para programar rígidamente un teaser por día a las `17:45` hrs de Colombia, sin publicaciones inmediatas que rompan la secuencia.
- **Lanzadores:** Acceso indirecto por medio del archivo principal consolidado de carga: `start_agent_youtube.sh`.

## Optimizacion Meta (Photo Uploader)
- Rediseño del pipeline para evitar doble procesamiento de fotos 4K.
- Generacion de Reels individuales de 5s y concatenacion ultra-rapida de Reel combinado de 30s usando demuxer de FFmpeg.
- Carpeta de salida persistente para Reels generados: `reels_generados_fb`.


## Seguimiento operativo heredado de `youtube_uploader`

## Resumen de Inventario (Carpeta 1)
- Shorts detectados: 96
- Videos largos detectados: 24
- Procesados en esta sesion: 2 (y un tercero en curso)

## Calendario de Publicacion (Gaps llenos)
- 2026-04-06: OK (V:1 S:1)
- 2026-04-07: Short programado (borrador previo o nuevo)
- 2026-04-08: Short programado (ID: ctntHGdGY-o)
- 2026-04-09: Short programado (ID: Z9_qrkXMkHo - pendiente confirmar)

## Proximos huecos a llenar
- Shorts faltantes del 10 de abril al 4 de mayo.
- Videos largos a partir del 5 de mayo (cuando se agoten los ya programados).

## Estado de la cuota (4 cuentas)
- Cuenta 0: en uso.
- Cuentas 1, 2 y 3: disponibles.

## Infraestructura de automatizacion
- `.antigravity/automation.json` agregado en la raiz del repo.
- Workflow `agent-validate.yml` agregado para validar PRs sin depender solo
  del contexto Markdown.
- El flujo de publicacion automatica ya puede validar el subproyecto anidado
  antes de abrir una rama o PR.

## ARM64 movil: tablet Samsung `SM-X210`
- Validacion remota completada el `2026-04-27` sobre una tablet Samsung
  `SM-X210` (`Android 16`, `arm64-v8a`) con usuario Termux `u0_a309` e IP
  observada `192.168.1.7`.
- El dispositivo ya tenia `debian` y `debian-gui` dentro de `proot-distro`,
  pero `~/agentes` no existia y el home de Termux seguia casi vacio.
- Se subio por ADB un bundle filtrado de la rama `linux-arm64` a
  `/sdcard/Download/agentes-linux-arm64-samsung.tgz` y se extrajo en
  `~/agentes`.
- `scripts/linux/bootstrap_termux_arm64.sh` quedo mejorado para reinstalar en
  Debian, de forma idempotente, `yt-dlp` y las dependencias Python de
  `youtube_uploader/requirements.txt` y `meta_uploader/requirements.txt`.
- Tras correr `bash ~/agentes/scripts/linux/bootstrap_termux_arm64.sh generic`,
  la tablet quedo con:
  - `~/.termux/boot/start_sshd.sh`
  - `~/.shortcuts/Arrancar_SSH.sh`
  - `~/.shortcuts/Estado_Remoto.sh`
  - `~/.shortcuts/Monitor_Logs.sh`
  - `~/.shortcuts/Monitorear_Temperaturas.sh`
  - `~/.shortcuts/sincronizar_yt_a_fb.sh`
  - `~/.shortcuts/vigia_meta.sh`
  - `/root/agentes -> /data/data/com.termux/files/home/agentes`
- Verificacion funcional final:
  - `yt-dlp 2026.03.17` presente en `/usr/local/bin/yt-dlp`
  - imports `google.auth`, `googleapiclient`, `google_auth_oauthlib`,
    `requests` y `dotenv` correctos
  - `fb_to_ig_vigia.py --help` responde
  - dry-run del watcher movil: `352` videos pendientes y primera muestra
    `2026-02-19 - 20251108 182940`

## ARM64 movil: Samsung S24 Ultra `SM-S928B`
- Validacion remota completada el `2026-04-28` sobre un Samsung S24 Ultra
  `SM-S928B` (`Android 16`, `arm64-v8a`) por USB, con serial
  `RFCX91HV4GD` y usuario Termux `u0_a447`.
- El telefono solo tenia `com.termux.api` y `com.termux.x11`, asi que por ADB
  se instalaron `com.termux`, `com.termux.boot` y `com.termux.widget` desde
  APK local; antes hubo que desactivar temporalmente la verificacion de
  paquetes ADB porque devolvia `INSTALL_FAILED_VERIFICATION_FAILURE`.
- En el host Termux quedaron instalados `curl`, `git`, `openssh`,
  `proot-distro`, `rsync`, `tar` y `termux-api`, con
  `~/.ssh/authorized_keys` ya cableado para el host controlador.
- El puerto WiFi directo `10.44.0.1:8022` quedo filtrado, por lo que el acceso
  estable se termino resolviendo con:
  - `adb -s RFCX91HV4GD forward tcp:38022 tcp:8022`
  - `ssh -p 38022 u0_a447@127.0.0.1`
- Debian se instalo desde cero con `proot-distro install debian`; luego hubo
  que corregir su `resolv.conf` desde `8.8.8.8` y `8.8.4.4` hacia
  `192.168.248.58` y `192.168.248.37` para que `apt` resolviera en esta red.
- El repo `~/agentes` se rehidrato desde un bundle filtrado de la rama
  `linux-arm64` copiado por `scp`. Hallazgo importante: no usar
  `--strip-components=1` al extraer este tar, porque rompe rutas como
  `scripts/linux/` y `meta_uploader/`.
- Tras correr `bash ~/agentes/scripts/linux/bootstrap_termux_arm64.sh generic`,
  el S24 quedo con:
  - `~/.termux/boot/start_sshd.sh`
  - `~/.agentes_termux_env`
  - `~/.shortcuts/Arrancar_SSH.sh`
  - `~/.shortcuts/Estado_Remoto.sh`
  - `~/.shortcuts/Monitor_Logs.sh`
  - `~/.shortcuts/Monitorear_Temperaturas.sh`
  - `~/.shortcuts/sincronizar_yt_a_fb.sh`
  - `~/.shortcuts/vigia_meta.sh`
  - `/root/agentes -> /data/data/com.termux/files/home/agentes`
- Verificacion funcional final:
  - `Python 3.13.5`
  - `FFmpeg 7.1.3`
  - `Node v20.19.2`
  - `yt-dlp 2026.03.17`
  - imports `google.auth`, `googleapiclient`, `google_auth_oauthlib`,
    `requests` y `dotenv` correctos
  - `fb_to_ig_vigia.py --help` responde
  - dry-run del watcher movil con `AGENTES_SYNC_SEARCH_LIMIT=20`: `20`
    videos pendientes y primera muestra `2026-02-19 - 20251108 182940`

## Pipeline Completo S24: `0_PIPELINE_COMPLETO.sh`
- Creado el `2026-05-18` en el S24 como copia mejorada de `1_CORTAR_TEASERS.sh`.
- **v6 actual (2026-05-18):** Pipeline reescrito. Flujo:
  1. `video_scanner.py` → escanea DB (foreground)
  2. `teaser_generator.py` → corta teasers de TODOS los crudos (foreground, ves logs)
  3. Por cada crudo: lanza TODOS sus teasers en PARALELO (`--single-file`, un proceso por teaser)
  4. Espera markers `.uploaded` de todos los teasers → 2s → arranca `uploader.py` del crudo
  5. Facebook sweep al final
- **Bug fixes v1→v6:**
  - Loop infinito: se eliminó la llamada redundante a `teaser_generator` dentro del while loop
  - Subida de teasers paralela: `--single-file` + background process por teaser
  - Crudo arranca 2s DESPUÉS del ÚLTIMO teaser subido (no después del primero)
  - `teaser_generator.py` escribe `.part` y renombra atómicamente (evita uploads prematuros)
  - Markers `.state/<crudo>.done` y `.state/<teaser>.uploaded` para sincronización
- Ubicación: `~/.shortcuts/0_PIPELINE_COMPLETO.sh` (widget #0).

## Teaser Generator: bitrate incrementado a 70 Mbps
- `2026-05-18`: se aumentó `-b:v` de `6000k` a `70000k` en
  `teaser_generator.py:85` para el pipeline `hw_transcode` (HEVC → H.264 vía
  mediacodec). El bitrate anterior (6 Mbps) producía pixelación notable en 4K.
- El encoder HW del S24 procesa cualquier bitrate hasta ~100 Mbps a la misma
  velocidad; no hay impacto en tiempo de corte.

## Facebook Evacuador: modo paralelo con confirmación
- `2026-05-18`: `subir_fb_evacuador.py` modificado para usar `threading`.
  Cada video se sube+verifica en su propio hilo. Todos corren simultáneamente.
  El archivo se mueve a "subidos a facebbok" SOLO cuando su hilo confirma el
  procesamiento en Facebook.

## Note 9 (SM-N9600): VNC + SSH
- `2026-05-17`: Se configuró el Note 9 (Android 10, SDM845) como dispositivo
  controlable remotamente desde la tablet SM-X210.
- **droidVNC-NG 2.19.0** instalado y funcionando como servidor VNC en puerto
  `5900`, también HTTP (noVNC) en puerto `5800`. Contraseña: `antigravity`.
- **OpenSSH** en Termux, puerto `8022`, usuario `u0_a309`, contraseña
  `antigravity`. SSH funcional desde la tablet.
- **ADB WiFi:** Se intentó autorizar desde la tablet al Note 9 sin éxito
  (permanecía "unauthorized" a pesar de `alwaysAllow=true` en el Note 9).
  Abandonado en favor de VNC+SSH.

## Tablet SM-X210: Control remoto del Note 9 por VNC
- `2026-05-17`: Se estableció túnel SSH desde la tablet al Note 9:
  `ssh -L 5900:localhost:5900 -p 8022 u0_a309@10.31.120.236`
- **freebVNC** (`com.iiordanov.freebVNC`) instalado en la tablet con conexión
  "Note9" apuntando a `localhost:5900`, contraseña `antigravity`.
- La conexión VNC se confirmó operativa: `RemoteCanvasActivity` activa mostrando
  la pantalla del Note 9.
- Scripts en la tablet:
  - `~/tunel_vnc.sh` — túnel SSH simple
  - `~/vnc_control.sh` — túnel + lanzar freebVNC
  - `~/.shortcuts/6_VNC_NOTE9.sh` — shortcut para Termux Widget (un toque)
- **noVNC** también probado: `http://10.31.120.236:5800/vnc.html` cargó en
  Chrome de la tablet (sin túnel necesario), requiere clickear "Connect".

## Vivo V2058: Conexión ADB y widget unificado
- `2026-05-22`: Se conectó un Vivo V2058 por USB al Parrot OS. Autorizada la
  depuración USB y verificado el stack Termux (`com.termux`) con Python, FFmpeg
  y scripts de agentes.
- **Problema:** `2_SUBIR_CRUDOS_YT.sh` no encontraba los 4 crudos (20 GB total)
  en `crudos_pendientes/` porque `video_scanner.py` no se había ejecutado desde
  que se copiaron. El uploader reportaba "Videos pendientes: 0".
- **Solución:** Se fusionó `video_scanner.py` + `uploader.py` en el widget
  `2_SUBIR_CRUDOS_YT.sh`. Ahora ejecuta escaneo antes de subir, garantizando
  que cualquier video nuevo en `crudos_pendientes/` sea detectado y subido.
- **Script instalado:** `~/.shortcuts/2_SUBIR_CRUDOS_YT.sh` en el Vivo.
  Fuente en repo: `scripts/linux/subir_crudos_yt_widget.sh`.
- **Logging:** El widget ahora escribe a `widget_logs/2_SUBIR_CRUDOS_YT.log`
  además de mostrar en terminal.
