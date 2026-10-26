# VIGIA_META720 — Dedupe por derivada, selección multipágina y transcode vertical

**Fecha:** 2026-10-26 (sesión 3)
**Rama:** `linux-arm64`
**Dispositivo verificado:** Samsung S24 (Termux + proot Debian), serial `RFCX91HV4GD`
**Commits:** `303dc93` (fix), `5206ea6` y `c51dcee` (verificación en vivo)
**Documento hermano:** `VIGIA_META720_POSTDEPLOY_FIX.md` (sesión 2: `IN_PROGRESS` + token Shirabyoshi)

---

## Resumen ejecutivo

El Vigía dejó de publicar teasers nuevos y, cuando lo intentaba, Meta rechazaba
el binario con `ProcessingFailedError` después de recibir el 100%. Eran cuatro
fallas independientes que se ocultaban entre sí:

| # | Síntoma | Causa raíz | Fix |
|---|---------|------------|-----|
| 1 | Todos los teasers de un mismo video se veían como "ya publicados" | `extract_content_keys()` emitía `stem:<stem>` para cualquier derivada | Identidad por derivada: `content:<stem>`, `content:<stem>_teaser_<n>`, `content:<stem>_teaser` |
| 2 | Se publicaba el primer candidato de la primera página, no el más reciente | El bucle cortaba en el primer post elegible | Comparar `created_time` entre las 4 páginas (bloques frescos y Deep Cursor) |
| 3 | El log decía "los N posts ya estaban publicados" aunque hubiera fallado la subida | Motivos de descarte no se resumían y `--once` devolvía 0 en todos los casos | Resumen por motivo + códigos `0/2/3/1` y casos separados en el launcher |
| 4 | `720x1280` vertical rechazado con HTTP 400 tras subir el 100% | Tope fijo de 1080 de alto reducía a `608x1080` | Escalar según orientación: `1920x1080` horizontal / `1080x1920` vertical |

La verificación en producción fueron dos ciclos consecutivos que publicaron
teasers distintos, elegidos correctamente entre páginas, con clips `720x1280`:

- Ciclo #26: Performatic `teaser_18` → Reel `18104992640284376`
  (`https://www.instagram.com/reel/De-F4qFgvMs/`).
- Ciclo #27: Seanchai `teaser_19` → Reel `18117973030825331`
  (`https://www.instagram.com/reel/De-HbfoAi-p/`).

---

## Bug 1 — `stem:` desnudo bloqueaba todas las derivadas

### Síntoma

El registro tenía una sola clave por video fuente:

```json
"stem:20260429_185945"
```

Cualquier teaser de ese fuente (`teaser_14`, `teaser_16`, `teaser_17`, ...)
generaba la misma clave al extraer su identidad. El resultado:

```log
[Ghawazee Writings] Bloque 1: los 89 posts ya estaban publicados. Siguiente bloque.
```

...aunque `teaser_16` nunca se hubiera subido a Instagram.

### Causa

`extract_content_keys()` convertía el stem a `stem:<stem>` sin distinguir si el
post era el video completo, un teaser numerado o un teaser sin número. El
registro viejo, además, conservaba cientos de claves `stem:` de sesiones
anteriores.

### Fix

Nueva identidad de contenido, independiente de la página:

| Tipo de post | Clave generada |
|---|---|
| Video completo | `content:<stem>` |
| Teaser numerado | `content:<stem>_teaser_<n>` |
| Teaser sin número | `content:<stem>_teaser` |

```python
# meta_uploader/fb_to_ig_vigia.py
teaser_match = TEASER_TAIL_RE.match(tail)
if teaser_match:
    identities.add(f"{stem}_teaser_{int(teaser_match.group(1))}")
elif unnumbered_teaser:
    identities.add(f"{stem}_teaser")
else:
    identities.add(stem)
```

Consecuencias:

- El video completo y sus teasers ya no colisionan.
- Dos teasers distintos del mismo fuente se publican por separado.
- El mismo teaser publicado en varias páginas colisiona a propósito (se sube
  una sola vez), porque la identidad no incluye el prefijo de página.

### Claves `stem:` viejas

Se dejaron en el registro pero **quedan inertes**: ya no se generan ni se
comparan. No fue necesario limpiar el JSON del dispositivo; limpiarlo sin
cambiar el extractor habría regenerado la clave mala en el siguiente ciclo.
`extract_content_keys()` también alimenta el catálogo de Instagram, así que el
fix corrige ambos lados de la deduplicación.

---

## Bug 2 — Selección del post más reciente entre las 4 páginas

### Síntoma

El Vigía procesaba las páginas en orden fijo (Performatic, Shirabyoshi,
Seanchai, Ghawazee) y se quedaba con el primer post elegible que encontraba.
Si Performatic tenía un teaser de las 19:00 y Shirabyoshi uno de las 19:39, se
publicaba el de las 19:00.

### Fix

Se agregó `parse_created_time()` (tolera formatos de Graph API y cadenas ya
normalizadas) y `_pick_newer_candidate()`, que compara `created_time` y
conserva el candidato más reciente junto con sus claves.

El mismo criterio se aplica en dos rutas:

1. **Bloques frescos:** se escanea el bloque 1 de cada página y se comparan los
   candidatos antes de publicar.
2. **Deep Cursor:** al rescatar bloques antiguos, el respaldo ya no se detiene
   en la primera página con candidato; compara todos los encontrados.

```log
Candidato mas reciente entre paginas: 824642984061807_122152838127038597 (Seanchai Writings, 2026-10-26T20:06:02+0000).
```

### Evidencia en vivo

- Ciclo #26: eligió Performatic 19:52Z sobre Shirabyoshi 19:39Z, Ghawazee
  19:26Z y Seanchai 19:13Z.
- Ciclo #27: apareció un post nuevo de Seanchai a las 20:06Z y lo eligió sobre
  Shirabyoshi 19:39Z (`teaser_17`), Ghawazee 19:26Z y el ya publicado
  Performatic 19:52Z.

---

## Bug 3 — Logs y códigos de salida engañosos

### Síntoma

- El resumen de bloque decía "los N posts ya estaban publicados" sin distinguir
  duplicados reales, posts sin media o fallos de publicación.
- `--once` salía con `0` tanto si publicaba como si no había nada que hacer.
- El launcher solo distinguía `0` y `2`; un `3` (candidato que falló al
  publicarse) caía en el caso genérico de error.

### Fix

Resumen por motivo en cada bloque:

```log
[Ghawazee Writings] Bloque 1: 87 duplicados (registry), 2 sin media.
```

Códigos internos y de shell:

| Resultado | Constante interna | Exit shell | Mensaje del launcher |
|---|---|---|---|
| Publicado | `CYCLE_PUBLISHED = 1` | `0` | `OK — crosspost exitoso` |
| Sin candidatos | `CYCLE_NO_CANDIDATE = 2` | `2` | `Sin candidatos (duplicados o sin media)` |
| Candidato encontrado, publicación fallida | `CYCLE_PUBLISH_FAILED = 3` | `3` | `Candidato encontrado, pero fallo la publicacion; se reintentara` |
| Error de ejecución | excepción | `1` | `Error de ejecucion` |

En modo continuo, un ciclo con error o con fallo de publicación reintenta en
10 minutos; "sin candidatos" duerme 24 horas.

---

## Bug 4 — Transcode vertical: `608x1080` rechazado por Meta

### Síntoma

```log
[CLIP-SPECS] ... | 608x1080 | 90.0s | 39.23 MB | 3.52 Mbps | 30.0fps
Subiendo IG: 100.0% (23793679/23793679 bytes)
ERROR - Fallo subida binaria HTTP 400 — ProcessingFailedError
```

El binario se subía completo dos veces y Meta lo rechazaba en el procesador.

### Causa

El filtro de `ensure_ig_compatibility()` usaba un tope fijo de 1080 en el lado
menor:

```python
"scale=w='min(iw,1920)':h='min(ih,1080)':force_original_aspect_ratio=decrease"
```

Un fuente `720x1280` se convertía en `608x1080` (reduce el alto a 1080 y
arrastra el ancho). Meta acepta el upload pero falla el procesamiento.

### Fix

Tope según orientación, aplicado en `meta_uploader/meta_uploader.py`:

```python
"-vf",
"scale=w='if(gte(iw,ih),min(iw,1920),min(iw,1080))':"
"h='if(gte(iw,ih),min(ih,1080),min(ih,1920))':"
"force_original_aspect_ratio=decrease,"
"scale=trunc(iw/2)*2:trunc(ih/2)*2",
```

- Horizontal: máximo `1920x1080`.
- Vertical: máximo `1080x1920`.
- Dimensiones finales siempre pares (requisito de codificación).

### Verificación del clip

Fuente real del post fallido: `720x1280`, 195.9 s, 3.73 Mbps.

| Propiedad | Valor |
|---|---|
| Resolución | `720x1280` |
| Duración | 90.0 s |
| FPS | 30 |
| Video | H.264 High, level 4.1, `yuv420p`, 2.25 Mbps |
| Audio | AAC LC, 48 kHz, estéreo, 128 kbps |
| Tamaño | 25.66 MB |

Ese clip se subió a un contenedor IG real (`upload_type=resumable`) y el
upload binario devolvió éxito. El ciclo #26 confirmó lo mismo en producción:
clip `720x1280`, 16.1 s, 3.10 MB, Reel publicado sin `ProcessingFailedError`.

---

## Verificación

### Pruebas automáticas

```bash
cd meta_uploader
python3 -m py_compile fb_to_ig_vigia.py meta_uploader.py test_vigia_dedupe.py
python3 -m unittest -v test_vigia_dedupe.py
bash -n ../scripts/linux/vigia_meta720_termux.sh
```

Resultado: **15 tests OK**, `py_compile` OK, `bash -n` OK. Los tests cubren:

- Teasers distintos del mismo fuente no colisionan.
- El mismo teaser en páginas distintas comparte claves `content:` y `text:`.
- Video completo y teaser numerado son distintos.
- Claves `stem:` viejas no bloquean teasers nuevos.
- Prefijos `#PW`, `#SW`, `#GW`, `#SC` se normalizan.
- Claves `text:` viejas con prefijo se normalizan al cargar.
- Selección del candidato más reciente (fechas y fallback de cadena).

### Ciclos en vivo

| Ciclo | Fecha local | Post elegido | Origen | `created_time` | IG media ID | Resultado |
|---|---|---|---|---|---|---|
| #26 | 2026-10-26 15:01 | `803559979506784_122157978075044766` (`teaser_18`) | Performatic | 19:52:30Z | `18104992640284376` | Reel `720x1280`, 16.1 s, exit 0 |
| #27 | 2026-10-26 15:13 | `824642984061807_122152838127038597` (`teaser_19`) | Seanchai | 20:06:02Z | `18117973030825331` | Reel `720x1280`, 16.1 s, exit 0 |

URLs publicadas:

- `https://www.instagram.com/reel/De-F4qFgvMs/`
- `https://www.instagram.com/reel/De-HbfoAi-p/`

### Estado del registro tras publicar

```json
{
  "processed_keys": [
    "content:20260429_185945_teaser_18",
    "stem:20260429_185945",
    "text:pw (20260429_185945)_teaser_18"
  ]
}
```

- La clave `content:` nueva quedó registrada junto con el post ID.
- La clave `stem:` vieja sigue presente pero no participa en la comparación.
- La simulación del feed después del ciclo #26 ya no bloqueaba `teaser_17`;
  el ciclo #27 publicó el post aún más nuevo de Seanchai.

---

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `meta_uploader/fb_to_ig_vigia.py` | Identidad por derivada, normalización de prefijos y registro, `parse_created_time()`, `_pick_newer_candidate()`, selección multipágina en Deep Cursor, resumen de motivos, códigos de salida |
| `meta_uploader/meta_uploader.py` | Escalado por orientación en `ensure_ig_compatibility()` |
| `meta_uploader/test_vigia_dedupe.py` | 15 tests de dedupe, normalización y selección |
| `scripts/linux/vigia_meta720_termux.sh` | Banner de 4 páginas y casos `0/2/3/1` |
| `meta_uploader/docs/DECISIONS.md` | D49 y D50 |
| `meta_uploader/docs/ARCHITECTURE.md` | Dedupe por derivada, escalado por orientación, códigos de salida |
| `meta_uploader/docs/PROGRESS.md` | Hitos y verificación en vivo |
| `meta_uploader/docs/HISTORIAL_CONVERSACIONES.md` | Resumen y estado de la sesión |

Commits:

| Commit | Contenido |
|---|---|
| `303dc93` | Fix completo + tests + docs |
| `5206ea6` | Verificación del ciclo #26 |
| `c51dcee` | Verificación del ciclo #27 |

---

## Despliegue y operación

### Estado del dispositivo

- S24 en `c51dcee`, rama `linux-arm64`, árbol de docs limpio.
- El proceso del launcher sigue siendo el que estaba en memoria al momento del
  deploy: el **Python nuevo sí está activo** (se lee del disco en cada ciclo),
  pero el banner y los textos de `case` se actualizan al reiniciar el widget.
- El registro del dispositivo conserva claves `stem:` históricas; son inertes.

### Cómo verificar el próximo ciclo

```bash
adb shell "tail -n 60 /sdcard/Antigravity/widget_logs/VIGIA_META720.log"
adb shell "grep -a 'Candidato mas reciente entre paginas' /sdcard/Antigravity/widget_logs/VIGIA_META720.log | tail -3"
```

Señales de salud:

- `Candidato mas reciente entre paginas: ...` con la página y `created_time`.
- `[CLIP-SPECS] ... | 720x1280 | ...` (o la orientación real del fuente).
- `Instagram acepto la publicacion. Media ID: ...`.
- `[CICLO #N] OK — crosspost exitoso`.

### Rollback

El fix es compatible hacia atrás a nivel de datos: las claves `content:` nuevas
conviven con las `stem:` viejas. Si se revierte el código, el registro seguirá
funcionando (las claves `content:` simplemente dejarán de compararse).

---

## Notas

- La cuota de Instagram se movía entre 4 y 6 de 100 publicaciones API durante
  las pruebas; no fue un factor.
- Los dos ciclos consecutivos publicaron derivadas distintas del mismo fuente
  (`teaser_18` y `teaser_19`), que es exactamente el comportamiento que el
  `stem:` desnudo impedía.
- El mismo teaser crossposteado en varias páginas seguirá deduplicándose: la
  identidad `content:` no incluye el prefijo de página.
