@echo off
setlocal
cd /d "%~dp0"
echo Preparing AutoClick with bundled Python, libraries, OCR and JavaScript...

set "PYTHON_CMD=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
%PYTHON_CMD% -c "import sys,struct,tkinter; assert sys.version_info >= (3,10); assert struct.calcsize('P') == 8; assert sys.platform == 'win32'"
if errorlevel 1 (
    echo [ERROR] Install 64-bit Python 3.10+ with Tcl/Tk on the BUILD machine.
    exit /b 1
)
%PYTHON_CMD% -m venv .build-venv
if errorlevel 1 exit /b 1
set "BUILD_PYTHON=%CD%\.build-venv\Scripts\python.exe"
"%BUILD_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m pip install ".[full,dev]"
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m pip check
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" scripts\verify_dependencies.py
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m PyInstaller --clean --noconfirm AutoClick.spec
if errorlevel 1 exit /b 1

set "ISCC_PATH="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC_PATH=ISCC.exe"
if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH (
    echo [ERROR] Install Inno Setup 6.3+ on the BUILD machine: https://jrsoftware.org/isdl.php
    exit /b 1
)
"%ISCC_PATH%" installer.iss
if errorlevel 1 exit /b 1
echo Installer ready: %CD%\Output\AutoClickSetup.exe
exit /b 0
