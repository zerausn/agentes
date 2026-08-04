# TikTok Uploader — Progreso

## Meta
Publicar videos en TikTok desde un nodo Android Note9 sin usar la Content Posting API (no aprobada).

## Estado Actual (2026-07-31): FUNCIONAL — Widget 720s con Share Intent + ADB local + autoreparación

El sistema produce publicaciones reales en TikTok usando UI automation sobre la app Android.
La API de TikTok sigue sin aprobarse; el método UI es la estrategia de producción.

### Fixes 2026-07-31 (sesión: wiget se cerraba solo, ADB caído, stale locks)
- **Widget muere**: `exec bash vigia...` hacía al vigía hijo del terminal del widget → SIGHUP al cerrarse. Fix: `nohup setsid` en el widget + `tail -f` del log en vivo.
- **ADB caído**: `ensure_adb_local || exit 1` mataba el vigía. Fix: ya no sale; `_adb_reconnect` + `_adb_self_repair` (`su -c setprop`) y fallback accessibility + reintento cada ciclo.
- **Stale lock evacuador**: `O_EXCL` sin chequeo de PID dejaba locks eternos tras crash/kill. Fix: `_lock_is_stale()` — si el PID del lock está muerto, se remueve y se reintenta.
- **Vigía duplicado**: lock propio `vigia_tiktok720.lock` evita dos instancias si se toca el widget dos veces.
- **Widget LIMPIAR_LOCKS_STALE**: borra solo locks con PID muerto; mantiene los vivos (a diferencia de LIMPIAR_LOCKS que borra todo).

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
- **Lock seguro y autorecuperable**: `os.O_CREAT | os.O_EXCL` previene condición de carrera, y la nueva función `_lock_is_stale()` detecta procesos huérfanos/muertos (zombies) liberando el candado si el PID murió o superó 30 mins, restaurando la autonomía.
- **Widget limpiador de locks**: `LIMPIAR_LOCK_TIKTOK.sh` para forzar limpieza manual y matar procesos colgados del script evacuador y el vigía.
- **Queue state**: `tiktok_queue.json` guarda historial de últimos 500 intentos.
- **touch en modo monkey**: Asegura que el video seleccionado aparezca primero en galería.
- **Ciclo 720s**: `vigia_tiktok720_termux.sh` con wake-lock y loop anti-Doze.
- **ADB local**: `127.0.0.1:5555` — no requiere USB ni WiFi.
- **ADB key bind**: `_proot_bind.sh` monta claves ADB dentro del proot para evitar re-autorización.
- **Prueba real exitosa**: 2 videos publicados y movidos a `subidos a tiktok` el 2026-07-20.
- **VIVO V2058 funcional**: Flujo completo probado desde PC via ADB (2026-07-23).
  Share intent → Siguiente → caption → Publicar → confirmado → movido a done.
- **Widget VIVO**: `widget_vivo.sh` como wrapper que llama al vigía compartido
  `vigia_tiktok720_termux.sh` con `TIKTOK_UI_BACKEND=adb`.
- **Settle dinámico**: `settle_seconds(video)` — 120s si ≤200MB, 300s si >200MB.
- **Retorno a HOME**: 20s después del settle (antes eran 45s).
- **Flags share intent**: Corregidos a `-f 0x08000000 --grant-read-uri-permission --eu`.

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

## 2026-07-25: Stale lock + Pipestatus fix + setsid

- **Stale lock**: `/sdcard/Antigravity/.state/tiktok_evacuador.lock` con PID 19740 (crash 2026-07-24 10:26:09). `finally` nunca ejecutó → lock persistió. Cada ciclo fallaba con "Otra instancia". Lock eliminado manualmente.
- **`$?` bug**: `vigia_tiktok720_termux.sh` capturaba `$?` después de `| tee`, que siempre es 0. Corregido a `${PIPESTATUS[0]}` en línea 160.
- **Vigía muerto sin motivo**: Android mató el proceso Termux del widget. El vigía no se reanuda solo. Se relanzó con `nohup setsid` para desenganchar de la sesión ADB. PID 2142 (parent=1).
- **Ciclo #1 (11:06)**: OK — publicado/movido en 124s (caption activo porque el script en Note9 era la versión vieja). Pendientes: 555.
- **Script actualizado en Note9**: `tiktok_evacuador_720.py` copiado con `CAPTION_ENABLED` al dispositivo.
- **Pipestatus también corregido en repo**: `vigia_tiktok720_termux.sh` linea 160 en `linux-arm64`.

## 2026-07-24: Caption desactivado + Rama vivo-tiktok aislada

- **Caption**: Envuelto tras `CAPTION_ENABLED` (default `False`). Para activar: `TIKTOK_CAPTION_ENABLED=1`.
  El código NO se borró — solo no se ejecuta. Pendiente de aprobación de API.
- **Rama `vivo-tiktok`**: Creada desde commit `10305849` con el `tiktok_evacuador_720.py` VIVO-modificado
  (`settle_seconds`, `_ImmediateFileHandler`, `CONTENT_URIS_CACHE`, ADB flexible).
- **Rama `linux-arm64`**: Limpia para Note9. `tiktok_evacuador_720.py` revertido a commit `10305849`.
  VIVO files en `vivo/` se quedan (referencia). Nada del VIVO TikTok contamina.
- **Problema Note9 detectado (NO por contaminación)**: Teclado Gboard queda abierto tras "Publicar".
  `close_caption_editor()` era no-op. Al desactivar caption, ese problema desaparece.

## Próximos Pasos

1. ~~Probar método `intent` como default y mantener `monkey` como fallback.~~ ✅
2. ~~Agregar notificación Termux cuando un video se publique exitosamente.~~
3. Implementar cola de reintentos con backoff (máximo 3 intentos, luego mover a `fallidos_tiktok`).
4. Agregar verificación real: abrir TikTok y revisar perfil para confirmar publicación.
5. Probar estabilidad del widget 720s en ejecución continua 24h+.
6. Si la API se aprueba, migrar a Content Posting API, reactivar caption con `CAPTION_ENABLED=1`.

## 2026-08-04: Protección Anti-Kill Brutal y Watchdog

- **Problema de Samsung OOM (Low Memory Killer)**: Android mataba el proceso de Bash y Python durante los picos de memoria (especialmente al generar UI dumps o capturas XML). TikTok Lite se sugirió como alternativa pero se descartó para evitar reescribir coordenadas UI.
- **Solución implementada en `vigia_tiktok720_termux.sh`**:
  - `am kill com.zhiliaoapp.musically`: Se mata la aplicación de TikTok inmediatamente después de publicar para liberar ~500MB de RAM durante los 720 segundos de espera.
  - `_heartbeat`: Bucle infinito en background que mantiene un `termux-wake-lock` vivo cada 60 segundos.
  - El Python ahora se lanza de manera síncrona (inline) para evitar `race conditions` y que Bash pierda el exit code si lo mata el sistema.
- **Capa Extra de Protección (Watchdog)**:
  - Creado `WATCHDOG_TIKTOK.sh` en `termux_widgets/`. Si el sistema operativo logra vencer el wake-lock y matar al vigía, este widget externo lo detecta tras 2 minutos de inactividad, limpia los lockfiles estancados y lo relanza automáticamente.
