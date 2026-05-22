# Codex Session Log - 2026-05-19

## Alcance de esta sesion

Esta nota deja trazabilidad de la ronda de trabajo validada en Codex sobre el
ecosistema movil ARM64 del Samsung S24 Ultra `SM-S928B` (`RFCX91HV4GD`),
centrada en widgets Termux, rutas moviles, OAuth de YouTube, arranque del
pipeline y destino final de crudos.

## Verificaciones reales hechas sobre el S24

### `1_CORTAR_TEASERS`
- Verificado el `2026-05-19` en `/sdcard/Antigravity/widget_logs/1_CORTAR_TEASERS.log`.
- Quedo registrado que `20260517_163647.mp4` y `20260515_224857.mp4` se
  ignoran correctamente porque ya tienen sus 3 teasers y su marker `.done`
  valido.
- Seguimiento correctivo del `2026-05-19 14:14:54` en el mismo log:
  - el widget volvio a hacer pre-scan antes del corte
  - se restauro el resumen por crudo con duracion real y total de partes
  - caso validado: `20260509_184854.mp4` ahora reporta
    `Duracion: 257.0s | Partes de 16s -> 16 segmentos totales`
  - el log volvio a exponer el progreso como `Parte N/M`
  - ya quedo visible `Parte 1/16 -> 20260509_184854_teaser_1.mp4 (s0 - s16)`

### `2_SUBIR_CRUDOS_YT`
- Verificado el `2026-05-19` en
  `/sdcard/Antigravity/widget_logs/2_SUBIR_CRUDOS_YT.log`.
- Inicio subida real del crudo `20260517_163647.mp4` y avanzo al `23%`.

### `3_SUBIR_TEASERS_YT`
- Verificado el `2026-05-19` en
  `/sdcard/Antigravity/widget_logs/3_SUBIR_TEASERS_YT.log`.
- Hubo una corrida valida usando `token_2.json`.
- Se subio un teaser completo y la API devolvio `Video ID: nvAj9w07cFo`.
- Esa observacion termino llevando al fix final de rotacion automatica descrito
  mas abajo: el sistema ahora solo rota entre pares `client_secret`/`token`
  realmente compatibles por `client_id`.

### `4_VIGIA_FACEBOOK`
- Verificado el `2026-05-19` en
  `/sdcard/Antigravity/widget_logs/4_VIGIA_FACEBOOK.log`.
- El evacuador retomo desde checkpoint y continuo subiendo chunks reales a
  Facebook desde `/sdcard/Antigravity/videos subidos exitosamente`.

### `0_PIPELINE_COMPLETO`
- Verificado el `2026-05-19` en
  `/sdcard/Antigravity/widget_logs/0_PIPELINE_COMPLETO.log`.
- Ya no aparece el error viejo `integer expression expected`.
- Ya no se cae por OAuth.
- Recorre `FASE 1`, `FASE 2` y `FASE 3`, lanzando las subidas esperadas.
- Seguimiento correctivo del `2026-05-19 14:15:42`:
  - `FASE 2` ya hereda el formato restaurado de `teaser_generator.py`
  - caso validado: `20260509_184854.mp4` reporta
    `Duracion: 257.0s | Partes de 16s -> 16 segmentos totales`
  - tambien se verifico la autorreparacion del backlog:
    `20260509_183023.mp4` aparece con
    `Partes de 16s -> 14 segmentos totales` y marker `.done` huerfano
    regenerable

## Archivos tocados en esta jornada

### Widgets y launchers Termux/Debian
- `scripts/linux/cortar_teasers_termux.sh`
- `scripts/linux/pipeline_completo_termux.sh`
- `scripts/linux/subir_crudos_yt_termux.sh`
- `scripts/linux/subir_teasers_termux.sh`
- `scripts/linux/vigia_facebook_termux.sh`

### YouTube uploader
- `youtube_uploader/teaser_generator.py`
- `youtube_uploader/teaser_uploader.py`
- `youtube_uploader/uploader.py`
- `youtube_uploader/video_helpers.py`
- `youtube_uploader/tests/test_video_helpers.py`

### Meta uploader
- `meta_uploader/subir_fb_evacuador.py`

## Cambios funcionales dejados hoy

### `youtube_uploader/teaser_generator.py`
- Ya no vuelve a marcar `.done` falsos.
- Repara markers huerfanos.
- Se elimino el hardcode de `3` teasers esperados.
- Ahora calcula los segmentos completos de `16s` segun la duracion real del
  video, manteniendo compatibilidad con clips muy cortos.
- Volvieron los logs operativos utiles:
  - `Generando teasers para: ...`
  - `Duracion: ... | Partes de 16s -> N segmentos totales`
  - `[OK] Parte N/M -> ... (sX - sY)`

### `youtube_uploader/teaser_uploader.py`
- Detecta correctamente `/sdcard/Antigravity`.
- Selecciona un token usable real sin depender de `token_0.json`.
- Se elimino el scope extra que provocaba `invalid_scope`.

### `youtube_uploader/uploader.py`
- Quedo alineado con la misma correccion de tokens/scopes para crudos.
- Se corrigio el destino final post-upload de los crudos para que vuelvan a la
  carpeta central `/sdcard/Antigravity/videos subidos exitosamente` cuando el
  origen real esta en `/sdcard/Antigravity/crudos_pendientes`.

### `youtube_uploader/video_helpers.py`
- Se corrigio el desfase del numero de teaser; `teaser_1` ahora sale como
  `#1`.
- Ahora trata `crudos_pendientes` y `teasers_pendientes` como staging folders,
  no como raiz final de biblioteca.

### `scripts/linux/pipeline_completo_termux.sh`
- Ajustadas rutas moviles correctas.
- Corregida la espera del pipeline para no romperse con el conteo previo.
- Integrado el flujo nuevo de logs operativos del S24.
- Validado de nuevo que `FASE 2` muestre los conteos reales de teasers tras el
  hotfix del generador.

### Widgets `1`, `2`, `3` y `4`
- Los logs quedaron centralizados en `/sdcard/Antigravity/widget_logs`.
- Se ajustaron rutas y entorno para correr en el almacenamiento real del
  telefono.

### Widget `1_CORTAR_TEASERS`
- Recupero el flujo previo de operador:
  - `Paso 1: Escaneando base de datos antes de cortar...`
  - `Paso 2: Generando recortes de avance...`
- Esto vuelve a dejar el mismo contexto visual que se usaba para revisar la
  jornada manual desde el S24.

### `meta_uploader/subir_fb_evacuador.py`
- Ya toma el storage del telefono en lugar de rutas de escritorio.

### `scripts/linux/vigia_meta.sh`, `vigia_meta_widget.sh` y `bootstrap_termux_arm64.sh`
- Se corrigio el arranque de `vigia_meta` en el S24.
- Causa real encontrada:
  - el shortcut real `~/.shortcuts/vigia_meta.sh` seguia generado con una
    version vieja del launcher
  - intentaba ejecutar `vigia_meta_termux.sh` directo dentro de Debian
  - en el telefono ese wrapper no siempre conservaba bit de ejecucion
  - el flujo viejo hacia `tail` sobre `fb_to_ig_vigia.log` antes de asegurar
    su existencia
- Fix aplicado:
  - `bootstrap_termux_arm64.sh` ahora regenera `~/.shortcuts/vigia_meta.sh`
    como wrapper fino hacia `vigia_meta_widget.sh`
  - `vigia_meta.sh` detecta mejor el contexto Termux y redirige al widget sin
    depender de execute bits
  - `vigia_meta_widget.sh` precrea el log, reenvia argumentos y ahora deja
    session log visible en `/sdcard/Antigravity/widget_logs/VIGIA_META.log`

### Rotacion automatica de llaves/tokens YouTube
- Se dejo corregida la seleccion automatica para que no dependa de un
  `token_N.json` implicito ni de un fallback por scopes a tokens de otra app
  OAuth.
- Caso real confirmado en el S24:
  - existen `client_secret_1.json` a `client_secret_4.json`
  - solo existian `token_2.json` y `token_3.json`
  - `token_2.json` corresponde a `client_secret_3.json`
  - `token_3.json` corresponde a `client_secret_4.json`
- Con el fix final:
  - los uploaders ordenan `client_secret_*` numericamente
  - solo reutilizan tokens cuyo `client_id` coincide con la credencial activa
  - las llaves sin token compatible se saltan del pool automatico hasta que el
    usuario renueve esos tokens
  - si una llave especifica necesita relogin, genera su token canonico
    (`token_0.json`, `token_1.json`, etc.) en lugar de tomar prestado un token
    ajeno

### Destino final de crudos en movil
- Causa real encontrada en repo: `move_file_and_update_db()` reconstruia la
  carpeta de exito con `file_path.parent / "videos subidos exitosamente"`.
- Efecto: cuando el crudo vivia en `/sdcard/Antigravity/crudos_pendientes`,
  el archivo podia terminar en
  `/sdcard/Antigravity/crudos_pendientes/videos subidos exitosamente`
  en lugar de la carpeta central usada por Meta.
- Fix aplicado:
  - `youtube_uploader/video_helpers.py` ahora considera
    `crudos_pendientes` y `teasers_pendientes` como staging folders
  - `youtube_uploader/uploader.py` ya mueve usando la raiz inferida de
    biblioteca + `videos subidos exitosamente`
- Resultado esperado tras el fix:
  - origen: `/sdcard/Antigravity/crudos_pendientes/<archivo>.mp4`
  - destino: `/sdcard/Antigravity/videos subidos exitosamente/<archivo>.mp4`

### Teasers completos sin limite artificial
- Causa real encontrada en repo: durante el endurecimiento del S24,
  `teaser_generator.py` quedo reducido a `EXPECTED_TEASER_COUNT = 3` como
  prueba robusta temporal y el widget manual perdio el pre-scan/resumen de
  segmentos.
- Efecto: los crudos largos solo producian `3` teasers, se escribian markers
  `.done` incompletos y luego los mismos crudos se negaban a volver a cortar.
- Fix aplicado:
  - el generador ahora usa la duracion real del video para calcular cuantas
    partes completas de `16s` corresponden
  - si existe `.done` pero faltan teasers respecto a ese total real, el marker
    se considera huerfano y se regenera
  - `1_CORTAR_TEASERS.sh` volvio a exponer el pre-scan y el resumen operativo
    por archivo
- Verificacion real en el S24:
  - `1_CORTAR_TEASERS.log` a las `14:14:58` ya muestra
    `20260509_184854.mp4 | Duracion: 257.0s | Partes de 16s -> 16 segmentos totales`
  - `0_PIPELINE_COMPLETO.log` a las `14:15:43` muestra el mismo calculo dentro
    de `FASE 2`

## Verificaciones tecnicas

- `py_compile` ejecutado con exito en el S24.
- `python -m unittest youtube_uploader.tests.test_video_helpers` ejecutado con
  exito.
- `python -m unittest youtube_uploader.tests.test_auth_rotation -v` OK.
- `python -m unittest youtube_uploader.tests.test_teaser_uploader -v` OK.
- `python -m unittest youtube_uploader.tests.test_uploader_queue -v` OK.
- `python -m py_compile youtube_uploader/uploader.py youtube_uploader/teaser_uploader.py meta_uploader/subir_fb_evacuador.py youtube_uploader/video_helpers.py`
  OK.
- Seguimiento local posterior al hotfix de ruta:
  - `python -m unittest youtube_uploader.tests.test_auth_rotation -v` OK
  - `python -m unittest youtube_uploader.tests.test_teaser_uploader -v` OK
  - `python -m unittest youtube_uploader.tests.test_uploader_queue -v` OK
  - `python -m unittest youtube_uploader.tests.test_video_helpers -v` OK
  - se agrego cobertura explicita para el caso
    `crudos_pendientes -> videos subidos exitosamente`
- Nota de alcance: este micro-fix final de ruta se valido por pruebas locales
  reproducibles sobre el repo; en esta misma micro-ronda no se hizo una nueva
  corrida manual completa del widget `2_SUBIR_CRUDOS_YT` en el S24.
- Verificacion real del pool OAuth dentro de Debian en el S24 despues del
  hot-sync final:
  - `uploader._build_credential_pool()` devuelve
    `['client_secret_3.json', 'client_secret_4.json']`
  - `teaser_uploader._build_credential_pool()` devuelve
    `['client_secret_3.json', 'client_secret_4.json']`
- Verificacion real de `vigia_meta` en el S24:
  - `~/.shortcuts/vigia_meta.sh --help` ya muestra `usage: fb_to_ig_vigia.py`
  - desaparecieron los fallos `Permission denied` y `No such file or directory`
    del arranque

## Nota operativa importante

Varias corridas se cortaron manualmente por timeout despues de confirmar que
estaban trabajando de verdad. Si algun log termina a mitad de subida, no
significa que haya aparecido un fallo nuevo: en esta jornada se hizo asi a
proposito para verificar sin dejar todos los procesos colgados.

## Estado al cierre de esta nota

- `vigia_meta` quedo corregido en repo y validado en el S24.
- La rotacion automatica de llaves/tokens YouTube quedo corregida y cubierta
  con pruebas para el caso real del S24.
- El movimiento final de crudos quedo otra vez alineado con
  `/sdcard/Antigravity/videos subidos exitosamente` y cubierto por prueba
  automatizada.
