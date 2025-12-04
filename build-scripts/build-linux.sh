#!/bin/bash

# ================================================================================
# MCP-Dandan - Linux Complete Build Script
# Includes: Python Runtime Bundling + PyInstaller + Electron AppImage/DEB
# ================================================================================

set -e

echo "==============================================="
echo "MCP-Dandan - Linux Complete Build Script"
echo "==============================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# Check Node.js
echo -e "\n${BLUE}[Pre-check] Verifying Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is not installed.${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi
echo "Node.js version: $(node --version)"

# Check Python3
echo -e "\n${BLUE}[Pre-check] Verifying Python3...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 is not installed.${NC}"
    echo "Please install Python3"
    exit 1
fi
echo "Python3 version: $(python3 --version)"

# Step 1: Setup bundled Python runtime
echo -e "\n${BLUE}[1/4] Setting up bundled Python runtime...${NC}"
bash "$ROOT_DIR/scripts/setup-python-linux.sh"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to setup Python runtime${NC}"
    exit 1
fi

# Step 2: Build PyInstaller executable
echo -e "\n${BLUE}[2/4] Building Python backend with PyInstaller...${NC}"
"$ROOT_DIR/build/python-linux/python/bin/python3" -m PyInstaller "$ROOT_DIR/server.spec" --clean
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to build Python backend${NC}"
    exit 1
fi

# Step 3: Install frontend dependencies
echo -e "\n${BLUE}[3/4] Installing frontend dependencies...${NC}"
cd "$ROOT_DIR/front"

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install --legacy-peer-deps
else
    echo "npm dependencies already installed, skipping..."
fi

# Step 4: Build Electron packages
echo -e "\n${BLUE}[4/4] Building Electron packages (AppImage + DEB)...${NC}"
npm run dist:linux

cd "$ROOT_DIR"

echo -e "\n${GREEN}===============================================${NC}"
echo -e "${GREEN}Build completed successfully!${NC}"
echo -e "${GREEN}===============================================${NC}"

# Display output files
echo -e "\n${GREEN}Output files:${NC}"
ls -lh "$ROOT_DIR/front/release/" | grep -E '\.(AppImage|deb)$' || echo "No packages found"

echo -e "\n${GREEN}Installation options:${NC}"
echo -e "  1. AppImage (portable):"
echo -e "     cd $ROOT_DIR/front/release"
echo -e "     chmod +x *.AppImage"
echo -e "     ./MCP-Dandan-*.AppImage"
echo ""
echo -e "  2. DEB package:"
echo -e "     cd $ROOT_DIR/front/release"
echo -e "     sudo dpkg -i mcp-dandan_*.deb"
echo ""
echo -e "  3. Quick install script:"
echo -e "     cd $ROOT_DIR/build-scripts"
echo -e "     ./quick-install.sh"
echo ""
