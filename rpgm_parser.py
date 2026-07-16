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
    clean_text: str = ""
    token_map: dict[str, str] = field(default_factory=dict)


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
    "fileName", "folder", "path", "directory", "src", "url",
    "soundName", "imageName", "movieName", "animationName", "tilesetName",
    "voiceName", "audioName", "videoName", "resourceName", "assetName",
}

# Contesti in cui la chiave "name" indica un asset (file audio/immagine/video)
ASSET_CONTEXT_KEYS = {
    "bgm", "bgs", "se", "me", "picture", "image", "animation", "tileset",
    "parallax", "battleback1", "battleback2", "title1", "title2", "file",
    "sound", "sounds", "movie", "voice", "audio", "video", "titleBgm", "titleBgs",
    "victoryMe", "defeatMe", "gameoverMe", "boatBgm", "shipBgm",
    "airshipBgm", "airshipBgs", "attackSound", "recoverySound", "missSound",
    "evasionSound", "magicEvasionSound", "magicReflectionSound", "shopSound",
    "useSound", "equipSound", "saveSound", "loadSound", "battleStartSound",
    "escapeSound", "enemyCollapseSound", "bossCollapse1Sound", "bossCollapse2Sound",
    "actorDamageSound", "actorNoDamageSound", "actorRecoverySound", "attackMotion",
}

# Chiavi parametro plugin considerate sicure per testi
SAFE_PARAM_KEYS = [
    "name", "text", "title", "msg", "message", "desc", "description",
    "term", "command", "word", "help", "display", "format", "menu",
    "label", "string", "header", "footer", "caption", "bio", "profile",
    "confirm", "ok", "ng", "cancel", "yes", "no", "select",
]

UNSAFE_PARAM_KEYS = {
    "dateselect", "dataselect", "selectid", "select_id",
    "file", "filename", "folder", "path", "directory", "src", "url",
    "sound", "soundname", "image", "imagename", "movie", "moviename",
    "animation", "animationname", "tileset", "tilesetname", "voice", "voicename",
    "audio", "audioname", "video", "videoname", "resource", "resourcename",
    "asset", "assetname", "filetext", "filepath", "filefolder",
}

# Regex escape code RPG Maker: \Word[123] (es. \OutlineColor[28], \FS[30], \C[3])
# oppure caratteri speciali \{ \} \. \| \^ \$ \> \< \\ \!
ESC_RE = re.compile(r"\\([A-Za-z]+)(?:\[\d+\])?|\\([{}!.|^$><\\])")


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


FILE_EXTENSIONS_RE = re.compile(
    r"\.(ogg|m4a|mp3|wav|wma|aac|flac|png|jpe?g|gif|bmp|webp|tga|tiff?|svg|ico|"
    r"webm|mp4|m4v|mov|avi|ogv|mkv|json|js|css|html|txt|xml|csv|ini|yaml|yml|"
    r"rpgmvp|rpgmvo|rpgmvm|m4v|ttf|otf|woff2?|eot|fnt|db)$",
    re.IGNORECASE,
)


def is_translatable_text(clean: str) -> bool:
    """Esclude stringhe che non sono testo da tradurre."""
    s = clean.strip()
    if not s:
        return False
    # Singolo carattere ASCII
    if len(s) == 1 and s.isascii():
        return False
    # Nomi file/asset audio, immagini, video, json, etc.
    if FILE_EXTENSIONS_RE.search(s):
        return False
    # Path separati da / o \
    if "/" in s or "\\" in s:
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
        if any(c in s for c in "_/\\") or "." in s.rstrip(".!?…"):
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
            clean_text=clean,
        ))

    def _is_script_literal_translatable(literal: str) -> bool:
        r"""Controlla se una stringa letterale in uno script va tradotta.

        Accetta sia frasi con spazi che singole parole, ma evita identificatori
        tecnici del tipo GUI-MAP-Outskirts (nessuno spazio, trattini e maiuscole)
        e stringhe con simboli di codice (es. $, {, }, [, ], <, >, =, +, \, /).
        """
        if not is_translatable_text(literal):
            return False
        if " " not in literal:
            # Identificatori come GUI-MAP-Outskirts: trattini e maiuscole
            if "-" in literal and re.search(r"[A-Z]", literal):
                return False
            # Identificatori camelCase come PoliceA, PoliceB
            if re.search(r"[a-z][A-Z]", literal):
                return False
            # Espressioni tipo Math.random() o www.example.com: punto senza spazi
            if "." in literal.rstrip(".!?…"):
                return False
        # Se la stringa contiene graffe non bilanciate o simboli chiaramente di codice,
        # probabilmente è codice o placeholder, non testo visibile.
        if literal.count("{") != literal.count("}"):
            return False
        if any(c in literal for c in "$[]<>+=\\/"):
            return False
        return True

    def add_script_text(script: str, keys: list[str | int]) -> bool:
        """Estrae stringhe letterali traducibili da un comando Script (code 355/655/122/357)."""
        str_re = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
        dialogue_prefix_re = re.compile(r"^([A-Za-z][A-Za-z0-9#^>{}]*\.)")
        literals: list[str] = []
        code_segments: list[str] = []
        current_code = ""
        prev_end = 0
        for m in str_re.finditer(script):
            current_code += script[prev_end:m.start()]
            literal = m.group(1)
            prefix_match = dialogue_prefix_re.match(literal)
            candidate = literal[prefix_match.end():] if prefix_match else ""
            prefix = prefix_match.group(1) if prefix_match and (" " in candidate or candidate.endswith((".", "!", "?", "…"))) else ""
            translatable = literal[len(prefix):]
            if _is_script_literal_translatable(translatable):
                code_segments.append(current_code + '"' + prefix)
                literals.append(translatable)
                current_code = ""
                prev_end = m.end() - 1  # include closing quote in the next code segment
            else:
                current_code += m.group(0)
                prev_end = m.end()
        if not literals:
            return False
        current_code += script[prev_end:]
        code_segments.append(current_code)

        clean_text = ""
        token_map: dict[str, str] = {}
        for i, lit in enumerate(literals):
            ph = f"@@RJS{i}@@"
            clean_text += ph + lit
            token_map[ph] = code_segments[i]
        final_ph = f"@@RJS{len(literals)}@@"
        clean_text += final_ph
        token_map[final_ph] = code_segments[-1]

        current_id = idx_ref[0]
        idx_ref[0] += 1
        texts.append(ExtractedString(
            id=current_id,
            kind="script_literal",
            text=script,
            file=file_name,
            key_path=list(keys),
            escape_parts=[],
            clean_text=clean_text,
            token_map=token_map,
        ))
        return True

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
                if any(k in ASSET_CONTEXT_KEYS for k in keys[:-1]):
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
                if code in (402, 408):
                    if is_translatable_text(val):
                        add_text(val, "event_param", keys)
                    return
                if code in (355, 655):
                    if add_script_text(val, keys):
                        return
                    if val.startswith("テキスト-"):
                        add_text(val[5:], "inline_script", keys)
                    return
                if code in (357, 356, 657):
                    # Comandi plugin (MV/MZ/ custom): anche le stringhe letterali
                    # all'interno sono spesso valori JSON/proprietà interne (es.
                    # "Center", "Normal", "left"). Tradurle rompe i plugin.
                    return
                # Per tutti gli altri codici evento (es. 122) estrai solo le
                # stringhe letterali tra virgolette.
                if isinstance(code, int):
                    add_script_text(val, keys)
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
        if any(u in low for u in UNSAFE_PARAM_KEYS):
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
                clean_text=clean,
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
