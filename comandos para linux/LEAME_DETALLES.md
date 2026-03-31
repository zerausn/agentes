# Detalles de la Configuración en Linux (Parrot OS 7)

## ¿Qué hicimos y por qué?

Dado que querías usar modelos de **Ollama** (los cuales descargas de su nube/registro oficial) directamente con **Claude Code**, nos encontramos con un problema de compatibilidad de idiomas:
- **Claude Code** solo sabe hablar el idioma de Anthropic (API `v1/messages`).
- **Ollama** solo entiende su propia API y el idioma de OpenAI (API `v1/chat/completions`).

Para solucionarlo sin interferir con la configuración de Windows (donde usas Antigravity-Manager), implementamos una solución **nativa para Linux** usando **LiteLLM**. 
LiteLLM es un proxy ligero que se pone en medio, escucha a Claude Code en idioma Anthropic, y le traduce la petición a Ollama en idioma OpenAI al instante.

## Estructura de esta carpeta

1. **`setup_claude_ollama.sh`**: Es el script automatizador principal. 
2. **`LEAME_DETALLES.md`**: Este archivo explicativo.

## ¿Qué hace exactamente el script de Bash?

Al inspeccionar el código del script `setup_claude_ollama.sh`, puedes ver que realiza los siguientes pasos de forma segura:

1. **Validación de Dependencias**: Revisa si tienes `python3` y `venv` instalados en tu Parrot OS 7. Al ser una distro basada en Debian 12+, es mandatorio usar entornos virtuales para no romper el sistema (`PEP-668`). Si no los tienes, usa `apt update` y los instala.
2. **Entorno Virtual Aislado**: Crea una burbuja segura en `~/.claude_ollama_venv` para instalar las librerías sin tocar tu Parrot OS.
3. **Instalación del Traductor**: Descarga e instala `litellm[proxy]` dentro de ese entorno virtual.
4. **Ejecución del Proxy**: Levanta el servidor traductor en el puerto `4000` apuntando directamente a tu modelo de Ollama local (por ejemplo `ollama_chat/qwen2.5-coder:7b`).

## ¿Cómo usarlo?

1. Abre una terminal y asegúrate de haber descargado tu modelo Cloud de Ollama. Si no lo tienes, descárgalo (ej. `ollama pull qwen2.5-coder:7b`).
2. Dale permisos de ejecución al script si aún no los tiene:
   ```bash
   chmod +x "comandos para linux/setup_claude_ollama.sh"
   ```
3. Ejecuta el script:
   ```bash
   "./comandos para linux/setup_claude_ollama.sh"
   ```
4. El script se quedará "escuchando" en esa terminal. 
5. Abre **una nueva terminal**, copia y pega las variables de entorno que te dio el script en pantalla, y lanza Claude Code:
   ```bash
   export ANTHROPIC_API_KEY="sk-local-ollama"
   export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
   claude
   ```

Con esto logramos una separación total entre el entorno de desarrollo que tenías originalmente en Windows y tu nuevo entorno hiper-optimizado en Linux Parrot OS 7.
