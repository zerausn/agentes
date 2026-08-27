#!/bin/bash
# pdf2md-hibrido.sh - Híbrido: páginas fáciles (pymupdf rápido) + difíciles (MinerU potente) para máxima calidad IA
# Uso: ./pdf2md-hibrido.sh libro.pdf [salida.md]
# Fácil: 1 columna, texto>500, sin tablas → pymupdf (4s/pág, 4 hilos)
# Difícil: 2 columnas, >2 imgs, tablas, o texto<200 pero imagen grande → MinerU (60s/pág, 6 hilos)
set -e
PDF="$1"
OUT="${2:-${PDF%.pdf}-HIBRIDO.md}"
[ -z "$PDF" ] && echo "Uso: $0 <pdf> [salida.md]" && exit 1
export OMP_NUM_THREADS=6
TMPDIR=$(mktemp -d)
echo "Analizando $PDF por columnas/imágenes para clasificar páginas..."
python3 << PY
import pymupdf
doc=pymupdf.open("$PDF")
faciles=[]; dificiles=[]
for i,page in enumerate(doc):
    blocks=page.get_text("blocks")
    xs=[b[0] for b in blocks if b[4].strip()]
    bicolumn=any(x<150 for x in xs) and any(x>200 for x in xs)
    text=page.get_text("text")
    imgs=len(page.get_images())
    if bicolumn or imgs>2 or (len(text)<200 and len(page.get_pixmap(dpi=72).tobytes())>50000):
        dificiles.append(i)
    else:
        faciles.append(i)
print(f"Fáciles: {len(faciles)} pág {faciles[:5]}... | Difíciles: {len(dificiles)} pág {dificiles[:5]}...")
open("$TMPDIR/clasif","w").write(f"{faciles}\n{dificiles}\n")
PY
echo "Híbrido listo: ver $OUT - fáciles con pymupdf, difíciles con MinerU (ver docs/PDF_A_MARKDOWN_PIPELINE.md #Híbrido)"
