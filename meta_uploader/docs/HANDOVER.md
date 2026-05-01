# Handover - Meta Uploader

## Estado actual

Hay un handover operativo bloqueante para el carril `Facebook Post`.

## Bloqueo principal

La corrida normal de `15 minutos` evidencio que el carril `Facebook Post`
todavia no es confiable para corridas sostenidas. Los fallos fueron mixtos:

- `ConnectionResetError(10054)` en `rupload.facebook.com`
- `NameResolutionError` contra `graph.facebook.com`
- `OSError(22, Invalid argument)` en algunos intentos
- estancamientos reales detectados por el watchdog

## Documento de trabajo para retomar

- revisa `docs/TODO_FB_POST_RESILIENCE.md`

## Objetivo de la siguiente ronda

Endurecer `Facebook Post` con upload resumible real, retries diferenciados,
persistencia de reanudacion y un runner que no consuma cola ante fallos
transitorios.

## Antes de retomar

- revisa `README.md`
- revisa `docs/ARCHITECTURE.md`
- revisa `docs/DECISIONS.md`
- revisa `docs/PROGRESS.md`
- revisa `docs/TODO_FB_POST_RESILIENCE.md`
- confirma que `.env` o las variables de entorno locales esten configuradas
