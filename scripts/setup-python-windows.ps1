# Setup Python for Windows build
# Downloads embeddable Python and installs required packages

param(
    [string]$PythonVersion = "3.12.8",
    [string]$OutputDir = "build\python-windows"
)

$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host "Setting up Python for Windows build"
Write-Host "======================================"
Write-Host "Python Version: $PythonVersion"
Write-Host "Output Directory: $OutputDir"
Write-Host ""

# Create output directory
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# Download embeddable Python
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$PythonZip = "$OutputDir\python-embed.zip"

Write-Host "[1/6] Downloading Python $PythonVersion embeddable..."
if (Test-Path $PythonZip) {
    Write-Host "  -> Already downloaded, skipping"
} else {
    Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip
    Write-Host "  -> Downloaded: $PythonZip"
}

# Extract Python
Write-Host "[2/6] Extracting Python..."
Expand-Archive -Path $PythonZip -DestinationPath $OutputDir -Force
Write-Host "  -> Extracted to: $OutputDir"

# Uncomment site-packages in pythonXXX._pth to enable pip
Write-Host "[3/6] Enabling site-packages..."
$PthFile = Get-ChildItem -Path $OutputDir -Filter "python*._pth" | Select-Object -First 1
if ($PthFile) {
    $content = Get-Content $PthFile.FullName
    $content = $content -replace '#import site', 'import site'
    $content | Set-Content $PthFile.FullName
    Write-Host "  -> Updated: $($PthFile.Name)"
} else {
    Write-Host "  -> ERROR: python*._pth file not found!"
    exit 1
}

# Download get-pip.py
Write-Host "[4/6] Downloading get-pip.py..."
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipPath = "$OutputDir\get-pip.py"
Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath
Write-Host "  -> Downloaded: $GetPipPath"

# Install pip
Write-Host "[5/6] Installing pip..."
$PythonExe = "$OutputDir\python.exe"
& $PythonExe $GetPipPath --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> ERROR: Failed to install pip"
    exit 1
}
Write-Host "  -> pip installed successfully"

# Install requirements
Write-Host "[6/6] Installing Python packages..."
$RequirementsFile = "requirements.txt"
if (Test-Path $RequirementsFile) {
    & $PythonExe -m pip install -r $RequirementsFile --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  -> ERROR: Failed to install requirements"
        exit 1
    }
    Write-Host "  -> All packages installed"
} else {
    Write-Host "  -> WARNING: requirements.txt not found, skipping package installation"
}

# Copy project modules to site-packages
Write-Host ""
Write-Host "======================================"
Write-Host "Copying project modules to site-packages"
Write-Host "======================================"

$SitePackages = "$OutputDir\Lib\site-packages"
New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null

# Copy internal modules
$ModulesToCopy = @(
    "state.py",
    "config.py",
    "database.py",
    "event_hub.py",
    "verification.py",
    "websocket_handler.py",
    "utils",
    "engines",
    "transports"
)

foreach ($module in $ModulesToCopy) {
    if (Test-Path $module) {
        Write-Host "Copying $module..."
        Copy-Item -Path $module -Destination $SitePackages -Recurse -Force
    } else {
        Write-Host "WARNING: $module not found, skipping"
    }
}

Write-Host ""
Write-Host "======================================"
Write-Host "Python setup completed successfully!"
Write-Host "======================================"
Write-Host "Python location: $OutputDir"
Write-Host "Site-packages: $SitePackages"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Build PyInstaller executable: pyinstaller server.spec"
Write-Host "  2. Run electron-builder: npm run dist:win"
Write-Host ""
