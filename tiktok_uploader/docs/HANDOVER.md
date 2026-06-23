# TikTok Uploader — Handover

## Current State (2026-06-18)

App review resubmission #2 was **rejected** with 3 issues:
1. Login entry point not working (trapdoor.sh down)
2. App icon allegedly missing from Privacy/Terms
3. Review description insufficient

## Critical Context

### Running Services
- **Flask**: Running on Note9 (192.168.1.7:8080) in tmux session `tiktok`
- **Tunnel**: `https://gravy-diaper-refrain.ngrok-free.dev` (via ngrok on Note9, stable URL)
- **Website**: `https://zerausn.github.io/agentes/`
- **PC services**: Stopped (localhost.run tunnel and local Flask killed)

### Note9 Access
```bash
ssh -p 8022 u0_a289@192.168.1.7
# Inside Termux:
tmux attach -t tiktok          # see Flask + ngrok status
proot-distro login debian       # enter Debian proot
```

### On the Note9
- Flask runs inside Debian proot at `/root/agentes/tiktok_uploader/`
- ngrok runs in Debian proot with authtoken
- Both managed by tmux session `tiktok` (windows: `flask`, `ngrok`)
- Auto-start on boot: `~/.termux/boot/start_tiktok.sh`
- Manual restart: `~/.shortcuts/Iniciar_TikTok.sh`
- ngrok API: `http://127.0.0.1:4040` (on Note9)

### Branch Structure
- `tiktok` — current documentation branch (from `main`)
- `main` — tiktok_uploader code (PR #3 merged)
- `gh-pages` — GitHub Pages website deployed

### Credentials (TikTok Developers)
- App: Uploaderbot
- Client Key: `awhfxd65i4i468x8`
- Client Secret: in `.env.local` (DO NOT commit)
- Sandbox account: `performaticwritingscali`

### Tunnel Status
- localhost.run is active; URL is `https://87a5f16efde353.lhr.life`
- Flask accessible through tunnel (HTTP 200 verified)
- **Redirect URI in portal must match current tunnel**: `https://87a5f16efde353.lhr.life/callback`
- If tunnel dies: `setsid ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -R 80:localhost:8080 nokey@localhost.run`

## What Needs to Happen

### Before Resubmitting Review
1. Update `index.html` login button URL → current tunnel URL
2. Push updated website to `gh-pages` branch
3. Write comprehensive review description (text ready below)
4. In TikTok Portal: update Redirect URI, App icon, App description, Website URL fields
5. Resubmit app review

### After Approval
- Enable monetization for the creator account
- Move from sandbox to production
- Consider custom domain or stable tunnel solution (e.g., ngrok with fixed subdomain, or a VPS)

## Review Description (copy-paste ready)

```
Uploaderbot es una aplicación web que permite a creadores de contenido autenticarse con su cuenta de TikTok y publicar videos directamente a través de la Content Posting API oficial de TikTok.

### Flujo de la aplicación:
1. El usuario visita uploaderbot.com e inicia sesión con su cuenta de TikTok mediante OAuth 2.0.
2. Una vez autenticado, selecciona o arrastra un archivo de video MP4 desde su dispositivo.
3. El usuario puede ajustar el título del video y la configuración de privacidad.
4. La aplicación sube el video a TikTok y lo publica en el perfil del usuario.

### Scopes solicitados y su uso:
- user.info.basic: Se utiliza para identificar al usuario (open_id) y mostrar su nombre de usuario en la interfaz después del inicio de sesión. Solo se accede a este dato una vez durante el callback de OAuth.
- video.upload: Necesario para inicializar la subida de videos y obtener la URL de carga desde TikTok. Se usa cuando el usuario sube un archivo de video.
- video.publish: Necesario para publicar el video subido en el perfil de TikTok del usuario autenticado. Se ejecuta solo cuando el usuario hace clic en "Publicar".

### Manejo de datos:
- Los tokens de acceso se mantienen únicamente en la memoria de la aplicación durante la sesión del usuario y se descartan al cerrar sesión o al expirar la sesión.
- No se almacenan videos, tokens ni datos personales de forma persistente en ningún servidor o base de datos.
- No se comparten datos con terceros. Los datos solo se comunican con las APIs oficiales de TikTok (ByteDance) durante la autenticación y publicación.

### Público objetivo:
Creadores de contenido que desean automatizar o simplificar la publicación de videos en TikTok desde una interfaz web.
```

## Termux Widget (cómo agregar shortcuts correctamente)

El widget de Termux lee shortcuts de `~/.shortcuts/` (`/data/data/com.termux/files/home/.shortcuts/`).

### Problema: SELinux entre UIDs
- SSH/scp como `u0_a289` crea archivos con contexto SELinux de ese usuario.
- El widget corre como `u0_a291` (UID interno de `com.termux`).
- `u0_a291` NO puede leer archivos creados por `u0_a289` aunque tengan `chmod 755`.
- El widget silenciosamente omite los archivos ilegibles (sin error visible).

### Forma correcta de agregar un shortcut
```bash
# 1. Leer contenido del archivo a añadir
CONTENT=$(cat ~/.shortcuts/mi_script.sh)

# 2. Crear el archivo desde run-as com.termux (contexto SELinux correcto)
adb shell "run-as com.termux sh -c 'cat > /data/data/com.termux/files/home/.shortcuts/mi_script.sh' << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
echo "Hello from widget"
EOF
chmod 755 /data/data/com.termux/files/home/.shortcuts/mi_script.sh"

# 3. Si el archivo ya existe (creado por otro usuario), copiarlo preservando contexto:
adb shell run-as com.termux cp <origen> /data/data/com.termux/files/home/.shortcuts/

# 4. Hacer scroll en el widget para verlo (no necesita re-agregarse)
```

### Refresh del widget
- Botón de refresh (↻) actualiza la vista pero NO reescanea el directorio.
- Para re-escaneo completo: remover el widget de la pantalla y agregarlo de nuevo:
  ```bash
  adb shell pm clear com.termux.widget
  # Luego re-agregar manualmente desde Widgets → Termux Widget
  ```

### Directorios alternativos que el widget puede leer
- `/data/data/com.termux/.shortcuts/` (legado, no siempre accesible desde `run-as`)
- `/data/user/0/com.termux/.shortcuts/` (equivalente al anterior, no recomendado)
- El widget prioriza `~/.shortcuts/` del home de Termux.

## Useful Commands
```bash
# Start Flask
cd /home/zerausn/Documents/Antigravity/agentes/tiktok_uploader
source venv/bin/activate
setsid python3 -u app.py > /tmp/flask.log 2>&1 &

# Start tunnel
setsid ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -R 80:localhost:8080 nokey@localhost.run > /tmp/tunnel.log 2>&1 &
TUNNEL_URL=$(grep -oP 'https://[a-z0-9]+\.lhr\.life' /tmp/tunnel.log | head -1)

# Verify
curl -s -o /dev/null -w "%{http_code}" "$TUNNEL_URL/"

# Deploy to gh-pages
git checkout gh-pages
# edit index.html login URL
git commit -am "update login URL"
git push origin gh-pages
```
