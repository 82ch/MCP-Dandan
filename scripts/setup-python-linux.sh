#!/bin/bash
# Setup Python for Linux build
# Uses python-build-standalone for maximum compatibility

set -e

PYTHON_VERSION="${PYTHON_VERSION:-3.12.7}"
OUTPUT_DIR="${OUTPUT_DIR:-build/python-linux}"

echo "======================================"
echo "Setting up Python for Linux build"
echo "======================================"
echo "Python Version: $PYTHON_VERSION"
echo "Output Directory: $OUTPUT_DIR"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Use python-build-standalone releases
# Repository moved from indygreg to astral-sh
# https://github.com/astral-sh/python-build-standalone
PYTHON_BUILD_VERSION="20241016"
PYTHON_MAJOR_MINOR=$(echo $PYTHON_VERSION | sed -E 's/([0-9]+\.[0-9]+)\..*/\1/')
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/$PYTHON_BUILD_VERSION/cpython-$PYTHON_VERSION+$PYTHON_BUILD_VERSION-x86_64-unknown-linux-gnu-install_only.tar.gz"
PYTHON_TAR="$OUTPUT_DIR/python-standalone.tar.gz"

echo "[1/5] Downloading Python $PYTHON_VERSION standalone build..."
if [ -f "$PYTHON_TAR" ]; then
    echo "  -> Already downloaded, verifying..."
    # Verify the tar file is valid
    if ! gzip -t "$PYTHON_TAR" 2>/dev/null; then
        echo "  -> Corrupted file detected, re-downloading..."
        rm -f "$PYTHON_TAR"
    fi
fi

if [ ! -f "$PYTHON_TAR" ]; then
    echo "  -> Downloading from: $PYTHON_URL"
    # Download with retry logic
    for i in {1..3}; do
        if curl -L -f --retry 3 --retry-delay 2 -o "$PYTHON_TAR" "$PYTHON_URL"; then
            echo "  -> Downloaded successfully: $PYTHON_TAR"
            break
        else
            echo "  -> Download attempt $i failed"
            rm -f "$PYTHON_TAR"
            if [ $i -eq 3 ]; then
                echo "  -> ERROR: Failed to download after 3 attempts"
                exit 1
            fi
            sleep 2
        fi
    done

    # Verify downloaded file
    if ! gzip -t "$PYTHON_TAR" 2>/dev/null; then
        echo "  -> ERROR: Downloaded file is corrupted"
        rm -f "$PYTHON_TAR"
        exit 1
    fi
else
    echo "  -> Using existing valid download"
fi

# Extract Python
echo "[2/5] Extracting Python..."
if ! tar -xzf "$PYTHON_TAR" -C "$OUTPUT_DIR"; then
    echo "  -> ERROR: Failed to extract tar file"
    rm -f "$PYTHON_TAR"
    exit 1
fi
echo "  -> Extracted to: $OUTPUT_DIR"

# Find python directory (usually named 'python')
PYTHON_DIR=$(find "$OUTPUT_DIR" -maxdepth 1 -type d -name "python" | head -1)
if [ -z "$PYTHON_DIR" ]; then
    echo "  -> ERROR: Python directory not found after extraction!"
    exit 1
fi

# Upgrade pip
echo "[3/5] Upgrading pip..."
"$PYTHON_DIR/bin/python3" -m pip install --upgrade pip
echo "  -> pip upgraded"

# Install requirements
echo "[4/5] Installing Python packages..."
cd "$(dirname "$0")/.."  # Go to project root
if [ -f "requirements.txt" ]; then
    "$PYTHON_DIR/bin/python3" -m pip install -r requirements.txt
    echo "  -> All packages installed"
else
    echo "  -> WARNING: requirements.txt not found, skipping package installation"
fi

# Copy project modules to site-packages
echo "[5/5] Copying project modules to site-packages..."
SITE_PACKAGES="$PYTHON_DIR/lib/python$PYTHON_MAJOR_MINOR/site-packages"

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

echo ""
echo "======================================"
echo "Python setup completed successfully!"
echo "======================================"
echo "Python location: $PYTHON_DIR"
echo "Site-packages: $SITE_PACKAGES"
echo ""
echo "Next steps:"
echo "  1. Build PyInstaller executable: pyinstaller server.spec"
echo "  2. Run electron-builder: npm run dist:linux"
echo ""
