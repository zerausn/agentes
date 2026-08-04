#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 0_RENOVAR_TOKEN_YT.sh — Renovar tokens OAuth de YouTube
# Abre el navegador Android para autenticar cada cuenta
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:/bin:/system/bin:/system/xbin"

# CRITICO: usar navegador nativo Android
export BROWSER=termux-open-url

# Pausa al salir para leer el resultado
trap 'echo ""; echo "========================================"; echo " RENOVACION FINALIZADA — cerrando en 20s"; echo "========================================"; sleep 20' EXIT

CREDS_DIR="/sdcard/Antigravity/agentes/youtube_uploader/credentials"
PYTHON_BIN="$PREFIX/bin/python3"

echo "========================================"
echo " RENOVAR TOKENS OAUTH YOUTUBE"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""
echo "Credenciales en: $CREDS_DIR"
echo ""

if [ ! -d "$CREDS_DIR" ]; then
  echo "ERROR: Directorio de credenciales no encontrado:"
  echo "  $CREDS_DIR"
  exit 1
fi

# Script de renovación inline
"$PYTHON_BIN" - <<'PYEOF'
import os
import sys
from pathlib import Path

# Detectar directorio de credenciales
creds_dir = Path("/sdcard/Antigravity/agentes/youtube_uploader/credentials")

# Buscar todos los client_secret_*.json
secrets = sorted(creds_dir.glob("client_secret_*.json"))

if not secrets:
    print("ERROR: No se encontraron archivos client_secret_*.json en:", creds_dir)
    sys.exit(1)

print(f"Encontradas {len(secrets)} cuentas de YouTube:")
for s in secrets:
    print(f"  - {s.name}")
print()

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("ERROR: Libreria google-auth-oauthlib no instalada.")
    print("Ejecuta: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

for i, secret_file in enumerate(secrets):
    token_file = creds_dir / f"token_{i}.json"
    print(f"[{i+1}/{len(secrets)}] Procesando: {secret_file.name}")
    print(f"           Token destino: {token_file.name}")

    # Intentar refrescar si ya existe
    creds = None
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
            if creds and creds.valid:
                print("  -> Token vigente, no es necesario renovar.")
                continue
            if creds and creds.expired and creds.refresh_token:
                from google.auth.exceptions import RefreshError
                try:
                    creds.refresh(Request())
                    token_file.write_text(creds.to_json(), encoding="utf-8")
                    print("  -> Token renovado automaticamente (refresh_token).")
                    continue
                except RefreshError:
                    print("  -> Token revocado. Se requiere login manual...")
                    creds = None
        except Exception as e:
            print(f"  -> Error leyendo token: {e}. Reautenticando...")
            creds = None

    # Necesita login nuevo
    print(f"  -> Abriendo navegador para login de cuenta {i+1}...")
    print("     (Se abrira Chrome/navegador en el S24 automaticamente)")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        print(f"  -> ¡Token guardado exitosamente en {token_file.name}!")
    except Exception as e:
        print(f"  -> Error en autenticacion: {e}")
        continue

    print()

print()
print("✅ Proceso de renovacion completado.")
PYEOF
