from pathlib import Path

folder = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\Fotos")
exts = {".jpg", ".jpeg", ".png", ".webp"}
fotos = sorted([p for p in folder.glob("*.*") if p.suffix.lower() in exts], key=lambda p: p.stat().st_size, reverse=True)

print(f"Total fotos: {len(fotos)}")
print("\nTop 15 mas pesadas:")
for f in fotos[:15]:
    print(f"  {f.stat().st_size/1_000_000:.1f} MB  {f.name}")
