@echo off
cd /d "%~dp0"
echo ===== 0. Environment (these two should normally be empty) =====
echo PYTHONHOME=%PYTHONHOME%
echo PYTHONPATH=%PYTHONPATH%
echo.
rem A stale PYTHONHOME / PYTHONPATH on the PC breaks Python at startup, so ignore them here.
set PYTHONHOME=
set PYTHONPATH=
echo ===== 1. Python =====
python --version
where python
echo.
echo ===== 2. Libraries =====
python -c "import tkinter; print('tkinter OK')"
python -c "import PIL; print('Pillow OK', PIL.__version__)"
python -c "import pystray; print('pystray OK')"
echo.
echo ===== 3. Starting the tracker with a fake Resolve (errors show below) =====
echo Close the tracker from its panel (Quit) when you are done looking.
set RET_DEBUG=1
set RET_DATA_DIR=%TEMP%\ResolveEditTrackerDemo
python run_tracker.py --simulate
echo.
echo ===== 4. Finished. Exit code %errorlevel% =====
if exist "%TEMP%\ResolveEditTrackerDemo\crash.log" (
  echo --- crash.log ---
  type "%TEMP%\ResolveEditTrackerDemo\crash.log"
)
if exist "%TEMP%\ResolveEditTrackerDemo\debug.log" (
  echo --- debug.log ---
  type "%TEMP%\ResolveEditTrackerDemo\debug.log"
)
echo.
pause
