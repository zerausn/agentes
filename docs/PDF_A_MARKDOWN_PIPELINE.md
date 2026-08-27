# Pipeline PDF → Markdown pulido para IA

**Branch:** `linux` | **Fecha:** 2026-08-27 | **Hardware:** Parrot 7.3 (Debian 13), i7-1355U 12 hilos @ 30% (4 hilos), Intel Iris Xe (Vulkan para Ollama, Marker solo CPU), 62GB RAM

## Objetivo
Convertir libros en PDF (escaneados o nativos) a Markdown **muy pulido** para RAG/LLM, sin ruido, con tablas legibles.

## Herramientas instaladas (GitHub, verificadas 2026)

| Herramienta | Repo | Uso | Instalación |
|---|---|---|---|
| **PyMuPDF4LLM** `1.28.2` | `pymupdf/pymupdf4llm` | PDFs nativos y escaneados, OCR rapidocr, CPU, 4.7s/pág | `pipx install pymupdf4llm && pipx inject rapidocr_onnxruntime` → `~/.local/bin/pymupdf4llm` |
| **MarkItDown** `0.1.7` | `microsoft/markitdown` | Todo-formato (PDF/DOCX/EPUB), falla en PDFs escaneados con watermark | `pipx install markitdown[all]` → `~/.local/bin/markitdown` |
| **Marker** `2.0.0` | `datalab-to/marker` | Tablas complejas, 5GB, necesita `llama-server` b10655 + surya, CPU 30% (`OMP_NUM_THREADS=4`) | `uv venv ~/marker-env && uv pip install marker-pdf` → `~/marker-env/bin/marker_single` |
| **Ollama + llava:7b** | `ollama` | Visión OCR para gráficos (Vulkan Intel Iris Xe, 31GB) | `ollama pull llava:7b` (138s CPU → con Vulkan) |

## PDFs procesados

### 1. Córdoba Padilla 2011 - Formulación y evaluación de proyectos (140 pág, 23MB, escaneado, iLovePDF)
- **Original:** `/media/.../padilla/Córdoba Padilla, M. 2011 Formulación y evaluación de proyectos    merged.pdf`
- **OCR completo:** `Córdoba-Padilla-2011-OCR-TEXTO.md` (258KB, 4367 líneas, 16.7 min, pymupdf4llm rapidocr, lotes 5 pág)
- **LIMPIO (pulido para IA):** `Córdoba-Padilla-2011-OCR-TEXTO-LIMPIO.md` (230KB, 3526 líneas) — ver mejoras abajo
- **Rápido sin OCR:** `Córdoba-Padilla-2011-RAPIDO-TEXTO.md` (36KB, solo watermark, descartado)

### 2. Lewis 2007 - Chapter 1 An Overview (23 pág, 358KB, nativo 2 columnas)
- **Original:** `LewisJamesP._2007_Chapter1AnOverviewofP_FundamentalsofProject.pdf`
- **OCR:** `LewisJamesP_2007_Chapter1-OCR.md` (45KB, 17.8s)
- **LIMPIO corregido columnas:** `LewisJamesP_2007_Chapter1-OCR-LIMPIO.md` (38KB, 853 líneas)

> **Regla:** siempre se duplica el original y se pule la copia `-LIMPIO.md`, el original queda intacto.

## Mejoras aplicadas (para dejar Markdown pulido para IA)

### 1. Watermarks y headers repetidos
- `EBSCO Publishing: eBook Collection... 8/28/2025 ... UNAD` (46×) → eliminado
- `https://www.ebsco.com/terms-of-use` (22×) → eliminado
- `Córdoba Padilla, M. (2011)... https://elibro-net...` (125×) → eliminado
- `Copyright © 2011...` → eliminado
- `FORMULACION Y EVALUACION DE PROYECTOS` (58× header corriente) → eliminado
- `Fundamentals of Project Management` / `An Overview...` (11× cada uno) → eliminado
- `CHAPTER 1` duplicado y números de página sueltos `^\d+$` → eliminado
- `Marcial Cordoba Padilla` repetido → dejado 1×

### 2. Columnas independientes (2 columnas leídas como 1)
- **Problema:** Lewis pág 5: `of the word. “Leadership is the` (col izq) + `The best definition...` (col der) en misma línea
- **Causa:** lectura por `y` (fila) en vez de por columna
- **Fix:** detectar `x0<150` vs `x0>=150`, ordenar `left sorted(y) + right sorted(y)`, unir guiones `-\n`
- **Resultado:** `Leadership is the art...` ya separado correctamente, verificado `mezcla=False`

### 3. Guiones de fin de línea y <br> en tablas
- `ren-<br>tabilidad` → `rentabilidad`, `infra-<br>estructura` → `infraestructura`
- `Adquirirnuevastecnologias,<br>` → `Adquirir nuevas tecnologias,` + `Sernuevoenelmercado.` → `Ser nuevo en el mercado.`
- `<br>` → espacio, `-\n` → unión sin espacio, múltiples `\n{3,}` → `\n\n`

### 4. Tablas FODA rotas
- Antes:
```
|FACTORES|FUERZAS|DEBILIDADES||---|---|---|
|Internos<br>Externos|Imagen corporativa, ren-<br>tabilidad...|Sernuevoenelmercado.|
```
- Después:
```
| FACTORES | FUERZAS | DEBILIDADES |
|---|---|---|
| Internos / Externos | Imagen corporativa, rentabilidad... | Ser nuevo en el mercado. |
```
- Se normaliza `,(\w)` → `, \1`, se repara `,(\w)` y se deja tabla GFM legible para LLM. Para tablas complejas con `rowspan` se recomienda post-procesado con LLM o Marker.

### 5. Otras
- Unir palabras cortadas: `plan- ning` → `planning`, `califica- dos` → `calificados`
- Limpiar ` <mark>`, `<i>`, ` ``` ` vacíos, `<!-- PÁGINA -->` opcionales
- Normalizar espacios `  ` → ` ` y líneas vacías

## Uso para IA

```bash
# 1. Convertir nuevo PDF (ej. 100 pág escaneado, CPU 30%)
pymupdf4llm libro.pdf --out ./md --show-progress
# o página por página para evitar timeout:
# ver ~/marker-env y /tmp/convert_paullote.py (lotes 5 pág)

# 2. Limpiar (usar /tmp/limpiar.py + /tmp/pulir_tablas.py + /tmp/revisar_bien.py)
cp libro.md libro-LIMPIO.md
python limpiar.py  # aplica todos los fixes arriba

# 3. Para RAG: trocear por `##` o `<!-- PÁGINA -->`, cada chunk 2-4KB
```

## Estado Marker
- Instalado y con `llama-server b10655` (qwen35), pero en CPU sin NVIDIA da `Inference error: Request timed out` en 140 pág. Para 140 pág escaneadas necesita GPU. En CPU funciona página por página con `page_range` y `mode fast` + `OMP_NUM_THREADS=4` (ej. 5 pág en 120s). Se deja como opción para tablas críticas.

## Archivos en este repo
- Este doc: `docs/PDF_A_MARKDOWN_PIPELINE.md`
- Scripts de referencia: `/tmp/limpiar.py`, `/tmp/pulir_tablas.py`, `/tmp/corregir_columnas.py` (copiar a `scripts/linux/` si se quiere versionar)

## Próximas mejoras posibles
- Añadir LLM post-corrector para tablas FODA con `rowspan` y palabras concatenadas largas (usar `qwen2.5-coder` local)
- Integrar `MinerU` para CJK/tablas complejas si se dispone de GPU
- Automatizar pipeline en `scripts/linux/pdf2md-ia.sh` con flags `--clean --columns --tables`

## Híbrido (implementado 2026-08-27)
- **Script:** `scripts/linux/pdf2md-hibrido.sh` (CPU 6 hilos, 50%)
- **Lógica:** clasifica por `x0` (2 columnas), `imgs>2`, `texto<200`+imagen grande
- **Fáciles → pymupdf** (4s/pág), **Difíciles → MinerU** (60s/pág, 300s timeout, página por página)
- **Resultado:** Lewis 23 pág → 18 fáciles (1 min) + 5 difíciles (5 min) = 6 min con calidad MinerU donde importa, vs 23 min todo MinerU. No reprocesa lo ya hecho si no se pide.
