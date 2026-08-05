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
