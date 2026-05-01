# Seguridad y Secretos para NemoClaw

## Regla principal

Nunca subir secretos a Git.

Aplicado a:

- `NVIDIA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- tokens de UI
- URLs tokenizadas del dashboard
- cualquier archivo `.env` con valores reales

## Confirmaciones de esta implementacion

Se verifico lo siguiente:

- el valor literal de la `NVIDIA_API_KEY` no aparecio en `agentes`
- el valor literal de la `NVIDIA_API_KEY` no aparecio en `open-claw`
- el repo clonado de `NemoClaw` no quedo con cambios git pendientes
- no aparecio `~/.nemoclaw/credentials.json`

## Archivos locales que si existen

Existe:

- `~/.nemoclaw/onboard-session.json`

Ese archivo contiene metadatos del onboarding como:

- sandbox
- modelo
- provider
- nombre de la variable de credencial

No contiene el valor literal de la `NVIDIA_API_KEY`.

## Recomendacion sobre la key usada

Como la key fue pegada en una conversacion, tratarla como potencialmente expuesta.

Accion recomendada:

1. rotarla
2. generar una nueva
3. usar la nueva para uso prolongado

## Donde guardar secretos

Guardar secretos fuera del repo, por ejemplo:

```text
~/.config/antigravity/nemoclaw.env
```

Permisos recomendados:

```bash
mkdir -p ~/.config/antigravity
chmod 700 ~/.config/antigravity
touch ~/.config/antigravity/nemoclaw.env
chmod 600 ~/.config/antigravity/nemoclaw.env
```

## Formato recomendado

```bash
export NVIDIA_API_KEY='REEMPLAZAR'
export TELEGRAM_BOT_TOKEN='REEMPLAZAR'
export ALLOWED_CHAT_IDS='REEMPLAZAR'
export SANDBOX_NAME='nemoclaw-main'
```

## Verificacion antes de hacer commit

```bash
git status
git diff -- . ':(exclude)*.log'
grep -RIn 'nvapi-|TELEGRAM_BOT_TOKEN|NVIDIA_API_KEY=' .
```

## Controles operativos

- usar `openshell term` para observar solicitudes de red del sandbox
- no compartir la URL tokenizada del dashboard
- si se habilita Telegram, restringir `ALLOWED_CHAT_IDS`
- destruir el sandbox si deja de usarse

## Comandos de cierre

```bash
nemoclaw stop
nemoclaw nemoclaw-main destroy
unset NVIDIA_API_KEY
unset TELEGRAM_BOT_TOKEN
```
