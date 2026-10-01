# Estado de proveedores IA para Codex y Antigravity Manager

**Fecha:** 2026-09-06
**Alcance:** DeepSeek, OpenRouter, B.AI y Groq en la estacion Linux local.

## Resumen ejecutivo

Las cuatro credenciales estan presentes en `~/.dsh/.credentials.yaml` y las
cuatro APIs respondieron al listado de modelos. La compatibilidad directa con
Codex no es identica para todas:

| Proveedor | Credencial y modelos | Responses API | Estado en Codex |
| --- | --- | --- | --- |
| DeepSeek | OK, 3 modelos | Compatible, pero la cuenta devolvio `402 Insufficient Balance` en una generacion | Configurado como `deepseek-alt`; requiere recargar saldo |
| OpenRouter | OK, 430 modelos | Respuesta normal y streaming SSE verificados | Configurado como `openrouter`; requiere resolver el estado local de Codex para una prueba de agente completa |
| B.AI | OK, 48 modelos | Los modelos gratuitos indican que solo aceptan `chat/completions` | No se configura directamente en Codex; si esta contemplado por el adaptador de Antigravity Manager |
| Groq | OK, 14 modelos | Respuesta normal y streaming SSE verificados | Configurado como `groq`; requiere resolver el estado local de Codex para una prueba de agente completa |

Las claves no se incluyen en este repositorio ni deben copiarse a archivos
versionados.

## Restriccion de Codex

La configuracion vigente de Codex (`codex-cli 0.118.0`) admite solo
`wire_api = "responses"` para proveedores personalizados. Esta restriccion
esta documentada en la [referencia de configuracion de Codex](https://learn.chatgpt.com/docs/config-file/config-reference).

Consecuencias:

- OpenRouter y Groq pueden conectarse directamente a Codex porque exponen
  `POST /responses` compatible y streaming SSE.
- B.AI mantiene disponibles sus modelos gratuitos en OpenCode y en el
  adaptador de Antigravity Manager, pero sus modelos gratuitos probados
  (`glm-5.3-flash`, `qwen3.8-flash`, `hy3` y `mimo-v2.5`) rechazan
  `/responses` y piden usar `chat/completions`.
- DeepSeek acepta `/responses`, pero no puede generar hasta que la cuenta tenga
  saldo disponible.

## Configuracion local aplicada

El archivo de usuario `~/.codex/config.toml` conserva el predeterminado de
ChatGPT/OpenAI:

```toml
model = "gpt-5.6-terra"
model_provider = "openai"
```

Tambien tiene tres proveedores separados, todos con claves locales no
versionadas:

```toml
[model_providers.deepseek-alt]
base_url = "https://api.deepseek.com/"
wire_api = "responses"

[model_providers.openrouter]
base_url = "https://openrouter.ai/api/v1"
wire_api = "responses"

[model_providers.groq]
base_url = "https://api.groq.com/openai/v1"
wire_api = "responses"
```

El catalogo `~/.codex/models.json` se reconstruyo desde el catalogo embebido
de Codex para que sea compatible con la version instalada. Contiene modelos
oficiales mas estas opciones externas:

- `deepseek-v4-flash`, `deepseek-v4-pro`,
  `deepseek-v4-flash-vision-exp`
- `openrouter/free`
- `openai/gpt-oss-20b`
- `groq/compound-mini`

Se crearon copias previas de configuracion y catalogo bajo
`~/.codex/backup-*` antes de cada reparacion.

Cuando el runtime local de Codex quede sano, los comandos de seleccion son:

```bash
codex -c 'model_provider="openrouter"' \
  -c 'model_reasoning_effort="low"' \
  -m 'openrouter/free'

codex -c 'model_provider="groq"' \
  -c 'model_reasoning_effort="low"' \
  -m 'openai/gpt-oss-20b'

codex -c 'model_provider="deepseek-alt"' \
  -c 'model_reasoning_effort="low"' \
  -m 'deepseek-v4-flash'
```

## Validaciones ejecutadas

Se verifico lo siguiente sin mostrar ni registrar secretos:

- `GET /models` con autenticacion devolvio `200` para DeepSeek, OpenRouter,
  B.AI y Groq.
- OpenRouter y Groq devolvieron `200` tanto para una respuesta comun como para
  una respuesta con `stream: true` sobre `/responses`.
- DeepSeek devolvio `402 Insufficient Balance` al intentar generar una
  respuesta. La clave es valida; el bloqueo es de saldo.
- B.AI devolvio un error explicito de compatibilidad para sus modelos
  gratuitos: deben usarse mediante `/v1/chat/completions`.
- `http://127.0.0.1:3080/` es la interfaz de DeepSeek Harness activa, no un
  endpoint OpenAI/Responses para Codex: `/v1/models` devuelve `404` y no debe
  usarse como `base_url` de Codex.

La CLI de Codex alcanza los proveedores configurados y muestra el proveedor
seleccionado al iniciar. La prueba de agente completa no finalizo por problemas
locales independientes del proveedor:

- `state_5.sqlite` informa que una migracion ya aplicada no existe en la
  version actual del cliente.
- El cache de plugins contiene entradas incompatibles o no instaladas, y un
  MCP de Slack solicita autenticacion.

No se borro ni se modifico esa base de datos ni la configuracion de plugins.
Requiere una reparacion o actualizacion separada y prudente del cliente Codex.

## Antigravity Manager

La implementacion del enrutador de proveedores se encuentra en el repositorio
hermano `Antigravity-Manager`, no dentro de este repositorio `agentes`.
El trabajo pendiente alli incluye aproximadamente 1,100 lineas nuevas o
modificadas y un archivo nuevo:

- configuracion de proveedores externos y seleccion por coste o prioridad;
- adaptador que acepta APIs `responses` y `chat/completions`;
- aliases como `external:auto`, `cost:auto` y `cheapest`;
- carga de claves desde variables de entorno o `~/.dsh/.credentials.yaml`;
- refresco de modelos desde la interfaz y endpoint administrativo;
- UI en `ApiProxy` para activar proveedor, modelo, coste y prioridad.

El build frontend `npm run build` paso correctamente. La comprobacion Rust no
pudo completarse porque el sistema tiene `rustc 1.85.1`, mientras las
dependencias actuales requieren Rust `1.88` o posterior. No se debe declarar
esa parte lista para produccion hasta actualizar el toolchain y ejecutar
`cargo check`.

## Pendientes priorizados

1. Recargar saldo de DeepSeek para habilitar la generacion directa.
2. Reparar o actualizar el runtime local de Codex antes de declarar
   OpenRouter y Groq verificados de extremo a extremo desde un agente.
3. Actualizar Rust a `1.88+` y ejecutar `cargo check` en
   `Antigravity-Manager/src-tauri`.
4. Mantener B.AI gratuito en flujos que soporten `chat/completions` (OpenCode
   o Antigravity Manager), o usar un adaptador Responses si se necesita desde
   Codex.
