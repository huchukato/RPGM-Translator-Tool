"""
RPGM-Translator - Settings and localization utilities
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
SETTINGS_FILE = SCRIPT_DIR / "rpgm_settings.json"

LANGUAGES = {
    "English": "en", "Italian": "it", "French": "fr", "Spanish": "es",
    "German": "de", "Portuguese": "pt", "Japanese": "ja", "Chinese": "zh",
    "Russian": "ru", "Korean": "ko", "Arabic": "ar",
}

BACKENDS = {
    "Google Turbo": "google_turbo",
    "Bing Turbo": "bing_ultra",
    "OpenRouter": "openrouter",
    "Llama Local": "llama",
}
BACKEND_LABELS = {value: label for label, value in BACKENDS.items()}

UI_TEXTS = {
    "en": {
        "title": "RPGM Translator",
        "game_selection": "Game Selection",
        "game_selected": "Game selected",
        "no_game": "No game selected",
        "select_game_first": "Select a game first",
        "select_app": "Select .app game",
        "select_folder": "Select game folder",
        "btn_app": ".app",
        "btn_folder": "Folder",
        "strings_tab": "Strings",
        "log_tab": "Log",
        "filter_all": "All",
        "filter_translated": "Translated",
        "filter_untranslated": "Untranslated",
        "target_lang": "Target language:",
        "backend": "Backend:",
        "profile": "Profile:",
        "analyze": "Analyze Game",
        "analyze_translate": "Analyze & Translate",
        "translate_all": "Translate All",
        "translate_sel": "Translate Selected",
        "save": "Save Translation",
        "export": "Export Patch",
        "install_forge": "Install Forge Cheat Mod",
        "forge_select_file": "Select forge.js downloaded from the Forge release page",
        "forge_installed": "Forge installed at {0} with Toggle Cheat UI key '{1}'",
        "forge_installed_title": "Forge Installed",
        "settings": "Settings",
        "cancel": "Cancel",
        "start_translation": "Start Translation",
        "analysis_complete": "Analysis complete: {} strings in {} files",
        "translation_complete": "Translation complete: {}/{} strings",
        "translation_complete_title": "Translation Complete",
        "translation_complete_msg": "Translation finished. You can review and edit the strings in the table before saving.",
        "saved": "Saved {} strings in {}",
        "exported": "Exported patch to {}",
        "error": "Error",
        "col_num": "#",
        "col_kind": "Kind",
        "col_original": "Original",
        "col_translation": "Translation",
        "col_file": "File",
        "preserve_names": "Preserve names",
        "detected_engine": "Detected engine",
        "progress_ready": "Ready",
        "progress_analyzing": "Analyzing...",
        "progress_translating": "Translating...",
        "progress_saving": "Saving...",
        "progress_patching": "Patching...",
        "progress_exporting": "Exporting...",
        "no_strings": "No translatable strings found",
        "settings_title": "Settings",
        "openrouter_key": "OpenRouter API Key:",
        "openrouter_model": "OpenRouter Model:",
        "llama_repo": "Llama model repo (HuggingFace):",
        "llama_file": "Llama model file (.gguf):",
        "clear_cache": "Clear cache",
        "clear_cache_title": "Clear cache",
        "clear_cache_confirm": "This will delete the global translation cache and the local cache for the selected game. This cannot be undone. Proceed?",
        "clear_cache_done": "Cache cleared: {0} file(s) removed.",
    },
    "it": {
        "title": "RPGM Translator",
        "game_selection": "Selezione Gioco",
        "game_selected": "Gioco selezionato",
        "no_game": "Nessun gioco selezionato",
        "select_game_first": "Seleziona prima un gioco",
        "select_app": "Seleziona .app gioco",
        "select_folder": "Seleziona cartella gioco",
        "btn_app": ".app",
        "btn_folder": "Cartella",
        "strings_tab": "Stringhe",
        "log_tab": "Log",
        "filter_all": "Tutte",
        "filter_translated": "Tradotte",
        "filter_untranslated": "Non tradotte",
        "target_lang": "Lingua target:",
        "backend": "Backend:",
        "profile": "Profilo:",
        "analyze": "Analizza Gioco",
        "analyze_translate": "Analizza & Traduci",
        "translate_all": "Traduci Tutto",
        "translate_sel": "Traduci Selezionate",
        "save": "Salva Traduzione",
        "export": "Esporta Patch",
        "install_forge": "Installa Forge Cheat Mod",
        "forge_select_file": "Seleziona forge.js scaricato dalla pagina release di Forge",
        "forge_installed": "Forge installato in {0} con tasto Toggle Cheat UI '{1}'",
        "forge_installed_title": "Forge Installata",
        "settings": "Impostazioni",
        "cancel": "Annulla",
        "start_translation": "Avvia Traduzione",
        "analysis_complete": "Analisi completata: {} stringhe in {} file",
        "translation_complete": "Traduzione completata: {}/{} stringhe",
        "translation_complete_title": "Traduzione Completata",
        "translation_complete_msg": "Traduzione terminata. Puoi revisionare e modificare le stringhe nella tabella prima di salvare.",
        "saved": "Salvate {} stringhe in {}",
        "exported": "Patch esportata in {}",
        "error": "Errore",
        "col_num": "#",
        "col_kind": "Tipo",
        "col_original": "Originale",
        "col_translation": "Traduzione",
        "col_file": "File",
        "preserve_names": "Preserva nomi",
        "detected_engine": "Motore rilevato",
        "progress_ready": "Pronto",
        "progress_analyzing": "Analisi in corso...",
        "progress_translating": "Traduzione in corso...",
        "progress_saving": "Salvataggio in corso...",
        "progress_patching": "Applicazione patch in corso...",
        "progress_exporting": "Esportazione in corso...",
        "no_strings": "Nessuna stringa traducibile trovata",
        "settings_title": "Impostazioni",
        "openrouter_key": "OpenRouter API Key:",
        "openrouter_model": "Modello OpenRouter:",
        "llama_repo": "Repo modello Llama (HuggingFace):",
        "llama_file": "File modello Llama (.gguf):",
        "clear_cache": "Cancella cache",
        "clear_cache_title": "Cancella cache",
        "clear_cache_confirm": "Verranno cancellate la cache globale e quella locale del gioco selezionato. Non è annullabile. Procedere?",
        "clear_cache_done": "Cache cancellata: {0} file rimossi.",
    },
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "target_lang": "Italian",
    "backend": "bing_ultra",
    "translation_profile": "Balanced",
    "preserve_names": False,
    "openrouter_api_key": "",
    "openrouter_model": "google/gemma-2-9b-it:free",
    "llama_model_repo": "llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF",
    "llama_model_file": "",
}


def load_settings() -> dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def t(lang: str, key: str, *args) -> str:
    text = UI_TEXTS.get(lang, UI_TEXTS["en"]).get(key, key)
    if args:
        return text.format(*args)
    return text
