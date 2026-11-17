@echo off
cd /d "%~dp0"
set PYTHONHOME=
set PYTHONPATH=
start "" pythonw run_tracker.pyw --manual
