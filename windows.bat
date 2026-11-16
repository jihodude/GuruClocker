@echo off
rem guruclocker for Windows. Double-click this file to run it.
setlocal
cd /d "%~dp0"
title guruclocker
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
echo.
echo  guruclocker for Windows
echo  -----------------------

rem ---- 1. uv: a small free tool that installs Python and this program's parts ----------
rem      It installs into your user folder only; nothing else on your PC is changed.
where uv >nul 2>nul
if not errorlevel 1 goto have_uv
echo.
echo  First-time setup: installing "uv", a small free tool that installs Python for this program.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
where uv >nul 2>nul
if not errorlevel 1 goto have_uv
echo.
echo  Couldn't install uv. Check your internet connection, then double-click windows.bat again.
echo  If it keeps failing, send a screenshot of this window to whoever shared guruclocker with you.
goto end

:have_uv
rem ---- 2. This program's parts: first time takes a few minutes, later runs skip it --------
set "QUIET="
if exist ".venv" set "QUIET=--quiet"
if exist ".venv" goto sync
echo.
echo  First-time setup: installing guruclocker's parts.
echo  This takes 5 to 10 minutes and downloads about 3 GB. Later runs start in seconds.
:sync
uv sync --frozen --no-dev %QUIET%
if not errorlevel 1 goto run
echo.
echo  Setup failed - see the message above. Most often this is a dropped internet connection:
echo  double-click windows.bat to try again. If it keeps failing, send a screenshot of this
echo  window to whoever shared guruclocker with you.
goto end

:run
if not exist ".env" copy ".env.example" ".env" >nul
echo.
uv run --frozen --no-dev python -m guruclocker %*

:end
echo.
pause
