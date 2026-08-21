# Captura 4K vía Navegador + MITM (bypass del bloqueo de IP de YouTube)

Fecha: 2026-08-18
Estado: VALIDADO en PC (productivo); plan S24 al final

## Problema

- `yt-dlp` recibe 403 "unable to download video data" desde las IPs de Claro (fijo
  `186.168.x` y móvil `191.106.x`, ya sea la misma o una recién rotada por CGNAT).
- VPNs gratuitas (Proton/Windscribe/WARP) NO sirven: salen por IPs de datacenter
  preflaggeadas por YouTube (issue yt-dlp #13336) y con límites de datos.
- El navegador normal (Edge/Chrome/Firefox) **sí reproduce 4K desde la misma IP**
  bloqueada: su sesión (cookies + po-token) es confiable para YouTube mientras que
  el fingerprint de yt-dlp no lo es (issue #15865: mismo PC, incógnito reproduce,
  yt-dlp no).

## Solución

Interceptar el tráfico *media* del navegador con **mitmproxy**, capturar el nuevo
transporte **UMP** (`application/vnd.yt-ump`) que YouTube usa desde 2025/2026,
extraer el fMP4 embebido en el protobuf y concatenarlo → `.mp4` AV1 4K completo,
sin cookies y sin pasar por yt-dlp.

## Piezas (montadas en el PC)

| Pieza | Ruta | Detalle |
|---|---|---|
| Venv mitmproxy | `~/venv-mitm/` | mitmproxy 12.2.3 + websocket-client |
| Addon captura | `/mnt/Videos/yt_browser_capture/yt_capture.py` | filtra `googlevideo.com` + ct `vnd.yt-ump`/video/audio; guarda cuerpos en `segments/`, URLs en `logs/urls.txt` |
| Mitmdump | `nohup ~/venv-mitm/bin/mitmdump -s yt_capture.py --listen-host 127.0.0.1 --listen-port 8080` | proxy local |
| Edge de captura | perfil `/tmp/edge_capture` | flags: `--proxy-server=http://127.0.0.1:8080 --ignore-certificate-errors --no-first-run --autoplay-policy=no-user-gesture-required --remote-debugging-port=9222 --remote-allow-origins=*` |
| Driver CDP | `/mnt/Videos/yt_browser_capture/cdp_4k.py` | `Page.bringToFront` + `Emulation.setFocusEmulationEnabled` + `video.play()` + gear→Calidad→2160p60 por DOM (100% autónomo, ventana puede quedar atrás) |
| Extractor | `/mnt/Videos/yt_browser_capture/yt_ump_extract.py` | boxes anclados (`ftyp`/`styp`/`moof`/`sidx` con size válido 4 bytes antes); usa la **última** epoch (init más reciente) para no mezclar calidades |
| Salidas | `/mnt/Videos/yt_browser_capture/salidas/video_capturado.mp4` | verificado: AV1, 2160x3840, 115MB |

CA de mitmproxy generado en `~/.mitmproxy/` (para navegadores que validen certs;
el Edge de captura usa `--ignore-certificate-errors` para no tocarlo).

## Detalle técnico del transporte UMP

- Request: **POST** a `*.googlevideo.com/videoplayback` (no GET como antes).
- Response: `Content-Type: application/vnd.yt-ump` — protobuf que **envuelve fMP4**.
- Dentro del body: respuestas de init con `ftyp` + segmentos con `moof`/`mdat`
  (video AV1/VP9; audio por su propio stream, mime audio/mp4).
- Al cambiar de calidad, el player re-pide init nuevos → varias "epochs" en una
  sesión; el extractor concatena desde la última.
- **No sirve replay directo**: hacer GET/curl de la URL firmada capturada devuelve
  `sabr.malformed_config` — hay que capturar el cuerpo UMP en vivo.
- La heurística simple "primer box" falla (proto → falsos positivos); usar
  búsqueda anclada: 4 bytes de size antes de `ftyp`/`moof`/etc.

## Flujo de uso (PC, autónomo)

1. `mitmdump` corriendo (ver tabla; log: `logs/mitmdump.log`).
2. Lanzar Edge de captura con los flags. Si ya corre, matar SOLO la instancia de
   captura, por cmdline con perfil (`pgrep -f "^/app/extra/msedge"` + filtrar por
   `/proc/<pid>/cmdline` contiene `edge_capture`) — nunca matar el Edge normal.
3. `~/venv-mitm/bin/python cdp_4k.py` → play + 2160p60 (o manual: reproducir y
   Calidad→2160p; el perfil recuerda la calidad).
4. Verificar la ventana/stream; la captura se va guardando en `segments/`.
5. Al terminar: `python3 yt_ump_extract.py` → `salidas/video_capturado.mp4`.
6. Verificar: `ffprobe -select_streams v -show_entries stream=width,height,codec_name <file>`.

## Limitaciones conocidas

- Solo contenido **sin DRM** (videos normales; no películas de pago).
- El archivo arranca donde la calidad era 4K: si se sube calidad con el video
  avanzado, la captura empieza en ese punto → subir calidad antes de reproducir
  (o retroceder a t=0; el perfil la recuerda en la siguiente corrida).
- **Audio**: el player lo pide aparte; con autoplay sin gesto o `--mute-audio`
  NO llega pista de audio. Para capturar audio: reproducir con sonido activo.
  Unir: `ffmpeg -i video_capturado.mp4 -i audio_capturado.m4a -c copy salida.mp4`.

## Comandos útiles (S24, vía adb)

`adb shell "run-as com.termux ..."` ejecuta en contexto de Termux (documentado en
`agentes/AGENTS.md`); dentro del proot: `proot-distro login debian -- bash -c '...'`
con `PATH=/data/data/com.termux/files/usr/bin:$PATH`.

## Plan: hacerlo desde el Debian del S24 (proot de Termux)

### Por qué sí

No es necesaria la pantalla del S24: lo que se necesita es un **motor de navegador
real** con sesión confiable. Firefox headless dentro del proot reproduce "invisible"
y mitmproxy local captura igual que en el PC. (En el PC quedó demostrado con CDP:
la ventana puede quedar detrás, el tab se considera enfocado.)

### Pasos

1. **Mitmproxy en el proot**: crear `~/venv-mitm` (python3 del proot) e instalar
   `mitmproxy` + `websocket-client`; copiar el addon `yt_capture.py` apuntando a
   `/sdcard/Antigravity/captura/` (segments, salidas, logs).
2. **Firefox en el proot**: `apt install firefox-esr` (arm64) — o `firefox` +
   `xvfb` si alguna página exigiera ventana.
3. **Perfil Firefox para captura**:
   - Importar `mitmproxy-ca-cert.pem` como CA confiable (vía `certutil` de
     `libnss3-tools` en el perfil, o importar manualmente).
   - Proxy: `network.proxy.http=127.0.0.1`, `network.proxy.http_port=8080`,
     `network.proxy.ssl=127.0.0.1`, `network.proxy.ssl_port=8080`,
     `network.proxy.type=1` (manual). O usar el lanzador con
     `--proxy-server`? (Firefox no tiene flag de proxy por CLI → about:config o
     `-P <perfil>` preconfigurado).
   - Autoplay: `media.autoplay.default=0`, `media.autoplay.blocking_policy=0`,
     `media.autoplay.enabled=true`; sonido activo para capturar audio.
4. **Lanzador `captura_s24.sh`** en el proot:
   `firefox --headless --profile <perfil> <URL>` → esperar → `yt_ump_extract.py`
   → validar con `ffprobe` → mover a `/sdcard/Antigravity/captura/salidas/`.
5. **Prueba**: video corto del canal propio; verificar 3840x2160.
6. **Producción**: playlist propia en reproducción nocturna; mantener wake lock
   (como los widgets anti-Doze) porque con pantalla apagada/Doze se puede pausar.
7. (Opcional) Xvfb + Firefox normal si headless fallara en algún caso.

### Ventajas del S24

- Ruta automática: lista de URLs → captura nocturna sin pantalla → teasers
  directamente desde el material completo (seguir flujo teaser_generator).
- No depende del PC ni de cookies; usa la IP móvil con sesión Firefox propia.

## Validación en el S24 (widget 6_BAJAR_YOUTUBE_4K_CAPTURA)

Pipeline E2E probado en el propio teléfono (proot Debian, Xvfb + Firefox ESR
140 + mitmproxy 12.2.3). Hechos medidos:

- **`?` en nombres de segmento**: la FUSE de `/sdcard` rechaza `?` en nombres
  (EPERM). El addon usa `na` cuando falta el range (commit `3ccda6d`).
- **Inflado de epochs**: en el flujo del teléfono cada respuesta UMP trae su
  propio `ftyp` → un epoch por chunk (~150 inits en 10 min). No es un bug:
  cada epoch da un .mp4 válido; un epoch grande contiene el video entero.
- **Churn del ABR**: la decodificación software de AV1 (sin GPU en proot) hace
  que YouTube renegocie calidad continuamente (oscile 240↔480) y rompa las
  tomas largas. **PLAYBACK_RATE=0.5** (inyección vía addon, `PLAYBACK_RATE`) lo
  estabiliza: 8 epochs / 1080p en vez de 150 / 480p. Es el ajuste por defecto
  del driver.
- **Oferta real del teléfono**: el POST `/youtubei/v1/player` (capturado por el
  addon en `pagina.html`) ofrece hasta 1080p60 AV1; 4K no se ofrece a sesión
  anónima. Para 4K real, usar el PC (validado: 2160p60 AV1, 115 MB).
- **Filtros que no sirven**: cookie `PREF=f6` (valores 4/8/22) no cambia nada;
  CDP de Firefox ESR 140 eliminado (404) — la inyección UI se hace por HTML
  (addon) con INJECT_QUALITY=1 (experimental, puede generar churn).
- Salida validada con ffprobe: `epoch_0004.mp4` = 39 MB AV1 854x480 del video
  completo (3:17), copiado a `crudos_4k_captura/` por el propio driver.

## Referencias

- yt-dlp issues: #15796 (bloqueo por IP), #15865 (navegador sí / yt-dlp no),
  #10085 (baneos de cuenta con cookies), #16870 (proxies residenciales), #13336
  (datacenter bloqueados), #15294 (fuerza IPv4/IPv6).
- Guías 2026: VidKraken 403/bot-check; Tornado API; FAQ yt-dlp (PO tokens, EJS).
- Límites de la comunidad: ~20-50 descargas/día por IP residencial; 12-24h de
  pausa suelen resetear el flag por rate-limit.
## Login con cookies de PC (2026-08-21)

### Problema

YouTube no ofrece 2160p a sesiones anonimas. Solo sesiones logueadas con
cookies de Google (SID, HSID, SSID, APISID, SAPISID, LOGIN_INFO) reciben
la oferta completa de 2160p (VP9 + AV1).

### Solucion

1. Exportar cookies de Firefox PC (calivehiculo@gmail.com) a TSV o sqlite
2. Copiar cookies.sqlite al perfil del S24:
   ```
   adb push cookies_loggedin.sqlite /sdcard/Antigravity/
   proot-distro login debian -- bash -c "cp /sdcard/Antigravity/cookies_loggedin.sqlite /root/captura_firefox_profile/cookies.sqlite"
   ```
3. Verificar: `sqlite3 cookies.sqlite "select name from moz_cookies where name='LOGIN_INFO'"` → debe mostrar 1 resultado

### Resultado

- Oferta del player (POST /youtubei/v1/player): **2160p VP9 + 2160p AV1**
- Antes (anonimo): max 1080p60 AV1
- Login confirmed: `loggedIn` field en player response

### Limitacion

El ABR de YouTube sigue enviando 360p/480p porque:
- Exynos sin GPU: decodificador AV1 por software es lento
- YouTube mide bandwidth real + capacidad de decodificacion
- itag=18 (H.264 360p) es el fallback seguro del player

### FORCE_2160 (parcialmente efectivo)

Intentos de forzar 2160p:
1. **Modificar adaptiveFormats**: elimina formatos < 1440p → funciona (26→4)
   pero el player ignora el resultado y usa itag=18 (fallback)
2. **Vacias formats array**: el player falla completamente (0 segments)
3. **JS inyectado setPlaybackQualityRange**: el player no cambia de calidad
   (posiblemente el metodo no esta disponible en esta version del player)
4. **ANDROID_CLIENT**: el POST /youtubei/v1/player NUNCA se hace (YouTube
   usa el ytInitialPlayerResponse embebido en el HTML del /watch)

### Conclusion

2160p esta DISPONIBLE en la oferta pero YouTube lo entrega solo cuando
el browser puede decodificar VP9/AV1 a velocidad real. En Exynos sin GPU
esto no es posible → el ABR elige itag=18. Para 4K real se necesita:
- Hardware con GPU que soporte VP9/AV1 (Snapdragon 8 Gen 2+)
- O descargar directamente con yt-dlp desde una IP no bloqueada
- O usar un servidor proxy que no este en la lista negra de YouTube
