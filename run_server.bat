@echo off
chcp 65001 >nul
title بوابة التصاريح الأمنية - تشغيل السيرفر المحلي

cd /d "%~dp0"

echo ========================================================
echo   🚀 جاري تشغيل خادم بوابة التصاريح الأمنية (Backend)...
echo ========================================================
echo.

:: 1. البحث عن بايثون داخل البيئة الافتراضية .venv
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXEC=.venv\Scripts\python.exe"
    goto :START_SERVER
)

:: 2. البحث عن بايثون العام في النظام
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXEC=python"
    goto :START_SERVER
)

echo [ERROR] لم يتم العثور على Python مثبت في النظام أو البيئة الافتراضية!
echo يرجى التأكد من تثبيت Python ثم إعادة المحاولة.
pause
exit /b 1

:START_SERVER
echo [OK] استخدام بايثون: %PYTHON_EXEC%
echo.

:: فتح المتصفح بعد تأخير بسيط
start "" "http://localhost:8000"

:: تشغيل السيرفر
"%PYTHON_EXEC%" main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] حدث خطأ أثناء تشغيل السيرفر.
    pause
)
