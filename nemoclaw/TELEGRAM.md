# Telegram con NemoClaw

## Estado actual

En este equipo:

- `nemoclaw-main` ya existe
- `telegram-bridge` aparece disponible pero detenido
- falta proporcionar `TELEGRAM_BOT_TOKEN` para arrancarlo

## Lo que necesita NemoClaw

Segun el bridge oficial de `NemoClaw`, hacen falta:

- `TELEGRAM_BOT_TOKEN`
- `NVIDIA_API_KEY`
- `SANDBOX_NAME`
- opcional: `ALLOWED_CHAT_IDS`

## Recomendacion de seguridad

No exportar secretos dentro del repo ni dejarlos en archivos versionados.
Usar:

```text
~/.config/antigravity/nemoclaw.env
```

## Crear el bot

1. Abrir Telegram
2. Hablar con `@BotFather`
3. Ejecutar `/newbot`
4. Elegir nombre y username
5. Guardar el token fuera del repo

## Restringir quien puede usar el bot

Recomendado:

- obtener tu chat id
- definir `ALLOWED_CHAT_IDS`

Sin `ALLOWED_CHAT_IDS`, el bridge acepta cualquier chat que le escriba.

## Archivo externo recomendado

Ver plantilla:

- `nemoclaw.env.example`

Copiarla fuera del repo:

```bash
mkdir -p ~/.config/antigravity
cp /ruta/al/repo/nemoclaw/nemoclaw.env.example ~/.config/antigravity/nemoclaw.env
chmod 600 ~/.config/antigravity/nemoclaw.env
```

Luego editar el archivo real y reemplazar placeholders.

## Arranque seguro

Usar el helper de este repo:

```bash
bash nemoclaw/scripts/start_nemoclaw_telegram.sh
```

Ese script:

- lee secretos desde `~/.config/antigravity/nemoclaw.env`
- no escribe secretos al repo
- valida `node`, `nemoclaw` y `openshell`
- arranca el bridge directamente desde el checkout local de `NemoClaw`
- deja PID y log en `/tmp`

Archivos runtime:

- PID: `/tmp/nemoclaw-telegram-bridge.pid`
- log: `/tmp/nemoclaw-telegram-bridge.log`

## Verificar estado

```bash
ps -p "$(cat /tmp/nemoclaw-telegram-bridge.pid)" -o pid=,user=,cmd=
sed -n '1,80p' /tmp/nemoclaw-telegram-bridge.log
```

Esperado:

- proceso `node .../telegram-bridge.js` en running
- banner del bot en el log

## Monitoreo

```bash
openshell term
```

Esto es importante porque si el agente intenta salir a internet, el flujo de aprobacion de OpenShell es parte de la barrera de seguridad.

## Nota importante

El bridge oficial tambien usa `NVIDIA_API_KEY` en runtime.
Si la key fue compartida en una conversacion o se considera expuesta, rotarla antes de dejar Telegram activo de forma permanente.

## Hotfix aplicado en este host

En esta maquina el script oficial necesitó este ajuste local:

- `https.request(..., { family: 4, ... })`

Motivo:

- `curl` alcanzaba Telegram
- `node` fallaba con dual-stack e intentos IPv6/IPv4 no funcionales

Si en otro PC no hace falta, no aplicar el cambio.
