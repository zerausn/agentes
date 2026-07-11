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

## Album Diario Facebook (album_diario.py)
- `meta_uploader/photo_uploader/album_diario.py` creado: álbum por fecha (`Fotos YYYY-MM-DD`), sube fotos y publica teaser carrusel inmediato.
- Calidad DNG→JPEG en `100` para máxima calidad antes de la recompresión de Facebook.
- Progreso visible por álbum: foto actual, porcentaje, fotos restantes, tiempo transcurrido y ETA.
- Confirmación remota antes de archivar: Graph API verifica álbum, IDs de fotos y teaser publicado.
- Carpeta local por álbum en `fotos_subidas_album/Fotos YYYY-MM-DD/` con `copy2`; solo se usa tras confirmar Facebook.
- Token operativo corregido: `META_FB_PAGE_TOKEN` debe ser token `PAGE`; si entra `USER`, el script deriva token de página en memoria.
- Teaser en inglés con headline fuerte, pregunta final y carrusel distribuido por segmentos, priorizando fotos más pesadas.

## Vivo V2058 — Widgets Vigía Facebook (4_VIGIA_FACEBOOK)
- **Problema:** `run-as com.termux` no puede acceder a `/sdcard/` en Vivo V2058 (restricción FUSE de Vivo). El staging en `$PR_ROOT/sdcard/` falla porque ese directorio tiene permisos `000`.
- **Solución:** Cambiar staging a `$PR_ROOT/root/antigravity_staging/` (escribible) y usar `AGENTES_STORAGE_ROOT=/root/antigravity_staging` dentro del proot.
- **Scripts corregidos:**
  - `4_VIGIA_FACEBOOK.sh` — copia todos los videos, ejecuta evacuador batch, copia resultados de vuelta.
  - `4_VIGIA_FACEBOOK720.sh` — procesa 1 video por vez con espera de 720s entre cada uno.
- **Prueba funcional exitosa (via ADB pipe):** video 180MB subido a Facebook desde proot con `AGENTES_STORAGE_ROOT=/root/antigravity_staging` — 1 éxito, 0 fallos.
- **Pendiente:** Probar desde el widget drawer de Termux (no se puede disparar desde ADB por FUSE). Los logs quedan en `~/antigravity_vigia.log` y `~/antigravity_vigia_720.log`.

## TikTok Uploader (tiktok_uploader/)
- `tiktok_uploader/` creado como subproyecto para publicar videos en TikTok via Content Posting API.
- App Flask con OAuth login (scopes: user.info.basic, video.upload, video.publish), subida y publicación de videos.
- App "Uploaderbot" registrada en TikTok Developers (client_key: `awhfxd65i4i468x8`).
- Website desplegado en GitHub Pages (`zerausn.github.io/agentes/`) con páginas legales, app icon y favicon.
- Verificación URL prefix completada (meta tag + TXT + redirect URL).
- Productos añadidos en portal: Login Kit, Content Posting API, Share Kit.
- Cuenta sandbox `performaticwritingscali` agregada como Target User.
- PR #3 mergeado a main con cambios de verificación TikTok.
- **App review rechazada 2 veces** (2026-06-18): 3 issues — login entry point, app icon, review description.
- Tunnel localhost.run activo como alternativa a trapdoor.sh (caído con 429/502).
- Rama `tiktok` creada con documentación completa del subproyecto.

## Fix Android Doze Mode — VIGIA_FACEBOOK720 (2026-06-21)
- **Problema diagnosticado:** `time.sleep(720)` en Python dentro de proot-distro
  se congelaba por Android Doze Mode. Ciclos reales: 62-90 min en vez de 12 min.
  Confirmado en logs del Note9.
- **Solución implementada:**
  1. `subir_fb_evacuador_720.py` — refactorizado para subir **1 video y retornar**
     (exit 0=ok, 2=vacío, 1=error). Sin `time.sleep` interno.
  2. `vigia_facebook720_termux.sh` — loop bash con `termux-wake-lock` +
     `wait_until(epoch)` basado en `date +%s` chequeando cada 15s.
     Si Doze pausa el proceso, al despertar ve que ya pasaron 720s y actúa
     inmediatamente.
- **Certificado con test real 720s en Note9:**
  - Tiempo planeado: 720s / Tiempo real: 723s / Diferencia: **3s** ✅
- **Archivos nuevos en repo:**
  - `meta_uploader/subir_fb_evacuador_720.py`
  - `scripts/linux/vigia_facebook720_termux.sh`
  - `scripts/linux/shortcut_4_VIGIA_FACEBOOK720.sh`
  - `docs/VIGIA_FACEBOOK720_DOZE_FIX.md`
- **Pendiente:** Implementar en S24 Ultra y Vivo (conectar vivo para deploy).

## Optimización teaser_generator — HW encoding y stream copy (2026-07-01)
- **Problema:** `teaser_generator.py` forzaba `libx264` software encoding en Note 9, resultando en 0.01x–0.17x speed. Thermal throttling mataba la mayoría de los segmentos antes de completarlos.
- **Solución:** 3-path strategy:
  1. Stream copy si el source ya es h264+yuv420p (tarda segundos en vez de minutos).
  2. HW `h264_mediacodec` si el encoder está disponible.
  3. Fallback `libx264`.
- `detect_available_encoders()` con cache (`~/.cache/agentes/encoders.json`) para no escanear FFmpeg cada vez.
- `probe_video_stream_info()` para analizar el stream de video del crudo.
- **Deploy verificado** en Note 9 (SM-N9600), S24 Ultra (SM-S928B) y Vivo V2058.

## 3_SUBIR_TEASERS_YT720 — Widget anti-Doze para YouTube (2026-07-01)
- **Problema:** El widget `3_SUBIR_TEASERS_YT` subía TODOS los teasers de una sola vez y terminaba. Sin loop, sin wake-lock, sin anti-Doze.
- **Solución:**
  1. `vigia_teasers_yt720_termux.sh` — loop bash con `termux-wake-lock`, `wait_until(epoch)` con 15s checks (mismo patrón probado de VIGIA_FACEBOOK720).
  2. Reutiliza `teaser_uploader.py --single-file --from-orchestrator` — sube 1 teaser por ciclo, espera processing de YouTube + `move_file_to_success()`.
  3. Dos modos: NORMAL (720s) y LIMITED (3600s cuando YouTube rechaza por uploadLimitExceeded).
  4. Output del uploader en vivo (sin captura en variable).
  5. Cada ciclo reporta `[PENDIENTES] N teasers restantes`.
- **Archivos nuevos:**
  - `scripts/linux/vigia_teasers_yt720_termux.sh`
  - `scripts/linux/shortcut_3_SUBIR_TEASERS_YT720.sh`
  - `termux_widgets/3_SUBIR_TEASERS_YT720.sh`
  - `docs/VIGIA_TEASERS_YT720_DOZE_FIX.md`
- **Deploy:** Note 9 (widget instalado en `~/.shortcuts/`).

## Fix: Evacuador Facebook Reels Aspect Ratio (2026-07-01)
- **Problema:** El evacuador de Facebook subía todos los videos nombrados como `_teaser_` al endpoint `video_reels` de Meta, ignorando su formato real. Si el video era horizontal (ej. 3840x1644 / 2.33:1), la API de Meta lo rechazaba.
- **Solución:** Se integró `ffprobe` en `subir_fb_evacuador_720.py` para medir el `aspect ratio` real en tiempo de ejecución. Si es un `teaser` y es horizontal, ahora el script hace fallback y lo sube como un video estándar de Facebook para evitar el rechazo de la API.
- **Solución adicional:** Los videos que fallen por cualquier otra razón ahora se mueven a `fallidos_facebook/` para no congelar la cola. Se agregó un contador de videos pendientes al final de cada ciclo del Vigía en Bash.
- **Deploy verificado:** Note 9 (SM-N9600).

## Estabilización y Rendimiento de Descargador YouTube Lotes (2026-07-11)
- **Problema 1 (FUSE Bind):** Fallas en Termux al montar rutas en Android 11+ porque `proot-distro` no puede acceder directamente a `$PR_ROOT/sdcard/`.
  - **Solución:** Implementación global en `scripts/linux/_proot_bind.sh` usando staging estandarizado en `/root/antigravity_staging` para todos los scripts (YouTube y Meta).
- **Problema 2 (Autenticación y Red):** Las sesiones se rompían con `git push` pidiendo contraseñas en segundo plano o fallando por microcortes, causando bloqueos infinitos de la automatización.
  - **Solución:** Inyección de llaves `SSH (ed25519)` individuales en S24, Vivo y Note9. Implementación de una rutina anti-caídas con 3 reintentos en el push de `yt_downloader_lotes_sin_limite.py`.
- **Problema 3 (Branches Divergentes):** Descargas de videos de 1 hora causaban un `fetch first (rejected)` si otro equipo empujaba primero.
  - **Solución:** Inyección de `git pull --rebase origin linux-arm64` antes del `push` asegurando que cada celular absorba las descargas de los demás sin conflictos.
- **Problema 4 (Thermal Throttling / Note9 se apaga):** `ffmpeg` tardaba 26 horas por video 4K debido a re-encoding forzado (`libx264 fast`) agotando la batería.
  - **Solución:** Detección de codec inteligente con `ffprobe`. Si la fuente de YouTube ya es H.264, se realiza un remux instantáneo (`-c copy`) que toma 30 segundos. Para VP9 o AV1, se realiza un fallback a `libx264 ultrafast` para reducir la carga de CPU y el recalentamiento térmico.
- **Problema 5 (Rebases atascados y ejecuciones duplicadas):** S24 y Note9 quedaron en `HEAD (no branch)` por rebases interrumpidos, y varias instancias del widget escribieron al mismo registro/log, provocando commits locales que parecían subidos pero no llegaban realmente a `linux-arm64`.
  - **Solución:** `yt_downloader_lotes_sin_limite.py` ahora valida que Git esté en `linux-arm64`, aborta rebases pendientes antes de sincronizar, no empuja si el rebase falla, usa `git push origin HEAD:linux-arm64` y verifica que el remoto quede en el mismo SHA local. El wrapper `bajar_youtube_sin_limite_termux.sh` crea un lock en `~/.run/5_BAJAR_YOUTUBE_SIN_LIMITE.lock` para impedir ejecuciones simultáneas.
- **Runbook:** ver `docs/YOUTUBE_LOTES_NODOS_MOVILES.md` para la arquitectura de nodos, el incidente S24/Note9, rutas de backup y procedimiento de recuperación.
- **Estado de despliegue:** S24 y Note9 quedaron reparados y alineados con GitHub en `0798c040`. Los tres equipos del escuadrón (S24, Vivo, Note9) deben operar siempre desde `linux-arm64`, haciendo pull antes de decidir pendientes y push tras marcar descargas, para que ningún nodo repita videos ya reportados por otro.
