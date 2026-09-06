# Descargador YouTube por nodos moviles

Fecha de revision: 2026-07-12
Rama canonica: `linux-arm64`

## Objetivo

`5_BAJAR_YOUTUBE_SIN_LIMITE` permite que varios telefonos Android trabajen como nodos de descarga sobre el mismo canal de YouTube.

Cada nodo:

- corre Termux como host de widgets y almacenamiento;
- corre Debian en `proot-distro` para Python, Git, FFmpeg, Node y `yt-dlp`;
- usa el repo `~/agentes` en la rama `linux-arm64`;
- lee y escribe el registro compartido `youtube_uploader/yt_lotes_registro_sin_limite.json`;
- descarga videos a `/sdcard/Antigravity/crudos/`.

La regla operativa es simple: ningun nodo decide trabajo con un registro viejo. Antes de mostrar pendientes debe traer GitHub, y despues de marcar un video como `descargado` debe empujar el cambio para que los demas nodos no bajen el mismo video.

## Registro compartido

Archivo canonico:

```text
youtube_uploader/yt_lotes_registro_sin_limite.json
```

Campos relevantes por video:

- `status`: `pendiente`, `descargado` o `fallido`.
- `file`: ruta del MP4 final cuando ya fue descargado.
- `downloaded_at`: hora local del nodo que marco la descarga.
- `downloaded_by`: nombre del nodo (`AGENTES_DEVICE_NAME` o hostname).

Un video se considera tomado por la red cuando el registro remoto ya tiene `status: descargado`. Si un nodo conserva un temporal local de un video que otro nodo ya marco como descargado, ese temporal no debe transcodificarse salvo que se confirme manualmente que falta el MP4 final.

## Flujo normal de un nodo

1. El widget ejecuta:

```text
~/.shortcuts/5_BAJAR_YOUTUBE_SIN_LIMITE.sh
```

2. El wrapper llama a:

```text
~/agentes/scripts/linux/bajar_youtube_sin_limite_termux.sh
```

3. El wrapper crea un lock:

```text
~/.run/5_BAJAR_YOUTUBE_SIN_LIMITE.lock
```

4. Debian ejecuta:

```text
/root/agentes/youtube_uploader/yt_downloader_lotes_sin_limite.py
```

5. El script hace `sync_pull()`:

- valida que Git este en `linux-arm64`;
- aborta un rebase pendiente si existe;
- hace `fetch origin linux-arm64`;
- hace `pull --ff-only origin linux-arm64`;
- si hay divergencia, rescata el registro local en memoria, resetea a remoto y mezcla entradas locales faltantes.

6. Escanea YouTube, actualiza el registro y muestra lotes pendientes.

7. Al terminar una descarga valida, marca el video como `descargado` y ejecuta `sync_push()`:

- refresca `origin/linux-arm64` y preserva en el JSON local cualquier video que el remoto ya tenga como `descargado`;
- hace commit solo del registro;
- intenta `pull --rebase --autostash origin linux-arm64`;
- si el rebase falla, aborta el rebase y NO empuja;
- despues del rebase vuelve a preservar `descargado` remoto y, si hizo cambios, amenda el commit local;
- empuja con `git push origin HEAD:linux-arm64`;
- verifica con `ls-remote` que GitHub quedo en el mismo SHA local.

## Blindajes agregados el 2026-07-11

Commit de codigo:

```text
0798c040 fix: proteger descargador sin limite contra rebase y concurrencia
```

Cambios:

- El wrapper impide ejecuciones simultaneas con un lock por widget.
- El Python detecta rebases pendientes antes de sincronizar.
- El Python evita commits/push desde `HEAD (no branch)`.
- El push usa `HEAD:linux-arm64`, no el nombre de una rama local potencialmente atrasada.
- El push verifica que GitHub realmente haya recibido el commit.
- Si `pull --rebase` falla, el commit local queda conservado y no se empuja un estado ambiguo.

Commit de documentacion:

```text
12f4f899 docs: documentar sincronizacion de nodos moviles
```

## Blindajes agregados el 2026-07-12

Commits de codigo:

```text
04f3d7e3 fix: autostash al sincronizar registro youtube
a3104f2e fix: preservar descargados remotos en nodos youtube
```

Cambios:

- `sync_push()` usa `git pull --rebase --autostash` para que cambios locales no relacionados, como archivos de TikTok, no bloqueen la publicacion del registro YouTube.
- Antes de crear el commit y otra vez despues del rebase, el script fusiona desde `origin/linux-arm64` todos los videos con `status: descargado`.
- La regla nueva es monotonicidad: un video que ya quedo `descargado` en GitHub no puede volver a `pendiente` por culpa de un nodo con registro viejo cargado en memoria.
- Si se detectan descargados remotos preservados, el script imprime `Preservados N descargado(s) remotos ya informados por otros nodos`.

Caso real rescatado:

```text
8Ltnq81N0PU | 2025-05 | 20250404 181037.mp4 | descargado por localhost el 2026-07-11 23:47
```

Ese video habia sido subido por el S24 en `c7a03cf`, pero commits posteriores de otro nodo lo dejaron otra vez como `pendiente`. El registro remoto quedo corregido en `a3104f2e`.

## Incidente S24

Sintomas observados:

- Varias instancias de `5_BAJAR_YOUTUBE_SIN_LIMITE` corriendo al mismo tiempo.
- Log mezclado: una instancia en menu y otra descargando/transcodificando.
- Git con `.git/rebase-merge` activo.
- Repo en `HEAD (no branch)`.
- Commits locales reportados como "subidos", pero GitHub seguia en un SHA anterior.

Causa:

- `git pull --rebase` entro en conflicto en el registro.
- El script siguio creando commits en detached HEAD.
- `git push origin linux-arm64` empujaba la rama local `linux-arm64`, no el HEAD detached que tenia los nuevos commits.

Correccion aplicada:

- Se respaldo el registro y el rebase en:

```text
/sdcard/Antigravity/backups/s24_git_fix_20260711_1748
```

- Se anclaron ramas de rescate:

```text
s24-rescue-20260711-1748
s24-rescue-rebase-orig-20260711-1748
```

- Se movio `linux-arm64` al commit local valido.
- Se empujo GitHub de `d8c0319` a `f37af50`.
- Se aplico el fix de codigo y luego documentacion.

Estado verificado:

```text
S24: HEAD == origin/linux-arm64 == a3104f2e despues del arreglo de monotonicidad
```

Backup adicional del registro local viejo antes de actualizar el S24 el 2026-07-12:

```text
/sdcard/Antigravity/backups/s24_sync_fix_20260712/yt_lotes_registro_sin_limite.before_pull.json
```

Stash conservado en el S24:

```text
stash@{0}: On linux-arm64: s24 registry before monotonic youtube sync 2026-07-12
```

## Incidente Note 9

Dispositivo:

```text
SM-N9600
serial: 29396e8c1e3f7ece
```

Sintomas observados:

- Repo Debian en `HEAD (no branch)`.
- Rebase viejo en `.git/rebase-merge`.
- Commits locales `sync: Note9 bajo ...`.
- Temporales en `youtube_uploader/yt_temp_dl/`.

Revision de registro:

- Se comparo el registro local del Note 9 contra el registro remoto actual.
- No habia ningun `descargado` del Note 9 faltante en GitHub.
- Solo habia entradas `pendiente` que el remoto actual ya no conservaba.

Temporal relevante:

```text
dl_XaaLtfRD1bs.mkv
```

Ese temporal era valido por `ffprobe`, pero el video `XaaLtfRD1bs` ya estaba marcado como `descargado` en GitHub por otro nodo, asi que se movio a respaldo para evitar trabajo duplicado.

Backups:

```text
/sdcard/Antigravity/backups/note9_git_fix_20260711_1815
```

Ramas de rescate:

```text
note9-rescue-20260711-1815
note9-rescue-linux-arm64-20260711-1815
```

Estado verificado:

```text
Note 9: HEAD == origin/linux-arm64 == 12f4f899
```

Validaciones realizadas:

- sin procesos vivos de `yt_downloader_lotes_sin_limite.py` ni `yt-dlp`;
- sin `.git/rebase-merge`;
- `python3 -m py_compile` OK;
- `bash -n bajar_youtube_sin_limite_termux.sh` OK;
- `git status` limpio.

## Incidente Note 9 (bot-check por `--force-ipv4`)

Fecha: 2026-08-07

Sintomas observados:

- Todos los lotes seleccionados fallaban: `✅ 0 nuevos ⏭️ 0 omitidos ❌ 5` (lote 2026-08).
- El log del script solo mostraba `Falló la descarga de: ...` porque `--quiet --no-warnings` ocultaba el error real de yt-dlp.
- No era problema de versión: el yt-dlp del Debian (2026.07.04) es el más reciente y soporta `--js-runtimes node`.

Causa raíz (reproducida en PC y dentro del proot del Note 9):

```text
ERROR: [youtube] <id>: Sign in to confirm you're not a bot.
       Use --cookies-from-browser or --cookies for the authentication.
HTTP Error 429: Too Many Requests
```

- El flag `--force-ipv4`, agregado el 2026-07-07 (commit `cb83eebf`), pasó a disparar el bot-check de YouTube. Sin el flag, la misma descarga funciona en el Note 9 (2160p, 168 MB en 75s) y en PC.

Correccion aplicada (commit `7bcb06bf`):

- Se eliminó `--force-ipv4` de:
  - `youtube_uploader/yt_downloader_lotes_sin_limite.py`
  - `youtube_uploader/yt_downloader_lotes.py`
  - `youtube_uploader/youtube_to_fb_watcher.py`
  - `youtube_uploader/youtube_to_fb_watcher_termux.py`
- Se conservó `--js-runtimes node`.
- No fue necesario actualizar yt-dlp ni usar cookies.

Estado verificado:

- `python3 -m py_compile` OK en los 4 archivos.
- Descarga de prueba en el Note 9 sin `--force-ipv4`: exitosa a 2160p.

### Verificacion en produccion (2026-08-07)

- Se lanzo el descargador en el Note 9 seleccionando el lote 12 (2026-08, 5 videos).
- La primera descarga (1pMhT-v6imk) completo `Descarga OK (288.4 MB) | selector: bestvideo[height>=2160]+bestaudio[ext=m4a` y paso a transcodificar a MP4.
- La prueba se detuvo a mitad de transcodificacion por peticion del usuario; se limpiaron los temporales y el MP4 parcial.
- El registro no quedo corrupto: 404 `descargado`, 19 `fallido`, sin cambios de estado erroneos.
- El fix quedo confirmado: el problema era `--force-ipv4`, no la version de yt-dlp.

### Incidente colateral: registro viejo del Note 9 (2026-08-07)

- Al subir su escaneo, el Note 9 empujo su registro local que no incluia 81 videos `pendiente` que el auto-merge `6ca083e` habia agregado.
- Verificacion: los 81 perdidos eran todos `pendiente`, ninguno `descargado` (no se perdio historial de descargas).
- Correccion: restaurados en el PC desde `6ca083e` (commit `9ca23b04`) y empujados a `linux-arm64`.

## Fix 2026-09-06: PO Token Provider + cookies de sesión real (S24)

Fecha: 2026-09-06
Contexto: `docs/CAPTURA_4K_MITMPROXY_NAVEGADOR.md` documentó que, incluso después del
fix de `--force-ipv4`, `yt-dlp` seguía recibiendo 403 desde IPs de Claro
(residenciales, no datacenter) porque YouTube confía en la sesión/fingerprint
de un navegador real pero no en el de `yt-dlp`. Ese mismo documento identificó
un problema aparte y no relacionado: la captura por navegador en el S24 no
llega a 2160p real por falta de GPU AV1/VP9 — pero esa limitación es propia
del pipeline de captura en vivo (`6_BAJAR_YOUTUBE_4K_CAPTURA`), NO aplica a
`5_BAJAR_YOUTUBE_SIN_LIMITE`: yt-dlp no reproduce el video en tiempo real, solo
pide el itag exacto y lo escribe a disco, así que el cuello de botella de
decodificación del Exynos no es relevante para esta ruta.

Cambios aplicados a `yt_downloader_lotes_sin_limite.py` y
`bootstrap_termux_arm64.sh`:

1. **PO Token Provider (`bgutil-ytdlp-pot-provider`)**: genera un token de
   origen vía BotGuard (misma librería que usa un navegador real) para que
   YouTube confíe en las peticiones de yt-dlp. Se instala en
   `~/bgutil-ytdlp-pot-provider` (= `/root/...` corriendo como root en el
   proot), la ruta por defecto que el plugin detecta solo — no requiere
   flags nuevos en el comando de yt-dlp. Requiere `yt-dlp >= 2025.05.22`
   (ya se cumple: el proot trae `2026.07.04`+) y Node >= 20 (ya presente,
   `20.19.2`). Verificado en sandbox: sin el server instalado, yt-dlp reporta
   el provider `bgutil:script-node` como `unavailable`; con el server
   clonado y compilado (`npm ci && npx tsc`) en esa ruta, pasa a `available`
   sin tocar el comando de descarga.
2. **Cookies de sesión real vía `--cookies-from-browser firefox:<perfil>`**:
   apunta al mismo perfil de Firefox con login que ya usa la captura 4K por
   navegador (`/root/captura_firefox_profile`, ver "Login con cookies de PC"
   en `docs/CAPTURA_4K_MITMPROXY_NAVEGADOR.md`). Una sesión anónima nunca
   recibe la oferta de 2160p; con esa sesión sí. Tiene prioridad sobre el
   `cookies.txt` clásico (que sigue funcionando como respaldo si no existe
   ese perfil).
3. `bootstrap_termux_arm64.sh` instala/actualiza esto de forma idempotente
   dentro del bloque `INSTALL_DEBIAN_DEPS`, así que corre automáticamente en
   cualquier nodo (S24, Note 9, Vivo) la próxima vez que se ejecute
   `0_RENOVAR_REPO`.

Riesgo a vigilar: usar cookies de una cuenta logueada para automatización
puede invalidar la sesión si YouTube detecta un patrón de descargas
inusual (ver nota sobre `player_client=tv` deslogueando la sesión en
`youtube_uploader/docs/DECISIONS.md`). Si la cuenta usada es la personal,
conviene vigilar el registro de descargas fallidas por si hay que
re-loguear el perfil de Firefox.

Pendiente de verificar en el dispositivo real (no se pudo probar en el S24
desde este entorno, solo se validó la instalación del provider y la
compilación en un sandbox Linux x86_64 separado — sin acceso al teléfono):

- Correr `0_RENOVAR_REPO` en el S24 y confirmar que `apt-get`/`npm ci`
  terminan sin error dentro del proot (puede necesitar las libs de `canvas`
  ya incluidas: `libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev
  librsvg2-dev`).
- `yt-dlp -v <URL> 2>&1 | grep pot` debe mostrar `bgutil:script-node-X.X.X
  (external)` sin `unavailable`.
- Lanzar `5_BAJAR_YOUTUBE_SIN_LIMITE` con un video de prueba y confirmar
  `height=2160` en el `ffprobe` del archivo final.

## Procedimiento para reparar otro nodo

1. Ver dispositivos:

```bash
adb devices -l
```

2. Confirmar que no hay descargador activo:

```bash
adb -s <SERIAL> shell run-as com.termux sh -c 'ps -ef | grep -E "bajar_youtube_sin_limite|yt_downloader_lotes_sin_limite|yt-dlp" | grep -v grep'
```

3. Revisar Git dentro de Debian:

```bash
adb -s <SERIAL> shell 'run-as com.termux sh -c "files/usr/bin/proot-distro login debian -- git -C /root/agentes status --short --branch"'
```

4. Si esta en detached HEAD, crear rama de rescate antes de limpiar:

```bash
git -C /root/agentes branch -f <nodo>-rescue-<fecha> HEAD
```

5. Respaldar el registro local:

```bash
cp /root/agentes/youtube_uploader/yt_lotes_registro_sin_limite.json /sdcard/Antigravity/backups/<nodo>_git_fix_<fecha>/
```

6. Comparar el registro local contra GitHub antes de resetear. Solo hay que rescatar entradas locales con `status: descargado` que no existan en remoto.

7. Alinear a GitHub:

```bash
git -C /root/agentes fetch origin linux-arm64
git -C /root/agentes checkout linux-arm64
git -C /root/agentes reset --hard origin/linux-arm64
```

8. Verificar:

```bash
git -C /root/agentes status --short --branch
git -C /root/agentes rev-parse HEAD
git -C /root/agentes rev-parse origin/linux-arm64
python3 -m py_compile /root/agentes/youtube_uploader/yt_downloader_lotes_sin_limite.py
```

## Reglas para operar la red de nodos

- No lanzar dos veces el mismo widget en el mismo telefono.
- No usar un nodo que tenga `HEAD (no branch)` o rebase activo.
- No borrar temporales validos sin comparar antes con el registro remoto.
- Si el temporal corresponde a un video ya `descargado` por otro nodo, moverlo a respaldo y no transcodificarlo.
- Siempre operar desde `linux-arm64`.
- El UID de Termux puede cambiar por instalacion; no hardcodear `u0_a291`, `u0_a309`, etc. Para ADB usar `run-as com.termux`.
- Si un nodo estuvo desconectado durante un arreglo, correr `0_RENOVAR_REPO` antes de usarlo.
- Despues del commit `a3104f2e`, cualquier nodo que haya estado corriendo una version anterior debe cerrarse y actualizarse antes de escoger otro lote.

## Nodos

Estado confirmado en esta revision:

| Nodo | Modelo | Serial | Estado |
|---|---|---|---|
| S24 Ultra | SM-S928B | RFCX91HV4GD | Reparado y alineado en `a3104f2e`; proceso viejo cerrado antes del pull |
| Note 9 | SM-N9600 | 29396e8c1e3f7ece | Tenia `--autostash`; debe recibir `a3104f2e` antes de escoger otro lote |
| Vivo | pendiente de conexion | pendiente | Debe revisarse antes de usar si corre este descargador |

## Troubleshooting (Problemas Comunes)

### Git trabado por `index.lock` (Ej. `git add falló`)
Cuando un proceso de Termux se interrumpe de forma abrupta (por ejemplo, porque Android mata la aplicación por políticas de batería) justo en medio de una sincronización de Git, puede dejar abandonado el archivo `.git/index.lock`. 

Esto causa que posteriores ejecuciones del descargador fallen en la fase `sync_pull` o `sync_push` con el mensaje genérico "git add falló", sin poder subir ni bajar el registro `yt_lotes_registro_sin_limite.json`.

**Solución:**
Conectarse al nodo por ADB y ejecutar `run-as com.termux` para eliminar el archivo de bloqueo:
```bash
# Ejemplo de solución para el Note 9:
adb -s 29396e8c1e3f7ece shell "run-as com.termux rm files/home/agentes/.git/index.lock"
```
*(Nota: Hemos mejorado el script `yt_downloader_lotes_sin_limite.py` para capturar e imprimir el output del error real de `git add` en los logs y facilitar su detección en el futuro).*

## Migración a GitHub Gists (2026-09-06)

Para evitar conflictos de concurrencia y merge al mezclar descargas del PC (que corre en la rama `linux`) con la flota móvil (que corre en `linux-arm64`), la base de datos `yt_lotes_registro_sin_limite.json` fue **eliminada del control de versiones de Git**.

A partir de esta actualización, el archivo JSON se sincroniza globalmente a través de un **GitHub Gist**. 
Esto simplifica el código al eliminar toda la lógica compleja de subprocesos de `git pull/push/rebase`, permitiendo que todos los dispositivos interactúen en tiempo real con una única fuente de verdad alojada en la nube mediante peticiones HTTP `GET` y `PATCH`.

### Requisitos de Autenticación
Dado que ya no usamos las llaves SSH de Git para empujar los cambios, los scripts ahora usan la API REST de GitHub (vía HTTP). Para que un dispositivo móvil (o PC) pueda actualizar el Gist de estado, debe contar con un **Personal Access Token (PAT)** que tenga el scope `gist`.

Los tokens deben distribuirse a los nodos a través de la carpeta compartida de credenciales:
- `credentials/github_gist_token.txt` (El PAT)
- `credentials/github_gist_id.txt` (El ID del Gist creado)

**¿Qué pasa si un nodo no tiene el token?**
Si el token falta, el nodo descargará en modo *offline* usando únicamente la caché local que quedó guardada en la ejecución anterior (el archivo `yt_lotes_registro_sin_limite.json` sigue existiendo localmente pero está ignorado por `.gitignore`). Emitirá un `Warning` de que la sincronización en la nube se ha omitido.
