# Investigacion - Clipping, SMO y Segunda Jornada Local

## Tesis operativa

La idea util no es copiar "edicion flashy" por copiarla. Lo transferible de los
equipos de alto rendimiento es esto:

- convertir una pieza larga en multiples unidades cortas
- abrir cada pieza con un hook inmediato
- adaptar encuadre, duracion y empaque a cada plataforma
- medir donde cae la atencion y no solo donde "se ve bonito"

En otras palabras: **no es solo edicion, es empaquetado de atencion**.

## Que se puede traducir a codigo local

De los modelos publicos tipo GaryVee, MrBeast/Clipping y estrategas de
retencion, lo que si se puede automatizar localmente es:

- detectar ventanas con mas cambios de escena
- penalizar silencio y transiciones negras
- renderizar recortes 9:16 o 1:1
- normalizar audio
- quemar subtitulos cuando exista un `.srt`
- generar varias piezas a partir de un solo master

Lo que **no** conviene prometer como automatizable al 100% en esta fase:

- leer ironia, carisma o punchline semantico sin ASR/LLM
- decidir solo con vision si un clip es "viral"
- reemplazar el criterio humano de packaging (copy, titulo, miniatura)

## Patrones de la industria que si importan

### 1. Pilar -> microcontenido

El modelo de GaryVee lo resume muy bien: partir de una pieza "pillar" y
reconvertirla en docenas de piezas cortas para distintas plataformas. Eso es
exactamente lo que esta segunda jornada debe hacer de forma local.

Fuente:
- [GaryVee - How We Created 7 Million Extra Views](https://garyvaynerchuk.com/content-marketing-strategy/)

### 2. Hook temprano y empaque

En el mismo desglose de GaryVee aparecen reglas muy concretas para Instagram:

- hook de `3-5` segundos al inicio
- titulo claro
- CTA de cierre
- subtitulos pensando en consumo sin sonido

Eso vuelve natural una arquitectura de clipping que primero analiza y luego
renderiza ventanas cortas con apertura rapida.

Fuente:
- [GaryVee - How We Created 7 Million Extra Views](https://garyvaynerchuk.com/content-marketing-strategy/)

### 3. Clipping como infraestructura

El caso mas claro de clipping masivo reciente es el de MrBeast y el ecosistema
de Clipping, donde el incentivo economico ya no se da por "editar un video",
sino por fabricar y distribuir muchos fragmentos que compiten por atencion.

Fuentes:
- [Complex - MrBeast Pays Editors $50 Per 100,000 Views When They Clip His Content](https://www.complex.com/pop-culture/a/treyalston/mrbeast-content-pay-clippers-50-100-thousand)
- [GaryVee Content Model deck](https://garyvaynerchuk.com/wp-content/uploads/2018/07/GV-Content-Model-1.pdf)

## Implicaciones tecnicas para este repo

### Jornada 1

- subir el archivo fuente tal como esta
- no tocar el uploader base
- mantener compatibilidad con el flujo actual de Meta

### Jornada 2

- analizar el archivo fuente localmente
- seleccionar ventanas candidatas
- generar nuevos assets clippeados
- emitir colas separadas para reels e IG stories

## Restricciones oficiales de Meta relevantes

### Instagram

La guia oficial de `content publishing` ya contempla:

- videos/reels con `media_type=REELS`
- stories con `media_type=STORIES`
- `upload_type=resumable`

Fuentes:
- [Instagram Content Publishing](https://developers.facebook.com/docs/instagram-api/guides/content-publishing)
- [IG User Media Reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)

### Facebook

La guia oficial de reels para Pages mantiene el subconjunto seguro:

- solo Pages
- reels entre `3` y `90` segundos
- `24-60 FPS`

Fuente:
- [Facebook Reels Publishing](https://developers.facebook.com/docs/video-api/guides/reels-publishing)

Para video estandar de pagina, la publicacion sigue su propio carril y no debe
mezclarse con el carril Reel.

Fuente:
- [Facebook Video Publishing](https://developers.facebook.com/docs/video-api/guides/publishing)

## Herramientas locales que si sirven para esto

FFmpeg ya trae casi todo lo que necesitamos para la segunda jornada:

- `crop` para recorte local
- `cropdetect` para detectar area util o barras
- `silencedetect` para detectar pausas largas
- `blackdetect` para evitar fades/transiciones negras
- `select='gt(scene,0.4)'` para aislar cambios de escena
- `loudnorm` para normalizacion de audio
- `subtitles` para quemar subtitulos si existe sidecar

Fuentes:
- [FFmpeg crop](https://www.ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg cropdetect](https://www.ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg silencedetect](https://www.ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg blackdetect](https://www.ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg loudnorm](https://www.ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg subtitles](https://www.ffmpeg.org/ffmpeg-filters.html)

## Arquitectura recomendada

### Primer carril

- `meta_uploader.py`
- `test_batch_upload.py`
- `test_batch_upload_v2.py`
- sube el material tal cual

### Segundo carril

- `second_pass/local_clip_optimizer.py`
- analiza
- renderiza clips derivados
- guarda manifests
- emite colas separadas de segunda jornada

## Heuristicas utiles para la primera version

Para una primera automatizacion local, la ventana candidata se puede puntuar por:

- densidad de cambios de escena
- baja proporcion de silencio
- ausencia de negro/fade
- entrada temprana al conflicto o accion

Esto no garantiza viralidad, pero si aproxima la idea de **clipping orientado a
retencion** mejor que una simple transcodificacion.
