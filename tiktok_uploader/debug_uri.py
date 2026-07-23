import subprocess, pathlib, re, os

def run(cmd, timeout=30):
    env = os.environ.copy()
    env["PATH"] = "/system/bin:/system/xbin:/data/data/com.termux/files/usr/bin:" + env.get("PATH","")
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=env)

ADB = lambda c: run(["adb", "-s", "127.0.0.1:5555", "shell", "exec " + c])

SOURCE = pathlib.Path("/sdcard/Antigravity/subidos a facebbok")
DONE = pathlib.Path("/sdcard/Antigravity/subidos a tiktok")
EXTS = {".mp4", ".mov", ".mkv"}

real = sorted(
    [f for f in SOURCE.iterdir() if f.is_file() and f.suffix.lower() in EXTS],
    key=lambda p: p.stat().st_mtime
)
print(f"Real files in source: {len(real)}")

done_files = [f for f in DONE.iterdir() if f.is_file() and f.suffix.lower() in EXTS]
print(f"Files in done dir: {len(done_files)}")

r = ADB("content query --uri content://media/external/video/media --projection _data:_id")
ms_lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
print(f"Total MediaStore entries: {len(ms_lines)}")

ms_index = {}
for line in ms_lines:
    m = re.search(r"_data=(.*?)(?:,\s|$)", line)
    id_m = re.search(r"_id=(\d+)", line)
    if m and id_m:
        p = m.group(1).strip()
        p_sdcard = p.replace("/storage/emulated/0/", "/sdcard/")
        fname = pathlib.Path(p_sdcard).name
        ms_index.setdefault(fname, []).append((p_sdcard, id_m.group(1)))

print("\n--- First 10 pending files ---")
for f in real[:10]:
    entries = ms_index.get(f.name, [])
    if not entries:
        print(f"  NO URI  {f.name}")
        continue
    for p_sdcard, vid_id in entries:
        exists = pathlib.Path(p_sdcard).exists()
        if not exists:
            print(f"  GHOST id={vid_id} {p_sdcard}  <- TARGET: {f.name}")
        else:
            print(f"  OK id={vid_id} {p_sdcard}")

print("\n--- Check DONE files with MS entries pointing to SOURCE ---")
crossed = 0
for f in done_files:
    entries = ms_index.get(f.name, [])
    for p_sdcard, vid_id in entries:
        if "subidos a facebbok" in p_sdcard:
            print(f"  CROSSED: {f.name} -> id={vid_id} at {p_sdcard}")
            crossed += 1
if crossed == 0:
    print("  None")

print("\n--- Verify first URI ---")
if real:
    f = real[0]
    entries = ms_index.get(f.name, [])
    if entries:
        for p_sdcard, vid_id in entries:
            uri = f"content://media/external/video/media/{vid_id}"
            r2 = ADB(f"content query --uri {uri} --projection _data:_id")
            if r2.returncode == 0 and r2.stdout.strip():
                print(f"  URI OK: {uri}")
            else:
                print(f"  URI FAILS: {uri} -> {r2.stderr[:120]}")
    else:
        print(f"  NO MS ENTRY for {f.name}")
