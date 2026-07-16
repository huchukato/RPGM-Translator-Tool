#!/usr/bin/env python3
"""Ripristina i comandi plugin (code 356/357/657) dalla cartella data originale.

Dopo una traduzione che ha erroneamente tradotto nomi/argomenti di comandi plugin,
questo script copia i valori originali dei parametri di tali comandi dalla cartella
data originale a quella patchata, lasciando intatte tutte le altre traduzioni.
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path

PLUGIN_CODES = {356, 357, 657}


def _revert_plugin_params(original: dict, patched: dict) -> bool:
    """Se entrambi i comandi sono plugin command, ripristina i parametri stringa."""
    orig_code = original.get("code")
    pat_code = patched.get("code")
    if orig_code not in PLUGIN_CODES or pat_code not in PLUGIN_CODES:
        return False
    orig_params = original.get("parameters", [])
    pat_params = patched.get("parameters", [])
    if not isinstance(orig_params, list) or not isinstance(pat_params, list):
        return False
    changed = False
    for i, (o, p) in enumerate(zip(orig_params, pat_params)):
        if isinstance(o, str) and isinstance(p, str) and o != p:
            pat_params[i] = o
            changed = True
    return changed


def _walk(original: object, patched: object) -> bool:
    """Attraversa ricorsivamente entrambe le strutture e ripristina i comandi plugin."""
    changed = False
    if isinstance(original, dict) and isinstance(patched, dict):
        changed |= _revert_plugin_params(original, patched)
        for key in patched:
            if key in original:
                changed |= _walk(original[key], patched[key])
    elif isinstance(original, list) and isinstance(patched, list):
        for i, (o, p) in enumerate(zip(original, patched)):
            changed |= _walk(o, p)
    return changed


def revert_plugin_commands(original_dir: Path, patched_dir: Path) -> int:
    """Ripristina i comandi plugin in tutti i file JSON di patched_dir."""
    if not original_dir.is_dir():
        raise FileNotFoundError(f"Cartella originale non trovata: {original_dir}")
    if not patched_dir.is_dir():
        raise FileNotFoundError(f"Cartella patchata non trovata: {patched_dir}")

    total_changed = 0
    for patched_file in sorted(patched_dir.glob("*.json")):
        original_file = original_dir / patched_file.name
        if not original_file.exists():
            continue
        try:
            original = json.loads(original_file.read_text(encoding="utf-8"))
            patched = json.loads(patched_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"SKIP {patched_file.name}: {e}")
            continue

        if _walk(original, patched):
            patched_file.write_text(
                json.dumps(patched, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
            print(f"FIXED {patched_file.name}")
            total_changed += 1

    return total_changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ripristina i comandi plugin in una cartella data patchata."
    )
    parser.add_argument(
        "original",
        type=Path,
        help="Percorso della cartella data originale (inglese).",
    )
    parser.add_argument(
        "patched",
        type=Path,
        help="Percorso della cartella data patchata da correggere.",
    )
    args = parser.parse_args()
    count = revert_plugin_commands(args.original, args.patched)
    print(f"\nFile modificati: {count}")


if __name__ == "__main__":
    main()
