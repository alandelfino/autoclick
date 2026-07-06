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
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
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
