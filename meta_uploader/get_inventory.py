import argparse
import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def build_inventory(source_file):
    source_path = BASE_DIR / source_file
    if not source_path.exists():
        print(f"No existe {source_path.name}.")
        return

    with open(source_path, "r", encoding="utf-8") as handle:
        queue = json.load(handle)

    inventory = []
    for raw_path in queue:
        if not os.path.exists(raw_path):
            continue
        size_mb = os.path.getsize(raw_path) / (1024 * 1024)
        inventory.append(
            {
                "name": os.path.basename(raw_path),
                "path": raw_path,
                "size_mb": round(size_mb, 2),
            }
        )

    inventory.sort(key=lambda item: item["size_mb"], reverse=True)
    output_path = BASE_DIR / "full_inventory.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(inventory, handle, indent=2, ensure_ascii=False)

    print(f"Inventario creado en {output_path.name} con {len(inventory)} archivos.")


def main():
    parser = argparse.ArgumentParser(description="Genera inventario JSON desde una cola local.")
    parser.add_argument(
        "--source-file",
        default="pendientes_posts.json",
        help="Archivo JSON fuente relativo al directorio del script",
    )
    args = parser.parse_args()
    build_inventory(args.source_file)


if __name__ == "__main__":
    main()
