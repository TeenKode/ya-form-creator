@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 ne naiden. Ustanovite Python 3 s python.org
    pause
    exit /b 1
  )
  set "PY=python"
)
%PY% -c "import requests" >nul 2>nul
if errorlevel 1 (
  echo Installing Python package requests...
  %PY% -m pip install requests
  if errorlevel 1 (echo Cannot install requests & pause & exit /b 1)
)
%PY% form_editor.py
if errorlevel 1 pause
