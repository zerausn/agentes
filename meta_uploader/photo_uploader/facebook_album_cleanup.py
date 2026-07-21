#!/usr/bin/env python3
"""
facebook_album_cleanup.py
=========================
Detects and merges duplicate albums on a Facebook Page.
Also detects and deletes duplicate photos within albums.

Usage:
  # Dry-run mode (default, no changes made):
  python3 facebook_album_cleanup.py --dry-run

  # Execute mode (performs modifications/deletes):
  python3 facebook_album_cleanup.py --execute
"""

import os
import re
import sys
import time
import argparse
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent

# Load environment variables
def _load_env():
    env_path = PARENT_DIR / ".env"
    env = {}
    if not env_path.exists():
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env

ENV = _load_env()
FB_PAGE_ID = ENV.get("META_FB_PAGE_ID", "")
FB_TOKEN = ENV.get("META_FB_PAGE_TOKEN", "")

# API Setup
GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def debug_token(token):
    try:
        r = requests.get(
            "https://graph.facebook.com/debug_token",
            params={"input_token": token, "access_token": token},
            timeout=30,
        )
        return r.json().get("data", {})
    except Exception as e:
        print(f"[auth] Error debugging token: {e}", file=sys.stderr)
        return {}

def derivar_page_token(token):
    try:
        r = requests.get(
            f"{GRAPH_URL}/{FB_PAGE_ID}",
            params={"fields": "access_token", "access_token": token},
            timeout=30,
        )
        return r.json().get("access_token")
    except Exception as e:
        print(f"[auth] Error deriving page token: {e}", file=sys.stderr)
        return None

def asegurar_page_token():
    global FB_TOKEN
    if not FB_PAGE_ID or not FB_TOKEN:
        print("[auth] Error: META_FB_PAGE_ID or META_FB_PAGE_TOKEN is missing in .env.", file=sys.stderr)
        return False

    info = debug_token(FB_TOKEN)
    token_type = info.get("type")
    is_valid = info.get("is_valid")

    if token_type == "PAGE" and is_valid:
        print("[auth] META_FB_PAGE_TOKEN successfully validated as PAGE token.")
        return True

    if token_type == "USER" and is_valid:
        print("[auth] META_FB_PAGE_TOKEN is a USER token. Deriving Page Access Token...")
        page_token = derivar_page_token(FB_TOKEN)
        if page_token:
            page_info = debug_token(page_token)
            if page_info.get("type") == "PAGE" and page_info.get("is_valid"):
                FB_TOKEN = page_token
                print("[auth] Derived Page Access Token successfully validated.")
                return True
        print("[auth] Failed to derive a valid Page Access Token.", file=sys.stderr)
        return False

    print(f"[auth] Token is invalid or expired: type={token_type}, valid={is_valid}", file=sys.stderr)
    return False

def fetch_all_albums():
    for attempt in range(1, 4):
        albums = []
        url = f"{GRAPH_URL}/{FB_PAGE_ID}/albums"
        params = {
            "access_token": FB_TOKEN,
            "limit": 100,
            "fields": "id,name,count,created_time"
        }
        
        print(f"Fetching all albums from Facebook (Attempt {attempt}/3)...")
        success = True
        while url:
            try:
                r = requests.get(url, params=params if "?" not in url else {}, timeout=30)
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    print(f"Error listing albums: {data['error'].get('message')}", file=sys.stderr)
                    success = False
                    break
                
                page_albums = data.get("data", [])
                albums.extend(page_albums)
                
                url = data.get("paging", {}).get("next", "")
                if url:
                    time.sleep(0.5)  # Avoid hitting rate limits too fast
            except Exception as e:
                print(f"Exception listing albums: {e}", file=sys.stderr)
                success = False
                break
                
        if success and albums:
            print(f"  Successfully fetched {len(albums)} albums in total.")
            return albums
            
        print(f"  Attempt {attempt} yielded 0 albums or failed. Waiting to retry...")
        time.sleep(2)
        
    print("Failed to fetch albums after 3 attempts.", file=sys.stderr)
    return []

def fetch_all_photos(album_id):
    for attempt in range(1, 4):
        photos = []
        url = f"{GRAPH_URL}/{album_id}/photos"
        params = {
            "access_token": FB_TOKEN,
            "limit": 100,
            "fields": "id,name,created_time,images"
        }
        success = True
        while url:
            try:
                r = requests.get(url, params=params if "?" not in url else {}, timeout=30)
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    print(f"  Error listing photos for album {album_id}: {data['error'].get('message')}", file=sys.stderr)
                    success = False
                    break
                
                page_photos = data.get("data", [])
                photos.extend(page_photos)
                
                url = data.get("paging", {}).get("next", "")
                if url:
                    time.sleep(0.2)
            except Exception as e:
                print(f"  Exception listing photos for album {album_id}: {e}", file=sys.stderr)
                success = False
                break
                
        if success:
            return photos
            
        print(f"  Attempt {attempt} to fetch photos for album {album_id} failed. Retrying...")
        time.sleep(2)
        
    return []

def get_photo_identifier(photo_obj):
    caption = photo_obj.get("name", "")
    # Look for "Archive frame: 20250620_212750" or similar
    match = re.search(r"Archive frame:\s*([a-zA-Z0-9_-]+)", caption)
    if match:
        return match.group(1)
    
    # Fallback to normalized caption if there's any text
    if caption.strip():
        normalized = re.sub(r"\s+", " ", caption.strip())
        return f"caption_{normalized[:50]}"
        
    # If no caption, return ID so we don't falsely match
    return photo_obj.get("id")

def delete_photo(photo_id, dry_run=True):
    if dry_run:
        print(f"  [DRY-RUN] Would delete photo {photo_id}")
        return True
    
    url = f"{GRAPH_URL}/{photo_id}"
    payload = {"access_token": FB_TOKEN}
    for attempt in range(3):
        try:
            r = requests.delete(url, data=payload, timeout=30)
            data = r.json()
            if data.get("success") or data.get("id"):
                print(f"  [DELETED] Photo {photo_id} successfully deleted.")
                return True
            print(f"  [ERROR] Deleting photo {photo_id} (Attempt {attempt+1}/3): {data.get('error')}")
        except Exception as e:
            print(f"  [EXCEPTION] Deleting photo {photo_id} (Attempt {attempt+1}/3): {e}")
        time.sleep(1 * (attempt + 1))
    return False

def delete_album(album_id, dry_run=True):
    if dry_run:
        print(f"  [DRY-RUN] Would delete album {album_id}")
        return True
    
    url = f"{GRAPH_URL}/{album_id}"
    payload = {"access_token": FB_TOKEN}
    for attempt in range(3):
        try:
            r = requests.delete(url, data=payload, timeout=30)
            data = r.json()
            if data.get("success") or data.get("id"):
                print(f"  [DELETED] Album {album_id} successfully deleted.")
                return True
            print(f"  [ERROR] Deleting album {album_id} (Attempt {attempt+1}/3): {data.get('error')}")
        except Exception as e:
            print(f"  [EXCEPTION] Deleting album {album_id} (Attempt {attempt+1}/3): {e}")
        time.sleep(2 * (attempt + 1))
    return False

def copy_photo_to_album(dest_album_id, src_photo_obj, dry_run=True):
    images = src_photo_obj.get("images", [])
    if not images:
        print(f"  [ERROR] No image sources available for photo {src_photo_obj.get('id')}")
        return None
    
    # Largest resolution is usually the first item
    src_url = images[0].get("source")
    caption = src_photo_obj.get("name", "")
    
    if dry_run:
        print(f"  [DRY-RUN] Would copy photo {src_photo_obj.get('id')} to album {dest_album_id} (caption: {get_photo_identifier(src_photo_obj)})")
        return "dry_run_photo_id"
    
    url = f"{GRAPH_URL}/{dest_album_id}/photos"
    payload = {
        "url": src_url,
        "message": caption,
        "access_token": FB_TOKEN
    }
    
    for attempt in range(3):
        try:
            r = requests.post(url, data=payload, timeout=60)
            data = r.json()
            if "id" in data:
                print(f"  [COPIED] Photo {src_photo_obj.get('id')} copied to {dest_album_id} as new ID {data['id']}")
                return data["id"]
            print(f"  [ERROR] Copying photo to {dest_album_id} (Attempt {attempt+1}/3): {data.get('error')}")
        except Exception as e:
            print(f"  [EXCEPTION] Copying photo to {dest_album_id} (Attempt {attempt+1}/3): {e}")
        time.sleep(2 * (attempt + 1))
    return None

def run_deduplication(dry_run=True):
    print("=" * 60)
    print(f"  FACEBOOK ALBUM & PHOTO DEDUPLICATION (DRY_RUN={dry_run})")
    print("=" * 60)

    if not asegurar_page_token():
        return

    # 1. Fetch all albums
    all_albums = fetch_all_albums()
    if not all_albums:
        print("No albums found on Page.")
        return

    # 2. Identify duplicate albums by name
    albums_by_name = {}
    for a in all_albums:
        albums_by_name.setdefault(a["name"], []).append(a)

    duplicate_groups = {name: grp for name, grp in albums_by_name.items() if len(grp) > 1}
    
    print("\n--- DUPLICATE ALBUM SCAN RESULTS ---")
    if not duplicate_groups:
        print("No duplicate albums detected (all album names are unique).")
    else:
        print(f"Found {len(duplicate_groups)} groups of duplicate albums.")
        for name, grp in duplicate_groups.items():
            print(f"\nGroup '{name}':")
            for idx, a in enumerate(grp):
                print(f"  [{idx}] ID: {a['id']} | Photos count: {a.get('count', 0)} | Created: {a.get('created_time')}")

    # 3. Process/Merge Duplicate Albums
    print("\n--- MERGING DUPLICATE ALBUMS ---")
    for name, grp in duplicate_groups.items():
        print(f"\nMerging group: '{name}'")
        # Select primary album: highest count first, then oldest created_time
        # E.g. sort by count desc, then created_time asc
        grp_sorted = sorted(
            grp, 
            key=lambda x: (-int(x.get("count") or 0), x.get("created_time") or "")
        )
        primary = grp_sorted[0]
        secondaries = grp_sorted[1:]
        
        print(f"  Primary album selected: ID {primary['id']} (Count: {primary.get('count', 0)})")
        
        # Load photos for primary
        print(f"  Fetching photos for primary album {primary['id']}...")
        primary_photos = fetch_all_photos(primary["id"])
        primary_photo_ids = {get_photo_identifier(p) for p in primary_photos}
        print(f"    Loaded {len(primary_photos)} photos from primary album.")

        for sec in secondaries:
            print(f"  Processing secondary album {sec['id']} (Count: {sec.get('count', 0)})...")
            sec_photos = fetch_all_photos(sec["id"])
            print(f"    Loaded {len(sec_photos)} photos from secondary album.")
            
            copied_count = 0
            for photo in sec_photos:
                ident = get_photo_identifier(photo)
                if ident not in primary_photo_ids:
                    # Photo is missing in primary, copy it!
                    new_id = copy_photo_to_album(primary["id"], photo, dry_run=dry_run)
                    if new_id:
                        primary_photo_ids.add(ident)
                        copied_count += 1
                        if not dry_run:
                            time.sleep(1)
            
            print(f"    Copied {copied_count} unique photo(s) to primary album.")
            
            # Delete the secondary album
            print(f"    Deleting empty/redundant secondary album {sec['id']}...")
            delete_album(sec["id"], dry_run=dry_run)

    # 4. Detect & Clean Duplicate Photos within ALL albums
    print("\n--- CLEANING DUPLICATE PHOTOS WITHIN ALL ALBUMS ---")
    
    # To save API calls, we scan all albums that are currently active
    # (or we can refresh the list if we deleted some in execute mode, but in dry-run we just use the list)
    albums_to_scan = all_albums
    # If we deleted some in execute mode, we only scan the ones that were not deleted.
    # But since we just process them, let's look at the remaining list.
    
    total_scanned_albums = len(albums_to_scan)
    for idx, album in enumerate(albums_to_scan, 1):
        # If we deleted this album as a secondary, skip it
        # (in execute mode we would track which ones were deleted)
        album_id = album["id"]
        album_name = album["name"]
        
        # Check if it was deleted in this run
        # For simplicity, if we are in execute mode and it was a secondary album, it has been deleted, so skip:
        if not dry_run:
            # Let's check if this album was a secondary album in the duplicate groups
            is_deleted = False
            for name, grp in duplicate_groups.items():
                grp_sorted = sorted(grp, key=lambda x: (-int(x.get("count") or 0), x.get("created_time") or ""))
                secondaries = grp_sorted[1:]
                if any(sec["id"] == album_id for sec in secondaries):
                    is_deleted = True
                    break
            if is_deleted:
                continue

        print(f"[{idx}/{total_scanned_albums}] Scanning photos in album '{album_name}' (ID: {album_id})...")
        photos = fetch_all_photos(album_id)
        if not photos:
            print("  No photos found in this album.")
            continue
            
        # Group photos by identifier
        photos_by_ident = {}
        for p in photos:
            ident = get_photo_identifier(p)
            photos_by_ident.setdefault(ident, []).append(p)
            
        duplicates_in_album = {ident: lst for ident, lst in photos_by_ident.items() if len(lst) > 1}
        
        if not duplicates_in_album:
            print(f"  No duplicate photos found in album '{album_name}'.")
        else:
            print(f"  Found {len(duplicates_in_album)} duplicate photo groups in album '{album_name}'.")
            for ident, lst in duplicates_in_album.items():
                print(f"    Duplicate group for '{ident}':")
                # Sort by created_time ascending, keep the first/oldest one
                lst_sorted = sorted(lst, key=lambda x: x.get("created_time") or "")
                keep = lst_sorted[0]
                to_delete = lst_sorted[1:]
                
                print(f"      Keeping: ID {keep['id']} (Created: {keep.get('created_time')})")
                for p_del in to_delete:
                    print(f"      Deleting: ID {p_del['id']} (Created: {p_del.get('created_time')})")
                    delete_photo(p_del["id"], dry_run=dry_run)
                    if not dry_run:
                        time.sleep(0.5)

    print("\n" + "=" * 60)
    print("  DEDUPLICATION PROCESS COMPLETED")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Facebook Page Album and Photo Deduplicator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Print report of actions without executing changes (default)")
    group.add_argument("--execute", action="store_true", help="Execute the deletion and merge operations on Facebook")
    
    args = parser.parse_args()
    
    # Default to dry-run if neither is specified
    dry_run = not args.execute
    
    run_deduplication(dry_run=dry_run)

if __name__ == "__main__":
    main()
