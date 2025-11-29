#!/bin/bash
#
# 82ch Desktop - One-line Installation Script
# Usage: curl -fsSL https://raw.githubusercontent.com/your-org/82ch/main/install.sh | bash
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/your-org/82ch-desktop/releases/latest/download"
APP_NAME="82ch Desktop"
INSTALL_DIR="/opt/82ch-desktop"
BIN_LINK="/usr/local/bin/82ch-desktop"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  82ch Desktop Installation${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${YELLOW}This script requires sudo privileges.${NC}"
  echo -e "${YELLOW}Please run with sudo or as root.${NC}"
  exit 1
fi

# Detect Linux distribution
detect_distro() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    VERSION=$VERSION_ID
  elif [ -f /etc/lsb-release ]; then
    . /etc/lsb-release
    DISTRO=$DISTRIB_ID
    VERSION=$DISTRIB_RELEASE
  else
    DISTRO="unknown"
  fi

  echo -e "${BLUE}Detected: $DISTRO $VERSION${NC}"
}

# Check dependencies
check_dependencies() {
  echo -e "\n${BLUE}[1/6] Checking dependencies...${NC}"

  local missing_deps=()

  # Check Python
  if ! command -v python3 &> /dev/null; then
    missing_deps+=("python3")
  fi

  # Check pip
  if ! command -v pip3 &> /dev/null; then
    missing_deps+=("python3-pip")
  fi

  # Check curl
  if ! command -v curl &> /dev/null; then
    missing_deps+=("curl")
  fi

  if [ ${#missing_deps[@]} -gt 0 ]; then
    echo -e "${YELLOW}Missing dependencies: ${missing_deps[*]}${NC}"
    echo -e "${BLUE}Installing dependencies...${NC}"

    case "$DISTRO" in
      ubuntu|debian)
        apt-get update
        apt-get install -y "${missing_deps[@]}"
        ;;
      fedora|rhel|centos)
        dnf install -y "${missing_deps[@]}"
        ;;
      arch)
        pacman -Sy --noconfirm "${missing_deps[@]}"
        ;;
      *)
        echo -e "${RED}Please install the following manually: ${missing_deps[*]}${NC}"
        exit 1
        ;;
    esac
  else
    echo -e "${GREEN}All dependencies satisfied${NC}"
  fi
}

# Download appropriate package
download_package() {
  echo -e "\n${BLUE}[2/6] Downloading 82ch Desktop...${NC}"

  # Determine architecture
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)
      ARCH_NAME="amd64"
      ;;
    aarch64|arm64)
      ARCH_NAME="arm64"
      ;;
    *)
      echo -e "${RED}Unsupported architecture: $ARCH${NC}"
      exit 1
      ;;
  esac

  # Create temporary directory
  TMP_DIR=$(mktemp -d)
  cd "$TMP_DIR"

  # Try DEB package first (for Debian/Ubuntu)
  if [[ "$DISTRO" =~ ^(ubuntu|debian)$ ]]; then
    PKG_FILE="82ch-desktop_1.0.0_${ARCH_NAME}.deb"
    echo -e "${BLUE}Downloading DEB package: $PKG_FILE${NC}"

    if curl -fsSL -o "$PKG_FILE" "$REPO_URL/$PKG_FILE"; then
      echo -e "${GREEN}Package downloaded successfully${NC}"
      PACKAGE_TYPE="deb"
      return 0
    else
      echo -e "${YELLOW}DEB package not available, trying AppImage...${NC}"
    fi
  fi

  # Download AppImage (universal)
  PKG_FILE="82ch-Desktop-1.0.0.AppImage"
  echo -e "${BLUE}Downloading AppImage: $PKG_FILE${NC}"

  if curl -fsSL -o "$PKG_FILE" "$REPO_URL/$PKG_FILE"; then
    chmod +x "$PKG_FILE"
    echo -e "${GREEN}AppImage downloaded successfully${NC}"
    PACKAGE_TYPE="appimage"
    return 0
  else
    echo -e "${RED}Failed to download package${NC}"
    exit 1
  fi
}

# Install package
install_package() {
  echo -e "\n${BLUE}[3/6] Installing package...${NC}"

  if [ "$PACKAGE_TYPE" = "deb" ]; then
    dpkg -i "$PKG_FILE" || true
    apt-get install -f -y
    echo -e "${GREEN}DEB package installed${NC}"
  elif [ "$PACKAGE_TYPE" = "appimage" ]; then
    mkdir -p "$INSTALL_DIR"
    cp "$PKG_FILE" "$INSTALL_DIR/82ch-desktop.AppImage"
    ln -sf "$INSTALL_DIR/82ch-desktop.AppImage" "$BIN_LINK"
    echo -e "${GREEN}AppImage installed to $INSTALL_DIR${NC}"
  fi
}

# Install Python dependencies
install_python_deps() {
  echo -e "\n${BLUE}[4/6] Installing Python dependencies...${NC}"

  # Requirements are bundled with the app, skip for now
  echo -e "${YELLOW}Python dependencies will be managed by the application${NC}"
}

# Create desktop entry
create_desktop_entry() {
  echo -e "\n${BLUE}[5/6] Creating desktop entry...${NC}"

  if [ "$PACKAGE_TYPE" = "appimage" ]; then
    cat > /usr/share/applications/82ch-desktop.desktop <<EOF
[Desktop Entry]
Name=82ch Desktop
Comment=MCP Security Framework with Desktop UI
Exec=$BIN_LINK
Icon=82ch-desktop
Terminal=false
Type=Application
Categories=Development;Security;
EOF

    chmod +x /usr/share/applications/82ch-desktop.desktop
    echo -e "${GREEN}Desktop entry created${NC}"
  else
    echo -e "${GREEN}Desktop entry created by package manager${NC}"
  fi
}

# Cleanup
cleanup() {
  echo -e "\n${BLUE}[6/6] Cleaning up...${NC}"
  cd /
  rm -rf "$TMP_DIR"
  echo -e "${GREEN}Cleanup complete${NC}"
}

# Main installation flow
main() {
  detect_distro
  check_dependencies
  download_package
  install_package
  install_python_deps
  create_desktop_entry
  cleanup

  echo -e "\n${GREEN}========================================${NC}"
  echo -e "${GREEN}  Installation Complete!${NC}"
  echo -e "${GREEN}========================================${NC}\n"

  echo -e "You can now run ${GREEN}82ch Desktop${NC} from:"
  echo -e "  • Application menu"
  echo -e "  • Terminal: ${BLUE}82ch-desktop${NC}\n"

  echo -e "${YELLOW}Note: Make sure Python 3.8+ is installed on your system${NC}"
  echo -e "${YELLOW}      for full functionality.${NC}\n"
}

# Run installation
main
