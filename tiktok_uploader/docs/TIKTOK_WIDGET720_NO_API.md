# TikTok Widget 720 — Publicación sin API Oficial

## Enfoque Final

El sistema publica videos en TikTok **sin usar la Content Posting API** (no aprobada),
operando directamente la app de TikTok Android mediante ADB local + Android Share Intent.

---

## Métodos Soportados

### 1. Share Intent (Default) — `TIKTOK_SHARE_METHOD=intent`

El método principal. Flujo completo:

```
1. MediaStore query → content:// URI del video
2. am start -a ACTION_SEND -t video/mp4 --eu STREAM <content://URI>
3. TikTok se abre directamente en el editor con el video cargado
4. [Opcional] Tap Siguiente si aparece
5. Tap campo descripción → input text del caption
6. Tap Publicar (608, 80) arriba a la derecha
7. Esperar 90s con poll cada 15s → confirmar publicación
8. Mover archivo a /sdcard/Antigravity/subidos a tiktok
```

**Ventajas**:
- Abre TikTok directamente en el editor (menos taps, más rápido)
- No necesita buscar carpeta ni video en galería
- 6-8 taps en total vs 12-14 del método monkey

**Limitaciones**:
- Requiere `content://` URI desde MediaStore
- El chooser Android puede aparecer si es la primera vez
- Android 10+ bloquea `file://` completamente

### 2. Monkey UI Navigation (Fallback) — `TIKTOK_SHARE_METHOD=monkey`

Navegación completa por UI. Flujo:

```
1. monkey -p com.zhiliaoapp.musically → abre TikTok en Home
2. touch al video para que sea el primero en galería
3. Tap Crear (+) en barra inferior
4. Tap CREAR en pantalla cámara
5. Tap "Video nuevo" del menú desplegable
6. Tap dropdown "Recientes"
7. Buscar carpeta por nombre en UI → seleccionar
8. Tap al primer video (el toucheado)
9. Tap Siguiente en galería
10. Tap Siguiente en editor
11. Caption → Publicar / Borrador
```

**Ventajas**:
- No depende de MediaStore ni content:// URIs
- Funciona aunque Android bloquee intents

**Limitaciones**:
- Más taps, más lento, más puntos de fallo
- Requiere `touch` para ordenar galería
- TikTok actualizado puede cambiar layout

---

## Arquitectura de Ejecución

```
┌─────────────────────────────────────────────────┐
│               Note9 (SM-N9600)                   │
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │         Termux + proot-distro Debian      │   │
│  │                                           │   │
│  │  ┌─────────────────────────────────────┐  │   │
│  │  │  Widget: 6_SUBIR_TIKTOK720.sh      │  │   │
│  │  │  └→ vigia_tiktok720_termux.sh       │  │   │
│  │  │      (loop 720s con wake-lock)      │  │   │
│  │  └─────────────────────────────────────┘  │   │
│  │                    │                        │   │
│  │  ┌─────────────────────────────────────┐  │   │
│  │  │  tiktok_evacuador_720.py            │  │   │
│  │  │  └→ Lock → iter_videos() →         │  │   │
│  │  │     → launch_share_intent() →       │  │   │
│  │  │     → caption → publish →           │  │   │
│  │  │     → confirm → move_to_done()      │  │   │
│  │  └─────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────┘   │
│                    │                                │
│         ADB local (127.0.0.1:5555)                 │
│                    │                                │
│  ┌───────────────────────────────────────────┐   │
│  │         TikTok App (Android)              │   │
│  │  com.zhiliaoapp.musically                 │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## Configuración y Setup

### 1. Instalar dependencias en Termux
```bash
pkg install android-tools termux-api proot-distro
```

### 2. Habilitar ADB local
```bash
# Desde una terminal ADB USB (o shell con su):
adb tcpip 5555
# Luego desde Termux:
adb connect 127.0.0.1:5555
# Verificar:
adb devices
# Debe mostrar: 127.0.0.1:5555    device
```

### 3. Crear widget
```bash
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "
  mkdir -p ~/.shortcuts
  cp /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh ~/.shortcuts/6_SUBIR_TIKTOK720.sh
  chmod +x ~/.shortcuts/6_SUBIR_TIKTOK720.sh
"
```

### 4. Estructura de directorios requerida
```
/sdcard/Antigravity/
├── subidos a facebbok/     ← Fuente: videos MP4/MOV/MKV
├── subidos a tiktok/       ← Destino: videos publicados
├── fallidos_tiktok/        ← Fallos
├── .state/                 ← Estado interno
│   ├── tiktok_queue.json
│   ├── tiktok_caption_actual.txt
│   ├── tiktok_ui.xml
│   └── tiktok_evacuador.lock
├── agentes/
│   └── tiktok_uploader/    ← Código Python
├── scripts/linux/          ← Scripts bash
│   ├── vigia_tiktok720_termux.sh
│   └── _proot_bind.sh
└── termux_widgets/         ← Widgets
    └── 6_SUBIR_TIKTOK720.sh
```

### 5. Variables de entorno
```bash
AGENTES_STORAGE_ROOT=/sdcard/Antigravity
TIKTOK_UI_BACKEND=adb
TIKTOK_ADB_SERIAL=127.0.0.1:5555
TIKTOK_PUBLISH_MODE=direct     # o "draft"
TIKTOK_SHARE_METHOD=intent     # o "monkey"
TIKTOK_POST_SETTLE_SECONDS=90
TIKTOK_AUTOMATION_TIMEOUT=240
```

---

## Coordenadas (Base 720x1480, Note9 con override)

| Acción | Coordenada |
|---|---|
| Campo descripción | (178, 152) |
| Publicar (arriba derecha) | (608, 80) |
| Borradores | (187, 1333) |
| Siguiente editor | (531, 1341) |
| Crear (+) barra inferior | (360, 1353) |
| CREAR cámara | (517, 1337) |
| Dropdown Recientes | (360, 83) |
| Primer video galería | (200, 241) |
| Siguiente galería | (600, 1352) |
| Solo una vez (chooser) | (200, 1351) |

---

## Caption

Una sola línea. Formato:
```
{nombre_limpio} #PW [#teaser #N] Siguenos tambien en Instagram Facebook Youtube linktr.ee/performaticwritingscali #teatro #performance #escriturasperformaticas
```

- `#teaser` y `#N` solo cuando el archivo contiene `_teaser_N`.
- `input text` requiere espacios como `%s`.
- Máximo 240 caracteres después de sanitización.

---

## Modo Draft

Cuando `TIKTOK_PUBLISH_MODE=draft`, el sistema toca "Borradores" en vez de Publicar.
El video queda en borradores de TikTok para revisión manual antes de publicar.

Flujo draft:
```
1. Share Intent abre TikTok en editor
2. Siguiente → caption
3. Tap "Borradores" (detectado por UI o coordenada 187,1333)
```

---

## Validación

Pruebas exitosas realizadas el 2026-07-20 en Note9:
- `20251018 200806_teaser_2.mp4` → publicado con caption completo
- `20251018 200806_teaser_3.mp4` → publicado, confirmado con `foreground=com.sec.android.app.launcher` (launcher de Samsung), movido a `subidos a tiktok`

Ambos usando método Share Intent con detección de chooser y publicación vía coordenada `(608, 80)`.

---

## Limitaciones y Riesgos

1. **ADB local se pierde al reiniciar** — requiere reconexión USB.
2. **Sin API** — no hay verificación real de publicación, solo UI dump.
3. **Coordenadas fijas** — si TikTok actualiza el layout, hay que recalibrar.
4. **Share Intent falla sin content:// URI** — si MediaStore no tiene el video indexado, cae a método monkey.
5. **Chooser Android** — aparece solo la primera vez o después de reinstalar TikTok.
6. **`input text` limitado** — no acepta emojis, caracteres especiales, ni textos >240 chars.
7. **No hay backoff en fallos** — el video se reintenta en cada ciclo 720s sin límite.
