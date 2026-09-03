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

## 6 Problemas y soluciones históricas ("La hidra de mil cabezas")

1. **API Meta Graph bloqueada `#10` Page Public Content Access** en App `1455679229437683`
   → Solución: Usar Chrome con perfil Edge + CDP `ws://127.0.0.1:9222` + cookies `c_user`/`xs` simulando un usuario humano.

2. **Facebook virtualizado (Scroll infinito inútil)**: Solo 6 `[role="article"]` visibles a la vez en el DOM, hacer `window.scrollTo` normal no carga todo.
   → Solución: Script iterativo `fb_slow_60.py` que hace scroll y en cada pasada captura `body.innerText` y extrae la data partiéndola por `"Red De Huertos"`, limpiando caracteres raros (`U+034F`).

3. **Instagram CDN 403 Bad URL hash / Reels inaccesibles**: Hacer curl directo a las imágenes de `scontent` arroja 403.
   → Solución: Navegar explícitamente a cada post `/p/` mediante CDP. Extraer imágenes de alta calidad (`naturalWidth >= 500`) excluyendo las sugerencias del feed inferior (`!i.closest('a')`). Para `/reel/`, extraer el JSON nativo de `<script>` (`video_versions`) para sacar el `.mp4`.

4. **Faltantes masivos en el Excel (La Hidra)**: Los primeros scripts (e.g., `REDHAC_v2_Completo`) intentaban sacar likes, comentarios y fechas de un solo pantallazo del perfil (el grid estático). Como resultado, 467 posts quedaron sin comentarios, sin fechas y sin la lista de "quién dio like".
   → Solución: Se creó `scrape_ig_full.py`, que navega uno por uno todos los 469 posts y vuelca los datos en `output/ig_full_data.json` antes de mandarlos al Excel definitivo.

5. **Límite de la interfaz para capturar Likers**: El modal de likes visual en Instagram solo carga de a 20 usuarios y al hacer scroll se rompe o se traba después de 100 usuarios, haciendo el scraping por UI (clic y scroll) extremadamente lento y frágil.
   → Solución Definitiva (El hallazgo de oro): Se abandonó el scroll UI y se interceptó el endpoint REST nativo de Instagram `https://www.instagram.com/api/v1/media/{mediaId}/likers/`. Calculando el `mediaId` a partir del shortcode e inyectando la cookie `csrftoken` activa de la sesión, la API devuelve los usuarios de inmediato en un JSON limpio.

6. **Surrogates `\ud800-\udfff`** en JSON → `UnicodeEncodeError`
   → `re.sub(r'[\ud800-\udfff]', '', s)` y `json.dumps(..., ensure_ascii=True)`

7. **Discrepancia en "Total Likes" y comentarios vacíos para algunos posts**: Los primeros scripts leían la página completa en busca de "X Me gusta", lo cual a veces tomaba números falsos de otros comentarios en lugar del conteo real del post principal, o ignoraban los comentarios si no cargaban a tiempo.
   → Solución: Se integró el método preciso de `og:description` (como lo hacía `fetch_ig_likes.py`) dentro del scraper principal `scrape_ig_full.py`. Para reparar los posts que habían quedado con conteos erróneos o sin comentarios extraídos, se borraron del JSON base (`ig_full_data.json`) y se forzó una re-extracción limpiamente en segundo plano.

8. **Dependencia de la web vs Descarga Local Permanente**: Mantener URLs web (CDN) en el Excel de investigación representa riesgo de pérdida de datos cuando los links caducan (el error "URL signature expired").
   → Solución: `download_media.py` captura los mp4/jpg locales en paralelo, y `fill_docs_full.py` inserta **la ruta relativa local** (`media/REDHAC_codigo_foto1.jpg`) en el `.xlsx` y en el `.md` final.

9. **Comentarios capturados incorrectamente (menciones como texto)**: El selector JS original usaba `ul li span` para encontrar el texto de cada comentario. Esto causaba que cada etiqueta (`@usuario`) dentro de un comentario fuera interpretada como un comentario separado. Ejemplo de error: `'gustavo_bolivar: gustavo_bolivar'`, `'gustavo_bolivar: kelorengifo'` — era una sola mención de amigos partida en N entradas falsas.
   → Diagnóstico: Al revisar el JSON se veía que `nro_comentarios=2` pero había 5+ entradas, todas con el mismo autor y texto repetido.
   → Solución: Se reemplazó el selector de `span` individual por un selector de contenedor completo `ul > li[role="listitem"]`. Ahora se toma el `innerText` del `<li>` completo (que incluye texto + menciones en una sola cadena), se extrae el autor del primer `<a>` y se limpia del inicio del texto. Formato correcto resultante: `gustavo_bolivar: @kelorengifo @alejoocampog @ivancepedacastr`.
   → Estado: Corrección aplicada en `scrape_ig_full.py`. Se limpiaron 224 posts del caché y se relanzó la re-extracción (pendiente de completar mañana).

---

## Scripts

Repositorio: rama `linux` en `zerausn/agentes` (carpeta `redhac_extract/`)

| Script | Función | Tiempo |
|--------|---------|--------|
| `scripts/fb_slow_60.py` | SLOW 60×6s → Facebook 714 posts | ~6 min |
| `scripts/scrape_ig_full.py` | Navega 469 posts 1x1, extrae metadata + og:desc + API de likers | ~2 horas |
| `scripts/download_media.py` | Daemon paralelo que descarga las fotos y videos del JSON de posts | en vivo |
| `scripts/fill_docs_full.py` | Arma REDHAC_FINAL.xlsx y REDHAC_Instagram.md volcando links locales | <1 min |

Scripts del repo que se complementan:
- `agentes/meta_uploader/meta_uploader.py` → manejo Graph API y tokens
- `agentes/meta_uploader/photo_uploader/facebook_album_web_auto.py` → CDP WebSocket FB/IG

---

## Uso

```bash
# Prerrequisito: Chrome abierto con perfil Edge y CDP (Instagram con sesión activa)
google-chrome --remote-debugging-port=9222 \
  --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \
  --no-first-run &

# Flujo completo de extracción Instagram (desde raíz de agentes/)
# Terminal 1 — scraper principal (reanudable si se interrumpe):
python3 redhac_extract/scripts/scrape_ig_full.py

# Terminal 2 — descarga de medios en paralelo (opcional, corre a la vez):
python3 redhac_extract/scripts/download_media.py

# Una vez termine scrape_ig_full.py — generar Excel y Markdown:
python3 redhac_extract/scripts/fill_docs_full.py

# Monitorear progreso del scraper en tiempo real:
grep -o '\[[0-9]*/469\]' ~/.gemini/antigravity-ide/brain/4a5bfe4b-022b-4976-a005-c1e56d346c5e/.system_generated/tasks/<TASK_ID>.log \
  | tail -1 | tr -d '[]' | awk -F'/' '{printf "%.1f%% (%s/469)\n", $1/$2*100, $1}'
```

Salidas en `redhac_extract/output/` (carpeta creada automáticamente, gitignored).

---

## Estado Actual (2026-09-03)

| Etapa | Estado | Detalle |
|-------|--------|---------|
| Links Instagram (469) | ✅ Completo | `output/ig_all_final.json` |
| Scraping metadata + likes + likers | ✅ Completo | 466/469 con likes. 245 posts en caché limpio |
| Extracción de comentarios (corrección selector) | ⏳ Pendiente | 224 posts por re-extraer con selector corregido (`ul > li[role=listitem]`) |
| Descarga física de medios | ✅ En curso | `download_media.py` corriendo — fotos/videos en carpeta `media/` |
| Excel REDHAC_FINAL.xlsx | ⏳ Pendiente | Ejecutar `fill_docs_full.py` tras completar scraping |
| Markdown REDHAC_Instagram.md | ⏳ Pendiente | Se genera junto con el Excel |

**Para retomar mañana:**
```bash
cd /home/zerausn/Documents/Antigravity/agentes/redhac_extract
python3 scripts/scrape_ig_full.py   # salta los ya procesados automáticamente
# cuando termine:
python3 scripts/fill_docs_full.py
```


---

## Posicionamiento investigación ECACEN/UNAD

| Opción | Problema | Recomendación |
|--------|---------|---------------|
| **A - Movilización** ✓ | Débil diversificación y sostenibilidad en ESAL ambientales tipo REDHAC, pese a RESALTAR CCC + DAGMA 362 + CVC | **Recomendada** |
| B - Formalización | Bajo nivel de formalización limita acceso RESALTAR | Alternativa si REDHAC no es ESAL formal |
| C - Articulación | Desarticulación oferta vs demanda impide escalar bocashi/ecoturismo 4h/8h | Alternativa para enfoque cadena productiva |

**Ejes transversales:** pedagogía ambiental (biofábrica, jardín polinizador), laboratorio de paz (El Morro, Mojica), liderazgos (JAC Villas de Guadalupe, 300 huerteros).
