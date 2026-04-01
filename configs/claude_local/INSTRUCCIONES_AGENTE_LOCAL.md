# Instrucciones para el Agente Local (Claude Code + Ollama)

Este documento sirve como guía para que cualquier IA o desarrollador pueda retomar y mantener la configuración del agente local.

## Arquitectura del Sistema

El agente utiliza una configuración de "puente" para conectar Claude Code (que usa el protocolo de Anthropic) con modelos locales o en la nube a través de Ollama.

1. **Claude Code CLI**: Interfaz principal del agente.
2. **LiteLLM (Proxy)**: Traduce las peticiones de Claude Code al formato de Ollama.
3. **Ollama**: Gestiona los modelos (locales y cloud).

## Componentes del Configuración

- **`litellm_config.yaml`**: Define el mapeo de modelos y reglas de traducción (como `drop_params: true`).
- **`CLAUDE.md`**: Define la personalidad, idioma (Español LatAm) y responsabilidades del agente.

## Cómo Iniciar el Agente

1. **Asegurar que Ollama esté corriendo**: `ollama serve`.
2. **Iniciar el Proxy LiteLLM**:
   Desde la carpeta del repositorio, ejecutar:
   ```powershell
   & ".venv\Scripts\litellm.exe" --config configs/claude_local/litellm_config.yaml --port 4000
   ```
3. **Iniciar Claude Code**:
   En una nueva terminal, con las variables de entorno configuradas:
   ```powershell
   $env:ANTHROPIC_BASE_URL="http://localhost:4000"; $env:ANTHROPIC_API_KEY="ollama"; claude
   ```

## Modelo Actual Seleccionado
Actualmente configurado para usar **`gpt-oss:120b-cloud`** debido a limitaciones de hardware local (GPU integrada Intel Iris Xe). 

## Notas de Hardware (Intel Iris Xe)
- Se identificó que con 64GB de RAM, los modelos de >7B funcionan mejor en CPU si no se fuerza el uso de GPU.
- Se recomienda el uso de variables de entorno `OLLAMA_NUM_GPU=1` y `OLLAMA_INTEL_GPU="1"` para optimizar el rendimiento en gráficas integradas.

## Resumen de Sesiones anteriores
El historial completo de decisiones y cambios se encuentra en `docs/HISTORIAL_CONVERSACIONES.md`.
