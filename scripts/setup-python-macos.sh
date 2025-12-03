#!/bin/bash
# Setup Python for macOS build using python-build-standalone
# Creates a relocatable Python runtime

set -e

# Get the project root directory (parent of scripts directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

PYTHON_VERSION="3.12"
OUTPUT_DIR="build/python-macos"

echo "======================================"
echo "Setting up Python for macOS build"
echo "======================================"
echo "Python Version: $PYTHON_VERSION"
echo "Output Directory: $OUTPUT_DIR"
echo "Root Directory: $ROOT_DIR"
echo ""

# Create output directory
mkdir -p "$ROOT_DIR/$OUTPUT_DIR"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    PYTHON_ARCH="x86_64"
elif [ "$ARCH" = "arm64" ]; then
    PYTHON_ARCH="aarch64"
else
    echo "  -> ERROR: Unsupported architecture: $ARCH"
    exit 1
fi

# Download python-build-standalone
PYTHON_BUILD_VERSION="20251120"
PYTHON_MINOR_VERSION="12"  # 3.12.12
PYTHON_TARBALL="cpython-${PYTHON_VERSION}.${PYTHON_MINOR_VERSION}+${PYTHON_BUILD_VERSION}-${PYTHON_ARCH}-apple-darwin-install_only_stripped.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD_VERSION}/${PYTHON_TARBALL}"

echo "[1/5] Downloading Python $PYTHON_VERSION for macOS ($PYTHON_ARCH)..."
# Remove incomplete/corrupted downloads
if [ -f "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL" ]; then
    FILE_SIZE=$(stat -f%z "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL" 2>/dev/null || echo 0)
    if [ "$FILE_SIZE" -lt 10000 ]; then
        echo "  -> Removing corrupted download..."
        rm "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL"
    else
        echo "  -> Already downloaded, skipping"
        echo "  -> File size: $FILE_SIZE bytes"
    fi
fi

if [ ! -f "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL" ]; then
    echo "  -> Downloading from: $PYTHON_URL"
    curl -L -o "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL" "$PYTHON_URL"

    # Verify download
    FILE_SIZE=$(stat -f%z "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL" 2>/dev/null || echo 0)
    if [ "$FILE_SIZE" -lt 10000 ]; then
        echo "  -> ERROR: Download failed (file size: $FILE_SIZE bytes)"
        cat "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL"
        rm "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL"
        exit 1
    fi
    echo "  -> Downloaded: $PYTHON_TARBALL ($FILE_SIZE bytes)"
fi

# Extract Python
echo "[2/5] Extracting Python..."
# Clean up existing python directory completely
if [ -d "$ROOT_DIR/$OUTPUT_DIR/python" ]; then
    echo "  -> Removing existing Python directory..."
    # Remove immutable flags and grant full permissions
    chflags -R nouchg "$ROOT_DIR/$OUTPUT_DIR/python" 2>/dev/null || true
    chmod -R u+w "$ROOT_DIR/$OUTPUT_DIR/python" 2>/dev/null || true
    # Use find to delete files first, then directories
    find "$ROOT_DIR/$OUTPUT_DIR/python" -type f -delete 2>/dev/null || true
    find "$ROOT_DIR/$OUTPUT_DIR/python" -type d -delete 2>/dev/null || true
    rm -rf "$ROOT_DIR/$OUTPUT_DIR/python" 2>/dev/null || true
fi
if [ -d "$ROOT_DIR/$OUTPUT_DIR/python-temp" ]; then
    echo "  -> Removing python-temp directory..."
    chflags -R nouchg "$ROOT_DIR/$OUTPUT_DIR/python-temp" 2>/dev/null || true
    chmod -R u+w "$ROOT_DIR/$OUTPUT_DIR/python-temp" 2>/dev/null || true
    find "$ROOT_DIR/$OUTPUT_DIR/python-temp" -type f -delete 2>/dev/null || true
    find "$ROOT_DIR/$OUTPUT_DIR/python-temp" -type d -delete 2>/dev/null || true
    rm -rf "$ROOT_DIR/$OUTPUT_DIR/python-temp" 2>/dev/null || true
fi

# Extract and handle different archive structures
tar -xzf "$ROOT_DIR/$OUTPUT_DIR/$PYTHON_TARBALL" -C "$ROOT_DIR/$OUTPUT_DIR"

# Check which directory structure was created
if [ -d "$ROOT_DIR/$OUTPUT_DIR/python" ]; then
    # Archive already extracted to 'python' directory - we're good
    echo "  -> Extracted to: $ROOT_DIR/$OUTPUT_DIR/python"
elif [ -d "$ROOT_DIR/$OUTPUT_DIR/install" ]; then
    # Archive extracted to 'install' directory
    mv "$ROOT_DIR/$OUTPUT_DIR/install" "$ROOT_DIR/$OUTPUT_DIR/python"
    echo "  -> Extracted to: $ROOT_DIR/$OUTPUT_DIR/python"
else
    echo "  -> ERROR: Could not find extracted Python directory"
    ls -la "$ROOT_DIR/$OUTPUT_DIR/"
    exit 1
fi

# Upgrade pip
echo "[3/5] Upgrading pip..."
"$ROOT_DIR/$OUTPUT_DIR/python/bin/python3" -m pip install --upgrade pip
echo "  -> pip upgraded"

# Install requirements
echo "[4/5] Installing Python packages..."
if [ -f "$ROOT_DIR/requirements.txt" ]; then
    "$ROOT_DIR/$OUTPUT_DIR/python/bin/python3" -m pip install -r "$ROOT_DIR/requirements.txt"
    echo "  -> All packages installed"
else
    echo "  -> WARNING: requirements.txt not found, skipping package installation"
fi

# Copy project modules to site-packages
echo "[5/6] Copying project modules to site-packages..."
SITE_PACKAGES="$ROOT_DIR/$OUTPUT_DIR/python/lib/python$PYTHON_VERSION/site-packages"

if [ ! -d "$SITE_PACKAGES" ]; then
    echo "  -> ERROR: site-packages not found at $SITE_PACKAGES"
    exit 1
fi

# Copy internal modules needed by bundled scripts
for module in utils transports state.py config.py database.py event_hub.py verification.py websocket_handler.py engines; do
    if [ -e "$ROOT_DIR/$module" ]; then
        echo "  Copying $module..."
        cp -R "$ROOT_DIR/$module" "$SITE_PACKAGES/"
    else
        echo "  WARNING: $module not found at $ROOT_DIR/$module, skipping"
    fi
done

# Verify installation
echo "[6/6] Verifying installation..."
"$ROOT_DIR/$OUTPUT_DIR/python/bin/python3" --version
echo "  -> Python verified successfully"

echo ""
echo "======================================"
echo "Python setup completed successfully!"
echo "======================================"
echo "Python location: $ROOT_DIR/$OUTPUT_DIR/python"
echo ""
