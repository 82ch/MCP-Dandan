#!/bin/bash

# MCP-Dandan Linux Uninstaller
# This script removes the application and all its data

echo "=========================================="
echo "  MCP-Dandan Uninstaller"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Please do not run this script as root"
   exit 1
fi

echo "This will remove MCP-Dandan and all its data including:"
echo "  - Application files"
echo "  - Configuration files (~/.config/mcp-dandan)"
echo "  - Database and user data"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo ""
echo "Removing MCP-Dandan..."

# Remove application data
if [ -d "$HOME/.config/mcp-dandan" ]; then
    echo "Removing configuration directory: $HOME/.config/mcp-dandan"
    rm -rf "$HOME/.config/mcp-dandan"
fi

# Remove .desktop file (for .deb installs)
if [ -f "$HOME/.local/share/applications/mcp-dandan.desktop" ]; then
    echo "Removing desktop entry: $HOME/.local/share/applications/mcp-dandan.desktop"
    rm -f "$HOME/.local/share/applications/mcp-dandan.desktop"
fi

# For AppImage - remove the AppImage file if known
if [ -f "$HOME/Applications/MCP-Dandan.AppImage" ]; then
    echo "Removing AppImage: $HOME/Applications/MCP-Dandan.AppImage"
    rm -f "$HOME/Applications/MCP-Dandan.AppImage"
fi

# For .deb package - use dpkg to remove
if dpkg -l | grep -q "mcp-dandan"; then
    echo "Removing .deb package..."
    sudo dpkg -r mcp-dandan 2>/dev/null || echo "Note: Package removal requires sudo"
fi

echo ""
echo "=========================================="
echo "  MCP-Dandan has been uninstalled"
echo "=========================================="
echo ""
echo "All application data has been removed."
echo "Thank you for using MCP-Dandan!"
