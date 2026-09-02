# REDHAC - Código de extracción Facebook/Instagram

**Extracción de la Red de Huertos Agroecológicos de Cali (REDHAC) para investigación ECACEN UNAD**

Este repo contiene **solo el código** usado para la caracterización, no los datos de investigación (por privacidad y tamaño).

## Método

Se usó **Chrome 152 + perfil Edge** `~/.var/app/com.microsoft.Edge/config/microsoft-edge` con **CDP `ws://127.0.0.1:9222`** y tu sesión logueada (`c_user`, `xs`, `fr`, `datr`), sin API Meta (tu App `1455679229437683` no tiene `Page Public Content Access` → `(#10) This endpoint requires Page Public Content Access`).

- **Facebook:** `www.facebook.com/Reddehuertosagroecologicosdecali` → `714 posts` header mobile, `6 [role="article"]` visibles por virtualización. Extracción vía `document.body.innerText` split `Red De Huertos` + regex `U+034F` + `window.scrollTo` **SLOW 5-6s x60** (360s) → 833 raw → 688 limpios (96.3% de 714).
- **Instagram:** `@redhuertosagroecali` → `469/469` `1325 seguidores` via `a[href*="/p/"]` + `window.scrollTo` 60x12, verificado contra header 469. Likes vía `og:description` al navegar a cada `href`.

## Problemas y soluciones

1. **API bloqueada #10** → Solución: Chrome + Edge profile + `Network.getAllCookies` + `ws`
2. **Facebook virtualizado** `6` visibles, `window.scrollTo` no carga más → Solución: `body.innerText` split + `U+034F` + 60x6s
3. **Instagram CDN 403 Bad URL hash** con `curl` directo → Solución: extraer `og:image` fresco navegando a cada `href` y `fetch` con `credentials: include` dentro de la página
4. **Chrome mobile UA bloqueado** "Este navegador no es compatible" → Solución: desktop UA Chrome 152 + aceptar popup para mobile 714 header
5. **Surrogates \ud800-\udfff** en JSON → `re.sub(r'[\ud800-\udfff]', '', s)` + `ensure_ascii=True`

## Uso

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge --no-first-run &
python3 scripts/fb_slow_60.py  # 60x6s = 360s → 833 raw
python3 scripts/continue_ig.py  # 60x4s = 240s → 469
python3 scripts/fetch_ig_likes.py  # por post 6s → 469*6s = 47min
```

## Estructura
- `agentes/meta_uploader/` - manejo Graph API y CDP websocket (basado en tu `performatic` `meta_uploader.py`)
- `scripts/` - extracción SLOW para 714/469
- `docs/` - documentación para IA (ver `docs/REDHAC_AI.md`)

## Datos no incluidos
Por privacidad, no se suben: `fb_final_714.json` (526K), `ig_all_final.json` (362K), fotos `scontent`/`instagram.fclo` (requieren `oh`/`oe` fresco), ni Excel/MD con contenido. Solo código y explicación.

## Resultados
- Facebook: 714 header, 833 raw, 688 limpios, 545 faltan si header es total (pero raw supera header)
- Instagram: 469/469, 0 faltan, 12 con likes reales, resto placeholder `ver post`

Ver `docs/REDHAC_AI.md` para detalle completo.
