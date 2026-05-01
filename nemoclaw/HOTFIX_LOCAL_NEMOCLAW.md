# Hotfix Local Aplicado al Checkout de NemoClaw

## Importante

Este archivo documenta cambios aplicados en el checkout local:

- `/home/zerausn/NemoClaw`

No estan en el repo `agentes`.
No son secretos.
Si se quiere replicar el comportamiento en otro PC, estos cambios deben aplicarse otra vez al checkout local de `NemoClaw` o proponerse upstream.

## Archivo parcheado

- `scripts/telegram-bridge.js`

## Cambio 1: forzar IPv4 hacia Telegram

En la llamada `https.request(...)` se agrego:

```js
family: 4
```

## Motivo

En este host:

- `curl` hacia `api.telegram.org` funcionaba
- `node` fallaba con `ENETUNREACH` y `ETIMEDOUT`

Forzar IPv4 resolvio el problema de conectividad del bridge con Telegram.

## Cambio 2: usar salida JSON del agente

Se cambio la invocacion interna del agente de:

```bash
openclaw agent --agent main --local -m ...
```

a:

```bash
openclaw agent --agent main --local --json -m ...
```

## Motivo

La salida libre del agente devolvia bloques de `tool_call` o texto crudo dificil de parsear.
Con `--json`, el bridge puede leer:

- `payloads[].text`

de forma estable.

## Cambio 3: parseo de `payloads[].text`

Se agrego logica para:

1. detectar el JSON en `stdout`
2. hacer `JSON.parse(...)`
3. concatenar `payloads[].text`
4. usar fallback a parseo por lineas si el JSON falla

## Motivo

El bridge original dependia de filtrar texto suelto.
En este caso eso no fue confiable.

## Cambio 4: inicializacion del workspace del sandbox

No fue un patch al repo `NemoClaw`, pero si un cambio operativo dentro del sandbox:

- se completo `IDENTITY.md`
- se completo `USER.md`
- se creo `MEMORY.md`
- se elimino `BOOTSTRAP.md`

## Motivo

Mientras `BOOTSTRAP.md` seguia presente y el workspace estaba vacio, el agente principal se comportaba como una instalacion recien nacida y no generaba respuestas normales para Telegram.

## Resumen

Sin estos ajustes:

- Telegram recibia mensajes
- el bridge tomaba el update
- pero la respuesta del agente no volvia de forma util

Con estos ajustes:

- el bot `@OandroidNemoClawbot` responde
- el sandbox `nemoclaw-main` entrega texto normal al bridge
