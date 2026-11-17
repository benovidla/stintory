#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python scripts/install_mac.py disable-login
