#!/bin/bash
set -e
cd "$(dirname "$0")"
unset PYTHONHOME PYTHONPATH
PY="${STINTORY_PYTHON:-python3}"
"$PY" -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements.txt pyinstaller
.build-venv/bin/python -c "from PIL import Image; Image.open('resolve_edit_tracker/assets/icon.png').save('app.icns')"
.build-venv/bin/python -m PyInstaller --noconfirm --clean --onedir --windowed --name Stintory --osx-bundle-identifier org.stintory.app --icon app.icns --add-data 'resolve_edit_tracker/assets:resolve_edit_tracker/assets' --add-data 'resolve_edit_tracker/probe.py:resolve_edit_tracker' --hidden-import pystray._darwin run_tracker.py
echo 'Built dist/Stintory.app (local signature only; not notarized). Source installer is recommended for launch profiles.'
