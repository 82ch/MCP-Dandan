@echo off
REM ================================================================================
REM MCP-Dandan - Windows Complete Build Script
REM Includes: Python Runtime Bundling + PyInstaller + Electron MSI
REM ================================================================================

echo ================================================================================
echo MCP-Dandan - Windows Complete Build Script
echo ================================================================================
echo.

REM Get script directory and move to project root
cd /d "%~dp0\.."
set ROOT_DIR=%CD%

REM Check if PowerShell is available
powershell -Command "exit" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PowerShell is not available
    exit /b 1
)

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    exit /b 1
)

echo [1/4] Setting up bundled Python runtime...
echo ================================================================================
powershell -ExecutionPolicy Bypass -File "%ROOT_DIR%\scripts\setup-python-windows.ps1"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to setup Python runtime
    exit /b 1
)

echo.
echo [2/4] Building Python backend with PyInstaller...
echo ================================================================================
"%ROOT_DIR%\build\python-windows\python.exe" -m PyInstaller "%ROOT_DIR%\server.spec" --clean
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build Python backend
    exit /b 1
)

echo.
echo [3/4] Installing frontend dependencies...
echo ================================================================================
cd "%ROOT_DIR%\front"
if not exist "node_modules" (
    echo Installing npm dependencies...
    call npm install --legacy-peer-deps
) else (
    echo npm dependencies already installed, skipping...
)
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies
    cd "%ROOT_DIR%"
    exit /b 1
)

echo.
echo [4/4] Building Electron MSI installer...
echo ================================================================================
call npm run dist:win
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build Electron application
    cd "%ROOT_DIR%"
    exit /b 1
)

cd "%ROOT_DIR%"

echo.
echo ================================================================================
echo Build completed successfully!
echo ================================================================================
echo.
echo Output files:
dir /B "%ROOT_DIR%\front\release\*.msi" 2>nul
echo.
echo MSI Installer location:
echo   %ROOT_DIR%\front\release\MCP-Dandan-Setup-*.msi
echo.
echo You can now distribute the installer to users.
echo The installer includes:
echo   - Bundled Python 3.12.8 runtime
echo   - PyInstaller compiled backend (82ch-server.exe)
echo   - Electron frontend with all dependencies
echo.

pause
