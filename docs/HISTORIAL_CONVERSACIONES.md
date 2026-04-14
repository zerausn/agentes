# Historial de Conversaciones y Sesiones de Desarrollo

Este documento registra el contexto de las conversaciones con IAs que han trabajado en este proyecto,
para que cualquier desarrollador o IA futura pueda entender la historia y continuar sin perder contexto.

> Actualizacion 2026-04-13 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se resolvio el bug por el cual videos ya programados en Facebook seguian resucitando desde `pendientes_posts.json` y entraban otra vez al `meta_calendar.json`. Hallazgo raiz: `find_existing_facebook_video_by_caption_marker(...)` y el cache de `get_facebook_library_batch(...)` solo miraban `/{page}/videos`, pero varios programados reales viven solo en `/{page}/scheduled_posts` con el stem en `message`. Se comprobo en vivo que `20260409_183524`, `20260409_184059` y `20260409_192728` devolvian `None` por la ruta vieja, pero si aparecian en `scheduled_posts` con ids/fechas futuras. Correcciones aplicadas: lectura de `scheduled_posts` para guardia remota y cache, normalizacion del stem canonico para derivados como `slice_60s_*`, limpieza previa de colas locales contra Meta antes de reconstruir el calendario, y ajuste del carril post para no marcar `failed` un asset cuyo `facebook_post_full_scheduled` ya quedo confirmado si solo falla el reel inmediato auxiliar. Operacion local ejecutada: se detuvieron supervisores/runners duplicados que seguian corriendo con codigo viejo, la limpieza remota termino removiendo `42` entradas de `pendientes_posts.json` ya existentes en Meta y se regenero `meta_calendar.json` desde cero (`180` dias) sin reinsertar esos stems. Se intento reactivar el supervisor, pero en este entorno se autodupliko en cadena, asi que se apagaron todos los procesos de `meta_uploader` y el sistema quedo limpio y pausado para el siguiente arranque.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se ejecuto la auditoria operativa en `agentes/meta_uploader` sobre `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente` para evitar duplicados entre Facebook e Instagram antes de lanzar jornada 1. Se consultaron APIs oficiales de Meta y se detecto `1` coincidencia ya publicada en ambas plataformas (`20260310_184517.mp4`, FB id `1863981500985541`, IG id `18578908267001931`). Se generaron los archivos `listado_ya_subidos_fb_ig.txt` y `listado_ya_subidos_fb_ig.json` (copiados tambien en la carpeta fuente), se movio ese asset a `C:\Users\ZN-\Documents\ADM\Carpeta 1\ya_subidos_fb_ig\` y se reclasifico la carpeta para jornada 1 (`33` pendientes, `0` reels compartidos). Luego se inicio la subida real con `run_jornada1_normal.py --days 7` y `META_ENABLE_UPLOAD=1`; el proceso quedo activo en background (`python.exe` PID `13408`) transfiriendo `20260310_185649.mp4` por chunks de `8 MB`, con omision explicita de `instagram_feed` para ese crudo por exceder specs oficiales de IG (`~2796.5 MB > 315 MB`).
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): el usuario priorizo la subida de YouTube. Se verifico que `agentes/youtube_uploader/uploader.py` ya estaba activo desde las `19:53` y subiendo de verdad. Hallazgo operativo: el uploader completo `20260304_190054.mp4` con video id `2lrdekrU9lU` y luego siguio con `20260304_181602.mp4`, que quedo avanzando por encima de `50%`. Para no dividir ancho de banda con Meta, se detuvieron los procesos de `run_jornada1_supervisor.py` y `run_jornada1_normal.py`; la reanudacion de Meta quedo protegida por los checkpoints resumibles ya implementados.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): tras confirmar que la corrida de Meta se habia detenido sola despues de `3` videos completos, se endurecio la operacion de jornada 1. `run_jornada1_normal.py` ahora escribe `meta_calendar.json` de forma atomica, marca lanes como `in_progress`, conserva dias completados al relanzar y devuelve codigos de salida utiles. Ademas se agrego `run_jornada1_supervisor.py`, un wrapper local que relanza el runner si termina antes de completar el calendario y no dejo una pausa explicita por fallo, y `meta_uploader.py` ahora guarda checkpoints locales del upload resumible de Facebook (`upload_session_id` + `current_offset`) para intentar retomar videos grandes desde el ultimo offset confirmado. El cuarto video afectado por la caida fue `20260310_183619.mp4`; quedo con ultimo avance confirmado de `2,004,877,312 / 2,614,367,574 bytes` (`76.69%`) antes de reiniciar la estrategia operativa. Luego se hizo una prueba controlada real: se mato el hijo `run_jornada1_normal.py`, el supervisor lo relanzo en `15s` y el uploader retomo `20260310_183619.mp4` desde el checkpoint persistido en `125,829,120 bytes` en lugar de reiniciar desde cero.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; reindexacion puntual de `Carpeta 1` para YouTube): se detuvo `youtube_uploader` de forma controlada con `STOP`, se reescaneo solo `C:\Users\ZN-\Documents\ADM\Carpeta 1` excluyendo manualmente `videos subidos exitosamente` y `videos_excluidos_ya_en_youtube`, y se fusionaron `138` registros nuevos en `scanned_videos.json` (`248` totales). Luego se corrio `check_channel_videos.py` contra el canal real (`813` videos auditados) y no aparecieron repeticiones nuevas para mover. Hallazgo clave: `20260302_190317.mp4` quedo indexado como `uploaded: false` y paso a la posicion `1` del carril `video` con `2448.97 MB`; adicionalmente se confirmo que en esta maquina no hay `ffprobe`, por lo que los nuevos archivos grandes quedaron sin `type` y el uploader los tratara como `video` por defecto hasta instalar esa herramienta.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; verificacion operativa de exclusiones YouTube): se auditó la carpeta `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos_excluidos_ya_en_youtube` contra el canal real. Resultado: los `7/7` archivos ya existen en YouTube. Se detectaron duplicados programados para `20260310_184517`, `20260310_185649` y `20260310_190454`, cada uno con dos entradas privadas y fechas distintas; `20260201_191557` aparecio como `unlisted` sin fecha y los demas como `private` con `publishAt`.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se hizo auditoria real del canal de YouTube antes de continuar `agentes/youtube_uploader`. Hallazgos: `798` videos analizados en el canal, `603` publicos, `128` ocultos, `65` privados programados y `2` borradores reales sin fecha. En la ventana de 45 dias desde `2026-04-08`, el primer hueco de `video` estaba en `2026-04-08` y el primer hueco de `short` en `2026-04-16`, lo que confirmo que faltaba separar la prioridad por carril en vez de seguir subiendo por peso global.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se completo el entorno local de `youtube_uploader` dentro del `.venv` del workspace, instalando `pyparsing` y las dependencias de `requirements.txt`, lo que permitio volver a ejecutar la auditoria del canal, `check_channel_videos.py` y el uploader real con el Python aislado del proyecto.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se corrigio `agentes/youtube_uploader/uploader.py` para no tratar `uploadLimitExceeded` como si fuera agotamiento de credencial, se separaron las colas pendientes en dos carriles (`video` y `short`) ordenados cada uno por `size_mb`, y el selector del siguiente asset quedo basado en la fecha libre mas cercana de cada carril con desempate por el archivo mas pesado en cabeza de cola. Tambien se agregaron pruebas en `agentes/youtube_uploader/tests/test_uploader_queue.py` y pasaron en verde.
> Actualizacion 2026-04-08 (Antigravity + OpenAI Codex; Claude Code no intervino en esta sesion): se ejecuto una corrida real de `youtube_uploader` y se completaron `5` subidas nuevas, todas en estado `private` con `publishAt`: `20251010_210832.mp4` (`uf-Ti5w9SM4`, `2026-04-09T22:45:00Z`), `20251121_210754.mp4` (`0IQ2eYbftvQ`, `2026-04-16T22:45:00Z`), `20251018_193733.mp4` (`Rx_N3mE7caU`, `2026-04-17T22:45:00Z`), `20251010_204209.mp4` (`fcSydA_jIpc`, `2026-04-10T22:45:00Z`) y `20251010_195816.mp4` (`ejpySA0Fqbs`, `2026-04-11T22:45:00Z`). Luego se relanzo el uploader con la logica nueva por carril y quedo subiendo `20251010_200605.mp4` hacia `2026-04-12T22:45:00Z`.

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

## Sesion 8 - Meta Uploader, corrida normal de 15 minutos con segundo agente (Codex, 2026-04-08)

- El usuario pidio lanzar un segundo agente, no para prueba sino para una subida normal de `15 minutos`.
- Antes de arrancar se detecto y detuvo un `python.exe` huerfano que seguia ejecutando `meta_uploader/second_pass/local_clip_optimizer.py`; no correspondia al carril de publicacion real.
- Se eligio como runner operativo `meta_uploader/test_batch_upload.py --source posts --start-index 1 --limit 50`, con `META_ENABLE_UPLOAD=1`, para evitar volver a tocar el primer asset ya usado varias veces en las sondas.
- La corrida normal si arranco y avanzo sobre varios videos de `meta_uploader/pendientes_posts.json`. Durante la ventana operativa quedaron registrados al menos los assets `20260310_185649.mp4`, `20260201_191557.mp4`, `20260310_190454.mp4`, `20260310_183619.mp4`, `20260302_190317.mp4` y el arranque de `20260310_181709.mp4`.
- No aparecio ningun ID nuevo confirmado por Meta durante esta ventana. El batch siguio vivo a pesar de los fallos individuales.
- El patron de error fue mixto: se repitio `ConnectionResetError(10054)` en `rupload.facebook.com/video-upload/...`, aparecio un `NameResolutionError` contra `graph.facebook.com`, se reportaron `OSError(22, Invalid argument)` desde el segundo agente y el watchdog marco al menos un estancamiento real con degradacion fuerte de conectividad (`internet timed out`, `getaddrinfo failed`).
- Al cerrar la ventana de `15 minutos`, el segundo agente reporto que la ejecucion habia quedado sin publicaciones nuevas confirmadas y detuvo el proceso huerfano para no dejar una subida fantasma corriendo.

## Sesion 9 - Meta Uploader, tarea formal para manana sobre resiliencia de Facebook Post (Codex, 2026-04-08)

- Se aterrizo la estrategia tecnica para resolver los fallos mixtos del carril `Facebook Post` sin mezclarla con el segundo procesamiento de clipping.
- Se documento como tarea formal `meta_uploader/docs/TODO_FB_POST_RESILIENCE.md`.
- La estrategia quedo separada en fases: hardening HTTP, upload resumible real `start/transfer/finish`, persistencia local de reanudacion, watchdog accionable, runner conservador y trazabilidad especifica para `OSError(22)`.
- Tambien se actualizo `meta_uploader/docs/HANDOVER.md` para marcar este frente como bloqueo operativo real de la siguiente ronda.

## Sesion 10 - Meta Uploader, primera pasada de resiliencia y doble ejecucion paralela (Codex, 2026-04-08)

- El usuario pidio trabajar en paralelo con otros dos agentes: uno para la jornada 1 de videos crudos y otro para la jornada 2 de optimizacion local sin publicar.
- Se lanzaron ambos agentes en paralelo:
  - jornada 1: `test_batch_upload.py --source posts --start-index 1 --limit 50`
  - jornada 2: `second_pass/local_clip_optimizer.py --input-dir "C:\Users\ZN-\Documents\ADM\Carpeta 1" --limit 3 --render-top 1 --emit-queues --presets shared_reel instagram_story feed_teaser_square`
- Mientras corria esa dupla, se implemento una primera pasada de endurecimiento en `meta_uploader.py`:
  - retries clasificados en `_request_json(...)`
  - retries clasificados en `_post_binary(...)`
  - estado operativo expuesto por `get_last_operation_status()`
- Se endurecio tambien `test_batch_upload.py` para que reintente el mismo asset cuando el fallo sea transitorio y pueda pausar el batch en lugar de consumir la cola completa a ciegas.
- Validacion local: `python -m py_compile meta_uploader.py test_batch_upload.py` paso sin errores.
- Durante esta sesion, la jornada 1 si quedo viva como proceso Python activo; la jornada 2 tambien quedo viva y se confirmo que al menos estaba ejecutando `ffmpeg.exe` como hijo del optimizador, aunque todavia no habia dejado artefactos visibles en `second_pass/`.

## Sesion 11 - Meta Uploader, runner normal unificado de jornada 1 (Codex, 2026-04-08)

- El usuario pidio dejar atras los scripts de prueba y construir un runner normal de jornada 1 para videos crudos, manteniendo la jornada 2 separada y sin tocar originales.
- Se creo `meta_uploader/run_jornada1_normal.py` como carril operativo nuevo.
- El runner genera `meta_calendar.json` como calendario local por dias, usando las colas crudas ya ordenadas por peso (`pendientes_reels.json` y `pendientes_posts.json`).
- La logica quedo asi:
  - reel-safe -> `FB Reel + IG Reel`
  - no reel-safe -> `FB Post + IG Feed`
  - `IG Story` solo como intento best-effort cuando el asset vertical del dia cumple una politica conservadora (`<=60s`)
  - `Facebook Stories` se registra como `skipped_unsupported`
- Dentro de cada dia, el runner ejecuta primero el asset mas pesado disponible.
- Si falla la dupla principal FB+IG de un asset, pausa la jornada para no quemar cola.
- Validacion local completada:
  - `python -m py_compile meta_uploader.py test_batch_upload.py run_jornada1_normal.py`
  - `python run_jornada1_normal.py --days 2 --post-start-index 4 --plan-only` con `META_ENABLE_UPLOAD=1`
- La generacion de `meta_calendar.json` confirmo que para `2026-04-08` y `2026-04-09` la cola activa seguia entrando por `20260310_183619.mp4` y `20260302_190317.mp4`.
- No se hizo todavia el corte en vivo al nuevo runner porque seguia corriendo una transferencia real de `Facebook Post` sobre `20260310_183619.mp4` con el runner legacy (`test_batch_upload.py`), y detenerla en ese punto habria descartado cientos de MB ya confirmados por Meta.

## Sesion 12 - Meta Uploader, transicion automatica al runner normal (Codex, 2026-04-08)

- El usuario ordeno arrancar ya con las reglas del runner unificado de jornada 1:
  - reel-safe -> `FB Reel + IG Reel`
  - no reel-safe -> `FB Post + IG Feed`
  - `IG Story` solo como intento best-effort si el reel del dia es vertical y `<=60s`
  - `Facebook Stories` como salto explicito por soporte no versionado
- En lugar de cortar la subida cruda ya en curso, se preservo el progreso confirmado del proceso legacy `PID 26508`, que para ese momento ya llevaba mas de `600 MB` transferidos del asset `20260310_183619.mp4`.
- Se lanzo un proceso de espera (`PID 26304`) que monitoriza la salida del runner legacy y, apenas termine, arrancara automaticamente `run_jornada1_normal.py` con `META_ENABLE_UPLOAD=1`.
- El arranque diferido del runner nuevo quedo configurado desde `post-start-index=5`, para continuar en `20260302_190317.mp4` y no volver a reintentar desde cero el asset que ya estaba transfiriendo el carril legacy.
- En ese momento `pendientes_reels.json` seguia vacio, por lo que el runner nuevo comenzara de hecho por el carril `FB Post + IG Feed` hasta que existan assets reel-safe en la cola cruda.

## Sesion 13 - Meta Uploader, segunda jornada para encajar crudos en reels/stories (Codex, 2026-04-08)

- El usuario pidio verificar si la segunda jornada podia "hacer encajar" el material crudo para cumplir las reglas de `FB Reel + IG Reel` e `IG Story`, y alimentar `pendientes_reels.json` sin tocar la jornada 1.
- Se confirmo que ya existia una base reutilizable en `meta_uploader/second_pass/local_clip_optimizer.py`, con presets `shared_reel` e `instagram_story`.
- Se detecto un hueco operativo importante: al procesar varios videos, las colas de `second_pass/queues/` se sobrescribian por video. Ese comportamiento se corrigio para que ahora acumulen derivados y los ordenen por peso.
- Se agrego `meta_uploader/second_pass/prepare_second_jornada_meta.py`, que:
  - lee `pendientes_posts.json` y/o `pendientes_reels.json`
  - toma los assets mas pesados
  - renderiza derivados `shared_reel` e `instagram_story`
  - deja resumen en `second_pass/manifests/second_jornada_meta_prepare_summary.json`
  - puede fusionar esos derivados dentro de `pendientes_reels.json` solo con `--sync-main-reels-queue`
- Validacion local:
  - `python -m py_compile meta_uploader/second_pass/local_clip_optimizer.py meta_uploader/second_pass/prepare_second_jornada_meta.py`
  - corrida real sobre dos clips pequenos locales (`opt_20260310_184517.mp4` y `probe_vertical_20260310_184517.mp4`)
  - resultado: `second_pass/queues/pendientes_reels_second_pass.json` y `second_pass/queues/pendientes_ig_stories_second_pass.json` quedaron acumulando correctamente dos derivados cada una
- Con esto quedo lista la pieza que faltaba para la segunda jornada: transformar material crudo en assets reel/story-safe sin tocar originales ni contaminar la cola principal hasta que el operador lo autorice.

## Sesion 14 - Meta Uploader, laboratorio YOLO separado (Codex, 2026-04-08)

- El usuario pidio tomar la idea de `performatic_engine` sobre reencuadre inteligente tipo YOLO, pero dejarla aparte como herramienta de prueba antes de integrarla al codigo real.
- Se creo `meta_uploader/second_pass/experimental_yolo_reframer.py`.
- Esta herramienta:
  - recibe un video y un segmento puntual
  - calcula un plan de crop 9:16 guiado por deteccion de personas
  - puede renderizar un clip experimental separado
  - guarda todo en `second_pass/outputs/yolo_reframe_experiments/`
  - no toca colas ni runners productivos
- Tambien se agrego `meta_uploader/second_pass/EXPERIMENTAL_YOLO.md` para documentar su uso y limites.
- Validacion local completada:
  - `python -m py_compile meta_uploader/second_pass/experimental_yolo_reframer.py`
  - `python meta_uploader/second_pass/experimental_yolo_reframer.py --help`
  - chequeo de dependencias: `cv2` si esta presente; `ultralytics` no esta instalado en este entorno, por lo que no se ejecuto una prueba YOLO completa todavia
- Con esto quedo listo el laboratorio aislado para pruebas manuales, sin contaminar la segunda jornada estable ni la jornada 1.

## Sesion 15 - Meta Uploader, instalacion local de ultralytics y primera corrida YOLO (Codex, 2026-04-08)

- El usuario pidio instalar `ultralytics` para poder correr una prueba YOLO real en esta maquina.
- Se instalo `ultralytics 8.4.35` en el Python activo (`3.14.3`), junto con sus dependencias resueltas por `pip`.
- Quedaron verificados estos imports:
  - `ultralytics 8.4.35`
  - `torch 2.11.0+cpu`
  - `torchvision 0.26.0+cpu`
- Se ejecuto una prueba real del laboratorio YOLO sobre `meta_uploader/optimized_videos/probe_vertical_20260310_184517.mp4`.
- Resultado de la prueba:
  - plan experimental guardado en `second_pass/outputs/yolo_reframe_experiments/plans/`
  - `30/30` detecciones en una corrida de `5s`
  - `18/18` detecciones en una corrida posterior de `3s`
  - tasa de deteccion observada: `1.0`
- El modelo descargado `yolov8n.pt` se movio fuera de la raiz del repo hacia `second_pass/outputs/yolo_reframe_experiments/models/` para no dejar un binario suelto en el workspace versionado.

## Sesion 16 - Meta Uploader, optimizacion de velocidad para chunks de Facebook (Codex, 2026-04-08)

- El usuario reporto que la transferencia por chunks seguia siendo demasiado lenta y pidio acelerarla.
- Se midio el caso real de `20260310_183619.mp4`:
  - tamano total `2,614,367,574 bytes`
  - progreso observado `610,271,232 bytes`
  - velocidad efectiva promedio `0.074 MB/s` (`0.594 Mbps`)
  - con chunk de `1 MB`, ese archivo implicaba unas `2,493` requests multipart separadas
- Se concluyo que el cuello de botella no era solo el wifi, sino el overhead de miles de requests chicas, cada una con su confirmacion secuencial del lado de Meta.
- Se optimizo `meta_uploader.py` asi:
  - `requests.Session()` persistente por hilo para reutilizar conexiones HTTP/TLS
  - `META_FB_UPLOAD_CHUNK_BYTES` subido a `8 MB` por defecto
  - `META_FB_UPLOAD_MIN_CHUNK_BYTES` dejado en `1 MB` como piso de seguridad
  - el transfer ahora reduce el chunk automaticamente si el ultimo fallo fue transitorio
  - si la transferencia vuelve a estabilizarse, el chunk puede subir otra vez hasta el objetivo
  - el log ahora reporta tiempo por chunk y `MB/s` efectivos
- Validacion local: `python -m py_compile meta_uploader.py run_jornada1_normal.py test_batch_upload.py`
- El proceso que ya estaba corriendo (`PID 26508`) no absorbio este cambio automaticamente; para beneficiarse de esta optimizacion necesitara reiniciarse con el codigo nuevo.

## Sesion 17 - Meta Uploader, logs separados por plataforma (Codex, 2026-04-08)

- El usuario detecto que el log maestro estaba dominado por las trazas de `Facebook transfer`, lo que hacia dificil ver si Instagram estaba avanzando o no.
- Se actualizo `meta_uploader.py` para mantener el log maestro `meta_uploader.log` y, en paralelo, escribir dos logs locales derivados:
  - `meta_uploader_facebook.log`
  - `meta_uploader_instagram.log`
- La separacion se hace por filtros de palabras clave sobre el mismo stream de logging, sin romper compatibilidad con el log historico ni con los scripts existentes.
- Con esto queda mucho mas facil seguir hoy mismo:
  - progreso de transfer/polling de Facebook
  - creacion de contenedores, polling y `media_publish` de Instagram

## Sesion 18 - Meta Uploader, ajuste de caption operativo (Codex, 2026-04-08)

- El usuario pidio que el prefijo del caption del runner normal dejara de decir `Jornada 1 post` y pasara a usar `PW`.
- Se actualizo `run_jornada1_normal.py` para que el caption operativo quede como:
  - `PW | FECHA | NOMBRE_ORIGINAL`
- Se mantiene intacto el resto del formato:
  - fecha del dia operativo
  - nombre original derivado del stem del archivo

## Sesion 19 - Meta Uploader, preflight oficial para Instagram en jornada 1 (Codex, 2026-04-08)

- Despues de que `20260310_183619.mp4` publicara en Facebook pero fallara en Instagram con `ProcessingFailedError`, se contrasto el asset crudo contra las especificaciones oficiales del flujo `REELS`/`share_to_feed`.
- El hallazgo clave fue que el archivo crudo no es apto para Instagram en jornada 1:
  - tamano `2.61 GB` (muy por encima del maximo oficial de `300 MB`)
  - `3840x2160` (sobre el maximo oficial de `1920` columnas)
  - bitrate de video `~143.96 Mbps` (sobre el maximo oficial de `25 Mbps`)
- Se actualizo `run_jornada1_normal.py` para hacer preflight local de IG antes de intentar `instagram_feed`, `instagram_reel` o `instagram_story`.
- Si el crudo no cumple specs oficiales, el runner:
  - omite el upload a Instagram en jornada 1
  - registra la razon exacta
  - marca el asset como pendiente de segunda jornada
  - permite que Facebook siga sin pausar la jornada por un fallo inevitable de IG

## Sesion 20 - Meta Uploader, transcodificador full-length API-safe para Instagram (Codex, 2026-04-08)

- El usuario pidio resolver el caso en que Instagram movil acepta videos crudos grandes pero la API publica no, y pregunto si era posible generar una version compatible con la maxima calidad posible.
- Se implemento `meta_uploader/second_pass/transcode_instagram_api_safe.py`.
- La herramienta:
  - trabaja sobre el video completo, no sobre un clip corto
  - reescala preservando aspect ratio hasta un maximo de `1920` columnas
  - transcodifica a `H.264 + AAC`
  - calcula bitrate objetivo segun la duracion para entrar bajo un presupuesto seguro de archivo
  - usa `two-pass` para apurar calidad sin pasarse del limite
  - deja manifest propio y cola separada `second_pass/queues/pendientes_ig_feed_second_pass.json`
- Con esto queda lista la solucion correcta de segunda jornada para crudos que Facebook si acepta pero Instagram API rechaza por specs.

## Sesion 21 - Meta Uploader, deduplicacion remota y regla real de 1 publicacion por dia (Codex, 2026-04-08)

- El usuario detecto que `20260310_183619.mp4` aparecia dos veces y ademas reclamo que el runner estaba publicando varios dias del calendario en una sola noche.
- Se verifico por API que el duplicado era real en Facebook:
  - `1882074735828642` con descripcion `Jornada 1 post | 2026-04-08 | 20260310_183619`
  - `2143750206382044` con descripcion `PW | 2026-04-11 | 20260310_183619`
- La causa funcional encontrada fue doble:
  - el runner usaba `fecha` solo como plan/caption, no como barrera de ejecucion real
  - tras caidas/reintentos, el calendario local no alcanzaba para impedir una republicacion si Meta ya habia aceptado un asset en un intento anterior
- Se corrigio `meta_uploader.py` para consultar remotamente Facebook e Instagram antes de subir:
  - nuevos helpers para inspeccionar `/{page}/videos` y `/{ig-user}/media`
  - si el stem del archivo ya aparece remoto, el runner registra `already_exists_remote` y no vuelve a publicar ese asset
- Se corrigio `run_jornada1_normal.py` para respetar la regla operativa:
  - `--days` sigue planificando varios dias
  - la corrida viva ahora ejecuta como maximo `1` dia real por defecto (`--max-live-days=1`)
  - si el siguiente `fecha` del calendario todavia es futuro, la corrida se detiene
- Se corrigio `run_jornada1_supervisor.py` para no relanzar el runner cuando el siguiente dia pendiente aun no corresponde frente a la fecha real.
- Validaciones hechas:
  - `python -m py_compile meta_uploader.py run_jornada1_normal.py run_jornada1_supervisor.py`
  - `run_jornada1_supervisor.py --days 7` ahora corta con mensaje explicito al ver `2026-04-13` como siguiente dia pendiente futuro
  - `run_platform_pair(...)` sobre `20260310_183619.mp4` devuelve `already_exists_remote` en Facebook en lugar de disparar otra subida

## Sesion 22 - Meta Uploader, agenda programada por fecha para Facebook e Instagram (Codex, 2026-04-08)

- El usuario aclaro que no queria publicar todo el mismo dia, sino cargar y programar cada asset para que salga en su dia calendario.
- Tambien aclaro la regla operativa:
  - por dia debe existir `1` publicacion de cada tipo soportado en Facebook
  - por dia debe existir `1` publicacion de cada tipo soportado en Instagram
- Se reviso el patron usado en `youtube_uploader` y se adapto el flujo de Meta a agenda:
  - se creo `meta_uploader/schedule_jornada1_meta.py` para construir el calendario y programar por fecha
  - se creo `meta_uploader/publish_due_meta.py` para publicar los items locales de Instagram cuando llegue su hora
- El nuevo flujo aplica guardas remotas antes de programar:
  - si Facebook o Instagram ya tienen un asset con el stem del archivo, se marca `already_exists_remote`
  - eso evita reprogramar duplicados como `20260310_183619.mp4`
- Para Facebook se habilito confirmacion de estado programado en `meta_uploader.py`, aceptando `scheduled` como resultado exitoso del flujo de subida.
- Para Instagram jornada 1 se mantuvo la restriccion oficial de specs:
  - los crudos grandes siguen marcandose como `skipped_requires_second_jornada`
  - la programacion local queda separada del flujo de segunda pasada/transcodificacion

## Sesion 23 - Meta Uploader, diagnostico de atasco en la agenda de 2026-04-13 (Codex, 2026-04-08)

- Ante la duda de si algun video habia quedado colgado, se revisaron proceso, log y calendario operativo.
- Hallazgo principal:
  - el proceso `schedule_jornada1_meta.py --days 7 --rebuild-plan` siguio abierto
  - pero el calendario quedo detenido en `20260310_181709.mp4` para la fecha `2026-04-13`
- Evidencia:
  - `meta_calendar.json` no se movio despues de `2026-04-08 21:37:50`
  - el ultimo punto activo del calendario quedo como `summary.status = scheduling`, `active_filename = 20260310_181709.mp4`
  - `meta_uploader.log` registro un fallo previo de subida binaria y luego un `HTTP 500` en la consulta de videos de Facebook usada por la guarda remota
- Verificacion remota:
  - se consulto Facebook por el marcador `20260310_181709`
  - no aparecio ningun video existente, asi que el archivo no quedo programado ni duplicado en remoto
- Conclusion operativa:
  - el asset colgado es `20260310_181709.mp4`
  - el problema actual parece ser un atasco del proceso durante la verificacion remota/reintentos, no un duplicado ya creado en Meta

## Sesion 24 - Meta Uploader, correccion de carga de datos y reanudacion de la agenda (Codex, 2026-04-08)

- Despues del diagnostico, el calendario termino registrando el error exacto al intentar programar `20260310_181709.mp4`:
  - `HTTP 500`
  - mensaje de Meta: `Please reduce the amount of data you're asking for, then retry your request`
- Se ajusto la deduplicacion remota para pedir menos informacion y menos volumen por pagina:
  - `find_existing_facebook_video_by_caption_marker(...)` paso a consultar menos campos y a usar defaults mas chicos
  - `find_existing_instagram_media_by_caption_marker(...)` tambien quedo reducido
  - `schedule_jornada1_meta.py` ahora llama esas guardas con `page_size` y `max_pages` mas conservadores y deja trazas explicitas del chequeo remoto
- Luego se recompilo:
  - `meta_uploader.py`
  - `schedule_jornada1_meta.py`
- Se relanzo `schedule_jornada1_meta.py --days 7 --rebuild-plan`.
- Validacion de reanudacion:
  - el nuevo proceso avanzo otra vez hasta `20260310_181709.mp4`
  - la salida directa del scheduler mostro progreso real de `Subiendo FB handle`
  - se confirmo avance continuo, pasando aproximadamente de `11.4%` a `14.0%`
- Estado operativo al cierre de esta sesion:
  - la agenda ya no esta pegada en la consulta remota
  - `20260310_181709.mp4` sigue en transferencia hacia Facebook para quedar programado en `2026-04-13`

## Sesion 25 - Meta Uploader, supervisor dedicado para la agenda programada (Codex, 2026-04-08)

- El usuario pidio reanudar Meta y remarco que no debia quedarse parado si aparecian cortes transitorios.
- Se verifico que el supervisor existente solo cubria `run_jornada1_normal.py`, no el flujo nuevo de agenda `schedule_jornada1_meta.py`.
- Se creo `meta_uploader/schedule_jornada1_supervisor.py`.
- El nuevo supervisor:
  - relanza `schedule_jornada1_meta.py` cuando el proceso termina antes de completar la agenda
  - inspecciona `meta_calendar.json`
  - si detecta `paused_on_failure` con error `transient`, resetea ese mismo lane a `pending`
  - conserva contador local de reintentos por lane (`supervisor_retry_count`)
  - vuelve a intentar el mismo asset en vez de dejar la agenda detenida
  - arranca al hijo con reintentos HTTP/binarios mas altos
- En la reanudacion viva:
  - el supervisor detecto el fallo transitorio de `20260310_181709.mp4`
  - lo reseteo a `pending` con `supervisor_retry_count = 1`
  - relanzo `schedule_jornada1_meta.py`
  - se confirmo progreso real otra vez en `Subiendo FB handle`, alrededor de `5.4%` al ultimo corte observado
- Con esto ya queda una capa de autorecuperacion para la agenda programada, sin tocar `youtube_uploader`.

## Sesion 26 - Meta Uploader, reanudacion confirmada de la primera jornada (Codex, 2026-04-09)

- El usuario pidio volver a subir videos con la primera jornada.
- Se reviso el estado real antes de reiniciar para no romper una transferencia viva.
- Hallazgo:
  - `schedule_jornada1_supervisor.py` seguia activo
  - `schedule_jornada1_meta.py` tambien seguia activo
  - el calendario continuaba en `20260310_181709.mp4` para `2026-04-13`
- Se verifico el progreso real por `schedule_jornada1_supervisor_stdout.log`:
  - el archivo estaba creciendo en tiempo real
  - la subida de `Facebook handle` avanzaba, pasando de alrededor de `30.4%` a `40.8%`
- Decision operativa:
  - no se relanzo el proceso a ciegas
  - se dejo la primera jornada corriendo sobre el supervisor ya activo
  - no se toco `youtube_uploader`

## Sesion 27 - Meta Uploader, conteo acumulado real desde el reinicio del 2026-04-09 (Codex, 2026-04-09)

- El usuario pidio revisar cuantos videos iban acumulados desde el reinicio de hoy.
- Se cruzaron dos fuentes:
  - `meta_calendar.json`
  - consulta real por API a Facebook e Instagram para publicaciones creadas en fecha local `2026-04-09` (Bogota)
- Resultado:
  - el calendario si avanzo y dejo `5` dias marcados como `scheduled` / `scheduled_with_ig_skip` con `last_updated_at` de hoy
  - ese avance fue por deduplicacion remota (`already_exists_remote`) y no por publicaciones nuevas creadas hoy
  - la API devolvio `0` publicaciones nuevas en Facebook hoy
  - la API devolvio `0` publicaciones nuevas en Instagram hoy
- Estado del video en curso al momento del corte:
  - `20260310_181709.mp4`
  - sigue en transferencia por `Facebook handle`
  - progreso observado alrededor de `32.9%`

## Sesion 28 - Meta Uploader, relanzamiento con flujo chunked programado y menos overhead (Codex, 2026-04-09)

- El usuario detecto dos problemas:
  - el porcentaje visible bajaba entre intentos
  - la subida de Meta estaba demasiado lenta
- Diagnostico:
  - el porcentaje bajaba porque el carril `Facebook handle` reiniciaba desde `0` tras cortes transitorios
  - ademas estaba imprimiendo progreso demasiado frecuente, generando mucho overhead en `stdout`
- Se corrigio el flujo:
  - `schedule_jornada1_meta.py` paso a preferir `upload_fb_video_standard(..., scheduled_publish_time=...)` para `facebook_post`
  - ese carril usa upload resumible por chunks y checkpoints locales
  - `meta_uploader.py` quedo ajustado para aceptar `scheduled_publish_time` tambien en el finish del carril chunked
  - se redujo la frecuencia de logs de progreso para no ahogar el proceso
  - `run_jornada1_normal.py` tambien se endurecio para conservar la fecha asignada del mismo asset entre reinicios del calendario
- Luego se relanzo `schedule_jornada1_supervisor.py` con el codigo nuevo.
- Validacion viva:
  - el nuevo hijo ya no muestra `Subiendo FB handle`
  - en su lugar reporta chunks como `Subiendo FB 704643072-721420288: 100.0%`
  - eso confirma que la primera jornada quedo corriendo con el flujo chunked programado y chunks de `16 MB`

## Sesion 29 - Meta Uploader, verificacion final de la primera jornada programada (Codex, 2026-04-09)

- Se reviso si el flujo nuevo seguia usando las mejoras aplicadas y si aun habia videos pendientes por programar.
- Evidencia del flujo correcto:
  - `schedule_jornada1_supervisor_stdout.log` ya no mostraba `Subiendo FB handle`
  - el log mostraba chunks `Subiendo FB ...` de `16 MB`, confirmando el carril chunked/resumible
- Cierre confirmado del ultimo asset:
  - `20260310_185221.mp4`
  - Meta confirmo el video `1462148335366242` como programado para `2026-04-15T17:00:00+0000`
  - en horario Bogota eso corresponde a `2026-04-15 12:00:00 -05:00`
- `meta_calendar.json` quedo con `PENDING 0`, es decir, sin dias pendientes en la tanda actual de primera jornada.
- Conclusion operativa:
  - las mejoras si quedaron aplicadas
  - la programacion actual de primera jornada quedo completa

## Sesion 30 - Monitor de logs en tiempo real para Meta y YouTube (Codex, 2026-04-09)

- El usuario pidio una herramienta de consola para monitorear en paralelo:
  - Meta Facebook
  - Meta Instagram
  - YouTube
- Objetivo funcional:
  - mostrar cuantos videos se subieron hoy por herramienta
  - mostrar el video actual y el porcentaje en curso
  - mostrar bytes absolutos cuando el log los expone
  - mostrar hace cuanto no se completa una subida
- Se implemento `scripts/monitor_realtime.py` como lector de logs de solo
  lectura, mas `scripts/monitor_realtime.bat` como lanzador rapido.
- Se documentaron las reglas de mantenimiento para futuras IAs:
  - si cambian los formatos de salida de Meta o YouTube, tambien deben
    actualizar el monitor para que no quede desfasado.

## Sesion 31 - Integracion final del monitor y relanzamiento real de Meta (Codex, 2026-04-09)

- Se detecto que el scheduler nuevo de Meta no estaba fallando por logica sino por entorno:
  - dentro del sandbox no podia leer bien la carpeta `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente`
  - tampoco podia abrir sockets a Graph API, devolviendo `WinError 10013`
- Se relanzo `meta_uploader` fuera del sandbox con el Python correcto del proyecto:
  - `C:\Users\ZN-\Documents\Antigravity\.venv\Scripts\python.exe`
  - launcher: `schedule_jornada1_supervisor.py`
- Resultado operativo confirmado:
  - `meta_calendar.json` paso de `7` a `33` dias
  - quedaron `7` ya programados y `26` pendientes
  - la nueva tanda arranco sobre `20260310_192005.mp4`
  - el flujo activo confirmado sigue siendo el chunked de Facebook
- Se ajusto el monitor en `scripts/monitor_realtime.py` para que:
  - refresque tambien `meta_calendar.json` y `scanned_videos.json` en cada ciclo
  - muestre el nombre real del archivo actual de YouTube
  - estime bytes absolutos de YouTube aunque no pueda leer el video directo, usando `scanned_videos.json`
  - no mezcle errores de Facebook dentro del panel de Instagram
- Validacion del monitor:
  - `--once` ya muestra `Meta Facebook`, `Meta Instagram` y `YouTube`
  - reporta porcentaje, bytes, subidos hoy y tiempo desde la ultima subida exitosa
- Se dejo lanzador listo para el usuario:
  - repo: `scripts/monitor_realtime.bat`
  - Escritorio: `C:\Users\ZN-\Desktop\MONITOR_LOGS_REDES.bat`

## Sesion 32 - Eliminacion del parpadeo en el monitor de terminal (Codex, 2026-04-09)

- El usuario reporto molestia por el parpadeo del monitor en consola.
- Se hizo una verificacion externa breve y se confirmo la recomendacion de
  Microsoft Learn para Windows Console:
  - habilitar `ENABLE_VIRTUAL_TERMINAL_PROCESSING`
  - usar secuencias VT para mover el cursor y redibujar, en vez de invocar
    `cls` en cada refresco
- Se ajusto `scripts/monitor_realtime.py` para:
  - habilitar VT en Windows cuando la terminal lo soporta
  - ocultar temporalmente el cursor mientras el monitor esta vivo
  - reposicionar el cursor al inicio y reescribir el panel en sitio
  - conservar `cls` solo como fallback si VT no esta disponible
- Impacto:
  - el monitor deja de limpiar toda la pantalla en cada ciclo
  - se reduce el parpadeo visible en PowerShell / Windows Terminal

## Sesion 33 - Revision operativa de Meta y relanzamiento de YouTube (Codex, 2026-04-10)

- El usuario pidio:
  - ubicar el archivo que programa publicaciones futuras en Meta
  - identificar de donde salen las rutas de la carpeta fuente
  - contar cuantas publicaciones quedaron programadas el 2026-04-09
  - relanzar `youtube_uploader`
- Se verifico el flujo de Meta:
  - el scheduler de fechas futuras sigue siendo `schedule_jornada1_meta.py`
  - las fechas programadas se construyen con `build_slot_payload(...)`
  - las rutas fuente no estan hardcodeadas en el scheduler; llegan desde `pendientes_posts.json` / `pendientes_reels.json`, que a su vez nacen del clasificador ejecutado con una carpeta objetivo
- Hallazgo de Meta del 2026-04-09:
  - hubo `28` confirmaciones de Facebook como programado
  - equivalen a `25` archivos unicos, porque `20260310_181709.mp4` y `20260310_185221.mp4` tuvieron reintentos duplicados
  - la tanda unica efectiva quedo programada desde `2026-04-14` hasta `2026-05-08`
- Se relanzo `youtube_uploader` el 2026-04-10:
  - proceso `uploader.py` activo otra vez
  - ultimo arranque confirmado en `uploader.log` a las `09:37:18` hora Bogota
  - archivo en curso: `20260201_200546.mp4`
  - progreso verificado en log: al menos `61%` al ultimo corte revisado

## Sesion 34 - Limpieza local de archivos ya programados en Meta (Codex, 2026-04-10)

- El usuario pidio despejar `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente`
  de los archivos que ya quedaron programados en Facebook para fechas futuras.
- Se creo la carpeta destino:
  - `C:\Users\ZN-\Documents\ADM\Carpeta 1\ya_subidos_meta`
- Se movieron `25` archivos ya programados en Meta desde:
  - `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente`
  hacia:
  - `C:\Users\ZN-\Documents\ADM\Carpeta 1\ya_subidos_meta`
- Validacion:
  - `25` movidos
  - `0` faltantes del listado solicitado por el usuario

## Sesion 35 - Verificacion de 5 archivos ya despejados de la fuente Meta (Codex, 2026-04-10)

- El usuario pidio quitar tambien `5` archivos adicionales que ya habian sido
  detectados anteriormente como existentes en remoto para Meta.
- Se verifico su ubicacion actual:
  - `20260310_185649.mp4`
  - `20260201_191557.mp4`
  - `20260310_190454.mp4`
  - `20260310_183619.mp4`
  - `20260302_190317.mp4`
- Resultado:
  - ya no estaban en `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente`
  - ya estaban resguardados en `C:\Users\ZN-\Documents\ADM\Carpeta 1\ya_subidos_fb_ig`
- Verificacion operativa:
  - tambien quedaron fuera de `pendientes_posts.json`
  - tambien quedaron fuera de `pendientes_reels.json`
  - tampoco siguen como pendientes en `meta_calendar.json`
- Conclusion:
  - no hacia falta mover nada adicional para despejar la carpeta fuente de Meta
  - se conservaron en `ya_subidos_fb_ig` para no perder la distincion de que ya
    estaban identificados como subidos en Facebook e Instagram

## Sesion 36 - Unificacion de la convención operativa de Meta (Codex, 2026-04-10)

- El usuario pidio que la frase `sube videos a Meta` apuntara al flujo
  programado vigente de Meta y que lo que antes se llamaba `segunda jornada`
  pasara a nombrarse `videos optimizados`.
- Se actualizo la documentacion de `meta_uploader/` y `docs/` para dejar como
  entrypoint humano recomendado `schedule_jornada1_supervisor.py`.
- Se dejo una nota local en la carpeta de videos fuente:
  - `C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente\NOTA_META_FLUJO_DIARIO.txt`
- La nota aclara:
  - `run_jornada1_normal.py` construye/rehidrata el calendario
  - `meta_uploader.py` es la capa de subida de bajo nivel
  - `second_pass/` sigue existiendo tecnicamente, pero la documentacion ya usa
    `videos optimizados`

## Sesion 33 - Correccion del flooding del monitor (Codex, 2026-04-09)

- El usuario reporto flooding despues del cambio a VT sequences.
- Causa probable confirmada:
  - lineas muy largas de errores y avisos estaban haciendo wrap en la terminal
  - eso generaba scroll molesto aunque el monitor redibujara en sitio
- Se corrigio `scripts/monitor_realtime.py` para:
  - activar pantalla alterna `ESC[?1049h` y salir con `ESC[?1049l`
  - recortar cada linea al ancho real de la terminal antes de imprimirla
  - limitar la altura total del panel para que no empuje el buffer
- Validacion:
  - `--once` compila y corre
  - ya no deja crecer la consola por textos largos del monitor
- Alcance mantenido:
  - no se toco `meta_uploader` ni `youtube_uploader`

## Sesion 37 - Revision de `youtube_uploader` y `meta_uploader` + tercera plataforma candidata (Codex, 2026-04-13)

- Registro agregado al historial compartido de Antigravity/Codex/Claude Code.
- El usuario pidio:
  - revisar el repo `agentes`
  - verificar `youtube_uploader` y `meta_uploader`
  - recomendar una tercera plataforma monetizable para replicar el flujo
- Verificacion de `youtube_uploader`:
  - se leyo el contexto local (`AGENTS.md`, `AI.md`, `TODO.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`)
  - `python -m unittest discover -s tests -v` inicialmente fallo en `2` pruebas de cola/calendario
  - la causa fue fragilidad de pruebas por dependencia del reloj real del sistema y de la hora local cargada desde `config.json`
  - se corrigio `uploader.py` para aceptar `now_utc` inyectable en `get_next_publish_date(...)` y `pop_next_pending_video(...)`
  - se corrigio `tests/test_uploader_queue.py` para fijar tiempo/config de prueba
  - resultado final: `16/16` pruebas `OK`
  - `py_compile` de los scripts principales de `youtube_uploader` tambien quedo `OK`
- Verificacion de `meta_uploader`:
  - `py_compile` de los scripts principales quedo `OK`
  - `run_jornada1_normal.py --help` y `schedule_jornada1_supervisor.py --help` respondieron correctamente
  - `test_draft_logic.py` corrio como sonda local sin publicar
  - se confirmo que la mayoria de `test_*.py` en Meta son sondas/manuales con opt-in real (`META_ENABLE_UPLOAD=1`), no suite automatica segura para CI
- Riesgos abiertos detectados en `meta_uploader`:
  - `run_jornada1_normal.py` quedo con ruta absoluta hardcodeada a `C:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader`, lo que rompe portabilidad y contradice la regla documentada de resolver rutas desde el subproyecto
  - `run_jornada1_supervisor.py` ahora reintenta de forma agresiva cuando el calendario queda bloqueado por dia futuro o por pausa, alejandose de la decision documentada de respetar `1 publicacion por dia real`
  - `crosspost_history.json` sigue versionado aunque funciona como estado operativo mutable
- Observaciones de repo:
  - `youtube_uploader/scanned_videos.json` sigue versionado a proposito y es parte del indice operativo del subproyecto
  - las credenciales OAuth de YouTube y `.env` de Meta no aparecen versionadas en Git en esta revision
- Recomendacion de tercera plataforma:
  - recomendacion principal: `TikTok`
  - motivo: hoy ofrece mejor upside de alcance/monetizacion para video corto y existe API oficial de publicacion (`Content Posting API`) compatible con un flujo parecido al carril de clips/verticales
  - condicion importante: la monetizacion fuerte depende del `Creator Rewards Program`, que exige cuenta personal elegible, contenido original de mas de `1 minuto` y disponibilidad por pais/region soportada por TikTok
  - fallback mas simple por API pero con menor upside: `Dailymotion`
