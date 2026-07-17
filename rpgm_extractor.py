"""
RPGM-Translator - Extractor
Coordina il rilevamento del motore e l'estrazione delle stringhe traducibili.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from rpgm_detector import detect_engine, DetectionError
from rpgm_parser import ExtractedString, parse_data_file, parse_plugins_js


class RPGMExtractor:
    def __init__(self, game_path: Path, use_original: bool = True):
        info = detect_engine(game_path)
        self.engine: str = info["engine"]
        self.root: Path = info["root"]
        self.data_dir: Path = info["data_dir"]
        self.www_dir: Path = info["www_dir"]
        self.items: list[ExtractedString] = []
        self.files_count: int = 0
        self.use_original = use_original

    def extract(self, progress_cb: Callable[[int, int, str], None] | None = None) -> list[ExtractedString]:
        """Estrae tutte le stringhe localizzabili dal gioco."""
        # Se use_original=True, usa i dati dal backup originale
        if self.use_original:
            from rpgm_writer import _original_backup
            original_backup = _original_backup(self.root)
            if original_backup:
                data_dir = original_backup
            else:
                data_dir = self.data_dir
        else:
            data_dir = self.data_dir
        
        data_files = sorted(data_dir.glob("*.json"))
        plugins_js = self.www_dir / "js" / "plugins.js"

        total = len(data_files) + (1 if plugins_js.exists() else 0)
        done = 0
        idx_ref = [0]
        items: list[ExtractedString] = []

        for file_path in data_files:
            file_name = file_path.name
            items.extend(parse_data_file(file_path, file_name, idx_ref))
            done += 1
            if progress_cb:
                progress_cb(done, total, f"Parsing {file_name}")

        # Disabilitato parsing plugin - l'utente non vuole tradurre i plugin
        # if plugins_js.exists():
        #     items.extend(parse_plugins_js(plugins_js, idx_ref))
        #     done += 1
        #     if progress_cb:
        #         progress_cb(done, total, "Parsing plugins.js")

        self.files_count = total
        self.items = items
        return items
