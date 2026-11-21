@echo off
chcp 65001 >nul
cd /d "%~dp0"
where git >nul 2>nul
if errorlevel 1 (
    echo Git не установлен. Установите Git for Windows.
    pause
    exit /b 1
)
git pull --ff-only
if errorlevel 1 (
    echo Обновление не удалось. Проверьте интернет и локальные изменения.
    pause
    exit /b 1
)
echo Готово! Перезапустите портал.
pause
