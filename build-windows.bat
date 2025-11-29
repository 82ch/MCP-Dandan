@echo off
REM ================================================================================
REM 82ch Desktop - Windows Build Script
REM ================================================================================

echo ================================================================================
echo 82ch Desktop - Windows Build Script
echo ================================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/
    exit /b 1
)

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    exit /b 1
)

echo [1/5] Installing Python dependencies...
echo ================================================================================
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies
    exit /b 1
)

echo.
echo [2/5] Installing PyInstaller...
echo ================================================================================
pip install pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller
    exit /b 1
)

echo.
echo [3/5] Building Python backend with PyInstaller...
echo ================================================================================
pyinstaller server.spec --clean
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build Python backend
    exit /b 1
)

echo.
echo [4/5] Installing frontend dependencies...
echo ================================================================================
cd front
call npm install --legacy-peer-deps
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies
    cd ..
    exit /b 1
)

echo.
echo [5/5] Building Electron application...
echo ================================================================================
call npm run dist:win
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build Electron application
    cd ..
    exit /b 1
)

cd ..

echo.
echo ================================================================================
echo Build completed successfully!
echo ================================================================================
echo.
echo Installer location:
echo   front\release\82ch Desktop-Setup-*.exe
echo.
echo You can now distribute the installer to users.
echo.

pause
