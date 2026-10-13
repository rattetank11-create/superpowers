@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: создаю .venv и устанавливаю PySide6 ...
    %PY% -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)

start "" ".venv\Scripts\pythonw.exe" main.py %*
exit /b 0

:fail
echo [ОШИБКА] Не удалось подготовить окружение. Установлен ли Python 3.10+?
pause
exit /b 1
