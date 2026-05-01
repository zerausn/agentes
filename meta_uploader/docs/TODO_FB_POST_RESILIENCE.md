# Tarea Pendiente - Endurecer Facebook Post ante fallos mixtos de red

## Estado

Pendiente para retomar manana.

## Contexto

Durante la corrida normal de `15 minutos` sobre `pendientes_posts.json`, el
carril `Facebook Post` no dejo publicaciones nuevas confirmadas. Los fallos no
fueron uniformes: aparecieron resets del host remoto, errores de resolucion DNS,
errores de socket locales y estancamientos detectados por el watchdog.

## Sintomas observados

- `ConnectionResetError(10054)` en `rupload.facebook.com/video-upload/...`
- `NameResolutionError` al resolver `graph.facebook.com`
- `OSError(22, Invalid argument)` en algunos intentos del runner
- alertas del watchdog tras `2` chequeos de `10s` sin avance

## Lectura tecnica actual

El flujo actual de `Facebook Post` es fragil para archivos grandes porque:

- hace `start` en `/{page-id}/videos`
- luego envia el archivo completo en un solo `POST` binario a `rupload`
- no tiene reanudacion por offsets ni persistencia de estado por video
- la capa HTTP de control no aplica retries con backoff
- el runner consume cola aunque el fallo haya sido transitorio

Puntos de codigo clave:

- `meta_uploader.py` -> `upload_fb_video_standard(...)`
- `meta_uploader.py` -> `_upload_facebook_video_binary(...)`
- `meta_uploader.py` -> `_post_binary(...)`
- `meta_uploader.py` -> `_request_json(...)`
- `test_batch_upload.py` -> `run_test_batch(...)`

## Hipotesis de causa

### H1. Upload monolitico demasiado fragil

Los videos pesados se estan enviando en una sola transferencia binaria. Si la
conexion se corta o el host remoto resetea el socket, se pierde todo el avance.

### H2. Sin reintentos diferenciados

`graph.facebook.com` y `rupload.facebook.com` tienen perfiles de fallo
distintos, pero hoy ambos quedan tratados como un fallo plano sin politica de
reintento ni reanudacion.

### H3. Cola demasiado agresiva

Cuando un asset falla por un problema transitorio, el runner sigue al siguiente
video. Eso erosiona la cola sin resolver la causa.

### H4. Diagnostico insuficiente de `OSError(22)`

Ese error necesita trazabilidad adicional para confirmar si nace del socket,
de la capa SSL o del progreso por consola.

## Plan de implementacion

### Fase 1 - Hardening de la capa HTTP

- anadir retries con backoff en `_request_json(...)`
- clasificar errores como:
  - DNS/resolucion
  - timeout
  - reset remoto
  - error HTTP terminal de Meta
- registrar en logs la clase exacta del error y la fase (`start`, `transfer`,
  `finish`, `poll`)

### Fase 2 - Reescribir `Facebook Post` a flujo resumible real

- reemplazar el upload binario monolitico por `start/transfer/finish`
- transferir por bloques
- leer y respetar offsets/sesion devueltos por Meta
- reutilizar `upload_session_id` y persistir el progreso

### Fase 3 - Persistencia local de reanudacion

Guardar por asset:

- `video_id`
- `upload_session_id`
- `last_confirmed_offset`
- `attempt_count`
- `last_error_class`

Objetivo: si la red cae o el proceso termina, no reiniciar desde cero ni
duplicar publicacion.

### Fase 4 - Watchdog accionable

Usar el watchdog no solo para alertar, sino para decidir:

- si abortar y reintentar el bloque actual
- si pausar el batch completo
- si distinguir entre:
  - Meta aun accesible
  - conectividad general degradada
  - DNS roto

### Fase 5 - Runner mas conservador

Cambiar `test_batch_upload.py` para que:

- no queme cola cuando el error sea transitorio
- reintente el mismo asset si el problema es DNS/reset/timeout
- solo salte al siguiente video cuando el fallo sea terminal o se supere un
  maximo de reintentos

### Fase 6 - Instrumentacion de `OSError(22)`

- capturar traceback completo
- registrar fase exacta
- validar si el problema nace de:
  - socket
  - SSL
  - progreso por consola / `print("\r...")`
- si hace falta, desactivar progreso interactivo cuando no haya TTY real

## Fuera de alcance de esta tarea

- no mezclar esta correccion con el segundo procesamiento/clipping
- no cambiar el carril base de Instagram mas alla de trazabilidad compartida
- no reestructurar todavia Stories de Facebook

## Criterios de cierre

La tarea se considera cerrada cuando:

- `Facebook Post` pueda reanudar transferencias sin reiniciar el archivo entero
- un fallo DNS o reset remoto no consuma automaticamente el siguiente asset
- el watchdog pueda distinguir y accionar frente a estancamientos reales
- una corrida sostenida de prueba controlada deje evidencia clara de:
  - reintento exitoso o pausa limpia
  - no duplicacion
  - logs con causa clasificada

## Primera accion recomendada manana

1. Revisar la documentacion oficial de `Facebook video publishing` para fijar
   la forma exacta de `transfer` y offsets.
2. Refactorizar `_upload_facebook_video_binary(...)` para soportar chunks.
3. Agregar persistencia local de estado de upload antes de volver a correr el
   batch normal.
