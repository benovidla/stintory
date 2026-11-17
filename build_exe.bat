@echo off
setlocal
set PYTHONHOME=
set PYTHONPATH=
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --console --name StintoryProbe --paths . --hidden-import resolve_edit_tracker.winapi resolve_edit_tracker/probe.py || exit /b 1
python -m PyInstaller --noconfirm --clean --onedir --noconsole --name Stintory --icon app.ico --add-data "resolve_edit_tracker/assets;resolve_edit_tracker/assets" --add-data "resolve_edit_tracker/probe.py;resolve_edit_tracker" --hidden-import pystray._win32 run_tracker.py || exit /b 1
copy /Y dist\StintoryProbe.exe dist\Stintory\StintoryProbe.exe || exit /b 1
echo Built: dist\Stintory\Stintory.exe (keep the whole folder)
