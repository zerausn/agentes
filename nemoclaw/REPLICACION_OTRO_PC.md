# Replicacion de NemoClaw en Otro PC

## Requisitos minimos

- Linux compatible
- 8 GB de RAM minimo; 16 GB recomendado
- 20 GB libres minimo; 40 GB recomendado
- acceso a internet
- una `NVIDIA_API_KEY` valida

## 1. Preparar Node 22

Instalar `nvm` para el usuario actual:

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install 22
nvm alias default 22
node --version
npm --version
```

Esperado:

- Node 22.x
- npm 10.x o superior

## 2. Instalar Docker real

Si `docker --version` muestra algo como "Emulate Docker CLI using podman", no sirve como ruta principal para este caso.

Instalacion recomendada en Debian/Parrot:

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker "$USER"
newgrp docker
docker version
```

## 3. Instalar OpenShell

No depender de `gh auth login`.
Instalar `openshell` por release directo:

```bash
tmpdir="$(mktemp -d)"
asset="openshell-x86_64-unknown-linux-musl.tar.gz"
checksums="openshell-checksums-sha256.txt"
curl -fsSL "https://github.com/NVIDIA/OpenShell/releases/latest/download/$asset" -o "$tmpdir/$asset"
curl -fsSL "https://github.com/NVIDIA/OpenShell/releases/latest/download/$checksums" -o "$tmpdir/$checksums"
(cd "$tmpdir" && grep -F "$asset" "$checksums" | sha256sum -c -)
tar xzf "$tmpdir/$asset" -C "$tmpdir"
mkdir -p "$HOME/.local/bin"
install -m 755 "$tmpdir/openshell" "$HOME/.local/bin/openshell"
export PATH="$HOME/.local/bin:$PATH"
openshell --version
```

## 4. Instalar NemoClaw

Clonar repo:

```bash
git clone https://github.com/NVIDIA/NemoClaw.git
cd NemoClaw
```

En esta instalacion se encontro recursion del `prepare`. Si vuelve a pasar, usar una copia saneada y luego verificar que `nemoclaw --version` funcione.

## 5. Verificar antes del onboarding

```bash
source ~/.bashrc
docker version
openshell doctor check
nemoclaw --version
```

## 6. Ejecutar onboarding

No guardar la key en el repo.
Usar solo variables de entorno temporales:

```bash
export NVIDIA_API_KEY='TU_KEY'
export NEMOCLAW_PROVIDER=build
export NEMOCLAW_MODEL='nvidia/nemotron-3-super-120b-a12b'
export NEMOCLAW_SANDBOX_NAME='nemoclaw-main'
export NEMOCLAW_POLICY_MODE=skip
nemoclaw onboard --non-interactive
```

## 7. Si el gateway parece fallar

Validar:

```bash
openshell doctor check
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

Puede pasar que el primer arranque solo este descargando imagenes y tarde mas de lo esperado.

## 8. Verificar sandbox

```bash
nemoclaw status
nemoclaw nemoclaw-main status
nemoclaw nemoclaw-main connect
```

## 9. UI local

El panel normalmente queda en:

```text
http://127.0.0.1:18789/
```

## 10. Telegram

No intentar Telegram hasta tener:

- `nemoclaw-main` listo
- `TELEGRAM_BOT_TOKEN`
- `NVIDIA_API_KEY`

Usar la guia `TELEGRAM.md`.

## 11. Nota de compatibilidad observada

En este host se observo que el bridge oficial de Telegram necesitaba forzar IPv4 en `https.request` para hablar con `api.telegram.org`.

Si el bot falla con errores tipo:

- `ENETUNREACH`
- `ETIMEDOUT`

pero `curl https://api.telegram.org/.../getMe` funciona, revisar la guia `TELEGRAM.md` y aplicar el hotfix local al script `telegram-bridge.js`.
