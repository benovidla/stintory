@echo off
rem Opens Stintory, even when Resolve is closed.
rem If nothing appears, run diagnose.bat: it shows what is wrong.
cd /d "%~dp0"
rem A stale PYTHONHOME / PYTHONPATH on the PC breaks Python at startup, so ignore them here.
set PYTHONHOME=
set PYTHONPATH=
start "" pythonw run_tracker.pyw --manual
