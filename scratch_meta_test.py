import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(r"c:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader")
load_dotenv(BASE_DIR / ".env")

import sys
sys.path.append(str(BASE_DIR))

from meta_uploader import _iter_graph_collection, FB_PAGE_ID, META_FB_PAGE_TOKEN

print(f"Page ID: {FB_PAGE_ID}")

# Query scheduled_posts
max_time = 0
for item in _iter_graph_collection(
    f"{FB_PAGE_ID}/scheduled_posts",
    access_token=META_FB_PAGE_TOKEN,
    fields="id,created_time,scheduled_publish_time",
    page_size=50,
    max_pages=5
):
    print(item)
    st_time = item.get("scheduled_publish_time")
    if st_time:
        max_time = max(max_time, int(st_time))

print("MAX TIME:", max_time)
