@echo off
rem Runs the tracker against a FAKE Resolve session so you can look at the UI without Resolve.
rem Data goes to a throwaway folder, your real history is untouched.
cd /d "%~dp0"
rem A stale PYTHONHOME / PYTHONPATH on the PC breaks Python at startup, so ignore them here.
set PYTHONHOME=
set PYTHONPATH=
set RET_DATA_DIR=%TEMP%\ResolveEditTrackerDemo
python run_tracker.py --simulate
echo.
echo The tracker has stopped (exit code %errorlevel%). If you did not close it yourself, copy the text above.
pause
