# 🎮 RPGM-Translator

![RPGM-Translator Logo](logo_512.png)

![Python](https://img.shields.io/badge/python-3.9+-06b6d4.svg)
![Version](https://img.shields.io/badge/version-1.1.0-10b981.svg)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-7c3aed.svg)
![License](https://img.shields.io/badge/license-As--Is-f59e0b.svg)

A GUI tool to translate **RPG Maker MV/MZ** games automatically.

Inspired by the logic of **Ren'Py Translator** and the interface style of **WTForge**.

![RPGM-Translator GUI](translator-gui.png)

## ✨ Features

- 🕹️ Auto-detects **RPG Maker MV/MZ** games.
- 📝 Extracts translatable strings from:
  - 🗺️ `Map*.json` (dialogues, choices, scrolling text)
  - 🔁 `CommonEvents.json`
  - ⚙️ `System.json` (game title, terms, labels)
  - 🛡️ `Items.json`, `Weapons.json`, `Armors.json`, `Skills.json`, `States.json`, `Enemies.json`, `Actors.json`, `Classes.json`
  - 🔌 `js/plugins.js` (translatable plugin text)
- 🌍 Translation backends: **Google Turbo**, **Bing Ultra**, **OpenRouter**, **Llama local**.
- 🔎 Editable translation table with filters (All / Translated / Untranslated) and live search by original text, translation, or both.
- 💾 In-place patching with one protected original `data` backup.
- 🗂️ Global and local translation cache, with a one-click cleanup option.
- 📦 Export translated `www/data` as a patch.

## 🆕 Latest

- **String search** — filter the table live by original text, translated text, or both.
- **Restore Backup** — restore the game from the single original `data_bak_original` backup.
- **Safe script dialogue translation** — preserves dialogue prefixes, placeholders, asset identifiers, and plugin command internals while translating visible text.

## 📋 Requirements

- Python 3.9+
- `customtkinter`, `pillow`, `deep-translator`, `requests`

## 🚀 Quick Start

```bash
# macOS / Linux
./start.sh

# Windows
start.bat

# Or directly
python3 rpgm_tool.py
```

## 🔄 Workflow

1. 🎮 **Select Game** — Click `.app` (macOS) or `Folder` and choose the game directory.
2. 🧠 **Analyze & Translate** — Extract and translate all strings automatically.
3. ✏️ **Edit** — Review or edit any string directly in the table.
4. 💾 **Save** — Patch the game files (the original backup is created only once).
5. 📦 **Export** — Optionally export the translated `www/data` as a patch.
6. ♻️ **Start over** — Use **Restore Backup**, then **Clear cache**, before analyzing and translating again.

## 🛡️ Backup

Before the first patch, the tool creates `www/data_bak_original`. This is the only backup kept, and **Restore Backup** always restores from it.

## 🙏 Credits

- Cheat mod powered by **[Forge for RPGM MV/MZ](https://gitgud.io/serjura/forge-mvmz)** by serjura / zero64801.
- The keybind to open the cheat UI is patched to the `1` key for quick access.

## ⚠️ License

Provided "as-is" without warranty. Use at your own risk.
