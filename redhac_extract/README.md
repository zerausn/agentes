# REDHAC - Extracción Facebook/Instagram vía Chrome CDP

**Extracción de la Red de Huertos Agroecológicos de Cali (REDHAC) para investigación ECACEN UNAD**

> Solo código. Los datos (JSON, Excel, fotos) no están en el repositorio por privacidad y tamaño.

---

## Estructura

```
redhac_extract/
├── README.md                     ← este archivo
├── scripts/
│   ├── fb_slow_60.py             ← extracción Facebook 714 posts (SLOW 60×6s)
│   ├── fb_chrome_full.py         ← extracción Facebook con scroll div interno
│   ├── continue_ig.py            ← extracción Instagram 469 posts (60×4s)
│   ├── fetch_ig_likes.py         ← likes/comments por post via og:description
│   ├── generate_excel.py         ← genera Excel de 4 hojas (caracterización + propuesta)
│   └── README_CORRECTO.md        ← método correcto para descargar fotos sin 403
├── docs/
│   └── REDHAC_AI.md              ← resumen para IA (estructura de datos, problemas, uso)
└── output/                       ← carpeta generada al ejecutar (gitignored)
    ├── fb_slow_all.json
    ├── ig_all_final.json
    └── REDHAC_Caracterizacion_y_Propuesta_ECACEN_2026.xlsx
```

---

## Método

Se usó **Chrome 152 + perfil Edge** (`~/.var/app/com.microsoft.Edge/config/microsoft-edge`) con **CDP `ws://127.0.0.1:9222`** y sesión logueada (`c_user`, `xs`, `fr`, `datr`), sin API Meta (la App `1455679229437683` no tiene `Page Public Content Access` → `(#10) This endpoint requires Page Public Content Access`).

- **Facebook:** `www.facebook.com/Reddehuertosagroecologicosdecali` → `714 posts` header mobile, solo `6 [role="article"]` visibles por virtualización. Extracción vía `document.body.innerText` split `Red De Huertos` + regex `U+034F` + `window.scrollTo` **SLOW 5-6s × 60** (360s) → **833 raw → 688 limpios** (96.3% de 714).
- **Instagram:** `@redhuertosagroecali` → `469/469` (1325 seguidores) via `a[href*="/p/"]` + `window.scrollTo` 60×4s, verificado contra header 469. Likes vía `og:description` navegando a cada `href`.

---

## 5 Problemas y soluciones

| # | Problema | Solución |
|---|----------|----------|
| 1 | **API Meta bloqueada `#10`** `Page Public Content Access` denegado | Chrome + perfil Edge + `Network.getAllCookies` + `ws://127.0.0.1:9222` |
| 2 | **Facebook virtualizado**: solo 6 `[role="article"]` visibles, `window.scrollTo` no carga más | `body.innerText` split `"Red De Huertos"` + `U+034F` + 60 iteraciones × 6s |
| 3 | **Instagram CDN 403 Bad URL hash / Reels bloqueados** con `curl` directo | Navegar a post con CDP → Para fotos `/p/`: raspar `img` en viewport `> 500px`. Para `/reel/`: extraer `video_versions` mp4 del JSON interno. |
| 4 | **Chrome mobile UA bloqueado**: "Este navegador no es compatible" | Desktop UA Chrome 152 + aceptar popup → header mobile muestra 714 posts |
| 5 | **Surrogates `\ud800-\udfff`** en JSON causan `UnicodeEncodeError` | `re.sub(r'[\ud800-\udfff]', '', s)` + `json.dumps(..., ensure_ascii=True)` |

---

## Uso rápido

```bash
# 1. Iniciar Chrome con perfil Edge y CDP habilitado
google-chrome --remote-debugging-port=9222 \
  --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \
  --no-first-run &

# 2. Abrir manualmente las páginas en Chrome:
#    - https://www.facebook.com/Reddehuertosagroecologicosdecali
#    - https://www.instagram.com/redhuertosagroecali/

# 3. Ejecutar scripts (desde la raíz del repo agentes/)
cd agentes/

# Facebook: 60×6s = 360s (~6 min)
python3 redhac_extract/scripts/fb_slow_60.py

# Instagram: 60×4s = 240s (~4 min)
python3 redhac_extract/scripts/continue_ig.py

# Likes por post: 469×6s = ~47 min (por defecto solo muestra de 15)
python3 redhac_extract/scripts/fetch_ig_likes.py

# Excel final (requiere ig_all_final.json + fb_chrome_all.json en output/)
python3 redhac_extract/scripts/generate_excel.py
```

Todos los archivos se guardan en `redhac_extract/output/` (carpeta creada automáticamente).

---

## Resultados

| Red | Header | Raw | Limpios | Cobertura |
|-----|--------|-----|---------|-----------|
| Facebook | 714 posts | 833 raw | 688 limpios | 96.3% |
| Instagram | 469 posts | 469/469 | 469 ✓ | 100% |
| Likes IG | 469 posts | 12 reales | 457 placeholder | 2.5% |

**Datos NO incluidos en el repo** (privacidad y tamaño): `fb_final_714.json` (526K), `ig_all_final.json` (362K), fotos `scontent`/`instagram.fclo` (requieren `oh`/`oe` fresco), Excel/MD con contenido.

---

## Requisitos

```bash
pip install websocket-client requests openpyxl
```

Ver `docs/REDHAC_AI.md` para resumen completo de estructura de datos y uso con IA.
