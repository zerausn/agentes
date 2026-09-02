# REDHAC - Documentación para IA

## Propósito
Contexto completo para que una IA pueda continuar el trabajo de extracción
de datos de Facebook/Instagram de la REDHAC sin necesidad de preguntar qué
se hizo o cómo funciona el entorno.

---

## Resumen de extracción

### Facebook
- **Página:** `www.facebook.com/Reddehuertosagroecologicosdecali`
- **Header mobile:** 714 posts
- **Método:** Chrome 152 + perfil Edge + CDP `ws://127.0.0.1:9222` + SLOW scroll 60×6s
- **Extracción:** `document.body.innerText` split `"Red De Huertos Agroecologicos Cali"` + `U+034F` + regex de limpieza
- **Resultado:** 833 raw → 688 limpios (96.3% del header 714)
- **Archivo generado:** `output/fb_slow_all.json` (139K aprox)

### Instagram
- **Perfil:** `@redhuertosagroecali` (1325 seguidores, 217 seguidos)
- **Header:** 469 publicaciones
- **Método:** `a[href*="/p/"]` + `window.scrollTo` 60×4s
- **Resultado:** 469/469 (100%)
- **Archivo generado:** `output/ig_all_final.json` (362K aprox)
- **Likes:** 12 con likes reales (via og:description), 457 con placeholder "ver post"
  - Ejemplo: 105 likes @ccinec__, 234 likes @karengrisales_cali

---

## Estructura de datos

### Facebook (`output/fb_slow_all.json`)
```json
{
  "count": 688,
  "posts": ["texto del post...", ...]
}
```
Posts adicionales:
- `output/fb_chrome_all.json` → extracción alternativa con scroll div interno
- `output/fb_about.txt` → texto de la sección "Información" de la página

### Instagram (`output/ig_all_final.json`)
```json
{
  "header": { "title": "..." },
  "media": [
    {
      "href": "https://www.instagram.com/redhuertosagroecali/p/CODE/",
      "alt": "caption del post (hasta 1500 chars)",
      "img": "https://scontent.cdninstagram.com/... (thumbnail, puede expirar)"
    }
  ]
}
```
Archivos adicionales:
- `output/ig_likes_sample.json` → primeros 15 posts con likes/comments/date/ogDesc/ogImage
- `output/ig_progress.json` → progreso incremental (reanudable si se interrumpe)

### Fotos
Las URLs de fotos (`scontent.cdninstagram.com`, `scontent.fclo8-1.fna.fbcdn.net`)
requieren firma `oh`/`oe` fresca. **NO** se pueden descargar con curl directo → 403.
**Método correcto:** navegar al post → extraer `og:image` → `fetch()` con `credentials: include`
dentro de la pestaña del navegador (ver `scripts/README_CORRECTO.md`).

---

## 5 Problemas y soluciones

1. **API Meta bloqueada `#10` Page Public Content Access** en App `1455679229437683`
   → Usar Chrome con perfil Edge + CDP `ws://127.0.0.1:9222` + cookies `c_user`/`xs`

2. **Facebook virtualizado**: 6 `[role="article"]` visibles, `window.scrollTo` no carga más
   → `window.scrollTo` + `body.innerText` split `"Red De Huertos"` + regex `U+034F`, 60 iter × 6s

3. **Instagram CDN 403 Bad URL hash / Reels inaccesibles**: curl directo a `scontent` → 403 (22 bytes)
   → Navegar al post con CDP. Para carruseles/fotos (`/p/`): extraer en full-page grid todos los `img` con `naturalWidth >= 500`. Para reels (`/reel/`): extraer el json embebido `video_versions` para obtener la URL directa `.mp4`. Luego descargar todo mediante Python `requests`.

4. **Chrome mobile UA bloqueado**: "Este navegador no es compatible"
   → Desktop UA Chrome 152 + perfil Edge, aceptar popup → header mobile muestra 714 posts

5. **Surrogates `\ud800-\udfff`** en JSON → `UnicodeEncodeError`
   → `re.sub(r'[\ud800-\udfff]', '', s)` y `json.dumps(..., ensure_ascii=True)`

---

## Scripts

Repositorio: rama `linux` en `zerausn/agentes` (carpeta `redhac_extract/`)

| Script | Función | Tiempo |
|--------|---------|--------|
| `scripts/fb_slow_60.py` | SLOW 60×6s → Facebook 714 posts | ~6 min |
| `scripts/fb_chrome_full.py` | Scroll div interno → FB alternativo | ~4 min |
| `scripts/continue_ig.py` | 60×4s → Instagram 469 posts | ~4 min |
| `scripts/fetch_ig_likes.py` | Likes/comments por post via og:description | ~47 min para 469 |
| `scripts/generate_excel.py` | Excel 4 hojas: caracterización + propuesta ECACEN | <1 min |

Scripts del repo que se complementan:
- `agentes/meta_uploader/meta_uploader.py` → manejo Graph API y tokens
- `agentes/meta_uploader/photo_uploader/facebook_album_web_auto.py` → CDP WebSocket FB/IG

---

## Uso

```bash
# Prerrequisito: Chrome abierto con perfil Edge y CDP
google-chrome --remote-debugging-port=9222 \
  --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \
  --no-first-run &

# Ejecutar (desde raíz de agentes/)
python3 redhac_extract/scripts/fb_slow_60.py    # 60×6s = 360s
python3 redhac_extract/scripts/continue_ig.py   # 60×4s = 240s
python3 redhac_extract/scripts/fetch_ig_likes.py  # muestra 15 posts
python3 redhac_extract/scripts/generate_excel.py  # genera Excel
```

Salidas en `redhac_extract/output/` (carpeta creada automáticamente, gitignored).

---

## Posicionamiento investigación ECACEN/UNAD

| Opción | Problema | Recomendación |
|--------|---------|---------------|
| **A - Movilización** ✓ | Débil diversificación y sostenibilidad en ESAL ambientales tipo REDHAC, pese a RESALTAR CCC + DAGMA 362 + CVC | **Recomendada** |
| B - Formalización | Bajo nivel de formalización limita acceso RESALTAR | Alternativa si REDHAC no es ESAL formal |
| C - Articulación | Desarticulación oferta vs demanda impide escalar bocashi/ecoturismo 4h/8h | Alternativa para enfoque cadena productiva |

**Ejes transversales:** pedagogía ambiental (biofábrica, jardín polinizador), laboratorio de paz (El Morro, Mojica), liderazgos (JAC Villas de Guadalupe, 300 huerteros).
