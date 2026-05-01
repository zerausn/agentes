# Lista de Tareas Pendientes y Mejoras de Código (YouTube Uploader)

> [!NOTE]
> Este archivo es una lista viva de tareas por resolver, ideas de optimización y deudas técnicas **exclusivas para este repositorio (`youtube_uploader`)**. Cualquier IA que lea este proyecto debe consultar esta lista para conocer el contexto de lo que está pendiente por arreglar o mejorar.

---

## 📋 Tareas Pendientes

### 1. Sistema de Nudge (Empujoncito) para Videos Estancados
**Estado:** `Pendiente (Bloqueado por Permisos)`

**El Problema:**
*   A veces los videos se quedan sin arrancar su procesamiento en YouTube (SD/HD o Checks) durante semanas.
*   Existe un método manual automatizable ("Nudge") que consiste en actualizar levemente la descripción del video en YouTube (ej. añadir un espacio) para forzar a los servidores a re-evaluar el estado del procesamiento.

**El Bloqueo Actual:**
*   El intento de crear un script de `nudge` falló el 08-04-2026.
*   **Razón:** Los tokens actuales de OAuth (`token_0.json` - `token_3.json`) fueron autorizados con el scope básico `youtube.upload`. Este alcance es muy seguro, pero **prohíbe estrictamente** la edición de videos que ya están subidos a la plataforma.

**La Solución a Implementar:**
*   Es necesario actualizar la variable `SCOPES` en el código (por ejemplo, cambiar o añadir `https://www.googleapis.com/auth/youtube`) para otorgar permisos más amplios que permitan la edición.
*   Cuando esto se haga, el usuario tendrá que **re-autenticar manualmente** los 4 tokens a través de su navegador usando el `auth_manager.py`.
*   Una vez con los tokens adecuados, se deberá reactivar el script de "nudge" y establecer un mecanismo para ejecutarlo periódicamente y desatascar los videos críticos.
