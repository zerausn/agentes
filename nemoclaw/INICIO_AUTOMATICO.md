# Inicio Automatico de NemoClaw + Telegram

## Que significa "dejar persistente el bridge"

Significa que no tengas que acordarte de abrir una terminal y lanzar el bot manualmente cada vez.

En este contexto, lo mas razonable es:

- que arranque al iniciar sesion en Linux
- que use secretos fuera de Git
- que puedas reiniciarlo con un solo comando

## Opcion implementada

Se deja un flujo de autostart para entorno grafico Linux usando:

- `~/.config/autostart/nemoclaw-telegram-bridge.desktop`

Ese lanzador llama al script:

- `/home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_telegram.sh`

## Archivo de secretos externo

El arranque automatico depende de:

```text
~/.config/antigravity/nemoclaw.env
```

Ese archivo no va al repo.

## Que hace el script de arranque

- carga `Node` correcto
- carga el archivo externo de secretos
- apunta al checkout local de `NemoClaw`
- arranca `telegram-bridge.js`
- deja PID y log en `/tmp`

## Arranque manual rapido

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_telegram.sh
```

## UI web local

El panel web no se debe abrir con el bare URL y asumir que conectara solo.
En este host, la forma estable es:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_dashboard.sh
```

Ese helper:

- saca la URL tokenizada correcta del sandbox
- reabre el forward local
- deja el forward en foreground para que no muera

La terminal debe quedar abierta mientras uses el panel.

## Activar autostart con un solo comando

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/enable_nemoclaw_autostart.sh
```

## Verificar si esta arriba

```bash
ps -p "$(cat /tmp/nemoclaw-telegram-bridge.pid)" -o pid=,user=,cmd=
tail -n 50 /tmp/nemoclaw-telegram-bridge.log
```

## Reiniciar

```bash
pkill -f '/home/zerausn/NemoClaw/scripts/telegram-bridge.js' || true
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/start_nemoclaw_telegram.sh
```

## Desactivar autostart con un solo comando

Mantener secretos:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/disable_nemoclaw_autostart.sh
```

Desactivar y borrar secretos locales:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/disable_nemoclaw_autostart.sh --remove-secrets
```

## Que hace exactamente el script de desactivacion

El script automatiza estos pasos:

```bash
rm -f ~/.config/autostart/nemoclaw-telegram-bridge.desktop
pkill -f '/home/zerausn/NemoClaw/scripts/telegram-bridge.js'
rm -f /tmp/nemoclaw-telegram-bridge.pid /tmp/nemoclaw-telegram-bridge.log
```

Y opcionalmente:

```bash
rm -f ~/.config/antigravity/nemoclaw.env
```

## Nota para otras IAs

Si una IA futura necesita desactivar el arranque automatico sin romper la instalacion base de `NemoClaw`, debe usar primero:

```bash
bash /home/zerausn/Documents/Antigravity/agentes/nemoclaw/scripts/disable_nemoclaw_autostart.sh
```

Solo debe usar `--remove-secrets` si el usuario realmente quiere borrar el archivo externo de credenciales.

## Replicacion en otro PC

Para replicar este comportamiento en otro equipo:

1. clonar `agentes`
2. instalar y dejar operativo `NemoClaw`
3. crear `~/.config/antigravity/nemoclaw.env`
4. ajustar `NEMOCLAW_CHECKOUT`
5. copiar o instalar el archivo `.desktop`
6. cerrar sesion e iniciar sesion de nuevo

## Limitacion importante

Este mecanismo arranca al iniciar sesion grafica.
No es lo mismo que arrancar antes de login.

Si mas adelante se necesita arranque sin login, la siguiente opcion natural es un `systemd --user` service con `linger`, o un servicio de sistema mas controlado.
