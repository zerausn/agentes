# YouTube Uploader — Documentación Técnica Completa
> **Versión:** 3.0 | **Mantenido por:** Antigravity AI Agent

---

## ¿Para qué sirve este sistema?

Automatiza la subida masiva de videos de performance artístico ("Performatic Writings") a YouTube. Los videos:
- Se suben como **privados** con fecha de publicación programada (17:45 hora Colombia).
- Se procesan de forma **reanudable**: si la conexión falla a mitad de subida, se retoma donde quedó.
- Rotan automáticamente entre múltiples llaves de API de Google Cloud cuando una se agota.

---

## 🗂️ Estructura de Archivos

| Archivo | Rol |
|---|---|
| `uploader.py` | Motor principal. Lee la cola y sube un video a la vez. |
| `video_scanner.py` | Escanea `ADM\Carpeta 1` y registra videos en `scanned_videos.json`. |
| `check_channel_videos.py` | Consulta la API de YouTube para marcar como ya subidos los videos que ya están en el canal (evita duplicados). |
| `clean_json.py` | Depura `scanned_videos.json`, eliminando rutas inválidas y aplicando exclusiones. |
| `config.json` | ⚠️ **No se sube a GitHub.** Contiene rutas privadas, exclusiones personales y metadatos. |
| `config.example.json` | Plantilla pública. Copiar como `config.json` y personalizar. |
| `scanned_videos.json` | Base de datos local: listado de videos con estado `uploaded: true/false`. |
| `quota_status.json` | Registro de llaves de API con cuota agotada (se resetea cada 24h). |
| `credentials/` | ⚠️ **No se sube a GitHub.** Contiene `client_secret_X.json` y `token_X.json`. |
| **`STOP`** | **Archivo de parada de emergencia.** Si existe, el uploader se detiene antes de la siguiente subida. |
| `STOP.txt` | Instrucciones para usar el mecanismo de parada. |

---

## 🛑 Cómo Detener la Subida (EMERGENCIA)

Crea un archivo llamado exactamente `STOP` (sin extensión) en esta misma carpeta:

**PowerShell (1 segundo):**
```powershell
# Para PARAR:
New-Item STOP -ItemType File

# Para REANUDAR:
Remove-Item STOP
```

El uploader detecta el archivo antes de cada video y se cierra limpiamente, sin corromper datos.

---

## 🔑 Flujo de Autenticación (OAuth2)

1. La primera vez con un nuevo `client_secret_X.json`, se abre un navegador para que el usuario autorice.
2. El token se guarda como `token_X.json` en `credentials/`. Las siguientes ejecuciones son automáticas.
3. El sistema necesita dos scopes: `youtube.upload` (para subir) y `youtube.readonly` (para leer el canal y evitar duplicados).

> **IA AGENT:** Si ves un error `insufficientPermissions`, el token fue generado con scopes antiguos. Borra todos los `token_*.json` de `credentials/` y vuelve a ejecutar. El usuario deberá re-autorizar una sola vez.

---

## 📅 Lógica de Programación de Fechas

La función `get_next_publish_date()` en `uploader.py` calcula la siguiente fecha disponible:
- Revisa el video subido con la fecha de publicación más tardía en `scanned_videos.json`.
- Añade exactamente 24 horas a esa fecha.
- Aplica la hora objetivo: **17:45, UTC-5 (Colombia)**.

Esto garantiza exactamente un video publicado por día.

---

## ⚙️ Gestión de Cuota de API

- Cada proyecto de Google Cloud tiene una cuota diaria de subidas (típicamente 6 videos de ~1GB).
- Cuando se agota, el script detecta el error HTTP 403 `quotaExceeded` y registra la llave en `quota_status.json`.
- Automáticamente rota al siguiente `client_secret_X.json` disponible.
- Al día siguiente, la cuota se resetea y todos los proyectos vuelven a estar disponibles.

---

## 🔄 Flujo de Trabajo Completo (Para IAs)

```
1. [OPCIONAL] Ejecutar check_channel_videos.py → Marca como 'uploaded: true' lo que ya está en YouTube.
2. Ejecutar clean_json.py → Quita entradas con rutas inexistentes y aplica exclusiones de config.json.
3. Ejecutar video_scanner.py → Agrega nuevos videos de ADM\Carpeta 1 a la base de datos.
4. Ejecutar uploader.py → Sube el siguiente video pendiente. Se repite hasta agotar la cola o la cuota.
```

Si el uploader se interrumpe, volver a ejecutar el paso 4. No hay pérdida de datos.

---

## 🚫 Política de Exclusiones

El scanner y el limpiador respetan las reglas de `config.json → scanner`:
- **`exclude_folders`**: Carpetas que se ignoran completamente (incluyendo `videos subidos exitosamente`).
- **`exclude_files`**: Archivos específicos que nunca se subirán.
- **`exclude_patterns`**: Si el nombre del archivo contiene cualquiera de estas cadenas, se omite.
- **`min_size_mb`**: Videos menores de 100MB se ignoran.

---

*Documentación generada y mantenida por Antigravity AI Agent. Actualizar esta sección después de cada modificación estructural.*
