import os
import json
import subprocess
import logging
from pathlib import Path

# Settings
LOG_FILE = "classifier.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])

def check_video_properties(filepath):
    """Uses ffprobe to get width, height, duration in a single call."""
    cmd = [
        "ffprobe", "-v", "error", 
        "-select_streams", "v:0", 
        "-show_entries", "stream=width,height,duration", 
        "-of", "json", filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        streams = data.get("streams", [])
        if not streams:
            return None
            
        stream = streams[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        duration = float(stream.get("duration", 0))
        
        return {"width": width, "height": height, "duration": duration}
    except Exception as e:
        logging.error(f"Error checking {filepath}: {e}")
        return None

def is_reel(props):
    if not props:
        return False
    w, h, d = props["width"], props["height"], props["duration"]
    
    # Check duration 5 to 90 seconds
    if not (5.0 <= d <= 90.0):
        return False
        
    # Check aspect ratio 9:16 (allow a small 5% tolerance)
    if h == 0: return False
    ratio = w / h
    if abs(ratio - (9/16)) > 0.05:
        return False
        
    return True

def classify_directory(target_dir):
    reels = []
    posts = []
    
    target_path = Path(target_dir)
    logging.info(f"Scanning {target_path} for MP4 videos...")
    
    for mp4_file in target_path.rglob("*.mp4"):
        props = check_video_properties(str(mp4_file))
        if props:
            if is_reel(props):
                reels.append(str(mp4_file))
                logging.info(f"[REEL]  {mp4_file.name} - Duration: {props['duration']:.2f}s, Res: {props['width']}x{props['height']}")
            else:
                posts.append(str(mp4_file))
                logging.info(f"[POST]  {mp4_file.name} - Duration: {props['duration']:.2f}s, Res: {props['width']}x{props['height']}")
                
    # Save results
    with open("pendientes_reels.json", "w", encoding="utf-8") as f:
        json.dump(reels, f, indent=4)
    with open("pendientes_posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4)
        
    logging.info(f"Classification finished. Found {len(reels)} Reels and {len(posts)} Posts.")

if __name__ == "__main__":
    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    classify_directory(directory)
