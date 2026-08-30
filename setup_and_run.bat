@echo off
setlocal
cd /d "%~dp0" || exit /b 1

if exist ".venv\Scripts\python.exe" goto python_ready

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 9))"
  if errorlevel 1 goto python_missing
  py -3 -m venv .venv
  if errorlevel 1 goto setup_failed
  goto python_ready
)

where python >nul 2>nul
if errorlevel 1 goto python_missing
python -c "import sys; raise SystemExit(sys.version_info < (3, 9))"
if errorlevel 1 goto python_missing
python -m venv .venv
if errorlevel 1 goto setup_failed

:python_ready
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 9))"
if errorlevel 1 goto python_missing
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --requirement requirements.lock
if errorlevel 1 goto setup_failed

where node >nul 2>nul
if errorlevel 1 goto node_missing
where npx >nul 2>nul
if errorlevel 1 goto node_missing
node -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit(major > 20 || (major === 20 && minor >= 19) ? 0 : 1)"
if errorlevel 1 goto node_missing

pushd client
call npx --yes pnpm@10.17.1 install --frozen-lockfile
if errorlevel 1 (
  popd
  goto setup_failed
)
call npx --yes pnpm@10.17.1 run build
if errorlevel 1 (
  popd
  goto setup_failed
)
popd

if "%HEATMAP_SETUP_ONLY%"=="1" (
  echo Environment setup and UI build completed.
  exit /b 0
)

".venv\Scripts\python.exe" heatmap_server.py
exit /b %errorlevel%

:python_missing
echo Python 3.9 or newer is required. 1>&2
exit /b 1

:node_missing
echo Node.js 20.19 or newer, including npx, is required to build the UI. 1>&2
exit /b 1

:setup_failed
echo Environment setup failed; the dashboard was not started. 1>&2
exit /b 1
