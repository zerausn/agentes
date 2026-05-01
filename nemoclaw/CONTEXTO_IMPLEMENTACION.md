# Contexto de Implementacion de NemoClaw

## Objetivo

Levantar `NVIDIA/NemoClaw` en Linux con `NVIDIA Endpoints`, dejar un sandbox funcional y documentar el procedimiento para que pueda repetirse en otro equipo.

## Resultado final

Se dejo operativo:

- `nemoclaw` CLI funcional
- `openshell` instalado y operativo
- gateway `nemoclaw` levantada
- sandbox `nemoclaw-main` creado y en estado usable
- forwarding local del dashboard en `http://127.0.0.1:18789/`
- acceso web documentado como `OpenClaw Control` sobre la gateway de `NemoClaw`

## Lo que se encontro al inicio

El host no cumplia de forma limpia los prerequisitos documentados por NVIDIA:

- `node` era `v20.20.2`
- el comando `docker` apuntaba a `podman` por el paquete `podman-docker`
- `NemoClaw` pide `Node >= 22.16.0`
- en Linux la ruta soportada es `Docker`

## Cambios realizados en el host

### 1. Node.js

Se instalo `nvm` para el usuario `zerausn` y se fijo `Node 22` como default.

Motivo:

- cumplir el minimo de `NemoClaw`
- evitar reemplazar de forma agresiva el `nodejs` del sistema

Estado validado:

- `node --version` -> `v22.22.2`
- `npm --version` -> `10.9.7`

### 2. Docker real

Se reemplazo la compatibilidad falsa de Docker sobre Podman:

- se removio `podman-docker`
- se instalo `docker.io`
- se habilito y levanto `docker.service`
- se agrego `zerausn` al grupo `docker`

Motivo:

- `NemoClaw` en Linux depende de Docker real
- el wrapper de Podman no es la ruta soportada

Estado validado:

- `docker version` responde cliente y servidor
- `dockerd` quedo activo

### 3. OpenShell

La primera instalacion intento usar `gh release download` y fallo porque `gh` no estaba autenticado.

Se resolvio instalando `openshell` manualmente por descarga directa del release oficial y dejando el binario en:

- `~/.local/bin/openshell`

Motivo:

- evitar depender de login de GitHub CLI
- mantener la instalacion fuera de un repo

Estado validado:

- `openshell --version` -> `0.0.19`

### 4. Instalacion de NemoClaw

El paquete alpha presento varios problemas de empaquetado.

Se hizo lo siguiente:

- se clono `NVIDIA/NemoClaw`
- se instalo la CLI desde una copia saneada para evitar recursion del script `prepare`
- se instalaron dependencias globales faltantes para que la CLI pudiera arrancar
- se parcheo la instalacion local con archivos faltantes del plugin:
  - `nemoclaw/tsconfig.json`
  - `nemoclaw/package-lock.json`
  - `nemoclaw/src/`

Motivo:

- el paquete alpha no quedaba listo solo con `npm install -g`
- el build del sandbox fallaba por archivos ausentes

Estado validado:

- `nemoclaw --version` -> `nemoclaw v0.1.0`

### 5. Onboarding y sandbox

Se ejecuto `nemoclaw onboard --non-interactive` usando:

- provider: `build`
- model: `nvidia/nemotron-3-super-120b-a12b`
- sandbox: `nemoclaw-main`
- policy mode: `skip`

Problemas encontrados y resueltos:

- el gateway de OpenShell parecia fallar al inicio, pero realmente estaba descargando imagenes y tardando mas que el timeout inicial
- el build del sandbox fallo una vez por archivos faltantes del plugin; se corrigio con el parche descrito arriba
- la exportacion y subida de la imagen al gateway tomo varios minutos, pero termino bien

Estado final validado:

- `nemoclaw status` muestra `nemoclaw-main`
- el sandbox quedo `Ready`
- el dashboard local quedo accesible via port forward

### 5.1 UI web local

Al abrir `http://127.0.0.1:18789/` aparecio una UI de `OpenClaw Control`, no una marca separada de `NemoClaw`.

Eso no fue un error.
Al revisar el repo original se confirmo que `NemoClaw` usa la interfaz de `OpenClaw` para el chat/control web.

El fallo real fue este:

- la UI cargaba
- pero mostraba `device identity required`
- y quedaba desconectada de la gateway

Se reviso el bundle de la UI y la configuracion real descargada desde el sandbox.
Se confirmo que:

- la UI soporta modo local por token
- `NemoClaw` construye URLs tokenizadas con `#token=...`
- el sandbox ya tenia:
  - `gateway.controlUi.allowInsecureAuth: true`
  - `gateway.controlUi.dangerouslyDisableDeviceAuth: true`

Ademas, en este host el `openshell forward` en background quedaba en estado `dead`, pero en foreground se mantenia bien.

Por eso la solucion operativa documentada fue:

- no depender de `http://127.0.0.1:18789/` pelado
- usar la URL tokenizada del sandbox
- sostener el forward en foreground con un helper dedicado

Helper agregado en `agentes`:

- `scripts/start_nemoclaw_dashboard.sh`

Documento asociado:

- `WEB_UI_LOCAL.md`

### 6. Telegram

Se creo el bot:

- `@OandroidNemoClawbot`

El token no se guardo en el repo.
Se guardo fuera de Git en:

- `~/.config/antigravity/nemoclaw.env`

Durante la integracion se encontro otro problema:

- `curl` podia hablar con `api.telegram.org`
- `node` desde `telegram-bridge.js` fallaba con `ENETUNREACH` y `ETIMEDOUT`

Se aplico un hotfix local al checkout de `NemoClaw`:

- archivo: `scripts/telegram-bridge.js`
- cambio: `family: 4` en la llamada `https.request`

Motivo:

- forzar IPv4 para la conexion a Telegram en este host

Ademas, el wrapper `nemoclaw start` no fue confiable para dejar el bridge estable en background en esta maquina.
Por eso el flujo operativo documentado usa el script oficial del checkout local de `NemoClaw` ejecutado directamente con `node`.

## Lo que NO se hizo

- no se escribio la `NVIDIA_API_KEY` en este repositorio
- no se escribio la `NVIDIA_API_KEY` en `open-claw`
- no se genero `.env` dentro de este repo con secretos reales
- no se subio nada automaticamente a GitHub

## Dato importante para otras IAs y desarrolladores

Esta instalacion no fue un "happy path". Se tuvo que corregir el entorno y trabajar alrededor de defectos del paquete alpha de `NemoClaw`.

Si se repite en otro PC, asumir que hay que validar:

- version de Node
- Docker real, no wrapper de Podman
- instalacion de OpenShell
- completitud de la instalacion local de `NemoClaw`
- tiempos largos en el build y upload del sandbox
