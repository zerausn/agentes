# Vigia Meta Widget - Revision S24

Fecha de revision: 2026-05-22

## Alcance

Esta revision se hizo sobre la copia real del S24 conectado por `adb` con serial
`RFCX91HV4GD`.

Archivos revisados en el telefono:

- `/data/data/com.termux/files/home/.shortcuts/vigia_meta.sh`
- `/data/data/com.termux/files/home/agentes/scripts/linux/vigia_meta_widget.sh`
- `/data/data/com.termux/files/home/agentes/scripts/linux/vigia_meta_termux.sh`
- `/data/data/com.termux/files/home/agentes/meta_uploader/fb_to_ig_vigia.py`

Verificacion:

- Los tres scripts shell del S24 coinciden byte a byte con el repo local.
- `fb_to_ig_vigia.py` coincide con el repo local despues de normalizar `CRLF`
  vs `LF`, asi que no hay divergencia funcional entre el S24 y el repo.

## Cadena real de ejecucion

1. El widget de Termux ejecuta `~/.shortcuts/vigia_meta.sh`.
2. Ese wrapper deriva a `agentes/scripts/linux/vigia_meta_widget.sh`.
3. El widget abre Debian via `proot-distro`.
4. Dentro de Debian ejecuta `agentes/scripts/linux/vigia_meta_termux.sh`.
5. Ese launcher entra a `meta_uploader/` y corre `fb_to_ig_vigia.py`.
6. `fb_to_ig_vigia.py` descarga el asset desde Facebook, lo vuelve a procesar
   y luego lo publica en Instagram usando Graph API y `rupload`.

## Aclaracion de nombres

Hay dos `vigia_meta.sh` distintos en el repo:

- `termux_widgets/vigia_meta.sh`: es el wrapper que se despliega a
  `~/.shortcuts/vigia_meta.sh` en Android.
- `scripts/linux/vigia_meta.sh`: es un launcher humano para desktop Linux y
  tambien sirve como puente cuando se ejecuta dentro de Termux.

El widget del S24 usa el primero. El segundo no es el atajo de Termux, pero
conviene documentarlo porque apunta al mismo flujo operativo.

## `scripts/linux/vigia_meta.sh` linea por linea

| Linea | Que hace |
| --- | --- |
| 1 | Usa `bash` del sistema como interprete. |
| 2 | Linea en blanco. |
| 3 | Comentario: identifica el script como puente Linux desktop / Termux. |
| 5 | Calcula el directorio real del script y lo guarda en `SCRIPT_DIR`. |
| 7 | Abre un `case` para detectar si el script esta corriendo desde una ruta de Termux. |
| 8 | Patron que coincide con rutas tipicas de `com.termux`. |
| 9 | Marca `IN_TERMUX_SCRIPT_DIR=1` si el script esta dentro de Termux. |
| 10 | Fin del primer brazo del `case`. |
| 11 | Rama por defecto. |
| 12 | Marca `IN_TERMUX_SCRIPT_DIR=0` cuando no esta en Termux. |
| 13 | Fin de la rama por defecto. |
| 14 | Cierra el `case`. |
| 16 | Decide si debe comportarse como launcher Android: entra si detecta Termux por ruta, `PREFIX` o `HOME`. |
| 17 | Construye la ruta a `vigia_meta_widget.sh` en el mismo directorio. |
| 18 | Define la ruta esperada del `bash` de Termux. |
| 20 | Verifica que exista el launcher Android. |
| 21 | Muestra error si falta el launcher. |
| 22 | Sale con error. |
| 23 | Cierra el `if` de existencia del launcher. |
| 25 | Comprueba si el `bash` de Termux tiene permiso de ejecucion. |
| 26 | Si no, busca otro `bash` disponible en `PATH`. |
| 27 | Cierra ese `if`. |
| 29 | Verifica que al final si haya un `bash` usable. |
| 30 | Reporta error si no encontro ninguno. |
| 31 | Sale con error. |
| 32 | Cierra ese `if`. |
| 34 | Comentario: explica que se usa `bash` explicito para no depender del bit ejecutable del repo en Android. |
| 35 | Reemplaza el proceso actual por `bash "$TERMUX_LAUNCHER" "$@"`. |
| 36 | Cierra el `if` grande de entorno Termux. |
| 38 | Imprime borde cyan para el modo desktop. |
| 39 | Imprime el titulo del agente en modo desktop. |
| 40 | Imprime borde inferior. |
| 41 | Imprime una linea en blanco. |
| 43 | Define `BASE_DIR` apuntando al repo local en desktop. |
| 44 | Entra a `meta_uploader` y sale si falla. |
| 46 | Ejecuta `fb_to_ig_vigia.py` con el Python del virtualenv local. |
| 48 | Revisa el codigo de salida del comando anterior. |
| 49 | Imprime una linea vacia si hubo fallo. |
| 50 | Muestra un error visible en rojo. |
| 51 | Espera Enter para que la terminal no se cierre de inmediato. |
| 52 | Cierra el `if` final. |

## `~/.shortcuts/vigia_meta.sh` linea por linea

| Linea | Que hace |
| --- | --- |
| 1 | Usa el `bash` de Termux como interprete. |
| 2 | Activa `set -euo pipefail`: aborta en error, variable no definida o error en pipelines. |
| 3 | Pone primero el `PATH` de Termux y deja acceso a binarios del sistema Android. |
| 4 | Define `TERMUX_HOME` con la ruta fija del home de Termux. |
| 5 | Construye la ruta al launcher real `agentes/scripts/linux/vigia_meta_widget.sh`. |
| 6 | Verifica que ese launcher exista. |
| 7 | Muestra error si falta. |
| 8 | Sugiere correr `0_RENOVAR_REPO` para traer el repo actualizado. |
| 9 | Sale con error. |
| 10 | Cierra el `if`. |
| 11 | Reemplaza el proceso por `bash "$LAUNCHER" "$@"`. |

## `scripts/linux/vigia_meta_widget.sh` linea por linea

| Linea | Que hace |
| --- | --- |
| 1 | Usa el `bash` de Termux. |
| 2 | Activa modo estricto con `set -euo pipefail`. |
| 4 | Exporta un `PATH` minimo y controlado para Termux/Android. |
| 6 | Define `TERMUX_HOME`. |
| 7 | Guarda la ruta de `proot-distro`, que es la puerta de entrada a Debian. |
| 8 | Define el launcher que correra dentro de Debian. |
| 9 | Define el log principal que escribe `fb_to_ig_vigia.py`. |
| 10 | Define un directorio de logs visible desde almacenamiento compartido Android. |
| 11 | Define el log de sesion del widget. |
| 13 | Crea el directorio del log de sesion si no existe. |
| 14 | Redirige stdout y stderr del script a `tee`, para verlos en pantalla y anexarlos al log de sesion. |
| 16 | Imprime el borde superior del banner. |
| 17 | Imprime el titulo visible del widget. |
| 18 | Imprime el borde inferior del banner. |
| 19 | Imprime una linea en blanco. |
| 21 | Verifica que `proot-distro` exista y sea ejecutable. |
| 22 | Muestra error si Debian/`proot` no esta disponible. |
| 23 | Espera Enter para que el usuario vea el error. |
| 24 | Sale con error. |
| 25 | Cierra el `if`. |
| 27 | Verifica que exista el launcher interno `vigia_meta_termux.sh`. |
| 28 | Reporta error si el repo no tiene ese launcher. |
| 29 | Sugiere refrescar repo con `0_RENOVAR_REPO`. |
| 30 | Espera Enter para mantener la ventana abierta. |
| 31 | Sale con error. |
| 32 | Cierra el `if`. |
| 34 | Comentario: explica por que se crea el log antes del `tail -f`. |
| 35 | Crea el directorio padre del log Python si hace falta. |
| 36 | Crea el archivo log vacio si no existe. |
| 38 | Informa que el vigia se lanzara dentro de Debian. |
| 39 | Muestra la ruta del log que se va a seguir. |
| 40 | Linea vacia. |
| 42 | Empieza a construir un comando shell escapado para lanzar el script dentro de Debian. |
| 43 | Revisa si el widget recibio argumentos. |
| 44 | Itera los argumentos recibidos. |
| 45 | Va anexando cada argumento escapado de forma segura a `LAUNCH_CMD`. |
| 46 | Cierra el `for`. |
| 47 | Cierra el `if` de argumentos. |
| 49 | Comentario: resume la estrategia final, lanzar en background y seguir log. |
| 50 | Ejecuta `proot-distro login debian` y abre un shell login dentro de Debian. |
| 51 | Dentro de Debian, garantiza el log, ejecuta el launcher en background y redirige toda su salida al log. |
| 52 | Espera 2 segundos para que el proceso arranque y empiece a escribir. |
| 53 | Sigue el log en vivo con `tail -f`. |

## `scripts/linux/vigia_meta_termux.sh` linea por linea

| Linea | Que hace |
| --- | --- |
| 1 | Usa el `bash` de Termux. |
| 2 | Activa `set -euo pipefail`. |
| 4 | Expande `PATH` para Debian mas Termux y binarios Android. |
| 6 | Define `TERMUX_HOME`. |
| 7 | Define `META_DIR`, la carpeta donde vive `fb_to_ig_vigia.py`. |
| 9 | Hace `cd` a `META_DIR` y sale con error si no puede entrar. |
| 10 | Reemplaza el proceso actual por `/usr/bin/python3 fb_to_ig_vigia.py "$@"`. |

## `fb_to_ig_vigia.py` explicado por secciones

No es el widget visual, pero es el motor real que decide que se descarga, como
se vuelve a codificar y como se publica en Instagram.

### Secciones del archivo

- `1-44`: imports, constantes, patrones regex y configuracion de logging.
- `46-97`: lectura y escritura de historial y registro de deduplicacion.
- `100-171`: normalizacion de texto y calculo de claves canonicas para evitar
  republicar el mismo post.
- `173-210`: extraccion de media desde el post de Facebook.
- `212-414`: loop principal de reconciliacion FB -> IG.
- `416-443`: loop daemonico (`--once`, `--dry-run`, espera 10 minutos o 24h).

### Lineas que mas afectan calidad y publicacion

| Linea | Que hace | Impacto real |
| --- | --- | --- |
| 283 | Construye el caption final sumando firma fija. | No afecta calidad de video, si afecta la deduplicacion y la presentacion. |
| 287-290 | Decide `targets`; imagen va a `FEED`, video arranca como `REELS`. | Para video ya asume el carril Reel moderno de la API. |
| 297 | Log de descarga local. | Marca el inicio del pipeline destructivo. |
| 298 | Crea un archivo temporal local `temp_vigia_<post>_<idx>.mp4`. | El asset se baja a disco antes de subir. |
| 299 | Descarga el binario desde la URL de Facebook con `requests.get(...)`. | Primer cuello de botella de calidad: el vigia no usa el master original, usa el archivo ya servido por Facebook. |
| 301-303 | Escribe a disco el archivo descargado en chunks. | Copia local del asset de Facebook. |
| 305 | Llama `ensure_ig_compatibility(..., force_recode=True)`. | Segundo cuello de botella: reencoda siempre, incluso si el video ya venia compatible. |
| 306-307 | Hace `probe_video()` y lee duracion. | Se usa para decidir recortes posteriores. |
| 309-313 | Si dura mas de 90s agrega un target `FEED`. | Regla heredada que hoy ya es dudosa porque Reels API soporta hasta 15 minutos. |
| 320-324 | Consulta el limite oficial de publicacion antes de seguir. | Bueno para no pasarse del limite de contenedores/API. |
| 329-330 | Si fuera `STORIES`, vuelve a recortar a 60s. | Alineado con Story API, que soporta 60s max. |
| 331-333 | Si es `REELS` y dura mas de 90s, recorta a 90s. | Regla antigua; hoy puede estar degradando contenido innecesariamente. |
| 345 | Para `REELS` crea un contenedor `REELS` con `share_to_feed=True`. | Correcto para la API moderna. |
| 349-350 | Para `FEED` tambien crea `REELS` con `share_to_feed=True`. | Aclara que `FEED` aqui no es otro media type; sigue siendo un Reel compartido al feed. |
| 355 | Espera 2 segundos antes del upload binario. | Mitiga carreras de consistencia del contenedor. |
| 356-358 | Sube binario, espera procesamiento y publica. | Es el tramo final server-side contra Meta. |
| 364-366 | Limpia recortes auxiliares cuando no son el archivo base. | Evita basura temporal. |
| 379-384 | Limpia el archivo optimizado y el temporal descargado. | Cierra el ciclo local. |
| 431-438 | Si hubo rescates reintenta en 10 minutos; si no, duerme 24h. | Es el modo operativo del daemon. |

## Hallazgos de revision

### 1. El mayor limite de calidad no es Instagram: es la fuente

`fb_to_ig_vigia.py` descarga el video desde Facebook (`297-303`) y luego lo
vuelve a codificar (`305`). Eso significa:

1. el master original ya no se usa en esta ruta,
2. el asset ya viene comprimido por Facebook,
3. luego el vigia lo recomprime,
4. luego Instagram vuelve a procesarlo.

En la practica es una cadena de perdida generacional.

## 2. `ensure_ig_compatibility()` recompime siempre, pero no garantiza todos los limites oficiales

En `meta_uploader.py:2082-2166`, cuando `force_recode=True`, el helper:

- usa `libx264`,
- usa `-preset veryfast`,
- usa `-crf 23`,
- solo fuerza dimensiones pares con `scale=trunc(iw/2)*2:trunc(ih/2)*2`,
- no baja explicitamente a `1920px` max,
- no controla explicitamente `23-60 FPS`,
- no controla explicitamente `25 Mbps` max,
- solo aplica `-fs 290M` si el archivo supera `300MB`.

Eso quiere decir que el helper si introduce perdida, pero no es el mejor
garante de compatibilidad API-safe.

## 3. La regla de 90 segundos esta desactualizada para Reels

El vigia recorta Reels a 90 segundos en `331-333`, pero la referencia oficial
de Meta para `media_type=REELS` indica `3 segundos minimo` y `15 minutos
maximo`.

Interpretacion: el recorte a 90s fue razonable en un momento anterior de la
API, pero hoy ya no es una exigencia general del endpoint moderno.

## 4. El repo ya tiene un transcoder mejor para Instagram, pero no estaba listo para Linux

`second_pass/transcode_instagram_api_safe.py` ya modela mejor el problema:

- limita ancho a `1920` (`22`, `80-88`),
- calcula bitrate objetivo segun duracion (`91-97`),
- respeta tope `25 Mbps` (`23`, `221-224`),
- hace `two-pass` con `preset slow` (`115-212`),
- usa `+faststart`,
- deja manifest verificable.

Correcion aplicada en esta revision:

- se cambio la salida del pass 1 de `NUL` a `os.devnull` para que funcione
  tambien en Linux/Debian del S24.

## Limites oficiales relevantes para mejorar calidad sin salirnos de la API

Segun la documentacion oficial de Meta revisada el 2026-05-22:

- Reels API:
  - contenedor `MOV` o `MP4`
  - `AAC` hasta `48 kHz`
  - `HEVC` o `H264`
  - `23-60 FPS`
  - ancho maximo `1920`
  - bitrate de video `VBR` hasta `25 Mbps`
  - audio `128 kbps`
  - duracion `3s` a `15 min`
  - tamano maximo `300 MB`
- Stories API:
  - mismas bases de codec
  - duracion `3s` a `60s`
  - tamano maximo `100 MB`
- Limites operativos:
  - los contenedores expiran a las 24h
  - una cuenta puede crear `400` contenedores en una ventana movil de 24h
- `share_to_feed=true` solo significa que el Reel puede aparecer en Feed y en
  Reels; no garantiza por si solo distribucion ni aparicion.

Adicionalmente, el Help Center de Instagram para Reels en la app indica:

- ratio entre `1.91:1` y `9:16`
- resolucion minima `720p`
- minimo `30 FPS`
- existe un toggle `Upload at highest quality`

Inferencia explicita:

- el toggle `Upload at highest quality` es util para subidas hechas desde la
  app de Instagram;
- `vigia_meta` no sube por la app, sino por Graph API y `rupload`;
- por tanto, ese toggle probablemente no cambia nada en este flujo automatizado.

## Recomendacion tecnica concreta

Si el objetivo es subir la calidad publicada en Instagram sin romper el flujo:

1. Mejor opcion: publicar en IG desde el master original, no desde el binario
   rescatado de Facebook.
2. Si hay que seguir rescatando desde Facebook: evitar recodificar siempre;
   solo recodificar cuando el video no cumpla los limites oficiales.
3. Cuando toque recodificar: usar el carril `instagram_api_safe` o migrar su
   logica al vigia:
   - ancho maximo `1920`
   - bitrate objetivo calculado por duracion
   - `two-pass`
   - `preset slow`
   - `AAC 48kHz`
   - preservacion de FPS si ya cae entre `23` y `60`
4. Revisar y probablemente eliminar la poda a `90s` para Reels.
5. Renombrar internamente `FEED` a algo como `REEL_SHARE_TO_FEED_FULL` para que
   el comportamiento coincida con la realidad de la API.

## Fuentes oficiales consultadas

- Meta Developers, IG User Media:
  `https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media`
- Snapshot accesible del mismo contenido oficial usado en la revision:
  `https://archive.ph/20251231074512/https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media`
- Instagram Help Center, Reel size and aspect ratios:
  `https://www.facebook.com/help/1038071743007909`
