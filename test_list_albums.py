import sys
from pathlib import Path
sys.path.insert(0, "/home/zerausn/Documents/Antigravity/agentes/meta_uploader/photo_uploader")
import facebook_album_web_auto

env = facebook_album_web_auto.load_env(Path("/home/zerausn/Documents/Antigravity/agentes/meta_uploader/.env"))
page_id = env.get("META_FB_PAGE_ID")
token = env.get("META_FB_PAGE_TOKEN")

print(f"Page ID: {page_id}")
print(f"Token: {token[:10]}...")

albums = facebook_album_web_auto.list_remote_albums(page_id, token)
print(f"Albums detected: {len(albums)}")
