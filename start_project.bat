@echo off
cd /d "%~dp0"
set PORT=5001
set AUTO_OPEN_BROWSER=1
python app.py
pause
