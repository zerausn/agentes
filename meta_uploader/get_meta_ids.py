import os
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # Asumimos que podemos leer manual si no hay dotenv

def get_tokens_manually():
    token = ""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(base_dir, ".env")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("META_PAGE_TOKEN="):
                    token = line.split("=", 1)[1].strip()
    except Exception as e:
        print(f"Error open: {e}")
    return token

def main():
    TOKEN = os.environ.get("META_PAGE_TOKEN", "")
    if not TOKEN:
        TOKEN = get_tokens_manually()
        
    if not TOKEN:
        print("❌ Error: No se detectó META_PAGE_TOKEN en el archivo .env. Asegúrate de haberlo pegado en la primera línea.")
        return

    print("🔎 Consultando los servidores de Meta para extraer tus IDs automáticamente...\n")
    url_fb = "https://graph.facebook.com/v19.0/me/accounts"
    res = requests.get(url_fb, params={"access_token": TOKEN}).json()

    if "data" in res and len(res["data"]) > 0:
        for page in res["data"]:
            page_name = page.get("name")
            page_id = page.get("id")
            print(f"✅ Página encontrada: '{page_name}'")
            print(f"👉 META_FB_PAGE_ID={page_id}")
            
            # Buscar IG account conectada a esta página
            url_ig = f"https://graph.facebook.com/v19.0/{page_id}"
            res_ig = requests.get(url_ig, params={"fields": "instagram_business_account", "access_token": TOKEN}).json()
            
            if "instagram_business_account" in res_ig:
                ig_id = res_ig["instagram_business_account"].get("id")
                print(f"✅ Instagram emparejado a la página de FB encontrado.")
                print(f"👉 META_IG_USER_ID={ig_id}\n")
                
                print("====================================")
                print("¡Copia esto y reemplázalo en tu .env!")
                print("====================================")
                print(f"META_FB_PAGE_ID={page_id}")
                print(f"META_IG_USER_ID={ig_id}")
            else:
                print(f"❌ La página '{page_name}' no reportó cuenta de Instagram enlazada por API.")
    else:
        print("❌ Operación fallida o no se encontraron páginas.")
        print(f"Respuesta de Meta: {res}")

if __name__ == "__main__":
    main()
