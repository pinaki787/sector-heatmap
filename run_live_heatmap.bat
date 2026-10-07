@echo off
setlocal
cd /d "%~dp0" || exit /b 1
call :load_runtime_switches
if errorlevel 1 exit /b 1
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

:load_runtime_switches
if not defined SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS if exist ".env" for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=" ".env"') do set "SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=%%B"
if not defined SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS if exist ".env" for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS=" ".env"') do set "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS=%%B"
if not defined SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS if exist ".env" for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS=" ".env"') do set "SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS=%%B"
if not defined SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS set "SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS=0"
if not "%SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS%"=="0" if not "%SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS%"=="1" goto runtime_switch_invalid
if not defined SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS set "SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=0"
if not defined SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS set "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS=0"
if not "%SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS%"=="0" if not "%SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS%"=="1" goto runtime_switch_invalid
if not "%SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS%"=="0" if not "%SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS%"=="1" goto runtime_switch_invalid
exit /b 0

:runtime_switch_invalid
echo Live-order switches must each be 0 or 1. 1>&2
exit /b 1
