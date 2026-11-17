# Contributing

Thanks for helping improve Stintory. Open an issue with OS version, Resolve version/edition, Python version, installed launch mode, reproduction steps and expected/observed behavior. Start from the isolated demo if possible. Never attach client names, project history, billing details or raw logs without redacting them.

## Development

1. Fork and clone the repository; create a branch.
2. Use Python 3.12 with Tkinter. Install `requirements.txt`. On Linux use Xvfb for UI tests and `PYSTRAY_BACKEND=dummy` for non-tray development if necessary.
3. Run `python scripts/test_all.py` (under Xvfb on Linux).
4. Test both launch modes on the relevant OS; test a crash, playback, idle, switching timelines and safe exit. Keep platform calls behind `winapi.py` and Resolve IPC behind `monitor.py`/`probe.py`.
5. Open a pull request explaining changes and test results. Do not bundle Resolve DLLs, libraries, personal data, proprietary font files or credentials.

Translations live in `resolve_edit_tracker/assets/translations.json`, using English source strings as keys. Add a locale to `i18n.py`, preserve `%s`/`%d` placeholders, use native-language display name, and verify UI widths and invoice glyphs. UI and invoice locale are independent; do not translate API IDs, saved project names, or CSV keys. Include native-speaker review where possible.
