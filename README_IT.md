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
  - 🔌 `js/plugins.js` (testo traducibile dei plugin)
- 🌍 Backend di traduzione: **Google Turbo**, **Bing Ultra**, **OpenRouter**, **Llama locale**.
- 🔎 Tabella di traduzione modificabile con filtri (Tutte / Tradotte / Non tradotte) e ricerca live per originale, traduzione o entrambi.
- 💾 Patch in-place con un unico backup originale protetto di `data`.
- 🗂️ Cache globale e locale delle traduzioni, cancellabile dalla GUI.
- 📦 Esportazione di `www/data` tradotte come patch.

## 🆕 Novità

- **Riutilizzo cache migliorato** — la cache ora funziona tra diversi backend di traduzione e dopo aver ri-analizzato giochi già tradotti.
- **Visualizzazione GUI pulita** — i token script sono nascosti nella tabella di traduzione e nell'editor per una migliore leggibilità.
- **Ricerca stringhe** — filtra la tabella in tempo reale per testo originale, traduzione o entrambi.
- **Ripristina Backup** — ripristina il gioco dall'unico backup originale `data_bak_original`.
- **Traduzione sicura dei dialoghi script** — conserva prefissi dei dialoghi, placeholder, identificatori degli asset e parti interne dei comandi plugin mentre traduce il testo visibile.

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
4. 💾 **Salva** — Applica le traduzioni ai file del gioco (il backup originale viene creato una sola volta).
5. 📦 **Esporta** — Opzionalmente esporta la `www/data` tradotte come patch.
6. ♻️ **Ricomincia** — Usa **Ripristina Backup**, poi **Cancella cache**, prima di analizzare e tradurre di nuovo.

## 🛡️ Backup

Prima della prima patch, lo strumento crea `www/data_bak_original`. È l'unico backup mantenuto e **Ripristina Backup** usa sempre questa copia.

## 🙏 Crediti

- Cheat mod basata su **[Forge for RPGM MV/MZ](https://gitgud.io/serjura/forge-mvmz)** di serjura / zero64801.
- Il tasto per aprire la cheat UI è modificato in `1` per un accesso rapido.

## ⚠️ Licenza

Fornito "così com'è" senza garanzia. Usalo a tuo rischio.
