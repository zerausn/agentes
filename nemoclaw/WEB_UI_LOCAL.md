# UI Web local de NemoClaw

## Hallazgo importante

La pagina que aparece en `http://127.0.0.1:18789/` no es una UI separada de `NemoClaw`.
Es la interfaz **OpenClaw Control** montada sobre la gateway de `OpenShell` que `NemoClaw` crea.

Eso coincide con la documentacion del repo original:

- `NemoClaw` documenta que `/nemoclaw` vive dentro de la **OpenClaw chat interface**
- al conectar al sandbox, la ruta interactiva abre la **OpenClaw chat UI**

## Por que aparecia `device identity required`

El problema no era el modelo ni Telegram.
El problema estaba en la forma de abrir la UI web.

En este host se observo:

- la UI cargaba por `http://127.0.0.1:18789/`
- el navegador mostraba `device identity required`
- la pagina quedaba `Disconnected from gateway`

Al revisar el bundle de la UI y el config real del sandbox se confirmo:

- el panel HTTP local existe
- el sandbox ya tenia:
  - `gateway.controlUi.allowInsecureAuth: true`
  - `gateway.controlUi.dangerouslyDisableDeviceAuth: true`
- la UI soporta modo local por token
- el codigo de `NemoClaw` original tambien construye una **tokenized URL** con `#token=...`

Conclusión:

- abrir solo `http://127.0.0.1:18789/` puede dejar la UI sin auth util
- la forma soportada y estable en este host es abrir la URL tokenizada del sandbox:

```text
http://127.0.0.1:18789/#token=<gateway-token>
```

## Flujo correcto en este equipo

Usar el helper:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_dashboard.sh
```

Ese script:

- descarga temporalmente `openclaw.json` desde el sandbox
- extrae solo `gateway.auth.token`
- imprime la URL tokenizada correcta
- reabre el port-forward local a `127.0.0.1:18789`
- mantiene el forward en primer plano para que no muera

## Importante

La terminal donde corre `start_nemoclaw_dashboard.sh` debe quedar abierta mientras uses el panel.

Motivo:

- en esta build alpha, el background forward de `openshell` quedaba marcado como `dead`
- en foreground el forward si quedo estable y la UI respondio con `HTTP 200`

## Seguridad

- el token del dashboard no se guarda en Git
- el helper lo extrae a un directorio temporal y lo limpia al salir
- tratar la URL tokenizada como una contraseña
- no compartir capturas ni texto con `#token=...`

## Validacion realizada

Se valido lo siguiente:

- el sandbox `nemoclaw-main` seguia en `Ready`
- la gateway `nemoclaw` seguia registrada
- el puerto `18789` respondia `HTTP 200` cuando el forward estaba vivo
- la configuracion del sandbox ya contenia el modo HTTP local permitido

## Nota para otras IAs

No asumir que ver `OpenClaw Control` es un error.
Eso es parte del diseño normal de `NemoClaw`.

El problema real a diagnosticar en este caso fue:

- auth web incompleta para HTTP local
- mas un forward local inestable en background

La solucion aplicada y documentada fue:

- usar URL tokenizada
- no depender del bare URL
- mantener el forward estable en foreground
