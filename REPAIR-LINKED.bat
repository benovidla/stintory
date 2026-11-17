@echo off
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
python "%~dp0setup_linked.py"
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
