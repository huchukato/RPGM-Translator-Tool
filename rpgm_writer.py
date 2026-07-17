"""
RPGM-Translator - Writer
Backup, patching in-place, cache locale ed esportazione patch.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from rpgm_parser import ExtractedString, restore_escape_codes, recompose_text


class WriteError(RuntimeError):
    pass


ORIGINAL_BACKUP_NAME = "data_bak_original"


def _data_dir(root: Path) -> Path:
    return root / "www" / "data" if (root / "www" / "data").is_dir() else root / "data"


def _legacy_backups(data_dir: Path) -> list[Path]:
    return sorted(
        (path for path in data_dir.parent.glob("data_bak_*")
         if path.is_dir() and path.name != ORIGINAL_BACKUP_NAME),
        key=lambda path: path.stat().st_mtime,
    )


def _original_backup(root: Path) -> Path | None:
    data_dir = _data_dir(root)
    original = data_dir.parent / ORIGINAL_BACKUP_NAME
    if original.is_dir():
        return original
    backups = _legacy_backups(data_dir)
    if not backups:
        return None
    backups[0].rename(original)
    for backup in backups[1:]:
        shutil.rmtree(backup)
    return original


def find_orphan_backups(root: Path) -> list[Path]:
    data_dir = _data_dir(root)
    return _legacy_backups(data_dir)


def restore_oldest_backup(root: Path) -> Path | None:
    original = _original_backup(root)
    if original is None:
        return None
    data_dir = _data_dir(root)
    if data_dir.exists():
        shutil.rmtree(data_dir)
    shutil.copytree(original, data_dir)
    return original


def backup_data_dir(root: Path) -> Path:
    data_dir = _data_dir(root)
    if not data_dir.is_dir():
        raise WriteError("Cartella dati non trovata per il backup.")
    original = _original_backup(root)
    if original is None:
        original = data_dir.parent / ORIGINAL_BACKUP_NAME
        shutil.copytree(data_dir, original)
    return original


def restore_data_backup(root: Path) -> Path:
    data_dir = _data_dir(root)
    if not data_dir.parent.is_dir():
        raise WriteError("Cartella dati non trovata.")
    original = _original_backup(root)
    if original is None:
        raise WriteError("Nessun backup originale trovato.")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    shutil.copytree(original, data_dir)
    return original


def load_local_cache(root: Path, cfg_key: str) -> dict[str, str]:
    cache_file = root / "trans_cache.json"
    if not cache_file.exists():
        return {}
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if data.get("cfgKey") == cfg_key and isinstance(data.get("translations"), dict):
            return data["translations"]
    except Exception:
        pass
    return {}


def save_local_cache(root: Path, cfg_key: str, items: list[ExtractedString]) -> None:
    translations = {}
    for item in items:
        if item.translated and item.translated != item.text:
            key = f"{item.file}:{'.'.join(str(k) for k in item.key_path)}:{item.text}"
            translations[key] = item.translated
    cache_file = root / "trans_cache.json"
    cache_file.write_text(
        json.dumps({"cfgKey": cfg_key, "translations": translations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_manual_edits(root: Path) -> list[dict]:
    """Carica le modifiche manuali dal file manual_edits.json."""
    manual_edits_file = root / "manual_edits.json"
    if not manual_edits_file.exists():
        return []
    try:
        data = json.loads(manual_edits_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "manual_edits" in data:
            return data["manual_edits"]
    except Exception:
        pass
    return []


def save_manual_edits(root: Path, manual_edits: list[dict]) -> None:
    """Salva le modifiche manuali nel file manual_edits.json."""
    manual_edits_file = root / "manual_edits.json"
    manual_edits_file.write_text(
        json.dumps({"version": "1.0", "manual_edits": manual_edits}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_manual_edit(root: Path, file: str, key_path: list[str | int], original_text: str, manual_translation: str, field: str = "translated") -> None:
    """Aggiunge una modifica manuale al tracking."""
    manual_edits = load_manual_edits(root)
    
    # Rimuovi eventuali modifiche esistenti per lo stesso item
    manual_edits = [edit for edit in manual_edits if not (
        edit["file"] == file and 
        edit["key_path"] == key_path and 
        edit["field"] == field
    )]
    
    # Aggiungi la nuova modifica
    from datetime import datetime
    manual_edits.append({
        "file": file,
        "key_path": key_path,
        "original_text": original_text,
        "manual_translation": manual_translation,
        "field": field,
        "timestamp": datetime.now().isoformat()
    })
    
    save_manual_edits(root, manual_edits)


def apply_manual_edits(items: list[ExtractedString], manual_edits: list[dict]) -> int:
    """Applica le modifiche manuali agli items corrispondenti. Restituisce il numero di modifiche applicate."""
    applied_count = 0
    
    # Crea un dizionario per lookup veloce degli items
    items_dict = {}
    for item in items:
        key = f"{item.file}:{'.'.join(str(k) for k in item.key_path)}"
        items_dict[key] = item
    
    for edit in manual_edits:
        key = f"{edit['file']}:{'.'.join(str(k) for k in edit['key_path'])}"
        if key in items_dict:
            item = items_dict[key]
            if edit["field"] == "text":
                item.text = edit["manual_translation"]
                applied_count += 1
            elif edit["field"] == "translated":
                item.translated = edit["manual_translation"]
                applied_count += 1
    
    return applied_count


def clear_manual_edits(root: Path) -> bool:
    """Cancella il file delle modifiche manuali. Restituisce True se cancellato con successo."""
    manual_edits_file = root / "manual_edits.json"
    if manual_edits_file.exists():
        try:
            manual_edits_file.unlink()
            return True
        except Exception:
            return False
    return False


def patch_data_files(
    root: Path,
    items: list[ExtractedString],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> int:
    """
    Applica le traduzioni ai file JSON del gioco e restituisce il numero di stringhe patchate.
    """
    data_dir = root / "www" / "data" if (root / "www" / "data").is_dir() else root / "data"
    plugins_js_path = root / "www" / "js" / "plugins.js" if (root / "www").is_dir() else root / "js" / "plugins.js"

    # Raggruppa per file
    trans_by_file: dict[str, dict[str, ExtractedString]] = {}
    for item in items:
        if not item.translated or item.translated == item.text:
            continue
        if item.file not in trans_by_file:
            trans_by_file[item.file] = {}
        key = ".".join(str(k) for k in item.key_path)
        trans_by_file[item.file][key] = item

    count = 0
    total = len(trans_by_file)
    for i, (file_name, file_trans) in enumerate(trans_by_file.items()):
        if file_name == "../js/plugins.js":
            count += _patch_plugins_js(plugins_js_path, file_trans)
        else:
            count += _patch_json_file(data_dir / file_name, file_trans)
        if progress_cb:
            progress_cb(i + 1, total, f"Patching {file_name}")

    return count


def _patch_json_file(file_path: Path, file_trans: dict[str, ExtractedString]) -> int:
    if not file_path.exists():
        return 0
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    count = 0
    for key_str, item in file_trans.items():
        keys = _parse_key_path(key_str)
        obj = data
        success = True
        for k in keys[:-1]:
            if isinstance(obj, dict) and k in obj:
                obj = obj[k]
            elif isinstance(obj, list) and isinstance(k, int) and 0 <= k < len(obj):
                obj = obj[k]
            else:
                success = False
                break
        if not success:
            continue
        last_key = keys[-1]
        current_val = None
        if isinstance(obj, dict) and last_key in obj:
            current_val = obj[last_key]
        elif isinstance(obj, list) and isinstance(last_key, int) and 0 <= last_key < len(obj):
            current_val = obj[last_key]
        if isinstance(current_val, str):
            # Usa il nuovo metodo basato su segmenti se disponibile
            if item.segments:
                restored = item.translated  # Già ricomposto durante la traduzione
            else:
                # Fallback al vecchio metodo per compatibilità
                restored = restore_escape_codes(item.translated, item.escape_parts)
            if item.token_map:
                for ph, code in item.token_map.items():
                    restored = restored.replace(ph, code)
            # Ricostruisce prefisso speciale per script inline solo se originale lo aveva
            if len(keys) >= 2 and not item.token_map:
                parent = _get_value_at_path(data, keys[:-2])
                if isinstance(parent, dict) and parent.get("code") in (355, 655):
                    restored = "テキスト-" + restored
            if restored != current_val:
                if isinstance(obj, dict):
                    obj[last_key] = restored
                else:
                    obj[last_key] = restored
                count += 1

    if count > 0:
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    return count


def _patch_plugins_js(plugins_js_path: Path, file_trans: dict[str, ExtractedString]) -> int:
    if not plugins_js_path.exists():
        return 0
    try:
        content = plugins_js_path.read_text(encoding="utf-8")
    except Exception:
        return 0

    start_idx = content.find("[")
    end_idx = content.rfind("]")
    if start_idx < 0 or end_idx < 0:
        return 0
    try:
        plugins = json.loads(content[start_idx:end_idx + 1])
    except Exception:
        return 0

    def patch_param(val, keys):
        if not isinstance(val, str) or not val:
            return val
        # JSON innestato
        if (val.startswith("[") and val.endswith("]")) or (val.startswith("{") and val.endswith("}")):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, (dict, list)):
                    patch_param_object(parsed, keys + ["__json__"])
                    return json.dumps(parsed, ensure_ascii=False)
            except Exception:
                pass
        key_str = ".".join(str(k) for k in keys)
        if key_str in file_trans:
            item = file_trans[key_str]
            # Usa il nuovo metodo basato su segmenti se disponibile
            if item.segments:
                restored = item.translated  # Già ricomposto durante la traduzione
            else:
                # Fallback al vecchio metodo per compatibilità
                restored = restore_escape_codes(item.translated, item.escape_parts)
            return restored
        return val

    def patch_param_object(obj, keys):
        if isinstance(obj, list):
            for idx in range(len(obj)):
                obj[idx] = patch_param(obj[idx], keys + [idx])
        elif isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = patch_param(v, keys + [k])

    count = 0
    for p_idx, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            continue
        params = plugin.get("parameters")
        if not isinstance(params, dict):
            continue
        for k, v in params.items():
            key_str = f"{p_idx}.parameters.{k}"
            if key_str in file_trans:
                item = file_trans[key_str]
                restored = restore_escape_codes(item.translated, item.escape_parts)
                if restored != v:
                    params[k] = restored
                    count += 1

    if count > 0:
        prefix = content[:start_idx]
        suffix = content[end_idx + 1:]
        plugins_js_path.write_text(prefix + json.dumps(plugins, ensure_ascii=False, indent=2) + suffix, encoding="utf-8")
    return count


def _parse_key_path(key_str: str) -> list[str | int]:
    parts = []
    for part in key_str.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
    return parts


def _get_value_at_path(obj, keys):
    cur = obj
    for key in keys:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        elif isinstance(cur, list) and isinstance(key, int) and 0 <= key < len(cur):
            cur = cur[key]
        else:
            return None
    return cur


def export_patch(
    root: Path,
    dest: Path,
    lang_code: str,
) -> Path:
    """Copia la cartella www/data tradotta in una patch pronta per la distribuzione."""
    data_dir = root / "www" / "data" if (root / "www" / "data").is_dir() else root / "data"
    if not data_dir.is_dir():
        raise WriteError("Cartella dati non trovata per l'esportazione.")
    patch_dir = dest / f"{root.name}-{lang_code}" / "www" / "data"
    if patch_dir.exists():
        shutil.rmtree(patch_dir)
    shutil.copytree(data_dir, patch_dir)
    return patch_dir.parent.parent
