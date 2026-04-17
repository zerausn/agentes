import json
import logging
from pathlib import Path
from uploader import get_authenticated_service, SCOPES

logging.basicConfig(level=logging.INFO, format="%(message)s")

def refresh():
    BASE_DIR = Path(__file__).resolve().parent
    CREDENTIALS_DIR = BASE_DIR / "credentials"
    
    print("\n==================================")
    print(" INICIANDO RENOVACION DE 4 TOKENS")
    print("==================================\n")
    
    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    
    for idx, client_name in enumerate(client_files):
        secret_path = CREDENTIALS_DIR / client_name
        token_path = CREDENTIALS_DIR / f"token_{idx}.json"
        
        # Eliminar el token viejo si existe
        if token_path.exists():
            print(f"- Borrando token expirado: {token_path.name}")
            token_path.unlink()
            
        print(f"\n>> Solicitando autorizacion para cuenta {idx+1} de {len(client_files)} ({client_name})...")
        print(">> Revisa la ventana de tu navegador (Edge).")
        
        # Esto lanzara el navegador y esperara
        get_authenticated_service(secret_path, token_path, SCOPES)
        print(f"[*] ¡Cuenta {idx+1} autenticada con exito!")

    print("\n[OK] Todos los tokens han sido renovados.")
    input("Presiona Enter para cerrar esta ventana...")

if __name__ == "__main__":
    refresh()
