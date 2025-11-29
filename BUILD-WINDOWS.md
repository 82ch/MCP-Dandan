# Building 82ch Desktop for Windows

This guide explains how to build the Windows installer for 82ch Desktop.

## Prerequisites

### Required Software

1. **Python 3.10 or higher**
   - Download from: https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"
   - Verify: `python --version`

2. **Node.js 18 or higher**
   - Download from: https://nodejs.org/
   - Verify: `node --version` and `npm --version`

3. **Git** (optional, for cloning the repository)
   - Download from: https://git-scm.com/

### Windows Build Tools

The build script will automatically install PyInstaller and other required dependencies.

## Build Instructions

### Method 1: Automated Build (Recommended)

Simply run the build script:

```cmd
build-windows.bat
```

This will:
1. Install Python dependencies
2. Install PyInstaller
3. Build the Python backend into a standalone executable
4. Install frontend dependencies
5. Build the Electron application with NSIS installer

The installer will be created at:
```
front\release\82ch Desktop-Setup-1.0.0.exe
```

### Method 2: Manual Build

If you prefer to build manually or need to debug:

#### Step 1: Install Python Dependencies

```cmd
pip install -r requirements.txt
pip install pyinstaller
```

#### Step 2: Build Python Backend

```cmd
pyinstaller server.spec --clean
```

This creates a standalone executable at `dist/82ch-server.exe`.

#### Step 3: Install Frontend Dependencies

```cmd
cd front
npm install --legacy-peer-deps
```

#### Step 4: Build Electron Application

```cmd
npm run dist:win
```

The installer will be in `front\release\`.

## Build Output

After a successful build, you will find:

- **Installer**: `front\release\82ch Desktop-Setup-1.0.0.exe`
  - This is the NSIS installer that end-users will run
  - It includes both the Electron frontend and Python backend

- **Unpacked Application**: `front\release\win-unpacked\`
  - Contains the unpacked application files
  - Useful for testing before distribution

## Troubleshooting

### Python not found

If you get "Python is not installed or not in PATH":
- Reinstall Python and check "Add Python to PATH" during installation
- Or manually add Python to your PATH environment variable

### Node.js not found

If you get "Node.js is not installed or not in PATH":
- Reinstall Node.js
- Restart your terminal/command prompt after installation

### PyInstaller build fails

If PyInstaller fails to build:
- Check that all dependencies in `requirements.txt` are installed
- Try running with `--clean` flag: `pyinstaller server.spec --clean`
- Check the `build\` and `dist\` directories for error logs

### Electron build fails

If Electron builder fails:
- Delete `node_modules` folder and reinstall: `npm install --legacy-peer-deps`
- Check that you have enough disk space (at least 2GB free)
- Try running `npm run build` first to verify the TypeScript compilation

### Missing Icons

If you see warnings about missing icons:
- Ensure `front/icons/dandan.ico` exists
- You can use any `.ico` file or create one from the PNG icon

## Distribution

### Installer

The generated NSIS installer (`82ch Desktop-Setup-1.0.0.exe`) can be distributed to users. When they run it:

1. They can choose the installation directory
2. Desktop and Start Menu shortcuts are created
3. The application can be uninstalled from Windows Settings

### Portable Version

If you want a portable version without installer:
1. Use the unpacked files from `front\release\win-unpacked\`
2. Zip the folder and distribute
3. Users can run `82ch Desktop.exe` directly without installation

## Configuration

### Changing Application Name or Version

Edit `front/package.json`:
```json
{
  "name": "82ch-desktop",
  "version": "1.0.0",
  "description": "82ch Desktop Application"
}
```

### Customizing Installer

Edit the `nsis` section in `front/package.json`:
```json
"nsis": {
  "oneClick": false,
  "allowToChangeInstallationDirectory": true,
  "createDesktopShortcut": true,
  "createStartMenuShortcut": true
}
```

### Code Signing (Optional)

For production releases, you should sign the executable:

1. Obtain a code signing certificate
2. Configure in `front/package.json`:
```json
"win": {
  "certificateFile": "path/to/cert.pfx",
  "certificatePassword": "your-password"
}
```

## PyInstaller Configuration

The Python backend is built using `server.spec`. Key configurations:

- **Entry Point**: `server.py`
- **Hidden Imports**: All modules from `engines/`, `transports/`, and `utils/`
- **Data Files**: `schema.sql`, Python source files
- **Output**: Single executable with console window

To modify PyInstaller settings, edit [server.spec](server.spec).

## Build Size

Typical build sizes:
- Python backend executable: ~30-50 MB
- Electron application: ~150-200 MB
- Complete installer: ~180-250 MB

The size is mainly due to:
- Electron runtime
- Python runtime embedded in executable
- Node.js dependencies (better-sqlite3, etc.)

## Clean Build

To perform a completely clean build:

```cmd
REM Clean Python build artifacts
rmdir /s /q build dist __pycache__

REM Clean frontend artifacts
cd front
rmdir /s /q dist dist-electron release node_modules
npm install --legacy-peer-deps
cd ..

REM Build
build-windows.bat
```

## Advanced Topics

### Debugging the Backend

The Python backend is built as a console application, so you can see debug output:

1. Run the unpacked application from command line:
```cmd
cd "front\release\win-unpacked"
"82ch Desktop.exe"
```

2. Backend logs will appear in the console

### Modifying Electron Main Process

The main Electron process is in `front/electron/main.ts`. It:
- Starts the Python backend server (`server.py`)
- Manages the application window
- Handles IPC communication with the renderer

After modifying, rebuild with:
```cmd
cd front
npm run build
```

## Release Checklist

Before releasing a new version:

- [ ] Update version in `front/package.json`
- [ ] Test the build on a clean Windows machine
- [ ] Verify all features work in the built application
- [ ] Check that database paths are correct
- [ ] Test installation and uninstallation
- [ ] Update README.md and CHANGELOG.md
- [ ] Create a GitHub release with the installer

## Support

For issues and questions:
- GitHub Issues: https://github.com/82ch/issues
- Documentation: See [README.md](README.md)
