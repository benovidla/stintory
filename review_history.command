#!/bin/bash
cd "$(dirname "$0")"
unset PYTHONHOME PYTHONPATH
exec .venv/bin/python run_tracker.py --manual
