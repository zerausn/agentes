#!/usr/bin/env python3
"""
renovar_tokens_pc.py
Renueva los tokens de YouTube que tienen invalid_grant (0, 1, 2)
haciendo el flujo OAuth en el navegador del PC.
Luego los copia automáticamente al Note9 via ADB.

Uso: ./renovar_tokens_pc.py [0 1 2]   (sin args = renueva todos los revocados)
"""
import json
import subprocess
import sys
from pathlib import Path

CREDS_DIR = Path(__file__).parent / "credentials"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
NOTE9_SERIAL = "29396e8c1e3f7ece"
NOTE9_SDCARD = "/sdcard/Antigravity/agentes/youtube_uploader/credentials"
NOTE9_TERMUX = "files/home/agentes/youtube_uploader/credentials"

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
except ImportError:
    print("ERROR: Instala dependencias: pip install google-auth-oauthlib")
    sys.exit(1)


def adb(cmd_args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb", "-s", NOTE9_SERIAL] + cmd_args,
        capture_output=True, text=True
    )


def push_token_to_note9(token_path: Path, token_name: str):
    """Copia el token al sdcard y al home de Termux del Note9."""
    # Primero al sdcard (accesible sin run-as)
    r = adb(["push", str(token_path), f"{NOTE9_SDCARD}/{token_name}"])
    if r.returncode == 0:
        print(f"  → Copiado a sdcard/{token_name} ✅")
    else:
        print(f"  → ⚠️  Error copiando a sdcard: {r.stderr.strip()}")

    # También al home de Termux (ruta que usa proot-Debian como /root/...)
    r2 = adb(["shell", "run-as", "com.termux", "cp",
              f"../../../files/home/agentes/youtube_uploader/credentials/../../../sdcard/Antigravity/agentes/youtube_uploader/credentials/{token_name}",
              f"{NOTE9_TERMUX}/{token_name}"])
    # Método alternativo más robusto: push directo vía content provider
    # Intentar cp desde sdcard al home de Termux
    r3 = adb(["shell", f"run-as com.termux cp /sdcard/Antigravity/agentes/youtube_uploader/credentials/{token_name} {NOTE9_TERMUX}/{token_name}"])
    if r3.returncode == 0:
        print(f"  → Copiado a Termux home/{token_name} ✅")
    else:
        print(f"  → ⚠️  No se pudo copiar a Termux home (puede no ser necesario si usa sdcard): {r3.stderr.strip()}")


def check_token(i: int) -> str:
    """Retorna 'ok', 'expired_refreshable', 'invalid_grant' o 'missing'."""
    f = CREDS_DIR / f"token_{i}.json"
    if not f.exists():
        return "missing"
    try:
        creds = Credentials.from_authorized_user_file(str(f), SCOPES)
        if creds.valid:
            return "ok"
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                f.write_text(creds.to_json(), encoding="utf-8")
                return "refreshed"
            except Exception:
                return "invalid_grant"
        return "invalid_grant"
    except Exception:
        return "invalid_grant"


def renew_token(i: int):
    secrets = sorted(CREDS_DIR.glob("client_secret_*.json"))
    if i >= len(secrets):
        print(f"token_{i}: ❌ No hay client_secret_{i+1}.json")
        return False

    secret_file = secrets[i]
    token_file = CREDS_DIR / f"token_{i}.json"
    print(f"\n{'='*55}")
    print(f"  Renovando token_{i}.json")
    print(f"  Secret:  {secret_file.name}")
    print(f"{'='*55}")
    print("  → Se abrirá el navegador. Haz login con la cuenta correspondiente.")
    print("  → Después de autorizar, el token se guardará automáticamente.")
    print()

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        print(f"  ✅ token_{i}.json guardado localmente.")
        return True
    except Exception as e:
        print(f"  ❌ Error en autenticación: {e}")
        return False


def main():
    # Determinar qué tokens renovar
    if len(sys.argv) > 1:
        indices = [int(x) for x in sys.argv[1:]]
    else:
        # Auto-detectar los que tienen invalid_grant
        indices = []
        print("Verificando estado de los 4 tokens...")
        for i in range(4):
            status = check_token(i)
            symbol = {"ok": "✅", "refreshed": "✅ (refrescado)", "invalid_grant": "❌ revocado", "missing": "⚠️  falta"}.get(status, status)
            print(f"  token_{i}.json: {symbol}")
            if status in ("invalid_grant", "missing"):
                indices.append(i)

    if not indices:
        print("\n✅ Todos los tokens están vigentes. Nada que renovar.")
        return

    print(f"\n→ Se renovarán: {['token_'+str(i)+'.json' for i in indices]}")
    print("→ Se abrirá el navegador para cada cuenta. Ten las cuentas listas.")
    input("\nPresiona ENTER para comenzar...")

    renewed = []
    for i in indices:
        ok = renew_token(i)
        if ok:
            renewed.append(i)

    if not renewed:
        print("\n❌ No se renovó ningún token.")
        return

    # Subir tokens renovados al Note9
    print(f"\n{'='*55}")
    print("  Subiendo tokens renovados al Note9 via ADB...")
    print(f"{'='*55}")

    result = adb(["devices"])
    if NOTE9_SERIAL not in result.stdout:
        print("  ⚠️  Note9 no detectado por ADB. Copia los tokens manualmente:")
        for i in renewed:
            print(f"    {CREDS_DIR}/token_{i}.json → {NOTE9_SDCARD}/token_{i}.json")
        return

    for i in renewed:
        token_path = CREDS_DIR / f"token_{i}.json"
        print(f"\n  token_{i}.json:")
        push_token_to_note9(token_path, f"token_{i}.json")

    print(f"\n✅ Proceso completo. {len(renewed)}/{len(indices)} tokens renovados y subidos al Note9.")


if __name__ == "__main__":
    main()
