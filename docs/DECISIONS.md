# Decisiones Arquitectonicas - Repo agentes

## 2026-04-20: Mantener hibernacion desactivada en Windows para dual boot con Parrot OS
- Contexto: en esta maquina el usuario necesita acceder desde Parrot OS a la
  particion NTFS de Windows. La sesion mostro `HiberbootEnabled = 0`, pero la
  hibernacion seguia activa, existia `C:\hiberfil.sys` y el registro de
  `Kernel-Power` mostraba entradas recientes `Event ID 42` por
  `Hibernate from Sleep`.
- Decision: desactivar la hibernacion del sistema (`powercfg /hibernate off`)
  y mantener el arranque rapido apagado para evitar que Linux vea la unidad de
  Windows como hibernada o en estado inseguro.
- Consecuencia: Windows ya no ofrecera el modo `Hibernar` mientras esta
  compatibilidad dual boot sea un requisito operativo.

## 2026-04-06: Corregir nesting accidental de `youtube_uploader`
- Contexto: el subproyecto estaba fisicamente dentro de `agentes/agentes/`,
  mientras otros subproyectos funcionales del repo viven en la raiz.
- Decision: mover `youtube_uploader` a `youtube_uploader/` en la raiz del repo
  y actualizar automatizacion, documentacion y scripts para no depender de la
  ruta vieja.
- Consecuencia: cualquier referencia a `agentes/youtube_uploader` queda
  obsoleta y debe tratarse como deuda ya cerrada.

## 2026-04-23: Ecosistema Shadow (Linux vs Windows) para Agentes
- Contexto: Con la desactivación de hibernación/fast-boot en Windows, el equipo usa Parrot OS (Linux) para ciertas tareas críticas, lo que expuso la dependencia de todo el repositorio a scripts de PowerShell (`.ps1`).
- Decision: Crear una jerarquía de scripts equivalente en `scripts/linux/` (`iniciar_agentes.sh`, `start_agent_meta.sh`, `subida_fb_fotos.sh`, etc.) para garantizar "paridad operativa". Los entornos virtuales (`.venv`) y rutas se construyen de forma agnóstica al OS.
- Consecuencia: Las futuras automatizaciones deben entregarse con scripts dobles: un `.ps1` para Windows y un `.sh` para Linux que invoquen al mismo entrypoint Python.

## 2026-04-23: Entorno Linux para la Migracion YouTube -> Facebook (Vigía 4K)
- Contexto: El usuario requiere automatizar la descarga de ~580 videos desde YouTube a su disco duro para ser pasados a Meta, enfrentando limites de cuota de API (Error 403) y bloqueos HLS (SABR Streaming). Por seguridad con BitLocker, esta operacion corre en Parrot OS sobre Microsoft Edge for Linux y herramientas open-source nativas, de forma agnostica al Windows original.
- Decision: El agente migrador se creo como herramienta exclusiva de Linux. Se dividio el proceso de descarga `yt-dlp` en 2 tracks asíncronos (video puro + audio puro) con clientes independientes (`ios`, `tv`, `web`, `mweb`).
- Consecuencia: Requerimos empaquetar de vuelta con `ffmpeg` local. Los reintentos por fragmento se redujeron para forzar rotacion rapida de clientes y evadir soft-bans de IP por parte de YouTube.

## 2026-06-09: Album diario Facebook — album por fecha, teaser inmediato y confirmacion remota
- Contexto: se creó `meta_uploader/photo_uploader/album_diario.py` para publicar álbumes de Facebook agrupados por fecha de archivo (`Fotos YYYY-MM-DD`) y mantener el archivo local ordenado.
- Decisiones:
  1. DNG→JPEG con `-quality 100` en ImageMagick para minimizar pérdida antes de la recompresión de Facebook.
  2. El teaser ya no se programa a las 20:00 COL; se publica inmediatamente después de subir todas las fotos del álbum.
  3. Antes de archivar, el script confirma por Graph API que el álbum existe, las fotos pertenecen al álbum y el teaser figura publicado.
  4. La carpeta local se mantiene como `fotos_subidas_album/Fotos YYYY-MM-DD/`; solo se copia/mueve allí cuando Facebook confirma todo.
  5. `META_FB_PAGE_TOKEN` debe ser token `PAGE`; si entra un token `USER`, el script deriva un Page Access Token en memoria.
  6. El teaser usa caption en inglés y carrusel distribuido: divide el álbum en segmentos y elige la foto más pesada de cada segmento como proxy de calidad.
  7. Tras prueba viva, `POST /{page-id}/albums` se trata como capability externa de Meta: si falla con `(#3) Application does not have the capability to make this API call`, el script aborta con diagnóstico claro y solo usa fallback si se configuró un álbum existente.
  8. El flujo Linux usa `facebook_album_web_auto.py` como preflight por Edge para crear álbumes faltantes automáticamente antes de subir fotos por Graph API.
  9. Fechas con una sola foto se agrupan en `Fotos sueltas`; fechas con `2+` fotos conservan `Fotos YYYY-MM-DD`.
  10. Las fotos se suben como JPEG seguro `2048px`/`sRGB`/EXIF aplicado/`quality=88` para evitar rechazos `Invalid parameter` en panorámicas gigantes.
- Consecuencia: la carpeta local representa contenido confirmado en Facebook, no intentos parciales ni publicaciones no verificadas.

## Estrategia YouTube Teaser Uploader (2026-04-21)

- **Aislamiento Total:** Se decidio que el Agente de Teasers sea un script 100% independiente (`teaser_uploader.py`) en lugar de añadir flags a `uploader.py`. Esto garantiza que los teasers/shorts jamas contaminen el sistema de playlists de los crudos largos.
- **Monitoreo de Procesamiento Asincrono:** Para evitar videos "zombies" (trabados en procesamiento HD), se implemento un sistema de hilos (`threading`) que verifica el estado del video en YouTube durante 10 minutos (20 intentos) en paralelo. Esto permite que la subida principal continue sin esperas bloqueantes.
- **Politica de Nombres Limpios:** Se usa Regex agresivo para eliminar `ig_compat_` y `slice_60s_` pero preservando el timestamp numerico original (`\d{8}_\d{6}`).
- **Ratio de Publicacion 1:3:** Se establecio que el bot publique 1 video de forma inmediata (`public`) y los siguientes 3 de forma programada (`private` con `publishAt`), repitiendo el ciclo para mantener relevancia en el feed sin saturar.

## Arquitectura de Teasers de 16s y Prevención de "Videos Zombies" (2026-04-27)
- Contexto: El usuario solicitó automatizar la generación de extractos tipo teaser desde los "crudos" largos. Requirió cortar el material en segmentos objetivo de 16 segundos, publicarlos como una serie ordenada `#teaser #1`, `#teaser #2`, etc., y no dejar que el pipeline continúe hasta confirmar que YouTube sí terminó de procesarlos.
- Decision: Se creó `teaser_generator.py` apoyado en `ffmpeg -f segment -c copy -segment_time 16` para generar cortes rápidos; `teaser_uploader.py` ahora consume esos archivos ordenados por serie y número, asigna el sufijo `#teaser #N`, y agenda estrictamente un teaser por día a las `17:45` hora de Colombia. Además, tanto `teaser_uploader.py` como `uploader.py` conservan los hilos verificadores y hacen `.join()` antes de cerrar, de modo que `start_agent_youtube.sh` no avanza al siguiente bloque mientras `youtube.videos().list(part="processingDetails")` no confirme estado sano o timeout explícito.
- Consecuencia: Se resolvió la carga administrativa de cortar videos. El pipeline actual `start_agent_youtube.sh` es monolítico pero robusto.

## Optimizacion Photo Uploader (2026-04-21)

- **Evitar Re-procesamiento 4K:** En lugar de renderizar el Reel de 30s desde fotos originales 10 veces, se procesa cada foto una sola vez a un mini-Reel de 5s, se sube, y luego se usan esos mini-MP4s para "coser" el Reel combinado usando el concat demuxer de FFmpeg.
- **Persistencia de Assets:** Los Reels individuales generados se conservan en `reels_generados_fb` para su re-uso optimo en Instagram u otras redes.

## 2026-04-06: Los docs raiz quedan reservados para el repo contenedor
- Contexto: la memoria del repo raiz habia quedado mezclada con estado operativo
  especifico de `youtube_uploader`.
- Decision: las decisiones y el progreso de cada subproyecto deben vivir en su
  propio `docs/`, mientras `docs/` en la raiz se usa para reglas del contenedor,
  automatizacion compartida y estructura del workspace.

## 2026-04-06: Estrategia de Doble Via (Double Track)
Se decidio implementar un calendario paralelo para Videos y Shorts para
maximizar el alcance del canal. El uploader ahora detecta huecos de forma
independiente por tipo.

## 2026-04-06: Clasificacion de Shorts (3 Min Rule)
Se adopto la nueva politica de YouTube de permitir Shorts de hasta 3 minutos
para videos verticales, actualizando los scripts de clasificacion locales y
del canal.

## 2026-04-06: Prefijo de Titulos (PW)
A solicitud del usuario, se cambio el prefijo de los titulos de
"Performatic Writings" a "PW" para mayor brevedad y consistencia visual en el
canal.

## 2026-04-06: Automatizacion en la raiz del repo para los subproyectos
- Contexto: `youtube_uploader` y `meta_uploader` viven dentro de este repo,
  pero no son repos Git separados.
- Decision: la capa `.antigravity/automation.json` se registra en la raiz del
  repo `agentes` y valida sintaxis de los subproyectos funcionales y del
  bootstrap `scripts/init-agents.ps1`.

## 2026-04-09: Monitor de logs en tiempo real para Meta y YouTube
- Contexto: el usuario necesita observar en consola el avance de Meta Facebook,
  Meta Instagram y YouTube sin depender de preguntar a la IA cada vez.
- Decision: agregar `scripts/monitor_realtime.py` como herramienta de solo
  lectura sobre los logs locales, mas un launcher `.bat` reutilizable.
- Consecuencia: si cambian los formatos de `meta_uploader.log`,
  `meta_uploader_facebook.log`, `meta_uploader_instagram.log` o `uploader.log`,
  tambien debe actualizarse el monitor para no romper la observabilidad.


## 2026-05-18: Pipeline completo S24 con solapamiento de uploads
- Contexto: El flujo anterior requería ejecutar 4 widgets manualmente en
  secuencia (1_CORTAR_TEASERS → 3_SUBIR_TEASERS → 2_SUBIR_CRUDOS →
  4_VIGIA_FACEBOOK), con tiempos muertos entre cada crudo y entre YouTube y
  Facebook.
- Decisión: Crear `0_PIPELINE_COMPLETO.sh` que orquesta toda la cadena en un
  solo script. Cada crudo se procesa individualmente: corta teasers → sube
  teasers (espera confirmación) → inicia subida del crudo en BACKGROUND → pasa
  al siguiente. Las subidas de crudos se solapan (crudo N+1 empieza mientras
  crudo N aún se sube). Facebook se lanza inmediatamente después de cada subida
  exitosa y al final del pipeline.
- Consecuencia: Sin tiempos muertos entre crudos ni entre YouTube y Facebook.

## 2026-05-18: Facebook evacuador paralelo con confirmación
- Contexto: `subir_fb_evacuador.py` subía videos a Facebook uno tras otro,
  esperando confirmación de procesamiento antes de empezar el siguiente.
- Decisión: Cada video se sube en su propio hilo Python con `background=False`
  (espera confirmación). Todos los hilos corren simultáneamente. El archivo se
  mueve a "subidos a facebbok" solo cuando su hilo confirma procesamiento.
- Consecuencia: Múltiples videos se suben a Facebook en paralelo, cada uno se
  mueve apenas está confirmado, sin bloquear a los demás.

## 2026-05-18: Pipeline v4-v6 — eliminación del loop, markers y paralelismo por teaser
- Contexto: El pipeline original (`0_PIPELINE_COMPLETO.sh` v1) llamaba a `teaser_generator.py`
  dentro del while loop de cada crudo, causando un loop infinito de cortes sin avanzar a subidas.
  Además, los teasers se subían secuencialmente (un proceso bloqueante por crudo) y el crudo
  arrancaba solo después de subir todos los teasers.
- Decisión v2: Eliminar la llamada redundante a `teaser_generator` dentro del loop.
- Decisión v3: `teaser_generator` corre en background; un loop vigilante revisa cada 2s y sube
  teasers al instante cuando aparecen. Crudo arranca 2s después del primer teaser.
- Decisión v4: Corregido — crudo arranca 2s después del ÚLTIMO teaser subido. Se añade
  `--single-file` y `--state-dir` a `teaser_uploader.py` para subir teasers individuales y
  escribir marker `.uploaded` apenas la API devuelve éxito (sin esperar processing de YT).
- Decisión v5: Conteo dinámico de teasers (sin hardcodear "3").
- Decisión v6: `teaser_generator` vuelve a foreground para que el usuario vea los logs en
  tiempo real. Después de cortar, lanza todos los teasers en paralelo. Espera markers
  `.uploaded` → 2s → crudo.
- Consecuencia: Pipeline sin loop, cada teaser se sube en su propio proceso, crudo arranca
  solo cuando todos los teasers terminaron de subirse.

## 2026-05-18: teaser_generator con escritura atómica y markers
- Contexto: `teaser_generator.py` escribía teasers directamente al `.mp4` final. El pipeline
  u otros procesos podían detectar el archivo antes de que `ffmpeg` terminara, causando
  subidas de archivos truncados o loops de detección.
- Decisión: Escribir a `<nombre>.part` y renombrar (`os.replace`) solo cuando `ffmpeg` termina
  con éxito. Además, crear markers `.state/<crudo>.lock` (mientras procesa) y
  `.state/<crudo>.done` (cuando termina) para evitar reprocesos y ejecuciones paralelas.
- Consecuencia: Subidas nunca ven archivos incompletos. Pipeline no reprocesa el mismo crudo.

## 2026-05-18: Bitrate de teasers incrementado a 70 Mbps
- Contexto: Los teasers generados vía HW transcode (HEVC → H.264 mediacodec)
  usaban `-b:v 6000k` (6 Mbps), insuficiente para 4K, causando pixelación.
- Decisión: Subir a `70000k` (70 Mbps) en `teaser_generator.py:85`. El encoder
  HW del S24 maneja cualquier bitrate hasta ~100 Mbps sin impacto en velocidad.
- Consecuencia: Teasers sin pérdida visible de calidad.

## 2026-05-17: Control remoto Note 9 vía VNC+SSH (no ADB WiFi)
- Contexto: Se intentó ADB WiFi desde la tablet SM-X210 al Note 9 SM-N9600 para
  control remoto, pero el Note 9 nunca autorizaba a la tablet (permanecía
  "unauthorized") a pesar de `alwaysAllow=true`.
- Decisión: Abandonar ADB WiFi. En su lugar, usar droidVNC-NG (VNC server) +
  OpenSSH (túnel). La tablet crea un túnel SSH al Note 9 y conecta freebVNC
  a `localhost:5900`.
- Consecuencia: Control remoto funcional con VNC. También disponible noVNC vía
  navegador (puerto 5800, sin túnel).

## 2026-05-26: TikTok Uploader como subproyecto independiente
- Contexto: El usuario necesita publicar videos en TikTok desde una interfaz web automatizada. No existe integración previa con TikTok en el repo.
- Decision: Crear `tiktok_uploader/` como subproyecto independiente con su propio contexto (AI.md, AGENTS.md, docs/), siguiendo el patrón de `youtube_uploader`.
- Consecuencia: El subproyecto tiene su propio ciclo de vida, documentación y configuración, aislado de YouTube y Meta.

## 2026-05-26: OAuth login via 302 redirect en vez de JS redirect
- Contexto: Cloudflare proxy en el túnel corrompía redirecciones JS.
- Decision: Usar `Flask.redirect()` (HTTP 302) para `/login`, sin JS client-side.
- Consecuencia: Flujo OAuth funcional detrás de cualquier proxy.

## 2026-05-26: localhost.run como túnel primario, trapdoor.sh como fallback
- Contexto: trapdoor.sh devolvía 429 (rate limit) y 502 (bad gateway) persistentemente en Parrot OS.
- Decision: Usar localhost.run (SSH reverse tunnel) como túnel principal por su estabilidad y cero configuración.
- Consecuencia: Cada reinicio del túnel genera un nuevo subdominio `.lhr.life`, obligando a actualizar manualmente la Redirect URI en el portal de TikTok.

## 2026-05-26: Redirect URI dinámica resuelta desde headers del proxy
- Contexto: La URL del túnel cambia constantemente; hardcodear REDIRECT_URI era insostenible.
- Decision: Implementar `ProxyFix` middleware y resolver `redirect_uri` dinámicamente desde `X-Forwarded-Proto` y `X-Forwarded-Host` en cada request.
- Consecuencia: La app funciona con cualquier URL de túnel sin cambios de configuración; la Redirect URI en el portal de TikTok aún debe coincidir.

## 2026-05-26: Static site en GitHub Pages + app dinámica detrás de túnel
- Contexto: TikTok requiere website público con páginas legales y punto de entrada de login.
- Decision: Hostear sitio estático (index, privacy, terms, data-deletion) en GitHub Pages. La app Flask corre detrás de túnel SSH con URL dinámica.
- Consecuencia: Dos dominios separados. El reviewer debe seguir el enlace de login desde el sitio estático hacia el túnel.

## 2026-05-26: terms.html convertido a directorio para verificación TikTok
- Contexto: TikTok requiere archivo verificador en `.../terms.html/tiktok...txt`.
- Decision: Convertir `terms.html` de archivo a directorio (`terms.html/index.html`).
- Consecuencia: URL de términos es `https://zerausn.github.io/agentes/terms.html/` (con slash final).

## 2026-05-26: Config.py refactorizado con env vars
- Contexto: Config tenía valores hardcodeados que requerían edición manual al cambiar de túnel.
- Decision: Extraer `PUBLIC_BASE_URL`, `REDIRECT_URI`, `PORT`, `DEBUG`, `SECRET_KEY` a variables de entorno, con defaults funcionales. Helper `_env_list()` para scopes.
- Consecuencia: Deployment configurado por entorno; mismo código funciona en desarrollo y producción.


## 2026-07-01: Vigía Teasers YT720 — bash loop anti-Doze con upload individual
- Contexto: El widget `3_SUBIR_TEASERS_YT` original subía TODOS los teasers pendientes de una sola vez y terminaba. No había loop, no había wake-lock, no había resiliencia contra Doze. El Note 9 necesita un flujo constante de contenido en YouTube (1 teaser cada 12 minutos) sin ser congelado por Doze.
- Decisiones:
  1. **Patrón idéntico a VIGIA_FACEBOOK720:** loop bash con `termux-wake-lock`, `date +%s` para reloj, `wait_until(epoch)` con chequeos de 15s — probado y certificado con 3s de latencia real en Note 9.
  2. **Reutilizar `teaser_uploader.py --single-file --from-orchestrator`** en vez de crear un nuevo script Python. El flag `--single-file` ya existía; `--from-orchestrator` saltea el lock de instancia.
  3. **Sin timeout:** El uploader hace faststart + upload + verificación de processing de YouTube (puede tardar 10+ min). Timeout de 180s hubiera matado el verifier antes de mover el archivo a `videos subidos exitosamente/`.
  4. **Detección de límite diario via log file:** Cuando YouTube responde `uploadLimitExceeded`, el uploader logea `LIMIT_EXCEEDED` en su archivo de log. El bash loop lee las últimas líneas del log después de cada subida fallida. Si detecta el límite, cambia a modo LIMITED (1h entre reintentos).
  5. **Output en vivo:** El stdout/stderr del uploader fluye directamente al session log (no se captura en variable como en la primera versión).
  6. **Conteo de pendientes:** Cada ciclo muestra `[PENDIENTES] N teasers restantes` para que el usuario sepa cuántos faltan.
- Consecuencia: 4 archivos nuevos (widget, bash loop, shortcut, docs). Ningún archivo existente fue modificado.

## 2026-07-01: Detección estricta de Aspect Ratio para Facebook Reels
- Contexto: El endpoint `video_reels` de Facebook falla categóricamente si recibe un video horizontal, pero el script `subir_fb_evacuador_720.py` forzaba la subida de todo archivo que contuviera la palabra `_teaser_`, asumiendo que siempre eran verticales.
- Decision: Replicar la política de `classify_meta_videos.py`: usar `ffprobe` en tiempo de subida para verificar la relación de aspecto exacta (tolerancia de 9:16 ±8%). Si es horizontal, se degrada a una subida estándar de post de Facebook.
- Consecuencia: Mayor tolerancia a inconsistencias en la fase de render. Los teasers horizontales ya no bloquearán la cola ni generarán errores terminales de API, publicándose exitosamente como videos normales.

## 2026-04-10: Unificar la convención de Meta
- Contexto: el usuario decidio que "sube videos a Meta" debe apuntar al flujo
  programado vigente, y que el carril previo de Meta pase a llamarse
  "videos optimizados".
- Decision: documentar `meta_uploader/schedule_jornada1_supervisor.py` como
  entrypoint humano recomendado para Meta, dejando `run_jornada1_normal.py`
  como constructor/runner base y `meta_uploader.py` como capa de subida.
- Consecuencia: los docs del repo deben usar "videos optimizados" para el
  carril `second_pass/`, aunque el folder tecnico siga existiendo por ahora.

### Fix Global de SDCard en Termux/Debian (Android 11+)
- **Problema:** En Android 11+ (ej: Vivo), Termux perdía el enlace de FUSE a `/sdcard` al entrar al proot-distro de Debian, causando fallos de "carpeta vacía" o "permisos denegados".
- **Solución:** Se implementó un script ayudante `scripts/linux/_proot_bind.sh` que detecta la ruta real de FUSE (ej: `/storage/emulated/0`) y la expone como `/sdcard` en Debian con `--bind`. Se parchearon automáticamente todos los widgets para inyectar este ayudante antes de arrancar `"$PROOT" login debian`.

### Fix de Identidad de Git en Entornos Limpios
- **Problema:** En entornos `proot-distro` recién inicializados (ej: Vivo), el paso `git commit` fallaba silenciosamente con un error de "Author identity unknown".
- **Solución:** Se configuró explícitamente dentro del Debian de los dispositivos de producción la identidad de Git (`zerausn@gmail.com` / `zerausn`) para que el script `sync_push()` pueda crear commits sin interrupciones.

## 2026-09-21: Fix error (#200) en upload de teasers a Shirabyoshi Writings (S24)

### Contexto
El agente `4_VIGIA_FB_TEASERS` (widget en S24) fallaba consistentemente con:
`(#200) Subject does not have permission to post videos on this target`
al intentar subir videos de teaser a la página **Shirabyoshi Writings** (ID: `1347014641828725`).

### Causa Raíz
Triple fallo en la cadena de credenciales:

1. **Token incorrecto:** El `META_FB_PAGE_TOKEN_TEASER` almacenado en `~/.agentes_termux_env`
   del S24 era un token de tipo `SYSTEM_USER` (derivado de Business Manager) en lugar de un
   `PAGE` Access Token. Los tokens `SYSTEM_USER` no tienen permisos de `publish_video` sobre
   páginas individuales a través del endpoint `/video_reels`.

2. **Variables sin `export`:** El archivo `~/.agentes_termux_env` usaba asignación directa
   (`VAR=valor`) en lugar de `export VAR=valor`. El shell bash las hereda dentro del mismo
   proceso, pero **proot-distro** las limpia completamente al hacer `login debian`. Python
   jamás recibía `META_FB_PAGE_TOKEN_TEASER`.

3. **Fallback catastrófico:** Al recibir string vacío para el token de Shirabyoshi, el código
   de `subir_fb_evacuador_teasers.py` caía al fallback `META_FB_PAGE_TOKEN` (token de
   Performatic Writings Cali), que tampoco tiene permisos sobre Shirabyoshi.

### Solución Aplicada

**a) Regeneración del Page Token de Shirabyoshi:**
Se usó `META_PAGE_TOKEN` (System User Token) para derivar el Page Access Token correcto
vía `GET /{page-id}?fields=access_token`. Este token derivado es de tipo `PAGE`, tiene
`profile_id=1347014641828725` y acepta `publish_video` en el endpoint `/video_reels`. 

Verificación con prueba de subida real:
```
POST /v21.0/1347014641828725/video_reels → start: video_id OK
Binary upload: 100% → upload: success:true
Finish: success:true, post_id: 122153788701044766
```

**b) Fix en `~/.agentes_termux_env` (S24):**
Se añadió `export` a todas las variables `META_*` para que proot-distro las herede:
```bash
# ANTES (roto)
META_FB_PAGE_TOKEN_TEASER=EAAUr7rt...
# DESPUÉS (correcto)
export META_FB_PAGE_TOKEN_TEASER=EAAUr7rt...
```

**c) Fallback hardcodeado en `subir_fb_evacuador_teasers.py`:**
Se agregó el token como valor por defecto en el `os.environ.get()`, garantizando
que incluso si proot limpia el entorno, el script tenga credenciales válidas:
```python
FB_PAGE_TOKEN_TEASER = os.environ.get(
    "META_FB_PAGE_TOKEN_TEASER",
    "EAAUr7rtgpvMBSmu..."  # fallback a prueba de proot
)
```

**d) Override global en `upload_video()`:**
Se añadió inyección de credenciales en los globales del módulo `meta_uploader`
antes de cualquier llamada a la API, para evitar que `_start_fb_upload` o
`_finish_fb_upload` usen el token equivocado:
```python
import meta_uploader
meta_uploader.META_FB_PAGE_TOKEN = page_token
os.environ["META_FB_PAGE_TOKEN"] = page_token
```

**e) Actualización de `META_GRAPH_API_VERSION` a `v21.0`:**
El `.env` local y en S24 usaban `v19.0` (febrero 2024). Se actualizó a `v21.0`
como prevención de deprecaciones. El cambio se sincronizó al S24 vía ADB.

### Archivos Modificados
- `meta_uploader/.env` — token + `META_GRAPH_API_VERSION=v21.0`
- `meta_uploader/subir_fb_evacuador_teasers.py` — fallback hardcoded + override global
- `meta_uploader/meta_uploader.py` — `get_facebook_page_feed()` acepta `page_id`/`page_token`
- `meta_uploader/fb_to_ig_vigia.py` — soporte multi-página (ver decisión siguiente)
- S24 `~/.agentes_termux_env` — `export` en todas las variables `META_*`
- S24 `scripts/linux/vigia_meta720_termux.sh` — inyecta tokens de Shirabyoshi en proot

### Consecuencia
Los teasers de Shirabyoshi Writings se suben sin error `(#200)`. El patrón de
fallback hardcoded en el script Python protege contra futuros borrados accidentales
del token en el entorno de Termux/proot.

---

## 2026-09-21: `fb_to_ig_vigia.py` ahora reconcilia MÚLTIPLES páginas de Facebook → Instagram

### Contexto
El Vigía solo leía el feed de **Performatic Writings Cali** (`META_FB_PAGE_ID`).
La página **Shirabyoshi Writings** también publica contenido que debe cruzarse a Instagram.

### Decisiones

1. **Lista `FB_PAGES`:** Se declara en el módulo como lista de tuplas `(page_id, page_token, page_name)`.
   Se lee de variables de entorno con fallback hardcoded para resistencia a proot:
   ```python
   FB_PAGES = [
       (os.environ.get("META_FB_PAGE_ID", ...), ..., "Performatic Writings Cali"),
       (os.environ.get("META_FB_PAGE_ID_TEASER", "1347014641828725"), ..., "Shirabyoshi Writings"),
   ]
   ```

2. **`get_facebook_page_feed()` con `page_id`/`page_token` opcionales:**
   Se extendió la firma para aceptar credenciales específicas por página sin mutar
   las variables globales del módulo. Retrocompatible: si no se pasan, usa los globales.

3. **Orden más reciente primero:** Se recopilan todos los posts de todas las páginas,
   se mezclan en una lista única y se ordenan descendente por `created_time` antes de
   procesar. Así el content más fresco llega primero a Instagram.

4. **Logs con prefijo de página:** Cada línea del log indica `[Shirabyoshi Writings]`
   o `[Performatic Writings Cali]` para facilitar trazabilidad.

5. **`vigia_meta720_termux.sh` actualizado:** Inyecta `META_FB_PAGE_TOKEN_TEASER` como
   variable de entorno explícita en el contexto proot antes de ejecutar Python.

### Consecuencia
El cruce FB→IG ahora cubre ambas páginas. Los posts más recientes (de cualquier página)
tienen prioridad. El registro de deduplicación compartido (`crosspost_dedupe_registry.json`)
evita duplicados entre páginas.

---

## 2026-09-22: Vigía v4.0 — Escaneo por bloques de 100 con fallback al reporte histórico

### Contexto
`fb_to_ig_vigia.py` usaba un early-stop que cortaba el escaneo en cuanto detectaba
3 posts consecutivos ya publicados. Esto era demasiado agresivo: si los últimos
3 posts en el feed ya estaban publicados pero había contenido nuevo en los primeros
100 posts, el Vigía no lo encontraba.

Además, el script no tenía una estrategia clara para el backlog histórico de ~8,945
posts identificados por `audit_crosspost.py`.

### Decisiones

1. **Escaneo por bloques de 100 por página:**
   Cada ciclo descarga hasta 5 bloques de 100 posts por página (usando
   paginación por cursor de la API de FB). Si dentro de un bloque hay
   al menos un post no publicado, se elige el más reciente y se interrumpe
   el escaneo de esa página. Si el bloque completo ya fue publicado, se pasa
   al siguiente bloque.

2. **Candidato más reciente entre páginas:**
   Si *Performatic* y *Shirabyoshi* tienen cada una un candidato nuevo,
   se sube el más reciente (por `created_time`).

3. **Fallback al reporte histórico:**
   Si tras 5 bloques de 100 posts (500 posts) ninguna página tiene contenido
   nuevo, el Vigía consulta `missing_crossposts_report.json` (generado por
   `audit_crosspost.py`) y toma el entry más antiguo que aún no haya sido publicado.
   Hace un fetch adicional a la API de FB para obtener el post completo con media.

4. **Pre-filtro de posts sin media en la búsqueda de candidato:**
   `_find_newest_uncrossposted()` ahora verifica que el post tenga media
   (foto o video) antes de seleccionarlo como candidato. Posts de solo texto
   se marcan en el registro como procesados (sin remember_keys) para no volver
   a evaluarlos, y el buscador continúa en el mismo bloque hasta encontrar
   uno con media. Esto evita gastar un ciclo de 720s solo para descartar
   un post de texto.

5. **Límite de 1 post por ciclo respetado en Python:**
   La función `process_new_posts()` retorna `1` apenas sube exitosamente
   un post. El shell bash (`vigia_meta720_termux.sh`) es quien decide cuándo
   re-ejecutar (cada 720s), de modo que Python no hace ningún `time.sleep` interno.

### Archivos Modificados
- `meta_uploader/fb_to_ig_vigia.py` — reescritura completa v4.0 (funciones
  `_fetch_block`, `_find_newest_uncrossposted`, `_pick_from_report`,
  `_resolve_full_post_from_report_entry`, `process_new_posts`)

### Consecuencia
El sistema ahora cubre los posts más recientes de forma eficiente (O(bloques)),
sin iterar todo el historial en cada ciclo. El backlog histórico se drena
gradualmente como último recurso. Los posts de solo texto no bloquean el ciclo.

---

## 2026-09-22: Fix `upload_fb_reel` y `upload_fb_video_standard` — soporte de `page_id`/`page_token`

### Contexto
El widget `4_VIGIA_FB_TEASERS` fallaba con:
```
TypeError: upload_fb_reel() got an unexpected keyword argument 'page_id'
```
`subir_fb_evacuador_teasers.py` pasaba `page_id` y `page_token` a `upload_fb_reel()`
para subir a Shirabyoshi Writings, pero la firma de esa función no aceptaba
esos parámetros.

### Solución
Se agregaron `page_id=None` y `page_token=None` a las firmas de:
- `upload_fb_reel()`
- `upload_fb_video_standard()`

Ambas funciones usan un bloque `try/finally` para sobreescribir temporalmente las
variables globales `FB_PAGE_ID` y `META_FB_PAGE_TOKEN` con los valores recibidos,
y las restauran al valor original al salir (incluso en caso de error). Esto permite
publicar en cualquier página sin mutar el estado global de forma permanente.

### Archivos Modificados
- `meta_uploader/meta_uploader.py` — firmas extendidas con `try/finally`
  para `upload_fb_reel` y `upload_fb_video_standard`

### Consecuencia
Cualquier script evacuador puede pasar sus propias credenciales de página
sin necesidad de sobreescribir variables de entorno globales. Retrocompatible:
si no se pasan `page_id`/`page_token`, el comportamiento es idéntico al anterior.

---

## 2026-09-22: Fix de permisos en workspace Codex (`.git/objects` propiedad de root)

### Contexto
El workspace `~/Documents/Codex/2026-08-17/rev/work/agentes-linux-arm64/` (usado
por otra instancia de IA) tenía los directorios dentro de `.git/objects/`
propiedad de `root:root` debido a que en algún momento un comando había corrido
con `sudo`. Esto impedía cualquier operación de escritura de Git (`git commit`,
`git push`) desde ese workspace.

### Solución
1. Se identificó el commit pendiente en el workspace bloqueado: `c67612a`
   (`feat: Facebook bifurcation system - parallel independent vigilantes`).
2. Desde el workspace principal (`/home/zerausn/Documents/Antigravity/agentes`)
   se hizo `git fetch` local del workspace Codex:
   ```bash
   git fetch ~/Documents/Codex/.../agentes-linux-arm64 linux-arm64:refs/remotes/codex/linux-arm64
   ```
3. Se aplicó el commit vía `cherry-pick`. El único conflicto fue en
   `meta_uploader.py` (el Codex tenía la versión antigua de la función;
   se aceptó la versión más reciente con `git checkout --ours`).
4. Push exitoso del commit `0520001` a `origin/linux-arm64`.
5. El usuario ejecutó `sudo chown -R zerausn:zerausn .git` para reparar
   los permisos del workspace Codex.
6. El workspace Codex quedó sincronizado con `origin/linux-arm64` mediante
   `git pull --rebase origin linux-arm64` y un nuevo push limpio.

### Consecuencia
Ambos workspaces (`Antigravity/agentes` y `Codex/agentes-linux-arm64`) apuntan
ahora al mismo HEAD en `origin/linux-arm64`. La otra IA puede hacer commits
y pushes sin restricciones.
