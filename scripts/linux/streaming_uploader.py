#!/usr/bin/env python3
"""
streaming_uploader.py — Pipeline de subida en streaming con evacuación.

Flujo:
  1. Escanea teasers_pendientes/ y agrupa teasers por crudo
  2. Por cada crudo:
     a. Sube todos sus teasers (llamando teaser_uploader.py --single-file)
     b. Cuando todos los teasers subidos y evacuados → sube el crudo en hilo aparte
  3. Hilos verifican procesamiento (sin frenar el flujo)
  4. Al final: Facebook evacuador

No modifica teaser_generator.py, teaser_uploader.py ni uploader.py.
"""

import argparse
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path("/data/data/com.termux/files/home/agentes")
YOUTUBE_DIR = BASE_DIR / "youtube_uploader"
META_DIR = BASE_DIR / "meta_uploader"
PYTHON_BIN = "python3"

FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, handlers=[
    logging.StreamHandler(sys.stdout),
])


def run_subprocess(cmd: list[str], label: str) -> int:
    """Ejecuta un subprocess y muestra su salida en tiempo real.
    Devuelve el código de retorno."""
    logging.info("[%s] >>> %s", label, " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in proc.stdout:
        sys.stdout.write(f"[{label}] {line}")
        sys.stdout.flush()
    proc.wait()
    if proc.returncode != 0:
        logging.warning("[%s] Salida con código %s", label, proc.returncode)
    return proc.returncode


def find_teasers_by_crudo(teaser_dir: Path) -> dict[str, list[Path]]:
    """Agrupa archivos teaser por crudo según el prefijo del nombre."""
    groups: dict[str, list[Path]] = {}
    if not teaser_dir.exists():
        return groups
    for f in sorted(teaser_dir.iterdir()):
        if f.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
            continue
        if "teaser" not in f.stem.lower():
            continue
        # El prefijo es todo antes de "_teaser_"
        parts = f.stem.split("_teaser_", 1)
        if len(parts) < 2:
            continue
        crudo_key = parts[0]
        groups.setdefault(crudo_key, []).append(f)
    return groups


def find_crudo_path(crudo_key: str, crudos_dir: Path) -> Path | None:
    """Busca el archivo crudo que coincide con el prefijo del teaser."""
    for ext in [".mp4", ".mov", ".mkv"]:
        path = crudos_dir / f"{crudo_key}{ext}"
        if path.exists():
            return path
    return None


def upload_teaser_blocking(teaser_path: Path, state_dir: Path) -> bool:
    """Sube un teaser, espera confirmación y evacuación.
    Devuelve True si fue exitoso."""
    cmd = [
        PYTHON_BIN, str(YOUTUBE_DIR / "teaser_uploader.py"),
        "--single-file", str(teaser_path),
        "--from-orchestrator",
        "--state-dir", str(state_dir),
    ]
    label = f"TEASER-{teaser_path.stem[:30]}"
    rc = run_subprocess(cmd, label)
    if rc == 0:
        logging.info("[%s] OK - subido, verificado y evacuado", label)
        return True
    logging.warning("[%s] Falló (rc=%s)", label, rc)
    return False


def upload_crudo_blocking(crudo_path: Path) -> bool:
    """Sube un crudo, espera confirmación y evacuación.
    Devuelve True si fue exitoso."""
    cmd = [
        PYTHON_BIN, str(YOUTUBE_DIR / "uploader.py"),
        "--video", str(crudo_path),
        "--from-orchestrator",
    ]
    label = f"CRUDO-{crudo_path.stem[:30]}"
    rc = run_subprocess(cmd, label)
    if rc == 0:
        logging.info("[%s] OK - subido, verificado y evacuado", label)
        return True
    logging.warning("[%s] Falló (rc=%s)", label, rc)
    return False


def upload_crudo_in_thread(crudo_path: Path, results: list, lock: threading.Lock, index: int):
    """Wrapper para correr upload_crudo_blocking en un hilo."""
    ok = upload_crudo_blocking(crudo_path)
    with lock:
        results[index] = ok


def run_facebook_evacuador(storage_root: Path) -> bool:
    """Ejecuta el evacuador de Facebook."""
    fb_script = META_DIR / "subir_fb_evacuador.py"
    if not fb_script.exists():
        logging.info("[FB] No existe %s, saltando", fb_script)
        return True
    env = os.environ.copy()
    env["AGENTES_STORAGE_ROOT"] = str(storage_root)
    cmd = [PYTHON_BIN, str(fb_script)]
    logging.info("[FB] >>> %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    for line in proc.stdout:
        sys.stdout.write(f"[FB] {line}")
        sys.stdout.flush()
    proc.wait()
    if proc.returncode != 0:
        logging.warning("[FB] Salida con código %s", proc.returncode)
        return False
    logging.info("[FB] Facebook evacuador completado")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Streaming Uploader — sube teasers y crudos en pipeline"
    )
    parser.add_argument(
        "--storage-root",
        default="/sdcard/Antigravity",
        help="Raíz de almacenamiento (default: /sdcard/Antigravity)",
    )
    parser.add_argument(
        "--skip-facebook",
        action="store_true",
        help="Saltar el evacuador de Facebook al final",
    )
    args = parser.parse_args()

    storage_root = Path(args.storage_root)
    teaser_dir = storage_root / "teasers_pendientes"
    crudos_dir = storage_root / "crudos_pendientes"
    state_dir = storage_root / ".state"

    print("=" * 60)
    print("   STREAMING UPLOADER — Pipeline concurrente")
    print("=" * 60)
    print(f"  Teasers: {teaser_dir}")
    print(f"  Crudos:  {crudos_dir}")
    print(f"  State:   {state_dir}")
    print("=" * 60)

    # FASE 1: Agrupar teasers por crudo
    groups = find_teasers_by_crudo(teaser_dir)
    if not groups:
        logging.info("No se encontraron teasers pendientes.")
        # Aun así, ver si hay crudos sin teasers que subir
        if crudos_dir.exists():
            solo_crudos = sorted(crudos_dir.glob("*.mp4"))
            if solo_crudos:
                logging.info("Se encontraron %s crudo(s) sin teasers.", len(solo_crudos))
                groups = {p.stem: [] for p in solo_crudos}
            else:
                logging.info("No hay crudos pendientes.")
                return
        else:
            logging.info("No hay crudos pendientes.")
            return

    crudo_threads: list[threading.Thread] = []
    crudo_results: list[bool | None] = []
    crudo_lock = threading.Lock()
    crudo_index = 0

    # FASE 2: Por cada crudo, subir teasers secuencialmente y luego crudo en hilo
    for crudo_key in sorted(groups.keys()):
        teasers = groups[crudo_key]
        print()
        print("=" * 60)
        print(f"  PROCESANDO CRUDO: {crudo_key}")
        print(f"  Teasers encontrados: {len(teasers)}")
        print("=" * 60)

        # 2a: Subir cada teaser (cada uno espera su confirmación y evacuación)
        teasers_ok = 0
        for i, t_path in enumerate(teasers, start=1):
            print()
            print(f"--- TEASER {i}/{len(teasers)}: {t_path.name} ---")
            ok = upload_teaser_blocking(t_path, state_dir)
            if ok:
                teasers_ok += 1
            else:
                logging.warning("Teaser %s falló, continuando con el siguiente", t_path.name)

        # 2b: Buscar el crudo correspondiente
        crudo_path = find_crudo_path(crudo_key, crudos_dir)
        if crudo_path is None:
            logging.warning("No se encontró el crudo para %s, saltando subida de crudo", crudo_key)
            continue

        # 2c: Subir crudo en hilo aparte (no frena el flujo)
        print()
        print(f"--- SUBIENDO CRUDO (hilo): {crudo_path.name} ---")
        crudo_results.append(None)
        t = threading.Thread(
            target=upload_crudo_in_thread,
            args=(crudo_path, crudo_results, crudo_lock, crudo_index),
            name=f"Crudo-{crudo_key[:20]}",
            daemon=True,
        )
        t.start()
        crudo_threads.append(t)
        crudo_index += 1

        logging.info(
            "Crudo %s lanzado en hilo. Continuando con el siguiente crudo...",
            crudo_key,
        )

    # FASE 3: Esperar a que terminen todos los crudos
    if crudo_threads:
        print()
        print("=" * 60)
        print(f"  ESPERANDO {len(crudo_threads)} subida(s) de crudo(s)...")
        print("=" * 60)
        for t in crudo_threads:
            t.join(timeout=7200)  # 2h timeout máximo por crudo

        ok_count = sum(1 for r in crudo_results if r)
        fail_count = sum(1 for r in crudo_results if r is False)
        print()
        print(f"  Crudos: {ok_count} OK, {fail_count} fallos, "
              f"{len(crudo_results) - ok_count - fail_count} sin confirmar")

    # FASE 4: Facebook evacuador
    if not args.skip_facebook:
        print()
        print("=" * 60)
        print("  FACEBOOK EVACUADOR")
        print("=" * 60)
        run_facebook_evacuador(storage_root)

    print()
    print("=" * 60)
    print("  STREAMING UPLOADER FINALIZADO")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
