"""
extract_4k.py — reensambla los segmentos UMP de cada epoch en un .mp4 AV1/VP9.

Uso:
  python3 extract_4k.py <segments_base> <salidas> [<destino_crudos>]

- Cada carpeta epoch_XXXX/ de <segments_base> produce salidas/epoch_XXXX.mp4.
- Solo aleja el noise del protobuf UMP con búsqueda anclada de boxes
  (ftyp/styp/moov/moof/sidx con size válido 4 bytes antes).
- Escribe salidas/manifest.csv con tamaño y, si hay ffprobe, resolución/códec.
- Si existe <destino_crudos>, copia los .mp4 terminados allí.
"""
import csv
import glob
import os
import shutil
import struct
import subprocess
import sys


def extract_media(data):
    for key in (b"ftyp", b"styp", b"moov", b"moof", b"sidx"):
        i = data.find(key)
        if i >= 0 and i - 4 >= 0:
            size = struct.unpack(">I", data[i - 4:i])[0]
            if 8 <= size <= len(data) - (i - 4):
                return data[i - 4:]
    return b""


def stampa(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=60)
        return out.stdout.strip()
    except Exception:
        return "?"


def main():
    seg_base, out_dir = sys.argv[1], sys.argv[2]
    dest = sys.argv[3] if len(sys.argv) > 3 else None
    os.makedirs(out_dir, exist_ok=True)

    epochs = sorted(d for d in glob.glob(os.path.join(seg_base, "epoch_*")) if os.path.isdir(d))
    if not epochs:
        print("SIN EPOCHS (no hubo captura)")
        return

    rows = []
    for ep in epochs:
        name = os.path.basename(ep)
        media = []
        last_init = -1
        for f in sorted(glob.glob(os.path.join(ep, "seg_*.ump"))):
            raw = open(f, "rb").read()
            med = extract_media(raw)
            if med:
                media.append((f, med, b"ftyp" in raw or b"styp" in raw))
        if not media:
            print(f"{name}: sin media")
            continue
        last_init = max(i for i, (_, _, is_init) in enumerate(media) if is_init)
        out_mp4 = os.path.join(out_dir, f"{name}.mp4")
        total = 0
        with open(out_mp4, "wb") as fh:
            for i, (_, boxes, _) in enumerate(media):
                if i >= last_init:
                    fh.write(boxes)
                    total += len(boxes)
        info = stampa(out_mp4)
        rows.append([name, total, info])
        print(f"{name}: {total}B media={info}")
        if dest:
            shutil.copy2(out_mp4, os.path.join(dest, f"{name}.mp4"))
            print(f"  -> {dest}/{name}.mp4")

    with open(os.path.join(out_dir, "manifest.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "bytes", "codec_wxh"])
        w.writerows(rows)


if __name__ == "__main__":
    main()