# Análisis de Retención Fantasma en `video_scanner.py`

## Contexto del Problema
Observamos una discrepancia recurrente en los reportes de `uploader.py` en relación a la cantidad de videos disponibles localmente frente al conteo que realiza el log interno. Recientemente, un usuario reportó el siguiente comportamiento:
- En la carpeta de crudos (`crudos_pendientes`) existían **14 archivos de video reales**.
- Los logs del bot indicaban reiteradamente: `Videos pendientes: 29`.
- Ocasionalmente se registraban errores de archivo no encontrado como `WARNING - Archivo no encontrado: /sdcard/Antigravity/crudos_pendientes/...`

## Causa Raíz
La discrepancia ocurre en la lógica de consolidación y guardado del estado dentro del archivo de persistencia `scanned_videos.json`. 

En la rutina actual (`merge_scan_results` dentro de `video_scanner.py`):
1. El script lee **todos los videos** previamente escaneados desde el JSON en la memoria (lista `existing_videos`).
2. El script inspecciona el sistema de archivos (local) y retorna un listado de los objetos actuales (lista `discovered_videos`).
3. El bucle cruza ambas listas. Si un archivo recién encontrado ya existe en `existing_videos`, actualiza detalles (como peso en MB). Si es completamente nuevo, lo adjunta a la lista.
4. **Falla estructural:** Nunca hay una rutina que limpie el JSON en el sentido inverso. De tal modo, si el usuario (u otro bloque de código de un agente externo) borra o cambia de ubicación los archivos de `crudos_pendientes`, esos archivos persisten marcados como `uploaded: false` internamente dentro del JSON. No se realiza un *"garbage collection"* sobre la base de datos local frente a la realidad del sistema de archivos.

## Comportamiento del Uploader
El script responsable de subir el contenido (`uploader.py`) carga primero el JSON sin verificar la existencia de los archivos físicos de antemano hasta que ya está en el bucle principal. 
1. Cuenta qué objetos tienen la bandera `uploaded: false` para arrojar su consola `INFO - Videos pendientes: 29`.
2. Durante el bucle de preparación visualiza que el objeto se encuentra "no cargado", y entonces intenta resolver y procesar la ruta:
   ```python
   file_path = Path(video["path"])
   if not file_path.exists():
       logging.warning("Archivo no encontrado: %s", file_path)
       continue
   ```
3. Esto ocasiona un salto a la siguiente fila de iteración. Consecuentemente, el programa no "falla" letalmente, sino que salta todos aquellos fantasmas y sube aquellos que todavía se encuentran disponibles (los 14 reales). 

## Impacto
Pese al error en las variables de diagnóstico que reporta por consola ("Videos pendientes 29"), la robustez del bloque con su correspondiente comprobación lógica (`not path.exists() -> continue`) previene que todo el orquestador colapse.

**¿Debe arreglarse?**
- A fines operativos, **no es letal ni bloqueante**, el sistema sube la cantidad real de videos sin problemas y salta los ausentes fluidamente.
- A fines de salud del software y diagnóstico, **debería arreglarse**. Un archivo JSON que nunca se depura podría crecer ilimitadamente degradando el rendimiento al escanear, o en un futuro ocasionar falsos positivos ante límites pre-calculados, así como confusión durante lecturas de cuota y auditorías programadas.

## Recomendación de Arreglo
Se sugiere implementar una purga (prune) en `merge_scan_results`:

```python
def merge_scan_results(existing_videos, discovered_videos):
    discovered_paths = {video["path"] for video in discovered_videos}
    
    # Filtrar solo aquellos archivos extra-DB que AUN subsisten en el disco
    # O implementar validación de Path(v["path"]).exists() y eliminar 
    # de existing_videos los que respondan de forma negativa. 
``` 
Este enfoque es sencillo de integrar y evitará que la discrepancia siga presentándose en sesiones posteriores de análisis.
