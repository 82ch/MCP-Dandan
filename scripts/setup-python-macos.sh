#!/bin/bash
# Setup Python for macOS build
# Creates a relocatable Python framework

set -e

PYTHON_VERSION="${PYTHON_VERSION:-3.12.8}"
OUTPUT_DIR="${OUTPUT_DIR:-build/python-macos}"

echo "======================================"
echo "Setting up Python for macOS build"
echo "======================================"
echo "Python Version: $PYTHON_VERSION"
echo "Output Directory: $OUTPUT_DIR"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Download Python macOS installer
PYTHON_MAJOR_MINOR=$(echo $PYTHON_VERSION | sed -E 's/([0-9]+\.[0-9]+)\..*/\1/')
PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg"
PYTHON_PKG="$OUTPUT_DIR/python-installer.pkg"

echo "[1/7] Downloading Python $PYTHON_VERSION for macOS..."
if [ -f "$PYTHON_PKG" ]; then
    echo "  -> Already downloaded, skipping"
else
    curl -o "$PYTHON_PKG" "$PYTHON_URL"
    echo "  -> Downloaded: $PYTHON_PKG"
fi

# Create temporary installation directory
TEMP_INSTALL="/tmp/python-temp-install"
echo "[2/7] Installing Python to temporary location..."
rm -rf "$TEMP_INSTALL"
mkdir -p "$TEMP_INSTALL"

# Extract Python from pkg (without installing system-wide)
pkgutil --expand "$PYTHON_PKG" "$TEMP_INSTALL/expanded"
cd "$TEMP_INSTALL/expanded"

# Find and extract the Python framework payload
FRAMEWORK_PKG=$(find . -name "Python_Framework*" -type d | head -1)
if [ -z "$FRAMEWORK_PKG" ]; then
    echo "  -> ERROR: Python framework package not found!"
    exit 1
fi

cd "$FRAMEWORK_PKG"
cat Payload | gunzip -dc | cpio -i
echo "  -> Extracted Python framework"

# Copy Python framework to output directory
echo "[3/7] Copying Python framework..."
FRAMEWORK_PATH="$TEMP_INSTALL/expanded/$FRAMEWORK_PKG/Library/Frameworks/Python.framework/Versions/$PYTHON_MAJOR_MINOR"

if [ ! -d "$FRAMEWORK_PATH" ]; then
    echo "  -> ERROR: Python framework not found at $FRAMEWORK_PATH"
    exit 1
fi

mkdir -p "$OUTPUT_DIR/python"
cp -R "$FRAMEWORK_PATH"/* "$OUTPUT_DIR/python/"
echo "  -> Copied to: $OUTPUT_DIR/python"

# Create symlinks for easy access
echo "[4/7] Creating symlinks..."
cd "$OUTPUT_DIR"
mkdir -p python/bin
ln -sf ../bin/python3 python/bin/python3
ln -sf python3 python/bin/python
echo "  -> Symlinks created"

# Upgrade pip
echo "[5/7] Upgrading pip..."
"$OUTPUT_DIR/python/bin/python3" -m ensurepip
"$OUTPUT_DIR/python/bin/python3" -m pip install --upgrade pip
echo "  -> pip upgraded"

# Install requirements
echo "[6/7] Installing Python packages..."
if [ -f "requirements.txt" ]; then
    "$OUTPUT_DIR/python/bin/python3" -m pip install -r requirements.txt
    echo "  -> All packages installed"
else
    echo "  -> WARNING: requirements.txt not found, skipping package installation"
fi

# Copy project modules to site-packages
echo "[7/7] Copying project modules to site-packages..."
SITE_PACKAGES="$OUTPUT_DIR/python/lib/python$PYTHON_MAJOR_MINOR/site-packages"

if [ ! -d "$SITE_PACKAGES" ]; then
    echo "  -> ERROR: site-packages not found at $SITE_PACKAGES"
    exit 1
fi

# Copy internal modules
for module in state.py config.py database.py event_hub.py verification.py websocket_handler.py utils engines transports; do
    if [ -e "$module" ]; then
        echo "  Copying $module..."
        cp -R "$module" "$SITE_PACKAGES/"
    else
        echo "  WARNING: $module not found, skipping"
    fi
done

# Clean up
rm -rf "$TEMP_INSTALL"

echo ""
echo "======================================"
echo "Python setup completed successfully!"
echo "======================================"
echo "Python location: $OUTPUT_DIR/python"
echo "Site-packages: $SITE_PACKAGES"
echo ""
echo "Next steps:"
echo "  1. Build PyInstaller executable: pyinstaller server.spec"
echo "  2. Run electron-builder: npm run dist:mac"
echo ""
