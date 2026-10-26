# VIGIA_META720 — Fix: ProcessingFailedError & reintentos infinitos

**Fecha:** 2026-10-26  
**Rama:** `linux-arm64`  
**Dispositivo afectado:** S24 (Termux + proot Debian)

---

## Diagnóstico previo

Una IA externa analizó 769.248 líneas / 150 MB de log y encontró:

- **433 `ProcessingFailedError` históricos** en `fb_to_ig_vigia.log`
- Solo **2 de 14 intentos** publicaron en la jornada del 26-oct
- El mismo post fallido fue reintentado **12 veces** (24 rechazos binarios)
- **4.9 GB** de temporales huérfanos acumulados en `.ig_temp`
- El binario llegaba al 100% pero Meta lo rechazaba con **HTTP 400**

---

## Bug 1 — Audio AAC a 44.1 kHz ← causa raíz del HTTP 400

### Síntoma
```
ProcessingFailedError: The video could not be processed.
```
El video llegaba completo a Meta pero era rechazado en el procesador interno.

### Causa
`ensure_ig_compatibility()` en `meta_uploader.py` transcodificaba el audio con:
```python
"-ar", "44100"   # ← INCORRECTO
```
**Meta requiere 48 kHz** para Reels según su documentación oficial.

### Fix — `meta_uploader/meta_uploader.py` línea ~2233
```diff
-"-ar", "44100"
+"-ar", "48000"  # Meta requiere 48 kHz para Reels
```

---

## Bug 2 — Contenedor IG no preparado antes del upload binario

### Síntoma
Error en logs históricos:
```
not in the status to upload a video
```

### Causa
Tras crear el contenedor con `_create_ig_video_container()`, el código solo esperaba:
```python
time.sleep(2)   # ← demasiado corto; Meta tarda 1-20s en preparar el contenedor
```
El binario se enviaba antes de que el contenedor estuviera en `UPLOAD_IN_PROGRESS`.

### Fix — nueva función en `meta_uploader/meta_uploader.py`
```python
def wait_for_ig_container_upload_ready(creation_id, max_wait_seconds=45):
    """
    Hace polling hasta UPLOAD_IN_PROGRESS antes de subir el binario.
    """
    url = graph_url(str(creation_id))
    params = {"fields": "status_code,status", "access_token": IG_ACCESS_TOKEN}
    deadline = time.time() + max_wait_seconds

    while time.time() < deadline:
        result = _request_json("GET", url, params=params)
        if result:
            status_code = (result.get("status_code") or "").upper()
            if status_code in {"UPLOAD_IN_PROGRESS", "FINISHED", "PUBLISHED"}:
                return True
            if status_code in {"ERROR", "EXPIRED"}:
                return False
        time.sleep(3)

    return True  # Timeout: intenta de todas formas
```

En `fb_to_ig_vigia.py`:
```diff
-time.sleep(2)
-if upload_ig_binary(creation_id, path_for_target):
+if not wait_for_ig_container_upload_ready(creation_id):
+    logging.error("Contenedor nunca llegó a UPLOAD_IN_PROGRESS. Abortando.")
+elif upload_ig_binary(creation_id, path_for_target):
```

---

## Bug 3 — Fallback "FEED" duplicaba el upload de REELS

### Síntoma
Para cada video > 90 s: **2 containers creados, 2 binarios subidos, 2 rechazos**.

### Causa
```python
# fb_to_ig_vigia.py — lógica original
active_targets = ["REELS"]
if duration > 90:
    active_targets.append("FEED")   # ← añadía un 2° target

# Pero en el loop, la rama FEED era idéntica a REELS:
if target_type in ("REELS", "FEED"):
    creation_id = _create_ig_video_container("REELS", share_to_feed=True)  # ← MISMO llamado
```
Ambos targets usaban `media_type=REELS` con `share_to_feed=True`. No había diferencia funcional.

### Fix
```diff
 active_targets = list(targets)
-if duration > 90 and "FEED" not in active_targets:
-    logging.info("Video largo: activando Feed Completo.")
-    active_targets.append("FEED")
+# FEED eliminado — era idéntico a REELS; videos >90s se recortan en REELS
```

---

## Bug 4 — Reintentos infinitos del mismo post fallido

### Síntoma
El mismo `post_id` aparece en 12 ciclos consecutivos, siempre fallando.

### Causa
`register_processed_post()` solo se llamaba cuando `at_least_one_success = True`.
Un post que fallaba todos los targets nunca se registraba → el siguiente ciclo lo
encontraba de nuevo y reintentaba indefinidamente.

### Fix — `crosspost_failure_counts.json` + lógica de skip

```python
# Constantes añadidas a fb_to_ig_vigia.py
MAX_CONSECUTIVE_FAILURES = 3
FAILURE_COUNTS_FILE = BASE_DIR / "crosspost_failure_counts.json"

# Al final de cada ciclo fallido:
failure_counts[post_id] = failure_counts.get(post_id, 0) + 1
if failure_counts[post_id] >= MAX_CONSECUTIVE_FAILURES:
    register_processed_post(history, registry, post_id, ...)  # salta el post
```

Al publicar con éxito, el contador se resetea:
```python
failure_counts.pop(post_id, None)
```

---

## Bonus — Limpieza automática de `.ig_temp`

Los 4.9 GB de temporales huérfanos en `.ig_temp` se limpian automáticamente
después de cada publicación exitosa:

```python
ig_temp_dir = BASE_DIR / ".ig_temp"
if ig_temp_dir.exists():
    for tmp in ig_temp_dir.iterdir():
        if tmp.is_file():
            tmp.unlink()
```

---

## Archivos modificados

```
meta_uploader/meta_uploader.py    # Fix AAC 48kHz + wait_for_ig_container_upload_ready()
meta_uploader/fb_to_ig_vigia.py   # Import; sin FEED fallback; wait real; failure counter; cleanup
docs/DECISIONS.md                  # Entrada 2026-10-26
docs/VIGIA_META720_PROCESSINGFAILED_FIX.md  # este archivo
```

## Archivos nuevos en runtime (auto-generados)

```
meta_uploader/crosspost_failure_counts.json   # contador de fallos por post_id
```

---

## Flujo corregido (resumen)

```
[1] Descarga video de FB
[2] ensure_ig_compatibility(force_recode=True)
      → H.264 High 4.1 / yuv420p / AAC 48kHz ← CORREGIDO
[3] _create_ig_video_container("REELS", share_to_feed=True)
[4] wait_for_ig_container_upload_ready()  ← NUEVO (era sleep(2))
      polling hasta UPLOAD_IN_PROGRESS (max 45s)
[5] upload_ig_binary()
[6] wait_for_ig_container()  (hasta FINISHED)
[7] publish_ig_container()
[8] Limpieza .ig_temp      ← NUEVO
[9] Registro en historial + reset failure_counts
```

Si falla en pasos 5-7 → `failure_counts[post_id] += 1`  
Si `failure_counts >= 3` → post marcado como procesado, siguiente candidato.
