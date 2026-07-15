"""
RPGM-Translator - Forge cheat mod installer
Scarica/usa in cache il plugin Forge MV/MZ e lo installa nel gioco,
modificando la keybind Toggle Cheat UI in un tasto configurabile.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from rpgm_detector import detect_engine

FORGE_CACHE_DIR = Path.home() / ".cache" / "rpgm-translator"
FORGE_CACHE_FILE = FORGE_CACHE_DIR / "forge.js"
FORGE_BACKUP_SUFFIX = ".forge_bak"

FORGE_ENTRY = {
    "name": "forge",
    "status": True,
    "description": "Forge - modern in-game editor",
    "parameters": {},
}


def _cache_forge_js(source_path: Path) -> None:
    FORGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, FORGE_CACHE_FILE)


def ensure_forge_js(user_path: Optional[Path] = None) -> Optional[Path]:
    """Restituisce il percorso di forge.js dalla cache o da quello fornito dall'utente."""
    if user_path and user_path.exists():
        _cache_forge_js(user_path)
        return FORGE_CACHE_FILE
    if FORGE_CACHE_FILE.exists():
        return FORGE_CACHE_FILE
    return None


def patch_keybind(forge_js_content: str, key: str = "1") -> str:
    """Modifica la keybind Toggle Cheat UI da Ctrl+C al tasto indicato."""
    # Sostituisce keyStr:"Ctrl C" / keyStr:'Ctrl C' / keyStr: "Ctrl C" etc.
    pattern = re.compile(r'(keyStr\s*[:=]\s*["\'])Ctrl\s*C(["\'])')
    return pattern.sub(lambda m: f'{m.group(1)}{key}{m.group(2)}', forge_js_content)


def _find_plugins_dir(game_root: Path) -> Optional[Path]:
    try:
        info = detect_engine(game_root)
    except Exception:
        return None
    data_dir = info.get("data_dir")
    if not data_dir:
        return None
    # data_dir è www/data; plugins.js è in www/js
    return data_dir.parent / "js"


def _backup_plugins_js(plugins_js_path: Path) -> None:
    backup = Path(str(plugins_js_path) + FORGE_BACKUP_SUFFIX)
    shutil.copy2(plugins_js_path, backup)


def _read_plugins_js(plugins_js_path: Path) -> tuple[list, str, str]:
    content = plugins_js_path.read_text(encoding="utf-8")
    start = content.find("[")
    end = content.rfind("]")
    if start < 0 or end < 0:
        raise ValueError("plugins.js non contiene un array JSON valido")
    import json

    plugins = json.loads(content[start : end + 1])
    return plugins, content[:start], content[end + 1 :]


def _write_plugins_js(plugins_js_path: Path, plugins: list, prefix: str, suffix: str) -> None:
    import json

    plugins_js_path.write_text(
        prefix + json.dumps(plugins, ensure_ascii=False, indent=2) + suffix,
        encoding="utf-8",
    )


def install_forge(game_root: Path, forge_js_path: Path, key: str = "1") -> dict:
    """Installa o aggiorna Forge nel gioco. Ritorna un dict con risultati."""
    plugins_dir = _find_plugins_dir(game_root)
    if not plugins_dir:
        raise RuntimeError("Impossibile determinare la cartella www/js del gioco")

    plugins_js_path = plugins_dir / "plugins.js"
    if not plugins_js_path.exists():
        raise RuntimeError(f"plugins.js non trovato in {plugins_dir}")

    # Legge e patcha forge.js
    forge_content = forge_js_path.read_text(encoding="utf-8")
    patched_content = patch_keybind(forge_content, key)

    # Scrive forge.js nella cartella plugins
    target_forge_js = plugins_dir / "forge.js"
    target_forge_js.write_text(patched_content, encoding="utf-8")

    # Backup e modifica plugins.js
    _backup_plugins_js(plugins_js_path)
    plugins, prefix, suffix = _read_plugins_js(plugins_js_path)

    existing = None
    for i, p in enumerate(plugins):
        if isinstance(p, dict) and p.get("name") == "forge":
            existing = i
            break

    if existing is not None:
        plugins[existing]["status"] = True
        action = "updated"
    else:
        plugins.append(FORGE_ENTRY)
        action = "added"

    _write_plugins_js(plugins_js_path, plugins, prefix, suffix)

    return {
        "action": action,
        "forge_js": str(target_forge_js),
        "plugins_js": str(plugins_js_path),
        "key": key,
    }
