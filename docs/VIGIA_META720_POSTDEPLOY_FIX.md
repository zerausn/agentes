# VIGIA_META720 — Fix post-deploy: IN_PROGRESS + Shirabyoshi token

**Fecha:** 2026-10-26 (sesión 2)
**Rama:** `linux-arm64`
**Commits:** `c0a4e62`

---

## Contexto

Después de desplegar `ad8c934` (5 fixes principales), el ciclo #18 reveló
3 bugs adicionales que solo eran visibles en producción real.

---

## Bug 6 — `wait_for_ig_container_upload_ready` esperaba `UPLOAD_IN_PROGRESS` (no existe)

### Síntoma en log ciclo #18
```log
Contenedor IG 17911959279565377 esperando estado upload (actual: IN_PROGRESS)...
Contenedor IG 17911959279565377 esperando estado upload (actual: IN_PROGRESS)...
[... × 13 veces durante 45 segundos ...]
Timeout (45s) esperando UPLOAD_IN_PROGRESS. Intentando upload de todas formas.
Subiendo IG: 100.0% (23793679/23793679 bytes)
WARNING - Subiendo IG parece detenida: sin avance en 24s...
ERROR - Fallo subida binaria HTTP 400 — ProcessingFailedError
```

### Causa raíz
```python
# CÓDIGO ORIGINAL (incorrecto)
if status_code in {"UPLOAD_IN_PROGRESS", "FINISHED", "PUBLISHED"}:
    return True
```

Meta usa `IN_PROGRESS` (no `UPLOAD_IN_PROGRESS`) para indicar que el contenedor
está listo para recibir el binario. El timeout de 45s dejaba expirar la ventana
de upload, y el binario se enviaba a un contenedor vencido → `ProcessingFailedError`.

### Flujo de estados reales de Meta (upload_type=resumable)

```
Crear contenedor → IN_PROGRESS (listo para upload binario)
Upload binario   → IN_PROGRESS (procesando)
Procesado        → FINISHED
Publicar         → PUBLISHED
Error            → ERROR / EXPIRED
```

### Fix
```python
# CÓDIGO CORREGIDO
if status_code in {"IN_PROGRESS", "UPLOAD_IN_PROGRESS", "FINISHED", "PUBLISHED"}:
    return True  # Primera poll (~2s) → True inmediato
```

El primer poll retorna `True` inmediatamente (el contenedor ya es `IN_PROGRESS`
en el momento en que responde la primera consulta). Timeout reducido a 30s.

---

## Bug 7 — Shirabyoshi: nombre de variable incorrecto

### Síntoma
```log
[Shirabyoshi Writings] Sin credenciales - saltando.
```

### Causa

| Commit | Acción | Consecuencia |
|--------|--------|-------------|
| Antes de `8811cdf` | Token hardcodeado en fuente | Siempre funcionaba |
| `8811cdf` (Oct 1) | Token removido por seguridad, fallback → `""` | Depende del `.env` |
| `ad8c934` (Oct 26) | Pull al S24 aplica `8811cdf` | Sin hardcode, busca env |
| `.env` del proot | Token guardado como `META_FB_PAGE_TOKEN_SHIRABYOSHI` | OK |
| Código `FB_PAGES` | Buscaba `META_FB_PAGE_TOKEN_TEASER` | ← NOMBRE INCORRECTO |

Resultado: el token existía con nombre diferente al que buscaba el código.

### Fix en `fb_to_ig_vigia.py`
```python
# ANTES
os.environ.get("META_FB_PAGE_TOKEN_TEASER", ""),

# DESPUÉS
os.environ.get("META_FB_PAGE_TOKEN_SHIRABYOSHI") or os.environ.get("META_FB_PAGE_TOKEN_TEASER", ""),
```

Busca el nombre correcto del `.env` primero; si no existe, intenta el nombre
legacy del `.agentes_termux_env`. Doble fallback → resiliente a ambos esquemas.

---

## Bug 8 — Alias faltante en proot `.env` (fix en runtime)

El `.env` del proot tenía `META_FB_PAGE_TOKEN_SHIRABYOSHI` pero no
`META_FB_PAGE_TOKEN_TEASER`. Se añadió el alias directamente:

```bash
echo "META_FB_PAGE_ID_TEASER=1347014641828725" >> /root/agentes/meta_uploader/.env
echo "META_FB_PAGE_TOKEN_TEASER=<token>" >> /root/agentes/meta_uploader/.env
```

> Este fix es de runtime — no requiere commit porque el `.env` está en `.gitignore`.
> Está documentado aquí para reproducirlo si se restaura el proot desde cero.

---

## Verificación de tokens en vivo

Llamada directa a `GET /{page_id}?fields=name,id` desde el S24 (curl, 2026-10-26 13:29):

| Variable | Página real en FB | Resultado |
|----------|-------------------|-----------|
| `META_FB_PAGE_TOKEN` | Performatic Writings Cali | ✅ Válido |
| `META_FB_PAGE_TOKEN_SHIRABYOSHI` | Shirabyoshi Writings | ✅ Válido |
| `META_FB_PAGE_TOKEN_SEANCHAI` | Seanchai Writings | ✅ Válido |
| `META_FB_PAGE_TOKEN_GHAWAZEE` | Ghawazee Writings | ✅ Válido |

### ¿Por qué los tokens no expiran?

Los `Page Access Tokens` que empiezan por `EAAUr7rtgpvMBSs...` son tokens derivados
de un **long-lived User Access Token** vinculado al Business Manager. Según la
documentación de Meta, estos tokens **no tienen fecha de expiración** mientras:
- La app mantenga los permisos (`pages_manage_posts`, `pages_read_engagement`)
- El usuario no revoque el acceso a la app
- La app siga activa en el Business Manager

No se requiere renovación automática ni cron de refresh.

---

## Resumen de ciclos pre/post fix

| Ciclo | Código | Shirabyoshi | FEED dup | Container wait | Resultado |
|-------|--------|-------------|----------|----------------|-----------|
| #17 | `7484df0` (viejo) | ✅ revisada | ❌ FEED duplicado (58MB falla) | sleep(2) | 1 REELS OK |
| #18 | `ad8c934` | ❌ Sin credenciales | ✅ eliminado | 45s timeout → expiró | 0 publicados |
| #19+ | `c0a4e62` | ✅ revisada | ✅ eliminado | IN_PROGRESS → ~2s | esperado: OK |

---

## Archivos modificados (commit `c0a4e62`)

```
meta_uploader/meta_uploader.py   — IN_PROGRESS aceptado; timeout 45→30s; docstring corregido
meta_uploader/fb_to_ig_vigia.py  — FB_PAGES: SHIRABYOSHI con fallback TEASER
docs/DECISIONS.md                 — entrada 2026-10-26 sesión 2
docs/VIGIA_META720_POSTDEPLOY_FIX.md  — este archivo
```

## Archivos de runtime modificados (no en git)

```
/root/agentes/meta_uploader/.env (proot S24)
  + META_FB_PAGE_ID_TEASER=1347014641828725
  + META_FB_PAGE_TOKEN_TEASER=<alias de META_FB_PAGE_TOKEN_SHIRABYOSHI>
```
