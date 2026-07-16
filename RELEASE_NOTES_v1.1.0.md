# Release Notes — RPGM-Translator v1.1.0

## What's New

- **String search** — search the translation table live by original text, translated text, or both.
- **Original data backup** — a single `data_bak_original` is retained and used by Restore Backup.
- **Clean translation workflow** — Clear cache removes local and global translation caches without touching the original data backup.

## Translation Reliability

- Plugin commands are excluded from translation to avoid changing internal plugin values.
- Script-dialogue prefixes are preserved while the visible dialogue is translated.
- The `1Hero` protagonist placeholder is preserved during translation.
- camelCase asset identifiers such as `PoliceA` are excluded to avoid breaking dynamically generated image filenames.

## Upgrade Notes

- Existing `data_bak_*` folders are migrated automatically: the oldest becomes `data_bak_original`, and duplicate timestamped backups are removed.
- To redo a game from scratch, select it, use **Restore Backup**, then use **Clear cache** before analyzing and translating again.
