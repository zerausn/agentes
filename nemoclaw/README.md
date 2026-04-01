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
- `scripts/start_nemoclaw_telegram.sh`: helper para arrancar servicios leyendo secretos fuera del repo
- `nemoclaw.env.example`: plantilla de variables sin secretos

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
