from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("meta_uploader/.env"))

from meta_uploader import _iter_graph_collection, FB_PAGE_ID, META_FB_PAGE_TOKEN

count = 0
for item in _iter_graph_collection(
    f"{FB_PAGE_ID}/videos",
    access_token=META_FB_PAGE_TOKEN,
    fields="id,scheduled_publish_time,published",
    page_size=50,
    max_pages=3,
):
    count += 1
    published = item.get("published")
    spt = item.get("scheduled_publish_time", "N/A")
    print(f"id={item['id']} published={published} spt={spt}")

print("Total videos vistos:", count)
