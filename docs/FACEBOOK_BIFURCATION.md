# Facebook Bifurcation System - Documentación Técnica

## Resumen del Sistema

Este documento describe la implementación de un **sistema de bifurcación para subida a Facebook** que separa los videos en dos categorías y los publica en páginas diferentes de forma **paralela e independiente**:

| Tipo de Video | Página Facebook | ID Página | Widget/Script |
|--------------|----------------|-----------|---------------|
| **CRUDOS** (sin `_teaser_`) | Performatic Writings Cali | `803559979506784` | `4_VIGIA_FB_CRUDOS.sh` |
| **TEASERS** (con `_teaser_`) | Shirabyoshi Writings | `1347014641828725` | `4_VIGIA_FB_TEASERS.sh` |

Cada vigilante tiene su **propio timer de 720s** y corre en **paralelo** sin bloquearse mutuamente.

---

## Arquitectura

```
videos subidos exitosamente/
├── *.mp4 (crudos)           → Vigilante CRUDOS → Performatic Writings Cali
└── *_teaser_*.mp4 (teasers) → Vigilante TEASERS → Shirabyoshi Writings
```

### Componentes Principales

1. **Scripts Python (evacuadores)** - En `/meta_uploader/`:
   - `subir_fb_evacuador_crudos.py` - Procesa solo videos sin `_teaser_`
   - `subir_fb_evacuador_teasers.py` - Procesa solo videos con `_teaser_`, intenta Reel primero
   - `subir_fb_evacuador_bifurcado.py` - Versión legacy (un solo proceso)

2. **Scripts Bash (vigilantes)** - En `/scripts/linux/`:
   - `vigia_facebook720_crudos_termux.sh` - Loop 720s para crudos
   - `vigia_facebook720_teasers_termux.sh` - Loop 720s para teasers
   - `vigia_facebook720_bifurcado_termux.sh` - Versión legacy

3. **Widgets Termux** - En `~/.shortcuts/`:
   - `4_VIGIA_FB_CRUDOS.sh` - Lanza vigilante crudos
   - `4_VIGIA_FB_TEASERS.sh` - Lanza vigilante teasers
   - `5_VIGIA_FACEBOOK_BIFURCADO.sh` - Versión legacy

4. **Core Library** - `meta_uploader/meta_uploader.py`:
   - Soporte para `page_id` y `page_token` dinámicos en todas las funciones de Facebook
   - Funciones: `upload_fb_reel()`, `upload_fb_video_standard()`, `_start_fb_upload()`, `_transfer_fb_upload()`, `_finish_fb_upload()`, `_finalize_facebook_upload()`, `wait_for_fb_video_status()`, `start_fb_status_verifier()`

---

## Flujo de Datos

### Detección de tipo de video
```python
TEASER_RE = re.compile(r"(?i)_teaser_\d+")
is_teaser = bool(TEASER_RE.search(video_path.stem))
```

### Lógica de subida (Teasers)
```python
# TEASERS son 9:16 → intentar REEL primero, fallback a VIDEO ESTÁNDAR
if is_reel_safe(video_path):
    result = upload_fb_reel(...)
    if result: return True
    logging.warning("REEL falló, probando VIDEO ESTÁNDAR...")

result = upload_fb_video_standard(...)
```

### Lógica de subida (Crudos)
```python
# CRUDOS: Reel si es 9:16, sino video estándar
if is_reel_safe(video_path):
    result = upload_fb_reel(...)
else:
    result = upload_fb_video_standard(...)
```

---

## Configuración de Tokens

### Variables de Entorno (`~/.agentes_termux_env`)
```bash
# Crudos - Performatic Writings Cali
META_FB_PAGE_ID_RAW=803559979506784
META_FB_PAGE_TOKEN_RAW=EAA... (token larga duración)

# Teasers - Shirabyoshi Writings
META_FB_PAGE_ID_TEASER=1347014641828725
META_FB_PAGE_TOKEN_TEASER=EAA... (token larga duración)

# Fallback genérico
META_FB_PAGE_TOKEN=EAA...
```

### Requisitos de Tokens
- **Tipo**: Page Access Token de larga duración (no expira)
- **Scopes requeridos**: `publish_video`, `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
- **Generación**: Graph API Explorer → User Token → `me/accounts` → Seleccionar página

---

## Instalación en S24 (Termux)

### 1. Copiar archivos al dispositivo
```bash
# Python scripts
adb push meta_uploader/subir_fb_evacuador_crudos.py /sdcard/Antigravity/agentes/meta_uploader/
adb push meta_uploader/subir_fb_evacuador_teasers.py /sdcard/Antigravity/agentes/meta_uploader/
adb push meta_uploader/meta_uploader.py /sdcard/Antigravity/agentes/meta_uploader/

# Bash scripts
adb push scripts/linux/vigia_facebook720_crudos_termux.sh /sdcard/Antigravity/agentes/scripts/linux/
adb push scripts/linux/vigia_facebook720_teasers_termux.sh /sdcard/Antigravity/agentes/scripts/linux/
adb push scripts/linux/4_VIGIA_FB_CRUDOS.sh /sdcard/Antigravity/agentes/scripts/linux/
adb push scripts/linux/4_VIGIA_FB_TEASERS.sh /sdcard/Antigravity/agentes/scripts/linux/

# Copiar a ubicaciones de ejecución
adb shell run-as com.termux cp /sdcard/Antigravity/agentes/meta_uploader/*.py /data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs/root/agentes/meta_uploader/
adb shell run-as com.termux cp /sdcard/Antigravity/agentes/scripts/linux/vigia_facebook720_*_termux.sh /data/data/com.termux/files/home/agentes/scripts/linux/
adb shell run-as com.termux cp /sdcard/Antigravity/agentes/scripts/linux/4_VIGIA_FB_*.sh /data/data/com.termux/files/home/.shortcuts/

# Permisos
adb shell run-as com.termux chmod 755 /data/data/com.termux/files/home/agentes/scripts/linux/vigia_facebook720_*_termux.sh
adb shell run-as com.termux chmod 755 /data/data/com.termux/files/home/.shortcuts/4_VIGIA_FB_*.sh
```

### 2. Configurar tokens
```bash
# Editar ~/.agentes_termux_env en el S24
META_FB_PAGE_ID_RAW=803559979506784
META_FB_PAGE_TOKEN_RAW=<token_crudos>
META_FB_PAGE_ID_TEASER=1347014641828725
META_FB_PAGE_TOKEN_TEASER=<token_teasers>
```

### 3. Lanzar widgets
Desde Termux en S24, tocar los widgets:
- `4_VIGIA_FB_CRUDOS`
- `4_VIGIA_FB_TEASERS`

### 4. Monitoreo
```bash
# Crudos
tail -f /sdcard/Antigravity/widget_logs/4_VIGIA_FACEBOOK720_CRUDOS.log

# Teasers
tail -f /sdcard/Antigravity/widget_logs/4_VIGIA_FACEBOOK720_TEASERS.log
```

---

## Logs y Debugging

### Ubicación de Logs
- **Widget logs**: `/sdcard/Antigravity/widget_logs/`
  - `4_VIGIA_FACEBOOK720_CRUDOS.log`
  - `4_VIGIA_FACEBOOK720_TEASERS.log`
  - `4_VIGIA_FACEBOOK720_BIFURCADO.log` (legacy)
  - `5_VIGIA_FACEBOOK720_BIFURCADO.log` (legacy)

- **Python logs**: `/root/agentes/meta_uploader/` (dentro de proot/Debian)
  - `fb_evacuador_crudos.log`
  - `fb_evacuador_teasers.log`
  - `fb_evacuador_bifurcado.log` (legacy)

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `403 (#200) Subject does not have permission` | Página no permite video posts | Configurar página en FB → Permisos → Publicar videos |
| `400 (#104) An access token is required` | Token no llega a proot | Verificar `export` en script bash antes de `proot login` |
| `400 (#6000) No tienes permiso para subir` | Página sin permisos de video | Habilitar en FB Settings → Permisos |
| `403 (#200) Reel permission` | Página no permite Reels | Solo sube como video estándar (fallback automático) |

---

## Problema Conocido: Shirabyoshi Writings

**Estado actual**: La página **Shirabyoshi Writings** (ID: `1347014641828725`) **no permite publicación de videos** aunque el token tenga los scopes correctos.

### Errores observados:
```
REEL (403): "(#200) Subject does not have permission to post videos on this target"
VIDEO ESTÁNDAR (400): "No tienes permiso para subir un video aquí"
```

### Solución pendiente:
En Facebook → Shirabyoshi Writings → **Configuración → Permisos → Publicar videos** → Habilitar.

---

## Changelog

### v2.0 - Bifurcación Paralela (2026-09-20)
- ✅ Dos vigilantes independientes con timers 720s separados
- ✅ Detección automática CRUDOS vs TEASERS por nombre de archivo
- ✅ Teasers: Reel-first (9:16) + fallback a video estándar
- ✅ Crudos: Reel si 9:16, sino video estándar
- ✅ `meta_uploader.py`: Soporte completo para `page_id`/`page_token` dinámicos
- ✅ Scripts bash: Export explícito de env vars antes de `proot login`
- ✅ Tokens de larga duración para ambas páginas

### v1.0 - Bifurcación Single (2026-09-20)
- `subir_fb_evacuador_bifurcado.py` - Un proceso que bifurca
- `5_VIGIA_FACEBOOK_BIFURCADO.sh` - Widget legacy

### v0.x - Original
- `4_VIGIA_FACEBOOK720.sh` / `vigia_facebook720_termux.sh` - Un solo vigilante, una sola página

---

## Estructura de Archivos

```
agentes-linux-arm64/
├── meta_uploader/
│   ├── meta_uploader.py              # Core library (modificado)
│   ├── subir_fb_evacuador_crudos.py  # Nuevo
│   ├── subir_fb_evacuador_teasers.py # Nuevo (Reel-first + fallback)
│   ├── subir_fb_evacuador_bifurcado.py # Legacy
│   └── subir_fb_evacuador_720.py     # Original
│
├── scripts/linux/
│   ├── vigia_facebook720_crudos_termux.sh    # Nuevo
│   ├── vigia_facebook720_teasers_termux.sh   # Nuevo
│   ├── vigia_facebook720_bifurcado_termux.sh # Legacy
│   ├── vigia_facebook720_termux.sh           # Original
│   ├── 4_VIGIA_FB_CRUDOS.sh                  # Widget nuevo
│   ├── 4_VIGIA_FB_TEASERS.sh                 # Widget nuevo
│   ├── 5_VIGIA_FACEBOOK_BIFURCADO.sh         # Widget legacy
│   └── 4_VIGIA_FACEBOOK720.sh                # Widget original
│
└── docs/
    └── FACEBOOK_BIFURCATION.md               # Esta documentación
```