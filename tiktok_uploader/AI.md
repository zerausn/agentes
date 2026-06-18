# TikTok Uploader — AI Instructions

Subproyecto de publicación de videos en TikTok via Content Posting API.

## Antes de editar
- Lee `AGENTS.md` en la raiz del repo.
- Lee `AI.md` en la raiz del repo.
- Revisa `docs/` local para estado y decisiones.

## Stack
- Flask 3.x con ProxyFix
- TikTok Content Posting API v2
- Ngrok tunnel para desarrollo local (con authtoken)
- GitHub Pages para website estático

## Reglas
- No subir CLIENT_SECRET ni tokens a git.
- No cambiar redirect URI dinámica sin registrar motivo.
- Si el tunel cambia, actualizar Redirect URI en portal TikTok.
- Cualquier cambio en scopes debe reflejarse en review description y website.

## Mapas
- `app.py` — rutas Flask, lógica OAuth y publicación
- `config.py` — credenciales y URLs desde env vars
- `docs/ARCHITECTURE.md` — diseño del sistema
- `docs/DECISIONS.md` — decisiones registradas
- `docs/PROGRESS.md` — estado actual

## Estado de Integración de TikTok Uploader (Actualización 18 de Junio 2026)
Se ha implementado el flujo OAuth de "Login with TikTok" localmente usando una aplicación Flask y un túnel inverso (Ngrok) para sortear las restricciones de desarrollo en local, junto con un entorno espejo en GitHub Pages para facilitar la revisión 24/7 por parte de los moderadores de TikTok.

### Infraestructura Implementada
1. **Servidor Local (Flask)**:
   - Se ejecuta mediante `tmux` y `nohup` (`tmux new-session -d -s flask_session 'python3 app.py'`).
   - Expuesto en `127.0.0.1:8080`.
2. **Túnel de Desarrollo (Ngrok)**:
   - Resuelve el error 502/404 corriendo forzosamente hacia IPv4 (`ngrok http 127.0.0.1:8080`).
   - Para que el proceso no muera por la terminal en fondo, se debe ejecutar dentro de `tmux`: `tmux new-session -d -s ngrok_session 'ngrok http 127.0.0.1:8080'`.
3. **Página Espejo (GitHub Pages)**:
   - Se modificó `index.html` en el repositorio base (`zerausn.github.io/agentes`) para que el botón "Login with TikTok" apunte al flujo OAuth de TikTok.
   - Se creó `callback.html` como página estática de éxito para que el revisor de TikTok pueda aprobar el flujo de Login sin que el servidor local de la máquina del desarrollador deba estar encendido.

### Problema Activo: Rechazo de `client_key`
Durante la última prueba local de integración, la API de autorización de TikTok arrojó un error que indica explícitamente:
`No se pudo iniciar sesión con TikTok, probablemente, debido a ajustes específicos de la aplicación. Si eres un desarrollador, corrige lo siguiente y vuelve a intentarlo: client_key`.

**Causas potenciales a revisar por el usuario en el Portal de Desarrolladores de TikTok:**
- **Cuenta equivocada en navegador:** Estar logueado en tiktok.com con una cuenta personal en lugar de la cuenta Sandbox oficial (`performaticwritingscali`).
- **Falta "Login Kit":** El producto "Login Kit" puede no haber sido añadido a la App "Uploaderbot" en el portal de developers.tiktok.com.
- **Plataforma errónea:** La aplicación debe tener añadida la plataforma "Web".
- **Llave regenerada o inhabilitada:** Aunque la llave actual (`awhfxd65i4i468x8`) hace match con el archivo `.env`, puede haber sido bloqueada por la plataforma de revisión.

### Flujo de Demostración para el Video de TikTok
Una vez resuelto el error de `client_key`, se debe grabar un video mostrando la URL de ngrok, pero empezando desde `zerausn.github.io/agentes`.
Ambos Redirect URIs deben estar en el portal de TikTok simultáneamente:
1. `https://zerausn.github.io/agentes/callback.html` (para el revisor)
2. `https://[SUBDOMINIO-NGROK].ngrok-free.dev/callback` (para el entorno local de grabación)
