# NemoClaw en Antigravity

Este directorio deja el contexto operativo de la instalacion local de `NemoClaw` realizada en Parrot OS 7 para que otras IAs y desarrolladores puedan:

- entender que se hizo
- replicarlo en otro PC
- evitar exponer secretos en Git
- continuar con Telegram sin improvisar

## Archivos

- `CONTEXTO_IMPLEMENTACION.md`: que se hizo, como se hizo y por que
- `REPLICACION_OTRO_PC.md`: paso a paso para repetir la instalacion
- `SEGURIDAD_Y_SECRETOS.md`: controles para no filtrar credenciales
- `TELEGRAM.md`: flujo de integracion y hardening para Telegram
- `WEB_UI_LOCAL.md`: como funciona realmente la UI web local y como abrirla sin caer en `device identity required`
- `HOTFIX_LOCAL_NEMOCLAW.md`: parches aplicados al checkout local de `NemoClaw`
- `INICIO_AUTOMATICO.md`: como dejar el bridge listo al iniciar sesion
- `scripts/start_nemoclaw_telegram.sh`: helper para arrancar servicios leyendo secretos fuera del repo
- `scripts/start_nemoclaw_dashboard.sh`: helper para reabrir el panel local con URL tokenizada
- `scripts/enable_nemoclaw_autostart.sh`: instala el autostart en `~/.config/autostart`
- `scripts/disable_nemoclaw_autostart.sh`: quita autostart, para el bridge, y opcionalmente borra secretos locales
- `nemoclaw.env.example`: plantilla de variables sin secretos
- `startup/nemoclaw-telegram-bridge.desktop`: plantilla de autostart para escritorio Linux

## Estado validado en este equipo

- SO: Parrot Security 7.1
- Node: `v22.22.2` via `nvm`
- Docker: `26.1.5+dfsg1`
- OpenShell: `0.0.19`
- NemoClaw: `0.1.0`
- Sandbox activo: `nemoclaw-main`
- Provider: `NVIDIA Endpoints`
- Modelo: `nvidia/nemotron-3-super-120b-a12b`

## Comandos utiles

```bash
source ~/.bashrc
nemoclaw status
nemoclaw nemoclaw-main status
nemoclaw nemoclaw-main connect
nemoclaw nemoclaw-main logs --follow
openshell term
```

## Regla de seguridad

No guardar `NVIDIA_API_KEY`, `TELEGRAM_BOT_TOKEN` ni otros secretos dentro de este repositorio.
Usar un archivo externo como `~/.config/antigravity/nemoclaw.env`.

## Inicio rapido

Arranque manual:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_telegram.sh
```

UI web local:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_dashboard.sh
```

Arranque automatico al iniciar sesion:

- ver `INICIO_AUTOMATICO.md`
