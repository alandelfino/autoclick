@echo off
echo ===================================================
echo   Building AutoClick Executable and Windows Installer
echo ===================================================
echo.

echo [1/2] Running PyInstaller...
python -m PyInstaller --noconfirm --noconsole --icon=logo.ico --add-data "locales;locales" --name "AutoClick" flow_builder_pro.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller compilation failed!
    exit /b %ERRORLEVEL%
)
echo.

echo [2/2] Running Inno Setup Compiler...
set "ISCC_PATH="

where ISCC.exe >nul 2>nul
if %ERRORLEVEL% equ 0 set "ISCC_PATH=ISCC.exe"

if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC_PATH (
    echo.
    echo [ERROR] Inno Setup Compiler ISCC.exe not found!
    echo Please install Inno Setup 6 from https://jrsoftware.org/isdl.php
    exit /b 1
)

echo Found Inno Setup Compiler at: "%ISCC_PATH%"
"%ISCC_PATH%" installer.iss
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Inno Setup compilation failed!
    exit /b %ERRORLEVEL%
)
echo.

echo ===================================================
echo   Success! Installer is at: Output\AutoClickSetup.exe
echo ===================================================
pause
