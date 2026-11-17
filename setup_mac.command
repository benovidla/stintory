#!/bin/bash
set -e
cd "$(dirname "$0")"
unset PYTHONHOME PYTHONPATH
mode="${1:-}"
if [[ -z "$mode" ]]; then
  printf 'Choose launch mode: [1] Linked with Resolve, [2] Resident at login: '
  read -r reply
  case "$reply" in 1) mode=linked;; 2) mode=resident;; *) echo 'Cancelled'; exit 1;; esac
fi
[[ "$(uname -s)" == Darwin ]] || { echo 'macOS required'; exit 1; }
echo 'Quit Stintory before continuing. Python 3.12 from python.org is recommended.'
PY="${STINTORY_PYTHON:-python3}"
"$PY" -c 'import sys, tkinter; assert sys.version_info >= (3,10), "Python 3.10+ required"'
"$PY" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import tkinter, PIL, reportlab, AppKit, Quartz; print("Dependencies OK")'
.venv/bin/python scripts/install_mac.py "$mode"
echo 'Installation complete. Read README.md for Resolve scripting and Gatekeeper notes.'
