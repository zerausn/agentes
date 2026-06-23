"""
Demo script for TikTok Uploaderbot - muestra el flujo completo de API
Ejecutar: python3 demo_script.py
"""
import json
from config import CLIENT_KEY, REDIRECT_URI, SCOPES

print("=" * 60)
print("  UPLOADERBOT - TikTok API Demo")
print("  Flujo completo de integracion")
print("=" * 60)

# Paso 1: Configuracion
print("\n[Paso 1] Configuracion de la app")
print("-" * 40)
config = {
    "client_key": CLIENT_KEY,
    "redirect_uri": REDIRECT_URI,
    "scopes": SCOPES,
}
print(json.dumps(config, indent=2))

# Paso 2: OAuth Login
print("\n[Paso 2] URL de autorizacion OAuth")
print("-" * 40)
auth_url = (
    "https://www.tiktok.com/v2/auth/authorize/"
    f"?client_key={CLIENT_KEY}"
    "&response_type=code"
    f"&scope={','.join(SCOPES)}"
    f"&redirect_uri={REDIRECT_URI}"
    "&state=CSRF_TOKEN_UNICO"
)
print(f"URL: {auth_url[:80]}...")
print("-> Usuario autoriza la app")
print("-> TikTok redirige a /callback?code=AUTHORIZATION_CODE")

# Paso 3: Token exchange
print("\n[Paso 3] Intercambio de codigo por access_token")
print("-" * 40)
token_request = {
    "method": "POST",
    "url": "https://open.tiktokapis.com/v2/oauth/token/",
    "body": {
        "client_key": CLIENT_KEY,
        "client_secret": "***",
        "code": "AUTHORIZATION_CODE",
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    },
}
print(json.dumps(token_request, indent=2))
print("\n-> Respuesta:")
token_response = {
    "access_token": "act.example123...",
    "open_id": "op123456...",
    "token_type": "Bearer",
    "expires_in": 86400,
}
print(json.dumps(token_response, indent=2))

# Paso 4: Query Creator Info
print("\n[Paso 4] Consultar info del creador")
print("-" * 40)
print("GET https://open.tiktokapis.com/v2/post/publish/creator_info/query/")
print("Authorization: Bearer {access_token}")
creator_info = {
    "data": {
        "creator_username": "performaticwritingscali",
        "privacy_level_options": [
            "PUBLIC_TO_EVERYONE",
            "MUTUAL_FOLLOW_FRIENDS",
            "SELF_ONLY",
        ],
        "max_video_post_duration_sec": 600,
    }
}
print(f"Respuesta: {json.dumps(creator_info, indent=2)}")
print("-> Duracion maxima permitida: 600 segundos (10 min)")

# Paso 5: Init Upload
print("\n[Paso 5] Inicializar subida de video")
print("-" * 40)
init_request = {
    "method": "POST",
    "url": "https://open.tiktokapis.com/v2/post/publish/video/init/",
    "headers": {
        "Authorization": "Bearer {access_token}",
        "Content-Type": "application/json",
    },
    "body": {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": 5242880,  # 5MB ejemplo
            "chunk_size": 5242880,
            "total_chunk_count": 1,
        }
    },
}
print(json.dumps(init_request, indent=2))
print("\n-> Respuesta:")
init_response = {
    "data": {
        "upload_url": "https://upload.tiktokapis.com/video/?upload_id=...",
        "publish_id": "pub123456...",
    }
}
print(json.dumps(init_response, indent=2))

# Paso 6: Upload file
print("\n[Paso 6] Subir archivo de video")
print("-" * 40)
upload_request = {
    "method": "PUT",
    "url": "{upload_url}",
    "headers": {
        "Content-Range": "bytes 0-5242879/5242880",
        "Content-Type": "video/mp4",
    },
    "body": "<binary video data>",
}
print(json.dumps(upload_request, indent=2))
print("\n-> Respuesta: HTTP 200 OK")

# Paso 7: Publish
print("\n[Paso 7] Publicar video")
print("-" * 40)
publish_request = {
    "method": "POST",
    "url": "https://open.tiktokapis.com/v2/post/publish/video/publish/",
    "headers": {
        "Authorization": "Bearer {access_token}",
        "Content-Type": "application/json",
    },
    "body": {
        "post_info": {
            "publish_id": "pub123456...",
            "privacy_level": "SELF_ONLY",
            "title": "Video de prueba - Uploaderbot",
        }
    },
}
print(json.dumps(publish_request, indent=2))
print("\n-> Respuesta:")
publish_response = {
    "data": {"status": "published", "video_id": "vid123456..."},
}
print(json.dumps(publish_response, indent=2))

# Resumen
print("\n" + "=" * 60)
print("  FLUJO COMPLETO DEMOSTRADO:")
print("  1. Configuracion de la app en TikTok Developers")
print("  2. Autorizacion OAuth (Login Kit)")
print("  3. Obtencion de access_token")
print("  4. Consulta de informacion del creador")
print("  5. Inicializacion de subida de video")
print("  6. Subida del archivo de video")
print("  7. Publicacion del video en TikTok")
print("=" * 60)
