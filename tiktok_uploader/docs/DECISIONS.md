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

## 2026-06-18: _proot_bind.sh para montar /sdcard y ADB keys
- **Contexto**: El proot Debian no tiene acceso a `/sdcard` (bind mount manual) ni a las claves ADB de Termux.
- **Decisión**: Script `_proot_bind.sh` que detecta la ruta real del almacenamiento externo y bind-mounta `/sdcard` y `~/.android` dentro del proot.
- **Consecuencia**: El evacuador Python dentro del proot puede acceder a archivos en `/sdcard` y conectar ADB local sin re-autorizar.
