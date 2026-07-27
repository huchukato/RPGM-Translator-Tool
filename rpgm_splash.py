from __future__ import annotations

import json
import shutil
from pathlib import Path

from rpgm_detector import detect_engine

SCRIPT_DIR = Path(__file__).resolve().parent
SPLASH_PLUGIN_SOURCE = SCRIPT_DIR / "rpgm_translator_splash.js"
SPLASH_IMAGE_SOURCE = SCRIPT_DIR / "img" / "splash.png"
SPLASH_PLUGIN_NAME = "rpgm_translator_splash"
SPLASH_ENTRY = {
    "name": SPLASH_PLUGIN_NAME,
    "status": True,
    "description": "RPGM Translator splash screen",
    "parameters": {
        "Picture": "splash",
        "Duration": "180",
    },
}


def ensure_splash_assets() -> tuple[Path, Path]:
    if not SPLASH_PLUGIN_SOURCE.exists():
        raise FileNotFoundError(f"Plugin splash non trovato in {SPLASH_PLUGIN_SOURCE}")
    if not SPLASH_IMAGE_SOURCE.exists():
        raise FileNotFoundError(f"Immagine splash non trovata in {SPLASH_IMAGE_SOURCE}")
    return SPLASH_PLUGIN_SOURCE, SPLASH_IMAGE_SOURCE


def _write_splash_image(image_source: Path, pictures_dir: Path, data_dir: Path) -> Path:
    system_path = data_dir / "System.json"
    system = json.loads(system_path.read_text(encoding="utf-8"))
    if not system.get("hasEncryptedImages"):
        target_image = pictures_dir / image_source.name
        shutil.copy2(image_source, target_image)
        return target_image
    key = bytes.fromhex(system.get("encryptionKey", ""))
    if len(key) != 16:
        raise RuntimeError("Chiave di cifratura immagini non valida in System.json")
    source = image_source.read_bytes()
    encrypted = bytes(byte ^ key[index] for index, byte in enumerate(source[:16])) + source[16:]
    header = bytes.fromhex("5250474d560000000003010000000000")
    target_image = pictures_dir / f"{image_source.name}_"
    target_image.write_bytes(header + encrypted)
    return target_image


def install_splash(game_root: Path) -> dict:
    info = detect_engine(game_root)
    www_dir = info["www_dir"]
    plugins_dir = www_dir / "js" / "plugins"
    plugins_js_path = www_dir / "js" / "plugins.js"
    pictures_dir = www_dir / "img" / "pictures"
    if not plugins_js_path.exists():
        raise RuntimeError(f"plugins.js non trovato in {plugins_js_path.parent}")

    plugin_source, image_source = ensure_splash_assets()
    plugins_dir.mkdir(parents=True, exist_ok=True)
    pictures_dir.mkdir(parents=True, exist_ok=True)
    target_plugin = plugins_dir / plugin_source.name
    target_image = pictures_dir / image_source.name
    shutil.copy2(plugin_source, target_plugin)
    target_image = _write_splash_image(image_source, pictures_dir, info["data_dir"])

    content = plugins_js_path.read_text(encoding="utf-8")
    start = content.find("[")
    end = content.rfind("]")
    if start < 0 or end < 0:
        raise ValueError("plugins.js non contiene un array JSON valido")
    plugins = json.loads(content[start:end + 1])
    entry = dict(SPLASH_ENTRY)
    entry["parameters"] = dict(SPLASH_ENTRY["parameters"])
    existing = next(
        (index for index, plugin in enumerate(plugins)
         if isinstance(plugin, dict) and plugin.get("name") == SPLASH_PLUGIN_NAME),
        None,
    )
    if existing is None:
        plugins.append(entry)
        action = "added"
    else:
        plugins[existing] = entry
        action = "updated"

    backup_path = Path(f"{plugins_js_path}.rpgm_translator_splash_bak")
    if not backup_path.exists():
        shutil.copy2(plugins_js_path, backup_path)
    plugins_js_path.write_text(
        content[:start] + json.dumps(plugins, ensure_ascii=False, indent=2) + content[end + 1:],
        encoding="utf-8",
    )
    return {
        "action": action,
        "plugin": str(target_plugin),
        "image": str(target_image),
        "plugins_js": str(plugins_js_path),
    }
