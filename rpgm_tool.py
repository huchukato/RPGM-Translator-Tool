#!/usr/bin/env python3
"""
RPGM-Translator - Main GUI
Interfaccia stile WTForge, flusso di traduzione di Ren'Py Translator.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from typing import Any

import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox

from rpgm_detector import detect_engine, DetectionError
from rpgm_extractor import RPGMExtractor
from rpgm_forge import ensure_forge_js, install_forge
from rpgm_parser import ExtractedString, strip_script_tokens, restore_script_tokens
from rpgm_translator import extract_character_names
from rpgm_settings import (
    BACKEND_LABELS, BACKENDS, DEFAULT_SETTINGS, LANGUAGES, SETTINGS_FILE,
    UI_TEXTS, load_settings, save_settings, t,
)
from rpgm_translator import OPENROUTER_FREE_MODELS, Translator, TranslatorConfig, TranslationError
from rpgm_writer import (
    WriteError, backup_data_dir, export_patch, load_local_cache, patch_data_files, restore_data_backup, save_local_cache,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Palette ispirata al logo: nero, ciano, magenta, viola e accenti dorati
COLOR_BG = "#0c0a12"
COLOR_PANEL = "#18122b"
COLOR_ACCENT = "#06b6d4"
COLOR_ACCENT_MAGENTA = "#ec4899"
COLOR_ACCENT_GOLD = "#f59e0b"
COLOR_BTN_MAIN = "#7c3aed"
COLOR_BTN_ALT = "#ec4899"
COLOR_BTN_WARN = "#f59e0b"
COLOR_BTN_SUCCESS = "#10b981"
COLOR_TEXT = "#f8fafc"
COLOR_SUBTEXT = "#a78bfa"
COLOR_ROW_EVEN = "#0c0a12"
COLOR_ROW_ODD = "#18122b"
COLOR_SELECTED = "#0e7490"

APP_TITLE = "RPGM Translator"
VERSION = "1.1.0"
SCRIPT_DIR = Path(__file__).parent


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(t(parent.current_lang, "settings_title"))
        self.geometry("500x420")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self._load()

    def _build(self):
        pad = {"padx": 16, "pady": 6}
        ctk.CTkLabel(self, text=t(self.parent.current_lang, "openrouter_key")).pack(anchor="w", **pad)
        self.or_key = ctk.CTkEntry(self, width=460, show="*")
        self.or_key.pack(**pad)

        ctk.CTkLabel(self, text=t(self.parent.current_lang, "openrouter_model")).pack(anchor="w", **pad)
        self.or_model = ctk.CTkComboBox(self, values=OPENROUTER_FREE_MODELS, width=460)
        self.or_model.pack(**pad)

        ctk.CTkLabel(self, text=t(self.parent.current_lang, "llama_repo")).pack(anchor="w", **pad)
        self.llama_repo = ctk.CTkEntry(self, width=460)
        self.llama_repo.pack(**pad)

        ctk.CTkLabel(self, text=t(self.parent.current_lang, "llama_file")).pack(anchor="w", **pad)
        self.llama_file = ctk.CTkEntry(self, width=460)
        self.llama_file.pack(**pad)

        ctk.CTkButton(self, text="Save", command=self._save, fg_color=COLOR_BTN_MAIN).pack(pady=12)

    def _load(self):
        s = self.parent.settings
        self.or_key.insert(0, s.get("openrouter_api_key", ""))
        self.or_model.set(s.get("openrouter_model", OPENROUTER_FREE_MODELS[0]))
        self.llama_repo.insert(0, s.get("llama_model_repo", DEFAULT_SETTINGS["llama_model_repo"]))
        self.llama_file.insert(0, s.get("llama_model_file", ""))

    def _save(self):
        self.parent.settings.update({
            "openrouter_api_key": self.or_key.get().strip(),
            "openrouter_model": self.or_model.get(),
            "llama_model_repo": self.llama_repo.get().strip(),
            "llama_model_file": self.llama_file.get().strip(),
        })
        self.parent._save_settings()
        self.destroy()


class RPGMTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        # Usa le dimensioni dello schermo per avviare in fit screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}")
        self.minsize(950, 650)
        self.configure(fg_color=COLOR_BG)

        self.current_lang = "en"
        self.settings = load_settings()
        self.game_path: Path | None = None
        self.extractor: RPGMExtractor | None = None
        self.items: list[ExtractedString] = []
        self.filtered: list[ExtractedString] = []
        self.translator: Translator | None = None
        self._page = 0
        self._page_size = 100
        self._selected_index: int | None = None
        self._analysis_done = False

        self._build_ui()
        self._set_icon()
        self._restore_last_game()

    # ─── UI Build ──────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = ctk.CTkFrame(self, fg_color=COLOR_PANEL, height=90)
        top.pack(fill="x", padx=0, pady=0)
        top.pack_propagate(False)

        self.logo_label = ctk.CTkLabel(top, text="")
        self.logo_label.pack(side="left", padx=12, pady=8)
        self._set_logo(top)

        game_frame = ctk.CTkFrame(top, fg_color="transparent")
        game_frame.pack(side="left", fill="both", expand=True, padx=8)

        self.game_section_label = ctk.CTkLabel(game_frame, text=t(self.current_lang, "game_selection"),
                                             font=ctk.CTkFont(size=12, weight="bold"),
                                             text_color=COLOR_SUBTEXT)
        self.game_section_label.pack(anchor="w")

        path_row = ctk.CTkFrame(game_frame, fg_color="transparent")
        path_row.pack(fill="x")
        self.path_entry = ctk.CTkEntry(path_row, width=520, placeholder_text="...")
        self.path_entry.pack(side="left", padx=(0, 6))
        ctk.CTkButton(path_row, text=t(self.current_lang, "btn_app"), width=60,
                      fg_color=COLOR_ACCENT, text_color="black", command=self._pick_app).pack(side="left", padx=2)
        ctk.CTkButton(path_row, text=t(self.current_lang, "btn_folder"), width=80,
                      fg_color=COLOR_ACCENT, text_color="black", command=self._pick_folder).pack(side="left", padx=2)

        self.game_status = ctk.CTkLabel(game_frame, text=t(self.current_lang, "no_game"),
                                        text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=11))
        self.game_status.pack(anchor="w")

        # Progress
        prog_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, height=36)
        prog_frame.pack(fill="x", padx=0, pady=(2, 0))
        prog_frame.pack_propagate(False)
        self.progress = ctk.CTkProgressBar(prog_frame, height=14)
        self.progress.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(prog_frame, text="", text_color=COLOR_SUBTEXT,
                                           font=ctk.CTkFont(size=11))
        self.progress_label.pack(side="right", padx=12)

        # Filter + controls row
        ctrl = ctk.CTkFrame(self, fg_color=COLOR_PANEL, height=44)
        ctrl.pack(fill="x", pady=(2, 0))
        ctrl.pack_propagate(False)

        ctk.CTkLabel(ctrl, text="Filter:", text_color=COLOR_SUBTEXT).pack(side="left", padx=(12, 4))
        self.filter_var = ctk.StringVar(value="all")
        for val, key in [("all", "filter_all"), ("translated", "filter_translated"),
                         ("untranslated", "filter_untranslated")]:
            rb = ctk.CTkRadioButton(ctrl, text=t(self.current_lang, key), variable=self.filter_var,
                                    value=val, command=self._apply_filter)
            rb.pack(side="left", padx=4)

        ctk.CTkLabel(ctrl, text="Source:", text_color=COLOR_SUBTEXT).pack(side="left", padx=(20, 4))
        self.source_lang_var = ctk.StringVar(value=self.settings.get("source_lang", "Auto"))
        self.source_lang_combo = ctk.CTkComboBox(ctrl, values=["Auto"] + list(LANGUAGES.keys()), width=130,
                                                  variable=self.source_lang_var, command=self._on_source_lang_change)
        self.source_lang_combo.pack(side="left", padx=4)

        ctk.CTkLabel(ctrl, text=t(self.current_lang, "target_lang"), text_color=COLOR_SUBTEXT).pack(side="left", padx=(20, 4))
        self.lang_var = ctk.StringVar(value=self.settings.get("target_lang", "Italian"))
        self.lang_combo = ctk.CTkComboBox(ctrl, values=list(LANGUAGES.keys()), width=130,
                                          variable=self.lang_var, command=self._on_target_lang_change)
        self.lang_combo.pack(side="left", padx=4)

        ctk.CTkLabel(ctrl, text=t(self.current_lang, "backend"), text_color=COLOR_SUBTEXT).pack(side="left", padx=(16, 4))
        saved_backend = self.settings.get("backend", "bing_ultra")
        self.backend_var = ctk.StringVar(value=BACKEND_LABELS.get(saved_backend, "Bing Turbo"))
        self.backend_combo = ctk.CTkComboBox(ctrl, values=list(BACKENDS), width=140,
                                             variable=self.backend_var, command=self._on_backend_change)
        self.backend_combo.pack(side="left", padx=4)

        ctk.CTkLabel(ctrl, text=t(self.current_lang, "profile"), text_color=COLOR_SUBTEXT).pack(side="left", padx=(12, 4))
        self.profile_var = ctk.StringVar(value=self.settings.get("translation_profile", "Balanced"))
        self.profile_combo = ctk.CTkComboBox(ctrl, values=["Safe", "Balanced", "Fast"], width=105,
                                             variable=self.profile_var, command=self._on_profile_change)
        self.profile_combo.pack(side="left", padx=4)

        # Tabs
        self.tabs = ctk.CTkTabview(self, fg_color=COLOR_PANEL)
        self.tabs.pack(fill="both", expand=True, padx=0, pady=(2, 0))
        self.tab_strings = self.tabs.add(t(self.current_lang, "strings_tab"))
        self.tab_log = self.tabs.add(t(self.current_lang, "log_tab"))
        self._build_strings_tab()
        self._build_log_tab()

        # Bottom buttons
        bottom = ctk.CTkFrame(self, fg_color=COLOR_PANEL, height=56)
        bottom.pack(fill="x", pady=(2, 0))
        bottom.pack_propagate(False)

        self.btn_translate = ctk.CTkButton(bottom, text=f"▶  {t(self.current_lang, 'analyze_translate')}",
                                           fg_color=COLOR_BTN_SUCCESS, hover_color="#047857",
                                           text_color="white", width=180, command=self._analyze_translate)
        self.btn_translate.pack(side="left", padx=10, pady=10)

        self.btn_cancel = ctk.CTkButton(bottom, text=t(self.current_lang, "cancel"),
                                        fg_color=COLOR_BTN_WARN, hover_color="#b45309",
                                        text_color="white", width=100, command=self._cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=6, pady=10)

        self.btn_save = ctk.CTkButton(bottom, text=t(self.current_lang, "save"),
                                      fg_color=COLOR_ACCENT, text_color="black",
                                      width=110, command=self._save_translation)
        self.btn_save.pack(side="left", padx=6, pady=10)
        self.btn_save.configure(state="disabled")

        self.btn_export = ctk.CTkButton(bottom, text=t(self.current_lang, "export"),
                                        fg_color=COLOR_ACCENT_MAGENTA, text_color="white",
                                        width=110, command=self._export_patch)
        self.btn_export.pack(side="left", padx=6, pady=10)
        self.btn_export.configure(state="disabled")

        self.btn_restore_backup = ctk.CTkButton(bottom, text=t(self.current_lang, "restore_backup"),
                                                fg_color=COLOR_BTN_WARN, hover_color="#b45309",
                                                text_color="white", width=120, command=self._restore_backup)
        self.btn_restore_backup.pack(side="left", padx=6, pady=10)
        self.btn_restore_backup.configure(state="disabled")

        self.btn_forge = ctk.CTkButton(bottom, text=t(self.current_lang, "install_forge"),
                                       fg_color=COLOR_ACCENT_GOLD, text_color="black",
                                       width=140, command=self._install_forge)
        self.btn_forge.pack(side="left", padx=6, pady=10)
        self.btn_forge.configure(state="disabled")

        self.btn_clear_cache = ctk.CTkButton(bottom, text=t(self.current_lang, "clear_cache"),
                                             fg_color=COLOR_BTN_WARN, hover_color="#b45309",
                                             text_color="white", width=100, command=self._clear_cache)
        self.btn_clear_cache.pack(side="right", padx=6, pady=10)

        ctk.CTkButton(bottom, text=t(self.current_lang, "settings"), fg_color=COLOR_ACCENT,
                      text_color="black", width=100, command=self._open_settings).pack(side="right", padx=10, pady=10)

        next_lang = "IT" if self.current_lang == "en" else "EN"
        ctk.CTkButton(bottom, text=next_lang, fg_color=COLOR_ACCENT,
                      text_color="black", width=50, command=self._toggle_lang).pack(side="right", padx=6, pady=10)

        # Options row
        opts = ctk.CTkFrame(self, fg_color=COLOR_PANEL, height=44)
        opts.pack(fill="x")
        opts.pack_propagate(False)

        ctk.CTkLabel(opts, text="Options:", text_color=COLOR_SUBTEXT,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 8), pady=10)

        self.preserve_names_var = ctk.BooleanVar(value=self.settings.get("preserve_names", False))
        ctk.CTkSwitch(opts, text=t(self.current_lang, "preserve_names"), variable=self.preserve_names_var,
                      command=self._on_option_change,
                      onvalue=True, offvalue=False).pack(side="left", padx=10, pady=8)

    def _build_strings_tab(self):
        self.tab_strings.grid_rowconfigure(0, weight=1)
        self.tab_strings.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self.tab_strings, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=0)

        # File filter sidebar
        file_sidebar = ctk.CTkFrame(main_frame, fg_color=COLOR_PANEL, width=200)
        file_sidebar.grid(row=0, column=0, sticky="ns", padx=(8, 4), pady=8)
        file_sidebar.grid_propagate(False)

        ctk.CTkLabel(file_sidebar, text="Files", text_color=COLOR_SUBTEXT,
                    font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(8, 4))

        self.file_filter_frame = ctk.CTkScrollableFrame(file_sidebar, fg_color="transparent")
        self.file_filter_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.file_filter_var = ctk.StringVar(value="All files")
        self.file_radio_buttons = {}

        # Table area
        table_outer = ctk.CTkFrame(main_frame, fg_color=COLOR_BG)
        table_outer.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        table_outer.grid_rowconfigure(2, weight=1)
        table_outer.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(table_outer, fg_color=COLOR_PANEL, height=36)
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        search_row.grid_propagate(False)
        ctk.CTkLabel(search_row, text=t(self.current_lang, "search"), text_color=COLOR_SUBTEXT).pack(side="left", padx=(8, 4))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = ctk.CTkEntry(search_row, width=310, textvariable=self.search_var,
                                         placeholder_text=t(self.current_lang, "search_placeholder"))
        self.search_entry.pack(side="left", padx=(0, 6), pady=4)
        self._search_scopes = {
            t(self.current_lang, "search_original"): "original",
            t(self.current_lang, "search_translation"): "translation",
            t(self.current_lang, "search_both"): "both",
        }
        self.search_scope_var = ctk.StringVar(value=t(self.current_lang, "search_both"))
        self.search_scope_combo = ctk.CTkComboBox(search_row, values=list(self._search_scopes), width=150,
                                                   variable=self.search_scope_var, command=self._on_search_scope_change)
        self.search_scope_combo.pack(side="left", padx=4, pady=4)

        # Header
        header = ctk.CTkFrame(table_outer, fg_color=COLOR_ACCENT, height=28)
        header.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        header.grid_propagate(False)
        cols = [
            (t(self.current_lang, "col_num"), 50),
            (t(self.current_lang, "col_kind"), 90),
            (t(self.current_lang, "col_original"), 420),
            (t(self.current_lang, "col_translation"), 420),
            (t(self.current_lang, "col_file"), 180),
        ]
        for text, width in cols:
            ctk.CTkLabel(header, text=text, width=width,
                         font=ctk.CTkFont(weight="bold"), anchor="w",
                         text_color=COLOR_TEXT).pack(side="left", padx=4, pady=2)

        self.table_frame = ctk.CTkScrollableFrame(table_outer, fg_color=COLOR_BG)
        self.table_frame.grid(row=2, column=0, sticky="nsew")

        # Pagination
        pag = ctk.CTkFrame(table_outer, fg_color=COLOR_PANEL, height=32)
        pag.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        pag.grid_propagate(False)
        ctk.CTkButton(pag, text="◀", width=36, fg_color=COLOR_ACCENT,
                      command=self._prev_page).pack(side="left", padx=6, pady=4)
        self.page_label = ctk.CTkLabel(pag, text="", text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=11))
        self.page_label.pack(side="left", padx=8)
        ctk.CTkButton(pag, text="▶", width=36, fg_color=COLOR_ACCENT,
                      command=self._next_page).pack(side="left", padx=2, pady=4)

        # Editor area
        editor_frame = ctk.CTkFrame(main_frame, fg_color=COLOR_PANEL)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(editor_frame, text="Edit selected translation:", text_color=COLOR_SUBTEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))
        self.edit_text = ctk.CTkTextbox(editor_frame, height=80, font=ctk.CTkFont(size=12))
        self.edit_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.edit_text.configure(state="disabled")

        btn_row = ctk.CTkFrame(editor_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="e", padx=10, pady=(0, 6))
        self.btn_edit_save = ctk.CTkButton(btn_row, text="Save Edit", width=100,
                                           fg_color=COLOR_BTN_MAIN, text_color="white", command=self._save_edit)
        self.btn_edit_save.pack(side="left", padx=4)
        self.btn_edit_save.configure(state="disabled")
        self.btn_replace_all = ctk.CTkButton(btn_row, text="Replace All", width=100,
                                             fg_color=COLOR_ACCENT, text_color="black", command=self._open_replace_dialog)
        self.btn_replace_all.pack(side="left", padx=4)
        self.btn_replace_all.configure(state="disabled")

    def _build_log_tab(self):
        self.tab_log.grid_rowconfigure(0, weight=1)
        self.tab_log.grid_columnconfigure(0, weight=1)
        self.log_text = ctk.CTkTextbox(self.tab_log, fg_color=COLOR_BG,
                                       font=ctk.CTkFont(family="Courier", size=11))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    def _set_icon(self):
        icon_path = SCRIPT_DIR / "logo_256.png"
        if icon_path.exists():
            self._tk_icon = ImageTk.PhotoImage(Image.open(icon_path))
            self.iconphoto(True, self._tk_icon)

    def _set_logo(self, parent):
        for candidate in ("logo_512.png", "logo_256.png", "logo_48.png"):
            logo_path = SCRIPT_DIR / candidate
            if logo_path.exists():
                pil_img = Image.open(logo_path)
                self._ctk_logo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(64, 64))
                self.logo_label.configure(image=self._ctk_logo, text="")
                return

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _t(self, key: str, *args) -> str:
        return t(self.current_lang, key, *args)

    def log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def root_after(self, func):
        self.after(0, func)

    def _set_progress(self, value: float, text: str = ""):
        self.progress.set(max(0.0, min(1.0, value)))
        self.progress_label.configure(text=text)

    # ─── Table rendering ─────────────────────────────────────────────────

    def _render_table(self, items: list[ExtractedString]):
        self.filtered = items
        self._page = 0
        self._selected_index = None
        self._render_page()

    def _render_page(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        items = self.filtered
        start = self._page * self._page_size
        end = start + self._page_size
        page_items = items[start:end]

        for i, item in enumerate(page_items):
            abs_i = start + i
            bg = COLOR_ROW_EVEN if abs_i % 2 == 0 else COLOR_ROW_ODD
            if self._selected_index is not None and abs_i == self._selected_index:
                bg = COLOR_SELECTED
            row = ctk.CTkFrame(self.table_frame, fg_color=bg, height=28)
            row.pack(fill="x", pady=(0, 1))
            row.pack_propagate(False)

            cols_w = [50, 90, 420, 420, 180]
            vals = [
                str(abs_i + 1),
                item.kind,
                item.text[:70],
                strip_script_tokens(item.translated or "")[:70],
                item.file,
            ]
            for val, w in zip(vals, cols_w):
                lbl = ctk.CTkLabel(row, text=val, width=w, anchor="w",
                                   text_color=COLOR_TEXT if item.translated else COLOR_SUBTEXT,
                                   font=ctk.CTkFont(size=11))
                lbl.pack(side="left", padx=4, pady=2)

            def make_click(idx=abs_i, it=item):
                return lambda event: self._on_row_click(idx, it)
            row.bind("<Button-1>", make_click())
            for child in row.winfo_children():
                child.bind("<Button-1>", make_click())

        total_pages = max(1, (len(items) + self._page_size - 1) // self._page_size)
        self.page_label.configure(text=f"Page {self._page + 1} / {total_pages}  ({len(items)} strings)")

    def _on_row_click(self, abs_i: int, item: ExtractedString):
        self._selected_index = abs_i
        self._render_page()
        self.edit_text.configure(state="normal")
        self.edit_text.delete("1.0", "end")
        self.edit_text.insert("end", strip_script_tokens(item.translated if item.translated else ""))
        self.edit_text.configure(state="normal")
        self.btn_edit_save.configure(state="normal")

    def _save_edit(self):
        if self._selected_index is None or self._selected_index >= len(self.filtered):
            return
        item = self.filtered[self._selected_index]
        edited_text = self.edit_text.get("1.0", "end-1c")
        # Reinserisci i token se l'item ne ha
        if item.has_script_tokens and item.token_map:
            item.translated = restore_script_tokens(edited_text, item.token_map)
        else:
            item.translated = edited_text
        self._render_page()
        self.btn_save.configure(state="normal")
        self.btn_export.configure(state="disabled")

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def _next_page(self):
        total_pages = max(1, (len(self.filtered) + self._page_size - 1) // self._page_size)
        if self._page < total_pages - 1:
            self._page += 1
            self._render_page()

    def _apply_filter(self):
        f = self.filter_var.get()
        if f == "translated":
            visible = [i for i in self.items if i.translated]
        elif f == "untranslated":
            visible = [i for i in self.items if not i.translated]
        else:
            visible = self.items

        # Filtro per file
        file_filter = self.file_filter_var.get()
        if file_filter != "All files":
            visible = [i for i in visible if i.file == file_filter]

        query = self.search_var.get().strip().casefold()
        scope = self._search_scopes.get(self.search_scope_var.get(), "both")
        if query:
            def matches(item: ExtractedString) -> bool:
                original = item.text.casefold()
                translation = item.translated.casefold()
                if scope == "original":
                    return query in original
                if scope == "translation":
                    return query in translation
                return query in original or query in translation
            visible = [item for item in visible if matches(item)]
        self._render_table(visible)

    def _on_search_scope_change(self, _value: str):
        self._apply_filter()

    def _on_file_filter_change(self, _value: str):
        self._apply_filter()

    def _update_file_filter_options(self):
        """Aggiorna le opzioni del filtro file basandosi sugli items caricati."""
        if not self.items:
            return
        # Pulisci i radiobutton esistenti
        for widget in self.file_filter_frame.winfo_children():
            widget.destroy()
        self.file_radio_buttons.clear()

        files = sorted(set(item.file for item in self.items))
        all_files = ["All files"] + files

        for file_name in all_files:
            rb = ctk.CTkRadioButton(self.file_filter_frame, text=file_name,
                                   variable=self.file_filter_var, value=file_name,
                                   command=self._on_file_filter_change)
            rb.pack(anchor="w", pady=2)
            self.file_radio_buttons[file_name] = rb

    def _open_replace_dialog(self):
        """Apre il dialogo per Replace All."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Replace All")
        dialog.geometry("400x300")
        dialog.configure(fg_color=COLOR_PANEL)
        dialog.transient(self)
        dialog.grab_set()

        # Find field
        ctk.CTkLabel(dialog, text="Find:", text_color=COLOR_SUBTEXT).pack(anchor="w", padx=20, pady=(20, 4))
        find_entry = ctk.CTkEntry(dialog, width=350)
        find_entry.pack(padx=20, pady=(0, 12))

        # Replace field
        ctk.CTkLabel(dialog, text="Replace with:", text_color=COLOR_SUBTEXT).pack(anchor="w", padx=20, pady=(0, 4))
        replace_entry = ctk.CTkEntry(dialog, width=350)
        replace_entry.pack(padx=20, pady=(0, 12))

        # Options
        case_sensitive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(dialog, text="Case sensitive", variable=case_sensitive_var).pack(anchor="w", padx=20, pady=(0, 8))

        filtered_only_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(dialog, text="Only in filtered items", variable=filtered_only_var).pack(anchor="w", padx=20, pady=(0, 12))

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)

        def do_replace():
            find_text = find_entry.get().strip()
            replace_text = replace_entry.get().strip()
            if not find_text:
                messagebox.showerror("Error", "Please enter text to find")
                return

            case_sensitive = case_sensitive_var.get()
            only_filtered = filtered_only_var.get()

            # Scegli gli items su cui applicare
            target_items = self.filtered if only_filtered else self.items

            count = 0
            for item in target_items:
                if item.translated:
                    if case_sensitive:
                        if find_text in item.translated:
                            item.translated = item.translated.replace(find_text, replace_text)
                            count += 1
                    else:
                        if find_text.lower() in item.translated.lower():
                            # Case-insensitive replace
                            import re
                            pattern = re.compile(re.escape(find_text), re.IGNORECASE)
                            item.translated = pattern.sub(replace_text, item.translated)
                            count += 1

            if count > 0:
                self._render_table(self.filtered if only_filtered else self.items)
                self.btn_save.configure(state="normal")
                self.btn_export.configure(state="disabled")
                messagebox.showinfo("Replace All", f"Replaced in {count} items")
                dialog.destroy()
            else:
                messagebox.showinfo("Replace All", "No matches found")

        ctk.CTkButton(btn_frame, text="Replace", fg_color=COLOR_BTN_SUCCESS, width=100,
                      command=do_replace).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color=COLOR_BTN_WARN, width=100,
                      command=dialog.destroy).pack(side="left", padx=4)

    # ─── Game Selection ──────────────────────────────────────────────────

    def _pick_app(self):
        initialdir = str(Path.home() / "Downloads")
        path = filedialog.askopenfilename(title=self._t("select_app"), initialdir=initialdir)
        if path:
            self._set_game(Path(path))

    def _pick_folder(self):
        initialdir = str(Path.home() / "Downloads")
        path = filedialog.askdirectory(title=self._t("select_folder"), initialdir=initialdir)
        if path:
            self._set_game(Path(path))

    def _set_game(self, path: Path):
        try:
            info = detect_engine(path)
        except DetectionError as e:
            messagebox.showerror(self._t("error"), str(e))
            return
        self.game_path = path
        self.extractor = None
        self.items = []
        self.filtered = []
        self._analysis_done = False
        self._save_settings()
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, str(path))
        engine_label = info.get("engine", "mv").upper()
        self.game_status.configure(text=f"{self._t('game_selected')}: {path.name}  |  {self._t('detected_engine')}: {engine_label}",
                                   text_color=COLOR_BTN_MAIN)
        self.btn_translate.configure(state="normal")
        self.btn_forge.configure(state="normal")
        self.btn_restore_backup.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self._render_table([])
        self.log(f"Selected game: {path}")
        self.log(f"Detected engine: {engine_label}")

    # ─── Pipelines ───────────────────────────────────────────────────────

    def _analyze_only(self):
        if not self.game_path:
            messagebox.showerror(self._t("error"), self._t("select_game_first"))
            return
        self._reset_ui_for_work()
        threading.Thread(target=self._analyze_thread, daemon=True).start()

    def _analyze_translate(self):
        if not self.game_path:
            messagebox.showerror(self._t("error"), self._t("select_game_first"))
            return
        self._reset_ui_for_work()
        threading.Thread(target=self._analyze_translate_thread, daemon=True).start()

    def _reset_ui_for_work(self):
        self.btn_translate.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.btn_forge.configure(state="disabled")
        self.btn_restore_backup.configure(state="disabled")
        self.progress.set(0)

    def _on_work_done(self):
        self.btn_translate.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        if self.game_path:
            self.btn_forge.configure(state="normal")
            self.btn_restore_backup.configure(state="normal")
        if self.items and self.game_path:
            self.btn_save.configure(state="normal")
            self.btn_export.configure(state="normal")
            self.btn_replace_all.configure(state="normal")
        self._apply_filter()

    def _cancel(self):
        self.btn_cancel.configure(state="disabled")
        if self.translator:
            self.translator.cancel()
            self.log("Cancelling translation...")
        else:
            self.log("No translation in progress to cancel.")

    def _install_forge(self):
        if not self.game_path:
            messagebox.showerror(self._t("error"), self._t("select_game_first"))
            return
        try:
            forge_path = ensure_forge_js()
        except FileNotFoundError as e:
            messagebox.showerror(self._t("error"), str(e))
            return
        self._reset_ui_for_work()
        threading.Thread(target=self._install_forge_thread, args=(forge_path,), daemon=True).start()

    def _install_forge_thread(self, forge_path: Path):
        try:
            self.root_after(lambda: self._set_progress(0.5, self._t("install_forge")))
            result = install_forge(self.game_path, forge_path, key="1")
            msg = self._t("forge_installed", result["forge_js"], result["key"])
            self.log(msg)
            self.root_after(lambda: self._set_progress(1.0, msg))
            self.root_after(self._on_work_done)
            self.root_after(lambda: messagebox.showinfo(self._t("forge_installed_title"), msg))
        except Exception as e:
            self._handle_error(e)

    # ─── Threads ─────────────────────────────────────────────────────────

    def _apply_local_cache(self):
        if not self.extractor or not self.items:
            return
        cfg = self._make_config()
        cfg_key = f"{cfg.source_lang}|{cfg.target_lang}"
        cached = load_local_cache(self.extractor.root, cfg_key)
        if not cached:
            return
        applied = 0
        for item in self.items:
            key = f"{item.file}:{'.'.join(str(k) for k in item.key_path)}:{item.text}"
            if key in cached:
                item.translated = cached[key]
                applied += 1
        if applied:
            self.log(f"Loaded {applied} translations from local cache.")

    def _analyze_thread(self):
        try:
            self.log(f"Starting analysis of: {self.game_path}")
            self.root_after(lambda: self._set_progress(0.1, self._t("progress_analyzing")))
            self.extractor = RPGMExtractor(self.game_path, use_original=True)
            self.items = self.extractor.extract(
                progress_cb=lambda c, t, msg: self.root_after(
                    lambda c=c, t=t: self._set_progress(0.1 + 0.2 * (c / max(t, 1)), msg)
                )
            )
            self._apply_local_cache()
            self._analysis_done = True
            translated_count = sum(1 for i in self.items if i.translated)
            msg = self._t("analysis_complete", len(self.items), self.extractor.files_count)
            if translated_count:
                msg += f" ({translated_count} from cache)"
            self.log(msg)
            self.root_after(lambda: self._set_progress(1.0, msg))
            self.root_after(self._update_file_filter_options)
            self.root_after(self._on_work_done)
        except Exception as e:
            self._handle_error(e)

    def _translate_thread(self):
        try:
            targets = [i for i in self.items if not i.translated]
            if not targets:
                self.log("No untranslated strings.")
                self.root_after(self._on_work_done)
                return
            self._do_translate(targets)
            self.root_after(self._on_work_done)
        except Exception as e:
            self._handle_error(e)

    def _analyze_translate_thread(self):
        try:
            # Analyze
            self.log(f"Starting analysis & translation for: {self.game_path}")
            self.root_after(lambda: self._set_progress(0.05, self._t("progress_analyzing")))
            self.extractor = RPGMExtractor(self.game_path, use_original=True)
            self.items = self.extractor.extract(
                progress_cb=lambda c, t, msg: self.root_after(
                    lambda c=c, t=t: self._set_progress(0.05 + 0.45 * (c / max(t, 1)), msg)
                )
            )
            self._apply_local_cache()
            self._analysis_done = True
            cached_count = sum(1 for i in self.items if i.translated)
            self.log(self._t("analysis_complete", len(self.items), self.extractor.files_count))
            if cached_count:
                self.log(f"{cached_count} translations loaded from local cache.")

            # Translate only items still missing a translation
            self._do_translate([i for i in self.items if not i.translated], base_progress=0.5, range_progress=0.5)

            self.root_after(lambda: self._set_progress(1.0, self._t("translation_complete",
                                                                   sum(1 for i in self.items if i.translated),
                                                                   len(self.items))))
            self.root_after(self._on_work_done)
            self.root_after(lambda: messagebox.showinfo(self._t("translation_complete_title"),
                                                          self._t("translation_complete_msg")))
        except Exception as e:
            self._handle_error(e)

    def _do_translate(self, targets: list[ExtractedString], base_progress: float = 0.0, range_progress: float = 1.0):
        if not targets:
            return
        self.root_after(lambda: self._set_progress(base_progress, self._t("progress_translating")))
        cfg = self._make_config()
        self.translator = Translator(cfg)
        
        # Separazione: items con segmenti vs senza segmenti
        items_with_segments = [i for i in targets if i.segments]
        items_without_segments = [i for i in targets if not i.segments]
        
        def _progress(done, total):
            frac = base_progress + (done / max(total, 1)) * range_progress
            self.root_after(lambda: self._set_progress(frac, f"{int(frac * 100)}%  ({done}/{total})"))
        
        # Traduzione items senza segmenti (metodo vecchio per compatibilità)
        if items_without_segments:
            texts = [i.clean_text for i in items_without_segments]
            result = self.translator.translate_many(texts, progress_cb=_progress)
            for item in items_without_segments:
                item.translated = result.get(item.clean_text, "")
        
        # Traduzione items con segmenti (nuovo metodo basato su delimitatori)
        if items_with_segments:
            from rpgm_parser import recompose_text
            # Raccogli tutti i segmenti di testo da tutti gli items
            all_segments = []
            item_segment_map = []  # mappa item -> indici segmenti
            for item in items_with_segments:
                start_idx = len(all_segments)
                for seg in item.segments:
                    if seg["type"] == "text":
                        all_segments.append(seg["content"])
                end_idx = len(all_segments)
                item_segment_map.append((item, start_idx, end_idx))
            
            # Traduci tutti i segmenti in un unico batch
            if all_segments:
                translations = self.translator.translate_many(all_segments, progress_cb=_progress)
                
                # Distribuisci le traduzioni back agli items
                for item, start_idx, end_idx in item_segment_map:
                    translated_segments = []
                    for seg in item.segments:
                        if seg["type"] == "text":
                            original = seg["content"]
                            translated = translations.get(original, original)
                            translated_segments.append({"type": "text", "content": translated})
                        else:
                            translated_segments.append(seg)
                    item.translated = recompose_text(translated_segments)
        
        done = sum(1 for i in self.items if i.translated)
        msg = self._t("translation_complete", done, len(self.items))
        self.log(msg)
        self.root_after(lambda: self._set_progress(base_progress + range_progress, msg))

    def _make_config(self) -> TranslatorConfig:
        lang_name = self.lang_var.get()
        target = LANGUAGES.get(lang_name, "it")
        source_lang_name = self.source_lang_var.get()
        # Se "Auto", usa "auto" per il rilevamento automatico, altrimenti mappa la lingua
        if source_lang_name == "Auto":
            source = "auto"
        else:
            source = LANGUAGES.get(source_lang_name, "en")
        s = self.settings
        preserve_names = bool(self.preserve_names_var.get())
        character_names = frozenset()
        if preserve_names and self.extractor:
            character_names = extract_character_names(self.extractor.root)
        return TranslatorConfig(
            backend=BACKENDS[self.backend_var.get()],
            source_lang=source,
            target_lang=target,
            libre_endpoint=s.get("libre_endpoint", "http://localhost:5000"),
            openrouter_api_key=s.get("openrouter_api_key", ""),
            openrouter_model=s.get("openrouter_model", OPENROUTER_FREE_MODELS[0]),
            llama_model_repo=s.get("llama_model_repo", DEFAULT_SETTINGS["llama_model_repo"]),
            llama_model_file=s.get("llama_model_file", ""),
            translation_profile=self.profile_var.get(),
            preserve_names=preserve_names,
            character_names=character_names,
            translate_menu=False,
        )

    # ─── Save / Export ─────────────────────────────────────────────────────

    def _save_translation(self):
        if not self.game_path or not self.extractor or not self.items:
            return
        self._reset_ui_for_work()
        threading.Thread(target=self._save_thread, daemon=True).start()

    def _save_thread(self):
        try:
            self.root_after(lambda: self._set_progress(0.5, self._t("progress_saving")))
            self._do_save()
            msg = self._t("saved", len([i for i in self.items if i.translated]), self.extractor.root)
            self.log(msg)
            self.root_after(lambda: self._set_progress(1.0, msg))
            self.root_after(self._on_work_done)
            self.root_after(lambda: self.btn_export.configure(state="normal"))
            self.root_after(lambda: messagebox.showinfo(self._t("save_complete_title"), msg))
        except Exception as e:
            self._handle_error(e)

    def _do_save(self):
        if not self.game_path or not self.extractor:
            return
        self.log("Creating backup...")
        backup_data_dir(self.extractor.root)
        self.log("Patching game data...")
        patched = patch_data_files(self.extractor.root, self.items)
        self.log(f"Patched {patched} strings.")
        cfg = self._make_config()
        cfg_key = f"{cfg.source_lang}|{cfg.target_lang}"
        save_local_cache(self.extractor.root, cfg_key, self.items)
        self.log("Local cache saved.")

    def _export_patch(self):
        if not self.game_path or not self.extractor:
            return
        lang_code = LANGUAGES.get(self.lang_var.get(), "it")
        default_name = f"{self.extractor.root.name}-{lang_code}"
        dest = filedialog.askdirectory(title=f"Export patch for '{default_name}'")
        if not dest:
            return
        threading.Thread(target=self._export_thread, args=(Path(dest), lang_code), daemon=True).start()

    def _export_thread(self, dest: Path, lang_code: str):
        tmp_parent: Path | None = None
        try:
            self.root_after(lambda: self._set_progress(0.3, self._t("progress_patching")))
            src_root = self.extractor.root
            # Apply the current translations to a temporary copy of the game data
            # so the exported patch is translated without forcing a Save first,
            # and without touching the original game files.
            tmp_parent = Path(tempfile.mkdtemp(prefix="rpgm_export_"))
            tmp_root = tmp_parent / src_root.name
            src_data = src_root / "www" / "data" if (src_root / "www" / "data").is_dir() else src_root / "data"
            dst_data = tmp_root / src_data.relative_to(src_root)
            dst_data.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_data, dst_data)
            patch_data_files(tmp_root, self.items)
            self.root_after(lambda: self._set_progress(0.7, self._t("progress_exporting")))
            export_dir = export_patch(tmp_root, dest, lang_code)
            msg = self._t("exported", export_dir)
            self.log(msg)
            self.root_after(lambda: self._set_progress(1.0, msg))
            self.root_after(self._on_work_done)
        except Exception as e:
            self._handle_error(e)
        finally:
            if tmp_parent is not None:
                shutil.rmtree(tmp_parent, ignore_errors=True)

    # ─── Settings & Options ──────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self)

    def _clear_cache(self):
        if not messagebox.askyesno(self._t("clear_cache_title"), self._t("clear_cache_confirm")):
            return

        removed = 0
        # Global cache files
        cache_dir = Path.home() / ".cache" / "rpgm-translator"
        if cache_dir.exists():
            for cache_file in cache_dir.glob("translation_cache_*.json"):
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception as e:
                    self.log(f"Could not delete {cache_file}: {e}")

        # Local cache for selected game
        if self.game_path:
            try:
                info = detect_engine(self.game_path)
                local_cache = info["root"] / "trans_cache.json"
                if local_cache.exists():
                    local_cache.unlink()
                    removed += 1
            except Exception as e:
                self.log(f"Could not detect local cache: {e}")

        msg = self._t("clear_cache_done", removed)
        self.log(msg)
        messagebox.showinfo(self._t("clear_cache_title"), msg)

    def _restore_backup(self):
        if not self.game_path:
            messagebox.showerror(self._t("error"), self._t("select_game_first"))
            return
        if not messagebox.askyesno(self._t("restore_backup_title"), self._t("restore_backup_confirm")):
            return
        try:
            info = detect_engine(self.game_path)
            root = info["root"]
            restored = restore_data_backup(root)
            self.extractor = None
            self.items = []
            self.filtered = []
            self._analysis_done = False
            self._render_table([])
            msg = self._t("restore_backup_done", restored.name)
            self.log(msg)
            messagebox.showinfo(self._t("restore_backup_title"), msg)
        except WriteError as e:
            self.log(str(e))
            messagebox.showinfo(self._t("restore_backup_title"), str(e))
        except Exception as e:
            self._handle_error(e)

    def _toggle_lang(self):
        self.current_lang = "it" if self.current_lang == "en" else "en"
        self._rebuild_ui()

    def _rebuild_ui(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        self._apply_filter()

    def _on_target_lang_change(self, language: str):
        self.settings["target_lang"] = language
        self._save_settings()

    def _on_source_lang_change(self, language: str):
        self.settings["source_lang"] = language
        self._save_settings()

    def _on_backend_change(self, label: str):
        self.settings["backend"] = BACKENDS[label]
        self._save_settings()

    def _on_profile_change(self, profile: str):
        self.settings["translation_profile"] = profile
        self._save_settings()

    def _on_option_change(self):
        self.settings["preserve_names"] = bool(self.preserve_names_var.get())
        self._save_settings()

    def _load_settings(self):
        self.settings = load_settings()

    def _save_settings(self):
        save_settings(self.settings)

    def _restore_last_game(self):
        pass

    # ─── Error handling ───────────────────────────────────────────────────

    def _handle_error(self, exc: Exception):
        err = str(exc)
        if self.translator and self.translator.cancelled:
            self.log(self._t("translation_cancelled"))
            self.root_after(lambda: self._set_progress(0.0, self._t("translation_cancelled")))
        else:
            self.log(f"Error: {err}")
            self.root_after(lambda: messagebox.showerror(self._t("error"), err))
        self.root_after(self._on_work_done)


def main():
    app = RPGMTranslatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
