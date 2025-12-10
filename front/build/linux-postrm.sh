#!/bin/bash
# post remove script - cleans up user config on purge

# $1 contains the action (remove, purge, etc.)
if [ "$1" = "purge" ]; then
    # Remove user config directories for all users
    for user_home in /home/*; do
        if [ -d "$user_home/.config/mcp-dandan" ]; then
            rm -rf "$user_home/.config/mcp-dandan"
            echo "Removed $user_home/.config/mcp-dandan"
        fi
    done

    # Also check root user
    if [ -d "/root/.config/mcp-dandan" ]; then
        rm -rf "/root/.config/mcp-dandan"
        echo "Removed /root/.config/mcp-dandan"
    fi
fi

exit 0