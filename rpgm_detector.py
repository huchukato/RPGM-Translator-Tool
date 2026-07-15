"""
RPGM-Translator - Engine detector
Rileva se un percorso punta a un gioco RPG Maker MV/MZ e ne localizza la cartella dati.
"""

from __future__ import annotations

from pathlib import Path


class DetectionError(RuntimeError):
    pass


def find_data_dir(root: Path) -> Path | None:
    """Trova la cartella data/ contenente i JSON del gioco."""
    candidates = [
        root / "www" / "data",
        root / "data",
    ]
    for cand in candidates:
        if cand.is_dir() and any(cand.glob("System.json")):
            return cand
    return None


def find_www_dir(root: Path) -> Path | None:
    """Trova la cartella www/ se presente."""
    www = root / "www"
    if www.is_dir():
        return www
    return root if (root / "data").is_dir() else None


def detect_engine(game_path: Path) -> dict:
    """
    Rileva il motore e restituisce:
      {
        "engine": "mv" | "mz",
        "root": Path,
        "data_dir": Path,
        "www_dir": Path,
      }
    """
    if not game_path.exists():
        raise DetectionError("Il percorso selezionato non esiste.")

    root = game_path
    if game_path.is_file():
        # Selezionato un file eseguibile: prendiamo la cartella genitore
        root = game_path.parent
    elif game_path.suffix.lower() == ".app":
        # macOS .app bundle: cercare Contents/Resources/autorun o simili
        for sub in ("Contents/Resources/autorun", "Contents/Resources", "Contents/MacOS"):
            cand = game_path / sub
            if cand.is_dir() and find_data_dir(cand):
                root = cand
                break
        else:
            # fallback: cerca in tutta la .app
            for cand in game_path.rglob("System.json"):
                root = cand.parent.parent if cand.parent.name == "data" else cand.parent
                break

    data_dir = find_data_dir(root)
    if not data_dir:
        raise DetectionError(
            "Cartella dati di RPG Maker MV/MZ non trovata. "
            "Assicurati di selezionare la cartella radice del gioco."
        )

    www_dir = find_www_dir(root) or root

    # Determina MV o MZ in base ai file js principali
    engine = "mv"
    js_dir = www_dir / "js"
    if js_dir.is_dir():
        names = {f.name.lower() for f in js_dir.iterdir() if f.is_file()}
        if "rmmz_core.js" in names or "rmmz_managers.js" in names:
            engine = "mz"
        elif "rpg_core.js" in names or "rpg_managers.js" in names:
            engine = "mv"

    system_json = data_dir / "System.json"
    if system_json.exists():
        try:
            import json
            data = json.loads(system_json.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # MZ introduce proprietà non presenti in MV; fallback sul nome engine
                version = str(data.get("version", ""))
                if "MZ" in version:
                    engine = "mz"
        except Exception:
            pass

    return {
        "engine": engine,
        "root": root,
        "data_dir": data_dir,
        "www_dir": www_dir,
    }
