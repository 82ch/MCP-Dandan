#!/bin/bash
#
# 82ch Desktop - Quick Local Installation Script
# For installing from locally built packages
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  82ch Desktop - Quick Install${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_DIR="$SCRIPT_DIR/front/release"

# Check if release directory exists
if [ ! -d "$RELEASE_DIR" ]; then
  echo -e "${RED}Error: Release directory not found${NC}"
  echo -e "${YELLOW}Please build the application first:${NC}"
  echo -e "  cd front"
  echo -e "  npm run dist:linux"
  exit 1
fi

# Find packages
APPIMAGE=$(find "$RELEASE_DIR" -name "*.AppImage" -type f | head -n 1)
DEB=$(find "$RELEASE_DIR" -name "*.deb" -type f | head -n 1)

if [ -z "$APPIMAGE" ] && [ -z "$DEB" ]; then
  echo -e "${RED}Error: No packages found in $RELEASE_DIR${NC}"
  echo -e "${YELLOW}Please build the application first${NC}"
  exit 1
fi

echo -e "${BLUE}Found packages:${NC}"
[ -n "$APPIMAGE" ] && echo -e "  • AppImage: $(basename "$APPIMAGE")"
[ -n "$DEB" ] && echo -e "  • DEB: $(basename "$DEB")"
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ] && [ -n "$DEB" ]; then
  echo -e "${YELLOW}DEB installation requires sudo privileges${NC}"
  echo -e "${YELLOW}Re-running with sudo...${NC}\n"
  exec sudo "$0" "$@"
fi

# Installation choice
if [ -n "$DEB" ] && [ -n "$APPIMAGE" ]; then
  echo -e "${BLUE}Choose installation method:${NC}"
  echo -e "  1) DEB package (recommended for Ubuntu/Debian)"
  echo -e "  2) AppImage (portable, works on any Linux)"
  echo -e "  3) Both"
  read -p "Enter choice [1-3]: " choice
  echo ""
elif [ -n "$DEB" ]; then
  choice=1
elif [ -n "$APPIMAGE" ]; then
  choice=2
fi

# Install DEB
if [ "$choice" = "1" ] || [ "$choice" = "3" ]; then
  echo -e "${BLUE}Installing DEB package...${NC}"
  dpkg -i "$DEB" || true
  apt-get install -f -y
  echo -e "${GREEN}✓ DEB package installed${NC}\n"
fi

# Install AppImage
if [ "$choice" = "2" ] || [ "$choice" = "3" ]; then
  echo -e "${BLUE}Installing AppImage...${NC}"

  INSTALL_DIR="$HOME/.local/share/82ch-desktop"
  BIN_DIR="$HOME/.local/bin"

  mkdir -p "$INSTALL_DIR"
  mkdir -p "$BIN_DIR"

  cp "$APPIMAGE" "$INSTALL_DIR/82ch-desktop.AppImage"
  chmod +x "$INSTALL_DIR/82ch-desktop.AppImage"

  # Create symlink
  ln -sf "$INSTALL_DIR/82ch-desktop.AppImage" "$BIN_DIR/82ch-desktop"

  # Create desktop entry
  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/82ch-desktop.desktop" <<EOF
[Desktop Entry]
Name=82ch Desktop
Comment=MCP Security Framework with Desktop UI
Exec=$BIN_DIR/82ch-desktop
Icon=82ch-desktop
Terminal=false
Type=Application
Categories=Development;Security;
EOF

  chmod +x "$HOME/.local/share/applications/82ch-desktop.desktop"

  # Update desktop database
  if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  fi

  echo -e "${GREEN}✓ AppImage installed to $INSTALL_DIR${NC}"
  echo -e "${GREEN}✓ Symlink created at $BIN_DIR/82ch-desktop${NC}"
  echo -e "${GREEN}✓ Desktop entry created${NC}\n"

  # Check if .local/bin is in PATH
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${YELLOW}Note: $BIN_DIR is not in your PATH${NC}"
    echo -e "${YELLOW}Add it to your PATH by adding this line to ~/.bashrc or ~/.zshrc:${NC}"
    echo -e "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
  fi
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "You can now run ${GREEN}82ch Desktop${NC} from:"
echo -e "  • Application menu (search for '82ch Desktop')"

if [ "$choice" = "2" ] || [ "$choice" = "3" ]; then
  echo -e "  • Terminal: ${BLUE}82ch-desktop${NC}"
  echo -e "  • Or directly: ${BLUE}$BIN_DIR/82ch-desktop${NC}"
fi

echo -e "\n${BLUE}Tip: Double-click the AppImage to run it without installation${NC}\n"
