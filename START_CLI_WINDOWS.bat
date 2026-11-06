@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
%PY% -c "import requests" >nul 2>nul
if errorlevel 1 %PY% -m pip install requests
%PY% create_yandex_form.py --create
pause
