### 2026-04-14: Triple solucion al procesamiento colgado de YouTube
**Resumen de la sesion:**
Se identifico que 30 videos de YouTube se habian quedado atascados en estado de
`uploadStatus: uploaded`. Dado que el usuario ya no poseia los archivos en
disco duro para re-subirlos, se recurrió a una tecnica basada en la API de
metadata touch a traves de `nudge_stuck_videos.py` para reactivar la
renderizacion en los servidores de Google agregando un espacio Unicode
invisible. Adicionalmente, se creo `diagnose_processing.py` para monitoreo
continuo y se fortalecio `uploader.py` con `wait_for_processing`.

### 2026-04-15: Rescate no destructivo y correccion de la causa raiz
**Resumen de la sesion:**
Se revisaron los logs del 15 de abril y se encontro la causa raiz de los
errores de red: `uploader.py` estaba corriendo `wait_for_processing()` en
paralelo sobre el mismo cliente HTTP que seguia usando `next_chunk()` para otra
subida. Eso explico `Resume Incomplete`, `WRONG_VERSION_NUMBER` y `BAD_LENGTH`,
ademas de por que el sistema podia dejar videos ya creados en YouTube sin
registrarlos bien en `scanned_videos.json`.

Tambien se detecto una segunda fuente de duplicados: artefactos
`*.faststart.tmp.*` estaban entrando al indice y podian subirse como si fueran
videos reales. Se corrigio esto en `video_scanner.py`, `video_helpers.py` y en
la cola del uploader para ignorar esos temporales y normalizar sus stems si ya
quedaron en metadata historica.

Finalmente, se implemento y ejecuto `rescue_stuck_processing.py` sobre el
canal. El rescate real mostro que de los 31 videos en estado `uploaded`, **28
ya tenian una copia hermana `processed`** y por tanto pudieron rescatarse sin
borrar nada, reparando metadata donde hacia falta. Solo quedaron **3 casos
realmente huerfanos** (`qLwX8PFeI_k`, `YsR_AG9A86I`, `V1pwp2HLQWA`), a los
cuales se les aplico un nudge reforzado no destructivo. `diagnose_processing.py`
se actualizo para reflejar esta diferencia y `nudge_stuck_videos.py` ahora se
enfoca en esos casos sin copia procesada.

### 2026-04-15: Limpieza definitiva de zombis y Heavy Nudge (Tarde)
**Resumen de la sesion:**
Tras confirmar que los 28 videos "uploaded" eran efectivamente duplicados
innecesarios que estorbaban en YouTube Studio, el usuario autorizo su borrado.
Se crearon dos olas de limpieza por lote mediante `cleanup_zombies.py`,
eliminando un total de **34 duplicados redundantes**.

Para los huerfanos restantes (donde no existe copia procesada), se fortalecio
`nudge_stuck_videos.py` con un modo **Heavy Nudge** que altera categoria y
titulo para resetear el cache de procesamiento de Google. Se aplico a **4
videos** huerfanos detectados. La verificacion final muestra un canal mucho mas
limpio, pasando de ~40 videos atascados a solo 4 huerfanos en observacion.
