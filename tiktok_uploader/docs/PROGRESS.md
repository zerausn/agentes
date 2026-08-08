# TikTok Uploader — Progreso

## Meta
Publicar videos en TikTok desde un nodo Android Note9 sin usar la Content Posting API (no aprobada).

## Estado Actual (2026-07-20): FUNCIONAL — Widget 720s con Share Intent + ADB local

El sistema produce publicaciones reales en TikTok usando UI automation sobre la app Android.
La API de TikTok sigue sin aprobarse; el método UI es la estrategia de producción.

---

## Lo que Funciona

### Subsistema ADB/UI (PRODUCCIÓN)
- **Share Intent method**: `am start SEND` con `content://` URI desde MediaStore. Abre TikTok directamente en el editor con el video cargado.
- **Chooser Android**: Detección automática de TikTok en el selector "Completar la acción mediante" y selección "Solo una vez".
- **Navegación UI**: Coordenadas escaladas base 720x1480 sobre Note9 con override display.
- **Detección de texto**: `uiautomator dump` parseado como XML para encontrar botones por etiqueta.
- **Caption**: Escritura con `input text` (espacios como `%s`) en el campo de descripción.
- **Publicar**: Botón rojo arriba a la derecha en coordenada `(608, 80)` escalada.
- **Modo Draft**: Alternativa que toca "Borradores" en vez de Publicar.
- **Confirmación post-publicación**: Detecta dump UI vacío (animación) o ausencia de botón Publicar.
- **Lock**: `fcntl.flock` evita ejecución concurrente.
- **Queue state**: `tiktok_queue.json` guarda historial de últimos 500 intentos.
- **touch en modo monkey**: Asegura que el video seleccionado aparezca primero en galería.
- **Ciclo 720s**: `vigia_tiktok720_termux.sh` con wake-lock y loop anti-Doze.
- **ADB local**: `127.0.0.1:5555` — no requiere USB ni WiFi.
- **ADB key bind**: `_proot_bind.sh` monta claves ADB dentro del proot para evitar re-autorización.
- **Prueba real exitosa**: 2 videos publicados y movidos a `subidos a tiktok` el 2026-07-20.

### Subsistema Web Flask (EN PAUSA)
- OAuth PKCE (S256 code_challenge + code_verifier) funcional.
- Login Kit con sandbox (scopes: user.info.basic, profile, stats, video.list).
- Dynamic redirect URI desde request.headers (ProxyFix + X-Forwarded-*).
- Terms of Service y Privacy Policy servidos en el mismo dominio ngrok.
- 3 TikTok verify files servidos.
- ngrok estable en Note9, URL fija: `https://gravy-diaper-refrain.ngrok-free.dev`.

## Lo que NO Funciona / Limitaciones

- **Content Posting API**: No aprobada. Sandbox no la soporta. Production app pendiente de review.
- **`input tap` desde Termux/Proot**: Falla con `INJECT_EVENTS`. Se requiere ADB local.
- **ADB local se pierde al reiniciar**: Requiere reconectar con `adb tcpip 5555` vía USB.
- **Monkey method más lento**: Requiere navegar Crear → Cargar → Recientes → carpeta → video. El share intent es mucho más directo.
- **No hay verificación de publicación real en TikTok**: Solo se confirma que la UI avanzó. No se consulta API para verificar que el video exista.
- **Sin cola de reintentos**: Si falla, el archivo queda en source para el próximo ciclo. No hay límite de reintentos ni backoff.

## Infraestructura

| Componente | Detalle |
|---|---|
| Host | Note9 (SM-N9600) Android 10 |
| Terminal | Termux + proot-distro (Debian arm64) |
| Automatización | ADB local + Python 3 |
| Loop | Widget Termux `6_SUBIR_TIKTOK720` |
| Logs | `/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log` |
| Control | ADB vía USB o scripts en `/sdcard/Antigravity/` |
| Repo | `agentes/` rama `linux-arm64` en GitHub |

## Próximos Pasos

1. Probar método `intent` como default y mantener `monkey` como fallback.
2. Agregar notificación Termux cuando un video se publique exitosamente.
3. Implementar cola de reintentos con backoff (máximo 3 intentos, luego mover a `fallidos_tiktok`).
4. Agregar verificación real: abrir TikTok y revisar perfil para confirmar publicación.
5. Probar estabilidad del widget 720s en ejecución continua 24h+.
6. Si la API se aprueba, migrar a Content Posting API y dejar UI automation como respaldo.

## 2026-08-04: Protección Anti-Kill Brutal y Watchdog (portado desde linux-arm64)

- **Problema de OOM (Low Memory Killer)**: Android mataba el proceso de Bash y Python durante los picos de memoria. Se diagnosticó en Note9 Samsung y se portó al Vivo.
- **Solución implementada en `vigia_tiktok720_termux.sh`**:
  - `am kill com.zhiliaoapp.musically`: Se mata TikTok inmediatamente después de publicar para liberar ~500MB de RAM durante los 720s de espera.
  - `_heartbeat`: Bucle infinito en background que mantiene un `termux-wake-lock` vivo cada 60 segundos para resistir App Standby de Android.
  - El Python se lanza de manera síncrona (inline) para evitar `race conditions` con el exit code.
- **Capa Extra de Protección (Watchdog)**:
  - Portado `WATCHDOG_TIKTOK.sh` a `termux_widgets/`. Si Android logra matar al vigía, el Watchdog lo detecta en 2 minutos y lo relanza automáticamente.

## 2026-08-04: Corrección de Seguridad Multi-rama (Widget RENOVAR_REPO)

- **Bug detectado**: El widget `0_RENOVAR_REPO.sh` (`renovar_repo_termux.sh`) tenía hardcodeado un `git pull origin linux-arm64`. Al ejecutarlo en el Vivo, sobreescribía los scripts especiales de la rama `vivo-tiktok` (arruinando la automatización del Vivo).
- **Solución implementada**:
  - Se modificó el script para detectar dinámicamente la rama actual mediante `git rev-parse --abbrev-ref HEAD`.
  - Ahora el widget hace `git pull origin <rama-actual>`. Es universalmente seguro y se puede ejecutar en cualquier dispositivo (Vivo, Note9, S24) sin riesgo de mezclar o dañar ramas.

## 2026-08-07: TypeError PosixPath en shlex.quote al capturar screenshot post-publicación

- **Síntoma**: Ciclo terminaba con `exit=1` tras "Dump UI vacío repetido en TikTok (3/3)". El traceback mostraba `TypeError: expected string object, got 'PosixPath'` en `run_android()` (línea 258) vía `shlex.quote`.
- **Causa raíz**: `publish_confirmed()` pasaba `STATE_DIR / "post_publish_empty_dump.png"` (un `PosixPath`) directamente a `run_android(["screencap", ...])`. `shlex.quote()` solo acepta strings y `run_android` lo llama sobre cada argumento cuando `UI_BACKEND == "adb"`.
- **Solución**: Envolver el Path con `str()` en los 2 puntos que pasaban rutas de screenshot a `run_android`:
  - `post_publish_empty_dump.png` (línea 966)
  - `post_publish.png` (línea 976)
- **Además**: se agregó un backup del archivo original (`backups/tiktok_evacuador_720.py.posixpath.bak`) en el Vivo antes de desplegar la corrección.
- **Verificación**: MD5 local == MD5 desplegado en Vivo (`83ea41d31a95e0d6b475c157738759bf`). Commit `fb7e83a3` en rama `vivo-tiktok`.

## 2026-08-07: Confirmación de publicación — Método simple (cambio de pantalla + 20s)

- **Contexto**: El VIVO publicaba videos reales (verificado en la app y en la cola: el head `PW (20260428_185308)_teaser_8.mp4` se publicó 3 veces el mismo día) pero el evacuador nunca confirmaba → `exit=1` → el archivo no se movía y el mismo video se republicaba cada ciclo (135 pendientes estancados).
- **Intento previo (descartado)**: Señal de la notificación "Cargando..." de TikTok (canal `com.ss.android.ugc.trill.publish`, foreground service). Problemas: (1) las notificaciones estaban bloqueadas en la app (`appops POST_NOTIFICATION: ignore`, importance NONE, userSet=true) → hubo que habilitarlas con `appops set com.zhiliaoapp.musically POST_NOTIFICATION allow`; (2) aún habilitadas, la notificación aparecía ANTES del tap Publicar (procesado del video) y el `NotificationRecord` persistía en `dumpsys notification` incluso tras matar TikTok (`am kill`), por lo que la señal "aparece→desaparece" nunca disparaba dentro de la ventana.
- **Decisión final (método simple)**: El tap en Publicar ya produce un cambio de pantalla verificado por UI (`Publicar fallback X,Y produjo cambio de pantalla` → el botón desapareció → TikTok salió del editor hacia el feed "Para ti"). Ese cambio de pantalla ES la confirmación. Solo se espera la subida del video: `TIKTOK_PUBLISH_UPLOAD_WAIT_SECONDS=20` (20s desde el tap/cambio de pantalla) y se confirma.
- **Cambios en `tiktok_evacuador_720.py`**:
  - Eliminado `_tiktok_publish_notification_active()` y `PUBLISH_NOTIF_CHANNEL` (señal descartada).
  - `publish_confirmed()` ahora: espera 15s (procesado) + `TIKTOK_PUBLISH_UPLOAD_WAIT_SECONDS` (default 20s), toma screenshot `post_publish.png` y retorna `True`.
  - Eliminadas las señales que fallaban en el VIVO: `SUCCESS_FOREGROUND_PACKAGES` (foreground inesperado com.termux tras publicar) y `IME_PACKAGES` (sin uso).
- **Timing real**: tap (5s pause) + sleep 15s + 20s de subida ≈ 40s desde el tap, ~20s después del cambio de pantalla (detectado ~6s tras el tap).
- **Verificación**: MD5 local == MD5 desplegado en VIVO (`41588ea9f4f6db88a46a1a439f05882e`). Desplegado vía `run-as com.termux cp` desde `/data/local/tmp` (run-as no lee /sdcard).
