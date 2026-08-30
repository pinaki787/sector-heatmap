@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0heatmap_server.py"
  exit /b %errorlevel%
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0heatmap_server.py"
  exit /b %errorlevel%
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0heatmap_server.py"
  exit /b %errorlevel%
)
echo Python 3 is required. 1>&2
exit /b 1
