@echo off
rem One-time setup when running from source: makes sure pip exists, installs the two small libraries, then checks them.
cd /d "%~dp0"
rem A stale PYTHONHOME / PYTHONPATH on the PC breaks Python at startup, so ignore them here.
set PYTHONHOME=
set PYTHONPATH=

echo === Python ===
python --version
if errorlevel 1 (
  echo.
  echo Python was not found. Install it from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

python -m resolve_edit_tracker --version
echo.
echo === pip ===
python -m pip --version >nul 2>nul
if errorlevel 1 (
  echo pip is missing, installing it now...
  python -m ensurepip --upgrade
  python -m pip --version >nul 2>nul
  if errorlevel 1 (
    echo.
    echo FAILED: this Python was installed without pip.
    echo Fix: run the Python installer again, choose Modify, tick "pip" and "tcl/tk and IDLE", finish, then start setup.bat again.
    pause
    exit /b 1
  )
)
python -m pip --version

echo.
echo === Installing libraries ===
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo FAILED: the libraries could not be installed. Check your internet connection and send me the text above.
  pause
  exit /b 1
)

echo.
echo === Checking ===
python -c "import tkinter; print('tkinter OK')"
if errorlevel 1 (
  echo FAILED: tkinter is missing. Run the Python installer again, choose Modify, tick "tcl/tk and IDLE".
  pause
  exit /b 1
)
python -c "import PIL; print('Pillow OK')"
if errorlevel 1 (
  echo FAILED: Pillow did not install.
  pause
  exit /b 1
)
python -c "import pystray; print('pystray OK')"
if errorlevel 1 (
  echo FAILED: pystray did not install.
  pause
  exit /b 1
)

echo.
python -c "import reportlab; print('PDF export OK')" || goto failed
if /i "%~1"=="resident" goto resident
if /i "%~1"=="linked" goto linked
choice /c LR /m "Launch mode: [L]inked to Resolve or [R]esident at login"
if errorlevel 2 goto resident
:linked
echo === Resolve-only launch ===
python "%~dp0setup_linked.py"
if errorlevel 1 (
  echo See setup-linked.log for details.
  pause
  exit /b 1
)
echo ALL GOOD. Desktop shortcut starts immediately; other launch paths within about one minute.
pause
exit /b 0
:resident
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0link_resolve.ps1" -Restore || goto failed
>launch-mode.txt echo resident
python -m resolve_edit_tracker --enable-resident || goto failed
cscript //nologo "%~dp0make_shortcut.vbs" || goto failed
wscript.exe "%~dp0launch_resident.vbs"
echo ALL GOOD. Stintory will start at Windows login and wait for Resolve.
pause
exit /b 0
:failed
echo FAILED: Resolve shortcut could not be linked. Use launch_with_resolve.vbs or contact support.
pause
exit /b 1
