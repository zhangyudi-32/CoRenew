@echo off
set CORENEW_HOST=%CORENEW_HOST%
if "%CORENEW_HOST%"=="" set CORENEW_HOST=127.0.0.1
set CORENEW_PORT=%CORENEW_PORT%
if "%CORENEW_PORT%"=="" set CORENEW_PORT=7860

python ui_app.py --host %CORENEW_HOST% --port %CORENEW_PORT% --home-path /run/setup
