import sys
import logging
from pathlib import Path
from uploader import get_authenticated_service

# Configuracion de logging basica para consola
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    """
    Script para generar o renovar tokens de Google OAuth de forma manual.
    Uso: python auth_manager.py <numero_de_llave>
    Ejemplo: python auth_manager.py 1  --> (usa client_secret_1.json y genera token_0.json)
    """
    if len(sys.argv) < 2:
        print("\n[!] Error: Debes especificar el numero de llave.")
        print("Uso: python auth_manager.py <numero_de_llave>")
        print("Ejemplo: python auth_manager.py 1\n")
        return

    try:
        key_num = int(sys.argv[1])
        client_idx = key_num - 1
        
        base_dir = Path(__file__).resolve().parent
        credentials_dir = base_dir / "credentials"
        
        client_secret = credentials_dir / f"client_secret_{key_num}.json"
        token_file = credentials_dir / f"token_{client_idx}.json"

        if not client_secret.exists():
            print(f"\n[!] Error: No se encuentra el archivo {client_secret}")
            return

        print(f"\n--- Iniciando Autenticacion Manual (Llave {key_num}) ---")
        print(f"Usando: {client_secret.name}")
        print(f"Destino: {token_file.name}")
        print("---------------------------------------------------\n")

        get_authenticated_service(client_secret, token_file)

        print(f"\n[+] EXITO: Token generado correctamente en {token_file}\n")

    except ValueError:
        print("\n[!] Error: El numero de llave debe ser un entero (1, 2, 3...).\n")
    except Exception as e:
        print(f"\n[!] Error durante la autenticacion: {e}\n")

if __name__ == "__main__":
    main()
