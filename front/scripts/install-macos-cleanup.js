#!/usr/bin/env node

/**
 * macOS LaunchAgent installer for automatic cleanup when app is deleted
 * This script installs a LaunchAgent that monitors the app and cleans up data when uninstalled
 */

const fs = require('fs')
const path = require('path')
const os = require('os')
const { execSync } = require('child_process')

// Only run on macOS
if (process.platform !== 'darwin') {
  console.log('This script is only for macOS')
  process.exit(0)
}

const homeDir = os.homedir()
const launchAgentsDir = path.join(homeDir, 'Library', 'LaunchAgents')
const plistName = 'com.82ch.mcp-dandan.cleanup.plist'
const plistPath = path.join(launchAgentsDir, plistName)

// LaunchAgent plist content
const plistContent = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.82ch.mcp-dandan.cleanup</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-c</string>
    <string>
    # Check if MCP-Dandan app exists
    if [ ! -d "/Applications/MCP-Dandan.app" ] &amp;&amp; [ ! -d "$HOME/Applications/MCP-Dandan.app" ]; then
      # App is deleted, clean up data
      rm -rf "$HOME/Library/Application Support/mcp-dandan"
      rm -rf "$HOME/.config/mcp-dandan"
      # Remove this LaunchAgent itself
      launchctl unload "$HOME/Library/LaunchAgents/com.82ch.mcp-dandan.cleanup.plist" 2>/dev/null
      rm -f "$HOME/Library/LaunchAgents/com.82ch.mcp-dandan.cleanup.plist"
    fi
    </string>
  </array>

  <key>StartInterval</key>
  <integer>60</integer>

  <key>RunAtLoad</key>
  <false/>

  <key>StandardOutPath</key>
  <string>/tmp/mcp-dandan-cleanup.log</string>

  <key>StandardErrorPath</key>
  <string>/tmp/mcp-dandan-cleanup-error.log</string>
</dict>
</plist>
`

try {
  // Create LaunchAgents directory if it doesn't exist
  if (!fs.existsSync(launchAgentsDir)) {
    fs.mkdirSync(launchAgentsDir, { recursive: true })
    console.log('Created LaunchAgents directory')
  }

  // Write plist file
  fs.writeFileSync(plistPath, plistContent, 'utf-8')
  console.log(`LaunchAgent installed at: ${plistPath}`)

  // Load the LaunchAgent
  try {
    execSync(`launchctl load "${plistPath}"`, { stdio: 'pipe' })
    console.log('LaunchAgent loaded successfully')
  } catch (err) {
    console.log('LaunchAgent file created (will be loaded on next login)')
  }

  console.log('MCP-Dandan cleanup agent installed successfully!')
  console.log('This agent will automatically remove app data when MCP-Dandan is uninstalled.')
} catch (error) {
  console.error('Failed to install LaunchAgent:', error)
  process.exit(1)
}
