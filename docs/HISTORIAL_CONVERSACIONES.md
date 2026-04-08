# Historial de Conversaciones y Sesiones de Desarrollo

Este documento registra el contexto de las conversaciones con IAs que han trabajado en este proyecto,
para que cualquier desarrollador o IA futura pueda entender la historia y continuar sin perder contexto.

> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se reparo `agentes/youtube_uploader` despues de detectar que `uploader.py` habia quedado truncado. Se reconstruyo el uploader sobre la base sana de `HEAD`, se integro de forma consistente el watchdog de progreso, se agrego `video_helpers.py` para centralizar configuracion/rutas/metadatos, se elimino la dependencia operativa a `C:\Users\ZN-\...` en `video_scanner.py`, `classify_local_videos.py` y `check_channel_videos.py`, y se alineo `schedule_drafts.py` con el prefijo vigente `PW`. Tambien se actualizo el flujo documentado para incluir clasificacion local, se agregaron pruebas unitarias en `youtube_uploader/tests/test_video_helpers.py` y la validacion local quedo en verde con `python -m compileall .` y `python -m unittest discover -s tests -v`.
> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se realizo una auditoria tecnica de `agentes/youtube_uploader` sin aplicar cambios de codigo. Hallazgos principales: `youtube_uploader/uploader.py` quedo roto en el working tree actual y no compila (`IndentationError` en la linea 112 al ejecutar `python -m compileall .`), el flujo documentado en `youtube_uploader/README.md` no genera todos los campos que el uploader consume (`type` y, para nuevos registros, `creation_date`), y siguen existiendo dependencias a la ruta absoluta `C:\Users\ZN-\Documents\ADM\Carpeta 1` en `video_scanner.py`, `check_channel_videos.py` y `classify_local_videos.py`, contradiciendo la regla local de portabilidad. Tambien se detecto desalineacion entre la decision de prefijo `PW` y la heuristica de `schedule_drafts.py`, que aun busca `Performatic Writings`. No se publico nada ni se tocaron credenciales, logs o configuraciones locales.
> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se abrio el panel real de Meta en Edge con la sesion del perfil local y se confirmo que la app `Uploader Bot` (`1455679229437683`) sigue en estado `Sin publicar`. Durante la revision se detecto que Meta bloquea el envio a App Review por falta de prerrequisitos de configuracion, no solo por permisos: faltaban icono 1024x1024, URL de politica de privacidad, URL o enlace para eliminacion de datos y categoria. Para destrabarlo se prepararon y versionaron activos publicos minimos en `meta_uploader/` (`docs/PRIVACY_POLICY.md`, `docs/DATA_DELETION.md`, `docs/TERMS_OF_SERVICE.md` y `assets/uploader_bot_icon_1024.png`), se publicaron en GitHub y se cargaron desde Edge en la configuracion basica de la app. La UI de Meta mantuvo el aviso de faltantes durante la misma sesion, por lo que el estado de validacion final quedo pendiente de relectura del panel por parte de Meta.
> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; continuidad sobre Meta App Review): se preparo una salida gratuita y mas robusta para destrabar la validacion de Meta: un mini sitio estatico en `meta_uploader/site/` con `index.html`, `privacy.html`, `data-deletion.html` y `terms.html`, junto con workflow de GitHub Pages en `.github/workflows/meta-uploader-pages.yml`. El objetivo es reemplazar URLs `github.com/.../blob/...` por URLs limpias de Pages, ya que el comportamiento del panel de Meta apunto mas a un problema de validacion/metadata del dashboard que a un fallo real del icono.
> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; ajuste de verificacion): se actualizo el sitio publicado de `meta_uploader` para que la portada y las paginas legales muestren explicitamente los datos que Meta estaba pidiendo durante la verificacion del business: `Performatic writings`, `7600001, km 28 via dagua, 7600001 cali` y `+573156816992`. Con esto la URL de GitHub Pages queda util tanto para App Review como para el campo de sitio web en Business Verification.
> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se verifico el cierre operativo de la ronda anterior en `meta_uploader/`. Resultado: el repo `agentes` quedo limpio y sincronizado en `origin/codex/20260406-163730` con el commit `b032b7a`, `python -m compileall C:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader` paso sin errores y no hay `HANDOVER` bloqueante. Lo pendiente no es una correccion obligatoria sino la siguiente ola de endurecimiento: validacion en vivo con tokens y assets de prueba, posible separacion formal del carril IG-only y mejoras operativas como preflight tecnico e idempotencia.
> Actualizacion 2026-04-07 (Antigravity + OpenAI Codex; evaluacion de SDK oficial): se reviso `facebook/facebook-python-business-sdk` como posible base alternativa para `meta_uploader`. Hallazgo: el SDK oficial sigue vivo y con release reciente (`25.0.1`, `2026-03-30`), pero su README y carpeta `examples/` siguen centrados sobre todo en Marketing API, objetos autogenerados y casos de anuncios. Decision operativa: no migrar el uploader al SDK; mantener `requests` como base y rescatar solo ideas puntuales del SDK, como sesiones por token, batch calls para lecturas no criticas y el modo `debug=True` para imprimir cURL comparables.
> Actualizacion 2026-04-06 (Antigravity + OpenAI Codex, con exploracion delegada a Raman; Claude Code no intervino): se reviso el estado del repo `agentes` contra GitHub y se confirmo que el trabajo pendiente de publicacion estaba en `meta_uploader/`. Se alineo el flujo con la documentacion oficial de Meta: `caption` en la creacion del contenedor de Instagram, polling explicito para Instagram y Facebook antes de declarar exito, version de Graph API configurable, separacion entre token de usuario IG y token de pagina FB, y regla local conservadora `3-90s` vertical para el carril compartido Reel/Reel. Tambien se sanearon `README.md`, `AI.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/GUIA_TOKENS_META.md` y se agrego `meta_uploader/docs/META_OFICIAL_Y_OPERACION_SEGURA.md` para dejar trazabilidad de la revision contra Meta, Facebook e Instagram sin subir datos personales, tokens ni artefactos locales.
> Actualizacion 2026-04-06 (Antigravity + OpenAI Codex, con exploracion delegada): se corrigio la ubicacion del subproyecto `youtube_uploader`, que estaba anidado por error en `agentes/agentes/youtube_uploader`, y se movio a `youtube_uploader/` en la raiz del repo `agentes`. Tambien se actualizaron rutas, scripts `.bat`, validaciones en `.antigravity/automation.json` y la documentacion del repo para eliminar dependencias de la ruta vieja. Se verifico adicionalmente que `meta_uploader/` si pertenece a este repo y se le dejo un contexto local minimo (`AGENTS.md`, `AI.md`, `docs/`, `.env.example`, `requirements.txt`) para alinearlo con la arquitectura del workspace.

> ActualizaciÃ³n 2026-04-01 (Antigravity + OpenAI Codex; Claude Code no intervino): se revisÃ³ `agentes/youtube_uploader`. Estado observado: `324` videos totales, `7` subidos, `317` pendientes, `4` credenciales con solo `token_0.json` autorizado. Hallazgos principales: `uploader.py` no corta ni rota ante `uploadLimitExceeded`, `video_scanner.py` usa rutas relativas y `clean_json.py` depende de rutas absolutas de esta mÃ¡quina. La corrida activa quedÃ³ esperando autorizaciÃ³n OAuth para la siguiente credencial despuÃ©s de agotar `client_secret_1.json`.
> Actualizacion 2026-04-06 (continuacion, Antigravity + OpenAI Codex): se agrego la capa `.antigravity/automation.json` en los repos propios con validaciones reales o baseline seguras, se incorporo soporte explicito para `push_remote` y `base_remote` en el starter kit para cubrir forks como `antigravity-manager-src`, y se dejaron workflows `agent-validate.yml` en los repos que no tenian CI propia.
> Actualizacion 2026-04-06 (Antigravity + OpenAI Codex; Claude Code y Gemini quedaron cubiertos por compatibilidad): se definio `AGENTS.md` como estandar abierto de interoperabilidad en `Antigravity`, manteniendo `AI.md` como alias neutral. Se anadieron capas de compatibilidad con `CLAUDE.md`, `GEMINI.md` y `.github/copilot-instructions.md` en los repos propios, se corrigio el `AI.md` raiz del repo `agentes` para que dejara de apuntar por error al subproyecto `youtube_uploader`, y se documentaron la arquitectura y la auditoria del rollout en `C:/Users/ZN-/Documents/Antigravity/docs/`.

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
---

## Sesion 4 - Meta Uploader y App Review (Codex, 2026-04-07)

- Se confirmo el despliegue de `https://zerausn.github.io/agentes/` y sus paginas legales para soporte de App Review y Access Verification en Meta.
- Se dejo como criterio operativo que `meta_uploader` es una app de publicacion organica para Facebook e Instagram y no una app de Ads ni Catalog API.
- Para `Access Verification`, mientras `Performatic Writings` siga siendo marca informal y los porfolios confirmados (`802657775463630` y `676518254917301`) sean propios del operador, la opcion mas segura para describir la empresa es `Autonomo`.

## Sesion 5 - Meta Uploader, sonda real y watchdog (Codex, 2026-04-07)

- Se endurecio `meta_uploader.py` con un watchdog de subida que revisa progreso cada 10 segundos y alerta despues de 2 verificaciones sin avance, con diagnostico basico para distinguir conectividad local vs socket a Meta.
- Se reemplazo el experimento de `test_single_scheduled.py` por una sonda real de un solo asset que toma el video mas pesado disponible, respeta `META_ENABLE_UPLOAD=1` y prueba reels/posts solo donde el asset y la documentacion oficial lo permiten.
- Resultado real de la sonda: Instagram post aceptado con media id `17921696511315151`; Facebook post fallo durante la subida binaria por `ConnectionResetError(10054)` del host remoto.
- Stories quedaron saltadas a proposito porque la documentacion oficial versionada en el repo no cubre ese flujo para este carril.
- Los carriles Reel quedaron sin ejecutar en la sonda porque `pendientes_reels.json` estaba vacio; la cola `pendientes_posts.json` si estaba ordenada por peso descendente y selecciono `20260310_184517.mp4` (2696.6 MB, 3840x2160, 157.258656 s).
- `single_format_probe_result.json` se dejo como artefacto operativo local fuera de Git.

## Sesion 6 - Meta Uploader, stories/reels derivados y nuevo retry FB (Codex, 2026-04-07)

- Se contrasto de nuevo con documentacion oficial y esta vez se confirmo soporte documentado para `Instagram Stories` mediante `media_type=STORIES` y `upload_type=resumable`.
- Se mantuvo fuera del flujo automatizado a `Facebook Stories`, porque no se encontro una guia oficial equivalente claramente aplicable a este carril de Pages dentro de las fuentes ya auditadas.
- `test_single_scheduled.py` se endurecio para derivar automaticamente un clip vertical corto (`1080x1920`, `30s`) cuando `pendientes_reels.json` esta vacio, de forma que el carril story/reel pueda probarse aun sin material vertical fuente.
- Resultado real de la nueva sonda: `Facebook Reel` publico con exito (`1863981500985541`) y `Instagram Post` publico con exito (`17883639039504468`).
- `Instagram Story` y `Instagram Reel` alcanzaron a crear contenedor pero fallaron en `rupload` con `ProcessingFailedError`, pese a que el clip derivado quedo dentro de specs basicas (`H.264`, `1080x1920`, `30s`, `6.4 MB`).
- `Facebook Post` ya no fallo por wifi: revelo un bug concreto del cliente, porque Meta exigio `upload_session_id` en el `finish` (`#194`). El codigo se ajusto para propagar ese parametro.
- Despues del fix se lanzo un retry puntual de `Facebook Post`, pero el usuario interrumpio la prueba. El proceso huérfano quedo con una conexion TLS abierta y fue detenido manualmente para dejar el estado limpio.

## Sesion 7 - YouTube Uploader, segunda jornada de clipping local (Codex, 2026-04-07)

- El usuario corrigio el alcance: la investigacion y la implementacion de clipping local debian integrarse en `youtube_uploader`, no en `meta_uploader`.
- Se mantuvo intacta la jornada 1 del uploader y se creo un carril nuevo `youtube_uploader/second_pass/` para una jornada 2 totalmente separada.
- `second_pass/local_clip_optimizer.py` analiza masters con `ffprobe` y `ffmpeg`, detecta escenas, silencios, negro, intenta `cropdetect`, lee sidecars (`.srt`, `.vtt`, `.json`) y puntua ventanas con enfasis en hook temprano.
- El optimizador renderiza derivados en `second_pass/optimized_videos/`, genera manifests y colas separadas, y propone `title_suggestion`, `description_suggestion` y `tags_suggestion`.
- `second_pass/register_optimized_videos.py` registra optimizados dentro de `scanned_videos.json` solo bajo accion explicita, para no contaminar la jornada 1.
- `uploader.py` y `video_helpers.py` ahora aceptan overrides de metadata por video (`title_override`, `description_override`, `tags_override`, etc.), con lo cual la jornada 2 puede empaquetar mejor los clips sin romper el comportamiento historico.
- Se actualizaron `README.md`, `AI.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md` y se agrego `docs/SECOND_PASS_CLIPPING.md`.
- Validacion local completada:
  - `python -m py_compile uploader.py video_helpers.py second_pass\local_clip_optimizer.py second_pass\register_optimized_videos.py tests\test_video_helpers.py tests\test_second_pass.py`
  - `python -m unittest discover -s tests -v`
  - ambos CLIs nuevos responden correctamente a `--help`
