import os
import shutil
import json
import time
import httplib2
from datetime import datetime, timedelta, timezone
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# Configuración y Scope para YouTube Upload
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
JSON_DB = 'scanned_videos.json'
CREDENTIALS_DIR = 'credentials'

def get_next_publish_date(videos):
    """Calcula la próxima fecha de publicación basándose en los videos ya programados."""
    max_date = None
    for v in videos:
        if v.get('uploaded') and v.get('publishAt'):
            try:
                # Parsear el ISO8601 (ej. 2026-04-02T15:00:00Z) a formato UTC
                dt_str = v['publishAt'].replace('Z', '+00:00')
                dt_obj = datetime.fromisoformat(dt_str)
                if max_date is None or dt_obj > max_date:
                    max_date = dt_obj
            except ValueError:
                pass

    now_utc = datetime.now(timezone.utc)
    colombia_tz = timezone(timedelta(hours=-5)) # Hora de Colombia
    now_col = now_utc.astimezone(colombia_tz)
    
    # Si no hay programaciones futuras o nunca hemos programado nada:
    # Programar para mañana a las 5:45 PM (17:45) hora de Colombia
    if max_date is None or max_date < now_utc:
        tomorrow_col = now_col + timedelta(days=1)
        next_pub_col = tomorrow_col.replace(hour=17, minute=45, second=0, microsecond=0)
        return next_pub_col.astimezone(timezone.utc)
    else:
        # Si ya hay un video programado, sumarle exactamente 1 día y forzarlo a las 17:45 Colombia
        max_col = max_date.astimezone(colombia_tz)
        next_pub_col = max_col + timedelta(days=1)
        next_pub_col = next_pub_col.replace(hour=17, minute=45, second=0, microsecond=0)
        return next_pub_col.astimezone(timezone.utc)

def get_authenticated_service(client_secret_file, creds_cache_file):
    """Autentica o refresca el token con un json de cliente particular."""
    creds = None
    if os.path.exists(creds_cache_file):
        creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            # Para evitar que el puerto local falle, usamos run_local_server
            creds = flow.run_local_server(port=0)
        with open(creds_cache_file, 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def upload_video(youtube, file_path, title, description, category, tags, publish_at_dt):
    """Sube un video de forma fraccionada y lo programa."""
    
    # El formato que acepta YouTube para publishAt es ISO 8601
    publish_at_str = publish_at_dt.isoformat().replace('+00:00', 'Z')
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category
        },
        'status': {
            # IMPORTANTE: Para usar 'publishAt', 'privacyStatus' DEBE ser 'private' al inicio.
            'privacyStatus': 'private', 
            'publishAt': publish_at_str,
            'selfDeclaredMadeForKids': False, 
        }
    }

    # Utilizamos MediaFileUpload para soportar subidas parciales de archivos pesados de video
    # Usamos chunksize=10MB (1024*1024*10)
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(file_path, chunksize=1024*1024*10, resumable=True)
    )

    print(f"Subiendo {title} de {file_path}")
    print(f"Programado automáticamente para: {publish_at_str}")
    
    response = None
    try:
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"Progreso subida: {int(status.progress() * 100)}%")
        print(f"¡Video subido y programado exitosamente! Video ID: {response['id']}")
        return response['id']
    except HttpError as e:
        if e.resp.status in [403]: # Quota Exceeded u otro límite de tasa
            error_content = json.loads(e.content.decode('utf-8'))
            reason = error_content['error']['errors'][0]['reason']
            if reason in ['quotaExceeded', 'rateLimitExceeded']:
                print(f"ERROR: Límite de cuota o rate limit alcanzado. Razón: {reason}")
                return "QUOTA_EXCEEDED"
        print(f"Error HTTP durante la subida: {e}")
        return None
    except Exception as e:
        print(f"Error de subida genérico: {e}")
        return None

def main():
    if not os.path.exists(CREDENTIALS_DIR):
        os.makedirs(CREDENTIALS_DIR)
        print(f"Por favor coloca tus archivos client_secret.json en la carpeta '{CREDENTIALS_DIR}'")
        print("Puedes nombrarlos client_secret_1.json, client_secret_2.json, etc.")
        return

    # Obtener los clientes configurados
    client_files = [f for f in os.listdir(CREDENTIALS_DIR) if f.startswith('client_secret') and f.endswith('.json')]
    if not client_files:
        print("No se encontraron archivos client_secret.json en credentials/")
        return
        
    client_files.sort()

    # Cargar la base de datos de los videos escaneados
    if not os.path.exists(JSON_DB):
        print("No se ha ejecutado video_scanner.py todavía o no hay videos encontrados.")
        return
        
    with open(JSON_DB, 'r', encoding='utf-8') as f:
        videos = json.load(f)

    videos_pendientes = [v for v in videos if not v.get('uploaded', False)]
    print(f"Videos pendientes de subir: {len(videos_pendientes)}")

    if not videos_pendientes:
        print("Todos los videos listados ya fueron subidos.")
        return

    # Procedimiento de subida
    # Iterar por videos intentando usar el cliente actual, rotando si se acaba la cuota
    current_client_idx = 0
    
    youtube = get_authenticated_service(
        os.path.join(CREDENTIALS_DIR, client_files[current_client_idx]), 
        os.path.join(CREDENTIALS_DIR, f'token_{current_client_idx}.json')
    )

    for video in videos_pendientes:
        if not os.path.exists(video['path']):
            print(f"El archivo no existe, saltando: {video['path']}")
            continue

        # Generar metadata provisoria
        clean_title = Path(video['filename']).stem[:100] # Max 100 caracteres YouTube
        description = "Video documental y de registro teatral (Performatic Writings). Subido automáticamente vía agent."
        
        # Obtener en qué fecha se debe programar
        next_publish_date = get_next_publish_date(videos)
        
        while True:
            # Intentar la subida
            result = upload_video(
                youtube=youtube,
                file_path=video['path'],
                title=clean_title,
                description=description,
                category='24', # 24 = Entertainment (puedes ajustarlo)
                tags=['teatro', 'performatic writings', 'performance', 'documental'],
                publish_at_dt=next_publish_date
            )

            if result == "QUOTA_EXCEEDED":
                print(f"La cuota para el proyecto {client_files[current_client_idx]} se agotó.")
                current_client_idx += 1
                if current_client_idx < len(client_files):
                    print(f"Rotando al siguiente proyecto: {client_files[current_client_idx]}...")
                    try:
                        youtube = get_authenticated_service(
                            os.path.join(CREDENTIALS_DIR, client_files[current_client_idx]), 
                            os.path.join(CREDENTIALS_DIR, f'token_{current_client_idx}.json')
                        )
                        continue # Reintentar el mismo video con el nuevo cliente
                    except Exception as e:
                        print(f"No se pudo usar el siguiente cliente: {e}")
                        return
                else:
                    print("Se acabaron todas las credenciales de proyectos para hoy. Ejecuta el script mañana.")
                    return # Apagar script hasta el día siguiente
            
            elif result is not None:
                # Éxito:
                video['uploaded'] = True
                video['youtube_id'] = result
                video['publishAt'] = next_publish_date.isoformat().replace('+00:00', 'Z')
                
                # Mover el archivo a la carpeta local de éxitos
                try:
                    original_path = video['path']
                    parent_dir = os.path.dirname(original_path)
                    success_folder = os.path.join(parent_dir, "videos subidos exitosamente")
                    if not os.path.exists(success_folder):
                        os.makedirs(success_folder)
                    
                    new_path = os.path.join(success_folder, os.path.basename(original_path))
                    shutil.move(original_path, new_path)
                    video['path'] = new_path
                    print(f"✅ Archivo movido a: {new_path}")
                except Exception as e:
                    print(f"⚠️ Video subido a YouTube, pero hubo error al mover la carpeta local: {e}")
                
                # Actualizar DB
                with open(JSON_DB, 'w', encoding='utf-8') as f:
                    json.dump(videos, f, indent=4, ensure_ascii=False)
                break # Rompe el ciclo while, pasa al siguiente video
            
            else:
                print("El video falló por un error no relacionado a cuotas. Saltando al siguiente.")
                break

if __name__ == "__main__":
    main()
