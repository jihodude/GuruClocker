@echo off
rem guruclocker for Windows. Double-click this file to run it.
setlocal
cd /d "%~dp0"
title guruclocker
echo.
echo  guruclocker for Windows
echo  -----------------------
echo.

rem ---- 1. Docker Desktop must be installed --------------------------------------------
where docker >nul 2>nul
if not errorlevel 1 goto docker_installed
echo  guruclocker runs inside a free program called Docker Desktop, which isn't installed yet.
echo.
echo  I'm opening the download page for you. Then:
echo    1. Download "Docker Desktop for Windows" and run the installer.
echo       Keep the default options. If it asks about WSL 2, say yes.
echo    2. Restart your computer when it asks.
echo    3. Open Docker Desktop from the Start menu, accept its terms,
echo       and wait until it says "Engine running". You can skip signing in.
echo    4. Double-click windows.bat again.
echo.
echo  Stuck? See "Windows: Docker problems" in README.md.
start "" "https://www.docker.com/products/docker-desktop/"
goto end

:docker_installed
rem ---- 2. Docker Desktop must be running ----------------------------------------------
docker info >nul 2>nul
if not errorlevel 1 goto docker_ok
echo  Docker Desktop isn't running. Starting it for you; this can take a minute...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a tries=0
:wait_docker
timeout /t 3 /nobreak >nul
docker info >nul 2>nul
if not errorlevel 1 goto docker_ok
set /a tries+=1
if %tries% lss 60 goto wait_docker
echo.
echo  Docker Desktop still isn't ready after 3 minutes.
echo  Open Docker Desktop from the Start menu, wait until it says "Engine running",
echo  then double-click windows.bat again.
goto end

:docker_ok
rem ---- 3. Build or update the guruclocker image ---------------------------------------
docker image inspect guruclocker >nul 2>nul
if errorlevel 1 (
  echo  First-time setup: preparing guruclocker inside Docker.
  echo  This takes 10 to 20 minutes and downloads about 7 GB. Later runs start in seconds.
  echo.
)
docker build -t guruclocker . 
if errorlevel 1 goto build_failed
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "output" mkdir "output"

rem ---- 4. Use the NVIDIA GPU if Docker can see one -------------------------------------
set "GPUFLAG="
set "GPUCOUNT=0"
for /f %%g in ('docker run --rm --gpus all --entrypoint python guruclocker -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())" 2^>nul') do set "GPUCOUNT=%%g"
if not "%GPUCOUNT%"=="0" set "GPUFLAG=--gpus all"
cls
echo.
if defined GPUFLAG echo  NVIDIA graphics card found: speech-to-text will run in fast mode.
if not defined GPUFLAG echo  No NVIDIA graphics card found: speech-to-text will run on the processor. Slower, but it works.

rem ---- 5. Run it -----------------------------------------------------------------------
docker run --rm -it %GPUFLAG% -v "%cd%\output:/app/output" -v "%cd%\.env:/app/.env" -v guruclocker-models:/cache guruclocker %*
if exist "output\INDEX.md" start "" "%cd%\output"
goto end

:build_failed
echo.
echo  Setting up guruclocker inside Docker failed - see the messages above.
echo  Most often this is a dropped internet connection: double-click windows.bat to try again.
echo  If it keeps failing, send a screenshot of this window to whoever shared guruclocker with you.

:end
echo.
pause
