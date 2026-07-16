# 🎮 RPGM-Translator

![RPGM-Translator Logo](logo_512.png)

![Python](https://img.shields.io/badge/python-3.9+-06b6d4.svg)
![Version](https://img.shields.io/badge/version-1.1.0-10b981.svg)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-7c3aed.svg)
![License](https://img.shields.io/badge/license-As--Is-f59e0b.svg)

Uno strumento GUI per tradurre automaticamente giochi **RPG Maker MV/MZ**.

Ispirato alla logica di **Ren'Py Translator** e allo stile dell'interfaccia di **WTForge**.

![RPGM-Translator GUI](translator-gui.png)

## ✨ Funzionalità

- 🕹️ Rileva automaticamente giochi **RPG Maker MV/MZ**.
- 📝 Estrae stringhe traducibili da:
  - 🗺️ `Map*.json` (dialoghi, scelte, testo scorrevole)
  - 🔁 `CommonEvents.json`
  - ⚙️ `System.json` (titolo del gioco, termini, etichette)
  - 🛡️ `Items.json`, `Weapons.json`, `Armors.json`, `Skills.json`, `States.json`, `Enemies.json`, `Actors.json`, `Classes.json`
  - 🔌 `js/plugins.js` (parametri testuali dei plugin)
- 🌍 Backend di traduzione: **Google Turbo**, **Bing Ultra**, **OpenRouter**, **Llama locale**.
- 🔎 Tabella di traduzione modificabile con filtri (Tutte / Tradotte / Non tradotte).
- 💾 Patch in-place con backup automatico dei dati.
- 🗂️ Cache globale e locale delle traduzioni.
- 📦 Esportazione di `www/data` tradotte come patch.

## 🆕 Novità

- Pulsante **Cancella cache** — cancella le cache globali e locali dalla GUI.
- **Traduzione stringhe dentro script** — traduce le stringhe letterali dentro i comandi JavaScript degli eventi (es. i tips dell’Oracolo in `CommonEvents.json`).

## 📋 Requisiti

- Python 3.9+
- `customtkinter`, `pillow`, `deep-translator`, `requests`

## 🚀 Avvio rapido

```bash
# macOS / Linux
./start.sh

# Windows
start.bat

# Oppure direttamente
python3 rpgm_tool.py
```

## 🔄 Flusso di lavoro

1. 🎮 **Seleziona Gioco** — Clicca `.app` (macOS) o `Cartella` e scegli la cartella del gioco.
2. 🧠 **Analizza & Traduci** — Estrai e traduci automaticamente tutte le stringhe.
3. ✏️ **Modifica** — Revisiona o modifica ogni stringa direttamente nella tabella.
4. 💾 **Salva** — Applica le traduzioni ai file del gioco (il backup viene creato automaticamente).
5. 📦 **Esporta** — Opzionalmente esporta la `www/data` tradotte come patch.

## 🛡️ Backup

Prima della patch, lo strumento salva un backup di `www/data` in `www/data_bak_<timestamp>`.

## 🙏 Crediti

- Cheat mod basata su **[Forge for RPGM MV/MZ](https://gitgud.io/serjura/forge-mvmz)** di serjura / zero64801.
- Il tasto per aprire la cheat UI è modificato in `1` per un accesso rapido.

## ⚠️ Licenza

Fornito "così com'è" senza garanzia. Usalo a tuo rischio.
