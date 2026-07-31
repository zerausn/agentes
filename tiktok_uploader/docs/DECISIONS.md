# TikTok Uploader — Decisiones Clave

## 2026-07-20: Share Intent como método principal (sobre monkey)
- **Contexto**: El método monkey requería navegar Crear → Cargar → Recientes → carpeta → video. Era frágil y lento. El share intent abre TikTok directamente en el editor.
- **Decisión**: `TIKTOK_SHARE_METHOD=intent` como default. `monkey` como fallback.
- **Consecuencia**: Flujo más rápido (menos taps), más robusto (menos puntos de fallo), pero requiere content:// URI de MediaStore.

## 2026-07-20: Content URI desde MediaStore en vez de file://
- **Contexto**: Android 10+ bloquea `file://` URIs en intents. Se requiere `content://` para compartir por `ACTION_SEND`.
- **Decisión**: Consultar `content://media/external/video/media` con `_data` y `_id`, construir URIs del caché local.
- **Consecuencia**: El share intent funciona en Android 10+ con permisos de almacenamiento. Cache de URIs evita consultas repetidas.

## 2026-07-20: Botón Publicar arriba a la derecha (608,80) en vez de buscar por UI
- **Contexto**: TikTok tiene múltiples botones "Publicar" (arriba, abajo, en el editor). Buscar por UI era inconsistente.
- **Decisión**: Coordenada fija `(608, 80)` en base 720x1480. Primero intenta detección por UI, si falla usa coordenada.
- **Consecuencia**: Publica consistentemente. El botón está siempre en la misma posición en la pantalla de descripción.

## 2026-07-20: No cerrar teclado (`close_caption_editor` es no-op)
- **Contexto**: En versiones anteriores se cerraba el teclado tocando el fondo de pantalla. Esto a veces movía el foco y rompía la secuencia.
- **Decisión**: `close_caption_editor()` retorna `True` inmediatamente sin hacer nada.
- **Consecuencia**: El teclado puede quedar abierto pero no interfiere con el botón Publicar (está arriba a la derecha, fuera del área del teclado). Menos taps = menos riesgo.

## 2026-07-20: ADB local (127.0.0.1:5555) como backend de UI
- **Contexto**: `input tap` desde Termux/Proot falla con `INJECT_EVENTS`. No hay permiso para inyectar eventos táctiles desde el contexto de Termux.
- **Decisión**: Usar ADB local (`adb -s 127.0.0.1:5555 shell input tap`) que sí tiene privilegios shell.
- **Consecuencia**: Requiere `android-tools` en Termux y `adb tcpip 5555` después de cada reinicio. Pero funciona de forma 100% local sin WiFi.

## 2026-07-20: Coordenadas base 720x1480 con escalado dinámico
- **Contexto**: Note9 tiene resolución nativa 1440x2960, pero se usa override display 720x1480 para que los taps sean más precisos (los elementos UI son más grandes).
- **Decisión**: `COORD_BASE_W=720`, `COORD_BASE_H=1480`. `tap_scaled()` escala proporcionalmente a la resolución real.
- **Consecuencia**: Las coordenadas funcionan en Note9 con override. Si se cambia la resolución, el escalado ajusta automáticamente.

## 2026-07-20: Widget Termux en vez de cron o systemd
- **Contexto**: En Termux no hay systemd ni cron confiable (Android mata procesos). El widget Termux con loop bash es la forma más estable de mantener un proceso perpetuo.
- **Decisión**: `vigia_tiktok720_termux.sh` como script bash con loop infinito y wake-lock. Llamado desde el widget `6_SUBIR_TIKTOK720.sh`.
- **Consecuencia**: El proceso vive mientras Termux Widget lo tenga. wake-lock evita Doze. Intervalo de 720s (12 min) alineado con YouTube/Facebook.

## 2026-07-20: Sin verificación real de publicación (confianza en UI)
- **Contexto**: No hay API para verificar si un video efectivamente se publicó. Solo se puede observar la UI.
- **Decisión**: `publish_confirmed()` asume éxito si: (1) dump_ui vacío (animación), (2) botón Publicar desapareció, (3) no estamos en pantalla de Borradores.
- **Consecuencia**: Posibles falsos positivos si la UI cambia. Pero es el mejor método disponible sin API.

## 2026-05-26: OAuth login via 302 redirect en vez de JS redirect
- **Contexto**: Cloudflare proxy corruptía redirects JavaScript.
- **Decisión**: Usar Flask `redirect()` (HTTP 302) para `/login`.
- **Consecuencia**: Flujo OAuth limpio, sin corrupción de Cloudflare.

## 2026-06-18: Note9 como host 24/7 con ngrok + tmux
- **Contexto**: localhost.run cambia URL cada reinicio. PC no está siempre encendido.
- **Decisión**: Migrar Flask + ngrok al Note9 (arm64) que está encendido 24/7.
- **Consecuencia**: URL fija para Redirect URI. PC ya no necesita procesos en segundo plano.

## 2026-06-18: Termux Widget — SELinux context
- **Contexto**: Scripts creados via SSH no aparecían en el widget por contexto SELinux incorrecto.
- **Decisión**: Usar `adb shell run-as com.termux cp` para crear shortcuts. El widget corre como `u0_a291`, los archivos deben tener ese contexto.
- **Consecuencia**: Los shortcuts siempre deben crearse desde `run-as com.termux`, no desde SSH.

## 2026-07-24: Caption desactivado tras CAPTION_ENABLED flag
- **Contexto**: El caption (`input text`) insertaba texto en el campo de descripción pero dejaba el teclado Gboard abierto. `close_caption_editor()` era no-op, entonces el teclado interfería con el tap de Publicar, causando que `publish_confirmed()` detectara Gboard en foreground y fallara.
- **Decisión**: Envolver los 3 pasos del caption (`tocar campo`, `type_caption`, `close_caption_editor`) tras `if CAPTION_ENABLED:`. Default desactivado (False). El código no se borra.
- **Consecuencia**: Publicación más rápida y confiable sin caption. Para reactivar: `TIKTOK_CAPTION_ENABLED=1` o cambiar la constante a True cuando la API esté aprobada.

## 2026-07-25: PIPESTATUS[0] en vez de $? tras pipe con tee
- **Contexto**: `comando | tee archivo.log` — el `$?` posterior captura el exit code de `tee` (siempre 0), no del comando real.
- **Decisión**: Usar `${PIPESTATUS[0]}` que retorna el exit code del primer segmento del pipeline.
- **Consecuencia**: El vigía ahora detecta correctamente cuando el evacuador falla (exit 3 = otra instancia, exit 1 = error, exit 2 = sin videos).

## 2026-07-25: setsid + nohup para vigía via ADB
- **Contexto**: Al lanzar `vigia_tiktok720_termux.sh` via `adb shell`, el proceso recibía SIGHUP al cerrarse la sesión ADB (cuando el comando timeout expiraba o la shell terminaba).
- **Decisión**: Usar `adb shell "nohup setsid bash script.sh > /dev/null 2>&1 &"` para que el proceso herede PID 1 (init) y sobreviva a la desconexión ADB.
- **Consecuencia**: El vigía corre como proceso init-child independiente de la sesión ADB. No se muere al cerrar la conexión.

## 2026-07-25: Stale lock — eliminación manual
- **Contexto**: Un crash (PID 19740, 2026-07-24 10:26:09) dejó el lock file `/sdcard/Antigravity/.state/tiktok_evacuador.lock` sin liberar. `fcntl.flock` no se libera automáticamente si el proceso no ejecuta el `finally` (lock release explícito).
- **Decisión**: Eliminar manualmente el archivo `.lock`. El lock no tiene protección contra stale locks (no hay heartbeat ni timeout).
- **Consecuencia**: El ciclos posteriores pueden ejecutarse de nuevo. Para prevenir recurrencia, considerar agregar un heartbeat timestamp al lock file y un cleanup automático si el PID ya no existe.

## 2026-07-24: Rama vivo-tiktok separada de linux-arm64
- **Contexto**: Las features VIVO (`settle_seconds`, `_ImmediateFileHandler`, `CONTENT_URIS_CACHE`) contaminaban `tiktok_evacuador_720.py` compartido. El Note9 no debía recibir código VIVO.
- **Decisión**: Crear rama `vivo-tiktok` desde commit `10305849` (Note9 limpio) con solo el `.py` VIVO-modificado + archivos TikTok-VIVO. En `linux-arm64`, revertir el `.py` a `10305849`.
- **Consecuencia**: `linux-arm64` es solo Note9. `vivo-tiktok` es solo VIVO TikTok. No hay contaminación cruzada.

## 2026-06-18: _proot_bind.sh para montar /sdcard y ADB keys
- **Contexto**: El proot Debian no tiene acceso a `/sdcard` (bind mount manual) ni a las claves ADB de Termux.
- **Decisión**: Script `_proot_bind.sh` que detecta la ruta real del almacenamiento externo y bind-mounta `/sdcard` y `~/.android` dentro del proot.
- **Consecuencia**: El evacuador Python dentro del proot puede acceder a archivos en `/sdcard` y conectar ADB local sin re-autorizar.

## 2026-07-31: Widget lanza vigía con nohup setsid (sobrevive al cierre del widget)
- **Contexto**: El widget usaba `exec bash vigia...` → el vigía moría con SIGHUP al cerrarse el terminal del widget (pantalla apagada, Android kill). El sistema "se cerraba solo" repetidamente.
- **Decisión**: El widget lanza `nohup setsid bash vigia... >> launcher.log 2>&1 &` y abre `tail -f` del session log para verlo en vivo. El vigía se desengancha del terminal y sobrevive.
- **Consecuencia**: El widget ya no es requisito de vida del vigía. Tocar el widget dos veces crea el riesgo de duplicados → se agregó lock propio del vigía.

## 2026-07-31: Vigía no muere si ADB falla (autoreparación)
- **Contexto**: `ensure_adb_local || exit 1` mataba el vigía cuando `adb connect 127.0.0.1:5555` fallaba (ej: tras reinicio, `adb tcpip 5555` se pierde).
- **Decisión**: El vigía ya no sale. Intenta `_adb_reconnect` (kill/start server + connect), luego `_adb_self_repair` (`su -c 'setprop service.adb.tcp.port 5555 && stop adbd && start adbd'`), y si nada funciona usa fallback `accessibility` para ese ciclo, reintentando en cada ciclo.
- **Consecuencia**: El sistema es autónomo ante ADB caído. En el Note9 sin ADB el share intent no puede resolver content URI → los ciclos fallan (exit=1) hasta que ADB vuelve; la autoreparación por `su` requiere root.

## 2026-07-31: Stale lock del evacuador — PID check en vez de O_EXCL ciego
- **Contexto**: `process_lock()` usaba `os.O_CREAT | os.O_EXCL` sin verificar si el PID del lock existía. Un crash/kill dejaba el lock eterno y TODOS los ciclos siguientes fallaban con "Otra instancia" hasta limpieza manual.
- **Decisión**: `_lock_is_stale()` — si el PID en el lock está muerto, se remueve y se reintenta tomar el lock. Si el PID está vivo, sí es "Otra instancia".
- **Consecuencia**: Crash de proceso ya no bloquea el sistema. Complemento manual: widget `LIMPIAR_LOCKS_STALE` (borra solo locks con PID muerto).

## 2026-07-31: Widget LIMPIAR_LOCKS_STALE (borrado selectivo de locks)
- **Contexto**: `LIMPIAR_LOCKS` borra TODOS los locks sin verificar procesos vivos — puede romper una ejecución en curso.
- **Decisión**: Nuevo widget que lee el PID de cada lock y solo borra si está muerto. Mantiene locks de procesos vivos.
- **Consecuencia**: Limpieza segura, sin riesgo de doble ejecución.
