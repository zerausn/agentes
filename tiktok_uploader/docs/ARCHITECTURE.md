# Arquitectura del Sistema TikTok Uploader (sin API)

## Visión General

Sistema híbrido compuesto por dos subsistemas independientes:

1. **Subsistema Web (Flask + TikTok Content Posting API)** — app para cuando la API de TikTok esté aprobada. Actualmente inactivo.
2. **Subsistema ADB/UI Automation** — método funcional hoy. Opera la app de TikTok Android mediante ADB local + `input tap` + Share Intents.

Este documento cubre el **subsistema ADB/UI Automation**, que es el que realmente está subiendo videos a TikTok.

---

## Diagrama de Flujo End-to-End

```
Note9 (Termux + proot-distro Debian)
         │
         ├─ widget 6_SUBIR_TIKTOK720.sh (loop 720s)
         │      │
         │      ▼
         │  vigia_tiktok720_termux.sh
         │      │
         │      ▼
         │  tiktok_evacuador_720.py
         │      │
         │      ├─ 1. Lock (fcntL LOCK_EX + LOCK_NB)
         │      ├─ 2. iter_videos() → MediaStore query → lista ordenada
         │      ├─ 3. build_caption() → caption con hashtags
         │      ├─ 4. wake_screen() + reset_tiktok()
         │      ├─ 5. Depende de TIKTOK_SHARE_METHOD:
         │      │      ├─ "intent" → launch_share_intent() + UI (default)
         │      │      └─ "monkey" → launch_tiktok_home() + UI completa
         │      ├─ 6. type_caption() en campo descripción
         │      ├─ 7. Publicar (arriba derecha 608,80) o Borrador
         │      ├─ 8. publish_confirmed() → verifica publicación
         │      └─ 9. move_to_done() → mueve archivo
         │
         └── ADB local (127.0.0.1:5555)
                │
                └── TikTok app (com.zhiliaoapp.musically)
```

---

## Método Share Intent (`TIKTOK_SHARE_METHOD=intent`)

Este es el método por defecto y el más rápido. Flujo:

1. **MediaStore query**: `content query --uri content://media/external/video/media` con proyección `_data:_id`. Ordena por `date_added DESC, _id DESC`. Construye caché de `nombre → content:// URI`.

2. **Share Intent**: `am start -a android.intent.action.SEND -t video/mp4 --eu android.intent.extra.STREAM <content://URI> -f 0x10000000 -n com.zhiliaoapp.musically/com.ss.android.ugc.aweme.share.SystemShareActivity`

3. **Chooser Android**: Si aparece el selector "Completar la acción mediante", detecta TikTok por UI (texto "TikTok") y toca "Solo una vez".

4. **Editor TikTok**: El share intent abre TikTok directamente en el editor con el video precargado.

5. **Siguiente**: Si aparece el botón Siguiente en el editor, lo toca una vez.

6. **Caption**: Toca el campo de descripción en `(178, 152)` y escribe el caption con `input text`.

7. **No se cierra teclado**: `close_caption_editor()` retorna `True` sin hacer nada — el teclado no interfiere con el botón Publicar.

8. **Publicar**: Toca `(608, 80)` — el botón rojo "Publicar" arriba a la derecha.

9. **Confirmación**: Espera `POST_SETTLE_SECONDS` (90s) haciendo poll cada 15s. Si `dump_ui()` devuelve lista vacía (animación post-publicación), asume éxito.

### Modo Draft (`TIKTOK_PUBLISH_MODE=draft`)

En vez de publicar, toca el botón "Borradores" (detectado por UI o coordenada `(187, 1333)`). El video se guarda en borradores de TikTok.

---

## Método Monkey (`TIKTOK_SHARE_METHOD=monkey`)

Fallback completo de navegación por UI. Flujo en `automate_tiktok_publish_coords()`:

1. **Home**: Abre TikTok con `monkey -p com.zhiliaoapp.musically -c android.intent.category.LAUNCHER 1`
2. **Crear (+)** en barra inferior: `tap_scaled(360, 1353)`
3. **CREAR** en pantalla cámara: `tap_scaled(517, 1337)`
4. **Video nuevo** del menú desplegable: detección por UI
5. **Dropdown Recientes**: `tap_scaled(360, 83)`
6. **Seleccionar carpeta**: busca el nombre de la carpeta fuente en UI
7. **Primer video**: `tap_scaled(200, 241)` — el archivo con `touch` ejecutado antes aparece primero porque TikTok ordena por fecha de modificación
8. **Siguiente galería**: `tap_scaled(600, 1352)`
9. **Siguiente editor**: `tap_scaled(531, 1341)`
10. **Caption**: igual que método intent
11. **Publicar/Borrador**: igual que método intent

### Importancia del `touch`

Antes de abrir TikTok en modo monkey, se ejecuta `touch` sobre el archivo de video. Esto actualiza su fecha de modificación al momento actual. Como la galería de TikTok ordena por fecha de modificación (más reciente primero), el video que Python seleccionó aparece como el primer video en la carpeta.

---

## Sistema de Coordenadas

| Concepto | Valor |
|---|---|
| Base virtual | 720 x 1480 |
| Resolución real Note9 | 1440 x 2960 (con override 720x1480) |
| Escalado | `sx = x * width_real / 720`, `sy = y * height_real / 1480` |
| Función | `tap_scaled(x, y, label, pause)` |

### Coordenadas clave (base 720x1480)

| Acción | Coordenada |
|---|---|
| Crear (+) barra inferior | (360, 1353) |
| CREAR en cámara | (517, 1337) |
| Dropdown Recientes | (360, 83) |
| Primer video en galería | (200, 241) |
| Siguiente galería | (600, 1352) |
| Siguiente editor | (531, 1341) |
| Campo descripción | (178, 152) |
| Publicar (arriba derecha) | (608, 80) |
| Borradores | (187, 1333) |
| Solo una vez (chooser) | (200, 1351) |

---

## Archivos de Estado y Lock

| Archivo | Propósito |
|---|---|
| `.state/tiktok_queue.json` | Historial de publicaciones (últimos 500) |
| `.state/tiktok_caption_actual.txt` | Caption del último video procesado |
| `.state/tiktok_ui.xml` | Dump de UI de uiautomator (se borra antes de cada dump) |
| `.state/tiktok_evacuador.lock` | Lock con flock para evitar ejecución concurrente |

---

## Directorios

| Ruta | Propósito |
|---|---|
| `/sdcard/Antigravity/subidos a facebbok` | Fuente: videos a evacuar |
| `/sdcard/Antigravity/subidos a tiktok` | Destino: videos publicados |
| `/sdcard/Antigravity/fallidos_tiktok` | Fallos (no implementado aún en open_next) |

---

## Variables de Entorno

| Variable | Default | Descripción |
|---|---|---|
| `AGENTES_STORAGE_ROOT` | `/sdcard/Antigravity` | Raíz de almacenamiento |
| `TIKTOK_PACKAGE` | `com.zhiliaoapp.musically` | Package de TikTok |
| `TIKTOK_SHARE_ACTIVITY` | `com.ss.android.ugc.aweme.share.SystemShareActivity` | Activity para share intent |
| `TIKTOK_ADB_SERIAL` | `127.0.0.1:5555` | Serial ADB local |
| `TIKTOK_UI_BACKEND` | `direct` | `direct` o `adb` |
| `TIKTOK_PUBLISH_MODE` | `direct` | `direct` o `draft` |
| `TIKTOK_SHARE_METHOD` | `intent` | `intent` o `monkey` |
| `TIKTOK_AUTOMATION_TIMEOUT` | `240` | Timeout total de automatización |
| `TIKTOK_POST_SETTLE_SECONDS` | `90` | Espera post-publicación |

---

## ADB Local

La conexión ADB es a `127.0.0.1:5555` porque:

1. `input tap` desde Termux/Proot falla con error `INJECT_EVENTS` (permiso insuficiente).
2. ADB local tiene privilegios `shell` que sí puede inyectar eventos táctiles.
3. No requiere USB ni red WiFi — el Note9 se habla a sí mismo.

### Habilitación

```bash
adb tcpip 5555                    # desde USB
adb connect 127.0.0.1:5555        # desde Termux
```

---

## Widget y Loop de Vigilancia

`vigia_tiktok720_termux.sh` ejecuta un loop infinito:

1. Toma `termux-wake-lock` para evitar Doze.
2. Cada 720 segundos ejecuta `tiktok_evacuador_720.py --open-next` dentro del proot Debian.
3. Usa `_proot_bind.sh` para bind-mount `/sdcard` y las claves ADB dentro del proot.
4. El widget `6_SUBIR_TIKTOK720.sh` (en `~/.shortcuts/`) arranca este loop.

### Exit codes de `tiktok_evacuador_720.py`

| Código | Significado |
|---|---|
| 0 | Video publicado y movido |
| 1 | Error durante apertura/automatización |
| 2 | No hay videos pendientes |
| 3 | Otra instancia corriendo |

---

## Caption

Reutiliza la lógica de YouTube/Facebook:

```
{nombre_limpio} #PW [#teaser #N] Siguenos tambien en Instagram Facebook Youtube linktr.ee/performaticwritingscali #teatro #performance #escriturasperformaticas
```

- `#teaser` y `#N` solo si el archivo termina en `_teaser_N`.
- Los espacios se envían como `%s` (formato `input text` de Android).
- Se guarda en `.state/tiktok_caption_actual.txt` para referencia.
