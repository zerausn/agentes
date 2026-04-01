# Historial de Conversaciones y Sesiones de Desarrollo

Este documento registra el contexto de las conversaciones con IAs que han trabajado en este proyecto,
para que cualquier desarrollador o IA futura pueda entender la historia y continuar sin perder contexto.

---

## Repositorios involucrados

| Repo | URL | Descripción |
|------|-----|-------------|
| Principal | https://github.com/zerausn/laboratorio-metodos-mixtos | Repo activo. El que tiene todo el código consolidado. |
| ASP (origen) | https://github.com/zerausn/laboratorio-metodos-mixtos-asp | Repo inicial desarrollado en el equipo de "andre". Fusionado al principal. |

---

## Sesión 1 — Equipo "andre" (Antigravity, ~marzo 2026)

**Objetivo:** Procesar un PDF institucional degradado (ejecución presupuestal Alcaldía de Cali, 69 páginas)
con ruido tipo "sal y pimienta" y manchas de fotocopia. Extraer texto y exportar a Word, PDF y Excel.

**Decisiones técnicas:**
- Se eligió Python sobre R por capacidad de análisis matricial con OpenCV
- Se implementó modelo de "Capas": separar texto tipográfico del ruido de fotocopia
- Principales librerías: `PyMuPDF`, `opencv-python`, `pytesseract`, `pandas`, `xlsxwriter`, `python-docx`, `reportlab`
- Se construyó `image_cleaner.py`, `export_module.py`, `pipeline_layers.py`
- Error Tesseract encontrado: diccionario `spa` no instalado → se usó `lang='eng'` temporalmente
- El procesamiento de 69 páginas corría en background (~30-60 segundos por página a 3x resolución)

**Estado al cierre de la sesión:** Pipeline corriendo en background. Outputs en `data/layer_pipeline_output`.

**Referencia:** `context_and_history.md` en raíz del repo.

---

## Sesión 2 — Esta máquina (Antigravity + OpenAI Codex, ~marzo 2026)

**Objetivo:** Fusionar el repo ASP con el repo principal. Transferir todo el código útil.

**Lo que hizo Codex:**
- Detectó que `app.py` y `requirements.txt` ya existían (del repo ASP trasladados previamente)
- Integró los módulos backend faltantes: `diagnostic_ocr.py`, `export_module.py`, `final_report_generator.py`,
  `full_recovery_manager.py`, `image_cleaner.py`, `layout_reconstructor.py`, `ocr_engine.py`, `path_utils.py`,
  `pipeline_layers.py`, `validator.py`
- Normalizó rutas duras `C:\Users\andre\...` → rutas relativas via `path_utils.py`
- Unificó dependencias en `requirements.txt` y `requirements_layers.txt`
- Creó `CONTEXT_FOR_AI.md` con instrucciones para futuras IAs
- Creó `docs/REPO_FUSION_ASP.md` documentando qué se fusionó y por qué
- **Se quedó sin tokens antes de completar la integración OCR en la UI**

**Lo que NO se hizo (quedó pendiente):**
- Integrar el motor OCR a la interfaz Streamlit
- Test de los módulos nuevos
- Push final a GitHub con contexto completo

---

## Sesión 3 — Esta máquina (Antigravity, 2026-03-24)

**Objetivo:** Continuar desde donde Codex se quedó. Integrar OCR en la UI, añadir redundancia de motores.

**Cambios realizados:**

### `backend/ocr_engine.py` — Reescritura completa
- Multi-engine con 3 capas de redundancia:
  1. **PyMuPDF nativo** — extracción de texto incrustado (sin OCR de imagen, instantáneo)
  2. **Tesseract** — OCR clásico, muy estable. Intenta `spa+eng`, cae a `eng` si no tiene el diccionario
  3. **EasyOCR** — Deep learning, mejor en documentos degradados. Requiere `torch`
- Función de **scoring automático** de calidad del texto (`_score_text`): evalúa ratio alfanumérico,
  densidad de palabras reconocibles, y penaliza caracteres raros
- El motor elige el mejor resultado automáticamente (`_select_best`)
- Si varios motores tienen scores similares (diff < 0.1), **combina** los textos
- Todos los imports son opcionales (`try/except`) → la app arranca aunque falten dependencias
- Preprocesamiento forense de imagen: denoising, threshold adaptativo, eliminación de líneas verticales,
  corrección de rotación (OSD de Tesseract)
- Mantiene alias `DegradedDocProcessor` para compatibilidad con código anterior

### `backend/export_module.py` — Ampliado
- Métodos `_bytes` que devuelven BytesIO en vez de archivo → para `st.download_button` de Streamlit
- `ocr_results_to_excel_bytes`: Excel multi-hoja (Resumen / Texto_Completo / Scores_Motores)
- `codebook_to_excel_bytes`: exporta codebook + citas + matriz de co-ocurrencia
- Soporte para Word sin tocar disco (`to_word_bytes`)

### `app.py` — Nueva sección OCR en la UI
- Nueva pestaña `🔍 OCR Multi-Motor (Documentos Degradados)` en el menú lateral
- Diagnóstico visual de motores disponibles (expandible)
- Subida de PDF degradado, selección de páginas (rango o lista)
- Tabla de scores por motor y por página
- Alerta automática para páginas de baja calidad (score < 0.15)
- Comparativa de texto por motor (con preview de 150 chars)
- Exportación directa: Excel (multi-hoja), Word (informe narrativo), CSV (texto plano)
- Sección cualitativa mejorada: exportar libro de códigos a Excel multi-hoja

### `tests/test_ocr_engine.py` — NUEVO
- Tests de calidad: texto limpio → score alto, texto basura → score bajo
- Tests de estructura de resultado por motor
- Tests de selección del mejor resultado
- Usa `skipTest` si las dependencias no están instaladas

### `tests/test_export_module.py` — NUEVO
- Tests de exportación CSV, Excel, Word con datos de muestra
- Tests de codebook con citas vacías y con citas reales
- Valida que los bytes de Excel sean formato ZIP (PK header)

---

## Instrucciones para la próxima IA

1. Lee `CONTEXT_FOR_AI.md` primero (en raíz del repo)
2. Lee `docs/REPO_FUSION_ASP.md` para entender la fusión
3. Lee este archivo para entender el historial completo
4. El código funciona sin necesidad de instalar TODOS los motores OCR —
   cada motor falla elegantemente si no está disponible
5. Para correr los tests: `python -m pytest tests/ -v`
6. Para lanzar la app: `streamlit run app.py` desde la raíz del repo
7. La app muestra un warning si OCREngine no inicia, pero sigue funcionando

## Próximos pasos sugeridos

- [ ] Integrar el módulo `reconstruccion_documental/` en la UI (subproyecto PowerShell)
- [ ] Añadir soporte Shapefile al módulo espacial (actualmente solo GeoJSON)
- [ ] Mejorar el análisis de sentimiento con modelo multilingüe (actualmente uses TextBlob básico)
- [ ] Añadir autenticación de usuario (para uso multi-investigador)
- [ ] Explorar integración de QGIS Desktop API para análisis espacial avanzado
- [ ] Implementar pipeline completo de métodos mixtos: NLP → R stats → mapa espacial en un solo workflow
