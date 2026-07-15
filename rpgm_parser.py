"""
RPGM-Translator - Parser module
Estrae stringhe traducibili dai file JSON di RPG Maker MV/MZ.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExtractedString:
    id: int
    kind: str
    text: str
    file: str
    key_path: list[str | int]
    translated: str = ""
    escape_parts: list[dict] = field(default_factory=list)


# Campi testo riconosciuti nei JSON data
TEXT_FIELDS = {
    "name", "nickname", "profile", "description", "message1", "message2",
    "gameTitle", "displayName", "currencyUnit",
}

# Array label da tradurre (termini di sistema)
ARRAY_LABELS = {
    "elements", "equipTypes", "skillTypes", "weaponTypes", "armorTypes",
}

# Chiavi da saltare (riferimenti ad asset o note non traducibili)
SKIP_KEYS = {
    "characterName", "battlerName", "faceName", "parallaxName",
    "battleback1Name", "battleback2Name", "pictureName",
    "title1Name", "title2Name", "note",
}

# Chiavi parametro plugin considerate sicure per testi
SAFE_PARAM_KEYS = [
    "name", "text", "title", "msg", "message", "desc", "description",
    "term", "command", "word", "help", "display", "format", "menu",
    "label", "string", "header", "footer", "caption", "bio", "profile",
    "confirm", "ok", "ng", "cancel", "yes", "no", "select",
]

UNSAFE_PARAM_KEYS = {"dateselect", "dataselect", "selectid", "select_id"}

# Regex escape code RPG Maker: \X[123] oppure \{ \} \. \| \^ \$ \> \< \\ \!
ESC_RE = re.compile(r"\\([A-Z])(\[\d+\])?|\\([{}!.|^$><\\])")


def extract_escape_codes(text: str) -> tuple[str, list[dict]]:
    """Separa gli escape code dal testo pulito, restituendo la mappa di reinserimento."""
    parts = []
    last_idx = 0
    clean = ""
    for match in ESC_RE.finditer(text):
        if match.start() > last_idx:
            clean += text[last_idx:match.start()]
        parts.append({"idx": len(clean), "code": match.group(0)})
        last_idx = match.end()
    if last_idx < len(text):
        clean += text[last_idx:]
    return clean, parts


def restore_escape_codes(translated: str, parts: list[dict]) -> str:
    """Reinserisce gli escape code nella posizione logica originale."""
    # Corregge spazio tra % e numero che alcuni traduttori inseriscono
    result = re.sub(r"%\s+(\d+)", r"%\1", translated)
    if not parts:
        return result
    if all(p["idx"] == 0 for p in parts):
        return "".join(p["code"] for p in parts) + result
    for p in reversed(parts):
        idx = p["idx"]
        code = p["code"]
        if idx == 0:
            result = code + result
        elif idx <= len(result):
            result = result[:idx] + code + result[idx:]
        else:
            result += code
    return result


def is_translatable_text(clean: str) -> bool:
    """Esclude stringhe che non sono testo da tradurre."""
    s = clean.strip()
    if not s:
        return False
    # Singolo carattere ASCII
    if len(s) == 1 and s.isascii():
        return False
    # Solo simboli/numeri
    if re.fullmatch(r"[\d\s.,!?\-+%=*/<>()\[\]{}@#$^&;:'\"`~|\\/]+", s):
        return False
    # Parole chiave RPG piccole
    skip_words = {"hp", "mp", "tp", "lv", "exp", "gold", "true", "false"}
    normalized = s.lower().replace(".", "").replace(":", "")
    if normalized in skip_words:
        return False
    # Stringhe senza spazi che sembrano identificatori/codici
    if " " not in s:
        if re.search(r"[a-zA-Z]", s) and re.search(r"[0-9]", s):
            return False
        if any(c in s for c in "_./\\"):
            return False
        if re.match(r"^[a-z]+[A-Z]", s):
            return False
        if re.match(r"^[A-Z0-9_-]{3,}$", s) and ("_" in s or re.search(r"[0-9]", s)):
            return False
    return True


def get_value_at_path(obj: Any, path: list[str | int]) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        elif isinstance(cur, list) and isinstance(key, int) and 0 <= key < len(cur):
            cur = cur[key]
        else:
            return None
    return cur


def _last_real_key(path: list[str | int]) -> str:
    for key in reversed(path):
        if isinstance(key, str):
            return key.lower()
    return ""


def parse_data_file(file_path: Path, file_name: str, idx_ref: list[int]) -> list[ExtractedString]:
    """Parsa un singolo file JSON in www/data e restituisce le stringhe estratte."""
    texts: list[ExtractedString] = []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return texts

    def add_text(raw: str, kind: str, keys: list[str | int]) -> None:
        clean, parts = extract_escape_codes(raw)
        if not is_translatable_text(clean):
            return
        current_id = idx_ref[0]
        idx_ref[0] += 1
        texts.append(ExtractedString(
            id=current_id,
            kind=kind,
            text=raw,
            file=file_name,
            key_path=list(keys),
            escape_parts=parts,
        ))

    def check_string(val: str, keys: list[str | int]) -> None:
        key = keys[-1]
        if isinstance(key, str):
            if key in SKIP_KEYS:
                return
            if key == "name":
                if file_name in ("Tilesets.json", "Animations.json", "Troops.json", "CommonEvents.json"):
                    return
                if file_name.startswith("Map") and file_name.endswith(".json"):
                    return
            if key in TEXT_FIELDS:
                add_text(val, key, keys)
                return
            if key in ARRAY_LABELS:
                add_text(val, "system_label", keys)
                return
        # Se siamo dentro un array label
        if any(isinstance(k, str) and k in ARRAY_LABELS for k in keys):
            add_text(val, "system_label", keys)
            return
        # Comandi evento: cerchiamo 'parameters' nel path
        try:
            params_idx = -1
            for i, k in enumerate(keys):
                if k == "parameters":
                    params_idx = i
                    break
        except Exception:
            params_idx = -1
        if params_idx >= 1:
            cmd_path = keys[:params_idx]
            cmd = get_value_at_path(data, cmd_path)
            if isinstance(cmd, dict):
                pi = keys[-1]
                code = cmd.get("code")
                if code == 401 and pi == len(cmd.get("parameters", [])) - 1:
                    add_text(val, "dialogue", keys)
                    return
                if code == 405:
                    add_text(val, "scroll", keys)
                    return
                if code == 101 and pi == 4:
                    add_text(val, "window_name", keys)
                    return
                if code == 102:
                    add_text(val, "choice", keys)
                    return
                if code in (320, 324):
                    add_text(val, "actor_name", keys)
                    return
                if code in (355, 655) and val.startswith("テキスト-"):
                    add_text(val[5:], "inline_script", keys)
                    return
        # Sezione terms
        if any(k == "terms" for k in keys):
            add_text(val, "term", keys)

    def walk(obj: Any, keys: list[str | int]) -> None:
        if obj is None:
            return
        if isinstance(obj, list):
            for i, v in enumerate(obj):
                new_keys = keys + [i]
                if isinstance(v, str):
                    check_string(v, new_keys)
                elif isinstance(v, (dict, list)):
                    walk(v, new_keys)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k == "meta":
                    continue
                new_keys = keys + [k]
                if isinstance(v, str):
                    check_string(v, new_keys)
                elif isinstance(v, (dict, list)):
                    walk(v, new_keys)

    walk(data, [])
    return texts


def parse_plugins_js(plugins_js_path: Path, idx_ref: list[int]) -> list[ExtractedString]:
    """Estrae stringhe traducibili dai parametri testuali di js/plugins.js."""
    texts: list[ExtractedString] = []
    if not plugins_js_path.exists():
        return texts
    try:
        content = plugins_js_path.read_text(encoding="utf-8")
    except Exception:
        return texts

    start_idx = content.find("[")
    end_idx = content.rfind("]")
    if start_idx < 0 or end_idx < 0:
        return texts
    try:
        plugins = json.loads(content[start_idx:end_idx + 1])
    except Exception:
        return texts

    def is_safe_key(last_key: str) -> bool:
        low = last_key.lower()
        if low in UNSAFE_PARAM_KEYS:
            return False
        return any(s in low for s in SAFE_PARAM_KEYS)

    def extract_param(val: Any, keys: list[str | int]) -> None:
        if isinstance(val, str) and val:
            # Prova a parsare JSON innestato
            if (val.startswith("[") and val.endswith("]")) or (val.startswith("{") and val.endswith("}")):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, (dict, list)):
                        extract_param_object(parsed, keys + ["__json__"])
                        return
                except Exception:
                    pass
            last_key = _last_real_key(keys)
            if not is_safe_key(last_key):
                return
            if not is_translatable_text(val):
                return
            clean, parts = extract_escape_codes(val)
            if not is_translatable_text(clean):
                return
            current_id = idx_ref[0]
            idx_ref[0] += 1
            texts.append(ExtractedString(
                id=current_id,
                kind="plugin_param",
                text=val,
                file="../js/plugins.js",
                key_path=list(keys),
                escape_parts=parts,
            ))

    def extract_param_object(obj: Any, keys: list[str | int]) -> None:
        if isinstance(obj, list):
            for i, v in enumerate(obj):
                extract_param(v, keys + [i])
        elif isinstance(obj, dict):
            for k, v in obj.items():
                extract_param(v, keys + [k])

    for p_idx, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            continue
        params = plugin.get("parameters")
        if not isinstance(params, dict):
            continue
        for k, v in params.items():
            extract_param(v, [p_idx, "parameters", k])
    return texts
