#!/bin/bash
# setup_captura_4k.sh — instalación idempotente del capturador 4K en el proot Debian
# (se ejecuta como root dentro del proot; lo invoca driver_captura_4k.sh la 1a vez)
# Instala: firefox-esr + xvfb + xauth + libnss3-tools (certutil) + python3-venv + mitmproxy

set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="/root"

MITM_VENV="/root/venv-mitm"
PROFILE="/root/captura_firefox_profile"
CAP_BASE="/sdcard/Antigravity/captura_4k"
LOG_DIR="$CAP_BASE/logs"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_DIR/setup.log") 2>&1

echo "== setup_captura_4k: actualizando paquetes =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq firefox-esr || apt-get install -y -qq firefox xvfb xauth libnss3-tools python3-venv curl || true
apt-get install -y -qq xvfb xauth libnss3-tools python3-venv curl

echo "== setup_captura_4k: venv mitmproxy =="
if [ ! -x "$MITM_VENV/bin/mitmdump" ]; then
    python3 -m venv "$MITM_VENV"
    "$MITM_VENV/bin/pip" install -q --upgrade pip
    "$MITM_VENV/bin/pip" install -q mitmproxy websocket-client
fi
"$MITM_VENV/bin/mitmdump" --version | head -1

echo "== setup_captura_4k: CA de mitmproxy =="
if [ ! -f /root/.mitmproxy/mitmproxy-ca-cert.pem ]; then
    timeout 5 "$MITM_VENV/bin/mitmdump" -q -p 18080 >/dev/null 2>&1 || true
fi
if [ ! -f /root/.mitmproxy/mitmproxy-ca-cert.pem ]; then
    echo "[ERROR] No se generó el CA de mitmproxy."
    exit 1
fi

echo "== setup_captura_4k: perfil Firefox de captura =="
mkdir -p "$PROFILE"
cat > "$PROFILE/user.js" << 'EOF'
user_pref("network.proxy.type", 1);
user_pref("network.proxy.http", "127.0.0.1");
user_pref("network.proxy.http_port", 8080);
user_pref("network.proxy.ssl", "127.0.0.1");
user_pref("network.proxy.ssl_port", 8080);
user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.blocking_policy", 0);
user_pref("media.autoplay.enabled", true);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.page", 0);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.tabs.warnOnClose", false);
user_pref("app.update.auto", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
EOF

certutil -A -d "sql:$PROFILE" -n mitmproxy -t "C,," -i /root/.mitmproxy/mitmproxy-ca-cert.pem
echo "CA importado en el perfil:"
certutil -L -d "sql:$PROFILE" | grep -i mitmproxy || true

echo "== setup_captura_4k: verificación =="
command -v firefox >/dev/null && firefox --version | head -1
command -v Xvfb >/dev/null && echo "Xvfb OK"
"$MITM_VENV/bin/mitmdump" --version | head -1
echo ""
echo "setup_captura_4k COMPLETADO"