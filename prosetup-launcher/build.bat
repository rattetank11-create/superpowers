@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo === ProSetup Launcher: сборка EXE ===

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [ОШИБКА] Python 3 не найден. Установите его с https://www.python.org/downloads/
    echo          и отметьте галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Создаю виртуальное окружение .venv ...
    %PY% -m venv .venv || goto :fail
)
set "VPY=.venv\Scripts\python.exe"

echo Устанавливаю зависимости ...
"%VPY%" -m pip install --upgrade pip >nul || goto :fail
"%VPY%" -m pip install -r requirements.txt "pyinstaller>=6.3" || goto :fail

echo Генерирую иконку ...
"%VPY%" tools\make_icon.py || goto :fail

echo Собираю EXE (это займёт 1-3 минуты) ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name ProSetupLauncher ^
    --icon assets\icon.ico ^
    --exclude-module tkinter ^
    main.py || goto :fail

echo.
echo === Готово! ===
echo Файл: %cd%\dist\ProSetupLauncher.exe
echo Его можно скопировать куда угодно и запускать как обычную программу.
pause
exit /b 0

:fail
echo.
echo [ОШИБКА] Сборка не удалась — смотрите сообщения выше.
pause
exit /b 1
