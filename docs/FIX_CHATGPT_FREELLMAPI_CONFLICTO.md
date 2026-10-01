# Fix: ChatGPT secuestrado por FreeLLMAPI — Incidente 2026-09-23

## Resumen del problema

La app de escritorio de **ChatGPT (Codex)** en Linux dejó de funcionar con la cuenta
de OpenAI del usuario. Síntomas:

- La app solo usaba FreeLLMAPI como backend
- El botón "Cerrar sesión" no respondía / quedaba atascado
- No era posible iniciar sesión con la cuenta normal de chatgpt.com
- El selector de modelo apuntaba a modelos de FreeLLMAPI (ej. `gpt-5.6-sol`)

---

## Causa raíz

FreeLLMAPI (proyecto open-source instalado en `/home/zerausn/Documents/Antigravity/freellmapi`)
modifica automáticamente la configuración de Codex al ejecutarse por primera vez.
Específicamente, escribe en **tres lugares** que persisten entre reinicios:

### 1. `~/.codex/config.toml` — el más crítico

FreeLLMAPI inyecta dos bloques delimitados por `# freellmapi:start ... # freellmapi:end`:

```toml
# freellmapi:start
model = "gpt-5.6-sol"
model_provider = "freellmapi"
model_context_window = 1048576
model_auto_compact_token_limit = 943718
tool_output_token_limit = 20000
# freellmapi:end
```

```toml
# freellmapi:start
[model_providers.freellmapi]
name = "FreeLLMAPI"
base_url = "http://localhost:3001/v1"
wire_api = "responses"
env_key = "FREELLMAPI_API_KEY"
requires_openai_auth = false
# freellmapi:end
```

Esto hace que Codex se conecte al servidor local de FreeLLMAPI (`localhost:3001`)
en lugar de los servidores de OpenAI, rompiendo la autenticación.

### 2. `~/.bashrc` — variable de entorno global

```bash
export FREELLMAPI_API_KEY=freellmapi-e4a75c8ce93566b376b308a66ac9b6bdcb64e45c44682d1b
```

Aunque Codex puede funcionar sin esta variable si el `config.toml` está limpio, su
presencia en el entorno puede interferir con otras herramientas.

### 3. `~/.config/Codex/` y `~/.config/orca/` — caché de sesión

La app almacena el estado de sesión en estas carpetas. Una vez corrompida la sesión
con FreeLLMAPI, aunque se limpie el config, la sesión en caché persiste hasta que
se borre este directorio.

---

## Proceso de diagnóstico

```bash
# 1. Ver qué procesos corrían en background desde el 18-Sep
ps aux | grep freellmapi
# → concurrently, tsx watch, vite, node — servidor FreeLLMAPI corriendo 5 días sin parar

# 2. Verificar variable de entorno
grep -i freellmapi ~/.bashrc
# → export FREELLMAPI_API_KEY=freellmapi-...

# 3. Encontrar la config corrupta
cat ~/.codex/config.toml | head -20
# → model_provider = "freellmapi"  ← CULPABLE PRINCIPAL

# 4. Backup original disponible
ls ~/.codex/config.toml.backup-*
# → config.toml.backup-2026-09-18T18-17-11-873Z ← antes de que FreeLLMAPI lo tocara
```

---

## Solución aplicada

### Paso 1 — Matar procesos de FreeLLMAPI

```bash
pkill -9 -f freellmapi
pkill -9 -f ChatGPT
```

### Paso 2 — Limpiar `~/.bashrc`

Eliminar la línea:
```bash
export FREELLMAPI_API_KEY=freellmapi-e4a75c8ce93566b376b308a66ac9b6bdcb64e45c44682d1b
```

### Paso 3 — Restaurar `~/.codex/config.toml` desde backup

```bash
cp ~/.codex/config.toml.backup-2026-09-18T18-17-11-873Z ~/.codex/config.toml
```

El backup tenía `model_provider = "openai"` — estado original correcto.

### Paso 4 — Borrar caché de sesión corrupta

```bash
rm -rf ~/.config/Codex
rm -rf ~/.config/orca
```

### Paso 5 — Relanzar ChatGPT

```bash
DISPLAY=:0 /bin/chatgpt &
```

La app inició mostrando la pantalla de login de OpenAI correctamente.

---

## Prevención futura

> **IMPORTANTE**: Si quieres usar FreeLLMAPI **a la vez** que ChatGPT/Codex,
> debes hacerlo con cuidado:

1. **No ejecutar `npm run dev` en freellmapi mientras usas Codex como agente**,
   ya que FreeLLMAPI detecta Codex y reescribe su `config.toml` automáticamente.

2. Si necesitas alternar entre OpenAI y FreeLLMAPI en Codex CLI, usa backups manuales:
   ```bash
   cp ~/.codex/config.toml ~/.codex/config.toml.openai-backup
   # para restaurar:
   cp ~/.codex/config.toml.openai-backup ~/.codex/config.toml
   ```

3. Los bloques `# freellmapi:start ... # freellmapi:end` en `config.toml` son
   la señal de que FreeLLMAPI tomó control. Basta eliminarlos para restaurar OpenAI.

---

## Archivos afectados

| Archivo | Qué hizo FreeLLMAPI | Acción de fix |
|---|---|---|
| `~/.codex/config.toml` | Inyectó bloques `freellmapi:start/end` | Restaurado desde backup del 18-Sep |
| `~/.bashrc` | Añadió `export FREELLMAPI_API_KEY=...` | Línea eliminada |
| `~/.config/Codex/` | Caché de sesión corrompida | Carpeta borrada |
| `~/.config/orca/` | Estado de sesión atascado | Carpeta borrada |

---

## Referencias

- FreeLLMAPI repo local: `/home/zerausn/Documents/Antigravity/freellmapi/`
- Backup original config: `~/.codex/config.toml.backup-2026-09-18T18-17-11-873Z`
- ChatGPT binary: `/lib/chatgpt/ChatGPT` → `/bin/chatgpt`
- Config oficial de Codex CLI: `~/.codex/config.toml`

---

*Documentado: 2026-09-23 | Fix aplicado por: Antigravity AI*
