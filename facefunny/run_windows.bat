@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title FACEFUNNY

rem --- find Python 3 -----------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [FACEFUNNY] Python 3.9+ not found. Install it from https://www.python.org/downloads/
    echo             and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

rem --- create the virtual environment on first start ---------------------
if not exist ".venv\Scripts\python.exe" (
    echo [FACEFUNNY] Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [FACEFUNNY] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

echo [FACEFUNNY] Checking dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo [FACEFUNNY] Dependency installation failed. Check your internet connection.
    pause
    exit /b 1
)

echo [FACEFUNNY] Starting...
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo [FACEFUNNY] The application exited with an error. See %%TEMP%%\facefunny.log
    pause
)
endlocal
