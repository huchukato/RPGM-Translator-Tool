# Release Notes — RPGM-Translator v1.1.0

🎉 **First stable release of RPGM-Translator**, a GUI tool to automatically translate **RPG Maker MV/MZ** games.

---

## 🆕 v1.1.0 additions

- 🆕 **Edited filter** — show only strings that have been manually edited and saved in `manual_edits.json`.
- 🔄 **Reset translation** — the `Delete Row` button has been replaced with `Reset`: it clears the manual translation for selected rows, removes the entry from `manual_edits.json`, and leaves the original string unchanged.

## ✨ v1.0.0 additions

- 🎯 **Delimiter-based escape code handling** — preserves exact positioning of escape codes (colors, icons) by treating them as delimiters and translating only text segments between them.
- ⚡ **Optimized segment translation** — batch processes all text segments for improved performance.
- 🔧 **Enhanced RPG Maker prefix recognition** — supports multiple consecutive special characters in prefixes (e.g., `<<`, `>>`).
- 👤 **Character name preservation in dialogues** — replaces character names with placeholders before translation and restores them after, preventing unwanted name translations.
- 🔍 **File filter** — filter strings by source file (e.g., Items.json, Armor.json) for easier navigation.
- 🔄 **Replace All** — find and replace specific words across all translations or filtered items only, with case-sensitive option.
- 🐛 **Short text translation fix** — workaround for very short text not being translated by Google due to Unicode special characters.
- **Clear cache** button — delete the global and local translation caches from the GUI.
- **Script literal translation** — translatable strings inside JavaScript event commands (e.g., Oracle tips in `CommonEvents.json`) are now extracted and translated while preserving the surrounding code.
- **RPG Maker dialogue prefix handling** — general logic to handle RPG Maker dialogue prefixes with special separators (`<`, `>`, `}`, `{`, `^`) while translating only the dialogue content.
- **Smart $gameVariables.setValue handling** — intelligently distinguishes between short NPC names (preserved) and dialogue phrases (translated) in script literals.
- **Automatic character name extraction** — automatically extracts character names from `Actors.json` to preserve them from translation.
- **Dynamic filename pattern exclusion** — excludes dynamic filename patterns (e.g., `CHR-`, `-Body`, `-Face`) from translation to prevent crashes.

## ✨ What's New

- **Auto-detect engine** for RPG Maker MV and MZ games.
- **Extract** all translatable strings from:
  - Maps (`Map*.json`)
  - Common events (`CommonEvents.json`)
  - Game database (`System.json`, `Items.json`, `Weapons.json`, `Armors.json`, `Skills.json`, `States.json`, `Enemies.json`, `Actors.json`, `Classes.json`)
  - JavaScript plugins (`js/plugins.js`)
- **Translation backends** supported:
  - Google Turbo
  - Bing Ultra
  - OpenRouter
  - Local Llama
- **Editable translation table** with filters (All / Translated / Untranslated).
- **In-place saving** with automatic `www/data` backup.
- **Global and local** translation cache.
- **Patch export** to distribute translations.
- **Cheat Mod integration**: one-click install of the **Forge for RPGM MV/MZ** plugin, with the **Toggle Cheat UI** hotkey set to the `1` key.
- **Dark tabbed GUI** with a color palette inspired by the logo (black, cyan, magenta, purple and gold).

---

## 🚀 Installation

### macOS / Linux

```bash
./start.sh
```

### Windows

```bat
start.bat
```

### Manual

```bash
python3 rpgm_tool.py
```

## 🔄 Quick Workflow

1. **Select the game** folder (or `.app` on macOS).
2. Click **Analyze & Translate**.
3. Review/edit strings in the table.
4. Click **Save** to apply the translation (backup is created automatically).
5. Optionally click **Export** to create a translation patch.
6. Optionally click **Install Forge Cheat Mod** to add the cheat overlay.

---

## 🙏 Credits

- **Forge for RPGM MV/MZ** — cheat mod by [serjura / zero64801](https://gitgud.io/serjura/forge-mvmz).
- Interface and workflow inspired by **WTForge** and **Ren'Py Translator**.

---

## ⚠️ Notes

- Requires **Python 3.9+**.
- `forge.js` is bundled in this release; to update the cheat mod replace `forge.js` and rebuild the release.
- Use at your own risk: an automatic backup is created before every patch.
