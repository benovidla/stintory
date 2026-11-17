@echo off
cd /d "%~dp0"
set PYTHONHOME=
set PYTHONPATH=
python -m resolve_edit_tracker --disable-autostart
call "%~dp0restore_resolve.bat"
