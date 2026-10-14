@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FACEFUNNY launcher

echo ==============================================================
echo   FACEFUNNY launcher
echo   Keep this window open. The app window opens separately.
echo   First start downloads about 120 MB - this can take minutes.
echo ==============================================================
echo.

rem ---------------------------------------------------------------
rem 1. Find a real 64-bit Python 3.10+ (skips the Microsoft Store stub)
rem ---------------------------------------------------------------
set "PY="
for %%V in (3.13 3.12 3.14 3.11 3.10 3.15) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
    )
)
if not defined PY (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY goto :nopython

echo [1/3] Found Python:
%PY% -c "import sys, struct; print('      ', sys.version.split()[0], str(struct.calcsize('P') * 8) + '-bit', sys.executable)"
%PY% -c "import struct, sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto :bits32

rem ---------------------------------------------------------------
rem 2. Virtual environment + dependencies (only when missing)
rem ---------------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
    if errorlevel 1 (
        echo       Existing .venv is broken, recreating it...
        rmdir /s /q ".venv"
    )
)
if not exist ".venv\Scripts\python.exe" (
    echo [2/3] Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :venvfail
)

".venv\Scripts\python.exe" -c "import PySide6.QtWidgets" >nul 2>nul
if errorlevel 1 (
    echo [2/3] Downloading PySide6 - about 120 MB, please wait...
    echo.
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --progress-bar on -r requirements.txt
    if errorlevel 1 goto :pipfail
    echo.
) else (
    echo [2/3] Dependencies already installed.
)

rem ---------------------------------------------------------------
rem 3. Run
rem ---------------------------------------------------------------
echo [3/3] Starting FACEFUNNY... the window should appear in a few seconds.
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto :appfail
exit /b 0

:nopython
echo [ERROR] Python 3.10 or newer was not found.
echo         Install it from https://www.python.org/downloads/
echo         and tick "Add python.exe to PATH" on the first installer screen.
echo         Then run this file again.
goto :end

:bits32
echo [ERROR] This Python is 32-bit. PySide6 needs 64-bit Python.
echo         Install the "Windows installer 64-bit" from https://www.python.org/downloads/
goto :end

:venvfail
echo [ERROR] Could not create the virtual environment in:
echo         %CD%\.venv
echo         Move the FACEFUNNY folder somewhere simple, e.g. C:\FACEFUNNY, and try again.
goto :end

:pipfail
echo.
echo [ERROR] Installing PySide6 failed - see the messages above.
echo         Check your internet connection or antivirus, then run this file again.
goto :end

:appfail
echo.
echo [ERROR] FACEFUNNY closed with an error. Details: %TEMP%\facefunny.log
goto :end

:end
echo.
echo Press any key to close this window.
pause >nul
exit /b 1
