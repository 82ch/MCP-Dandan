import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'path'
import { fileURLToPath } from 'url'
import { createRequire } from 'module'
import { execSync } from 'child_process'
import fs from 'fs'
import type BetterSqlite3 from 'better-sqlite3'

const require = createRequire(import.meta.url)
const Database = require('better-sqlite3') as typeof BetterSqlite3
const WebSocket = require('ws')

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Electron 보안 경고 비활성화 (개발 중)
process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true'

let mainWindow: BrowserWindow | null = null
let blockingWindow: BrowserWindow | null = null
let wsClient: any = null
let pendingBlockingData: any = null
let isRestarting = false

// Disable 82ch proxy and restore config files
function restoreConfigFiles() {
  try {
    console.log('[Electron] Disabling 82ch proxy and restoring config files...')
    // Get the project root (82ch directory)
    const projectRoot = path.join(__dirname, '..', '..')
    const configFinderPath = path.join(projectRoot, 'transports', 'config_finder.py')

    // Use python3 on macOS/Linux, python on Windows
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3'

    // Use --disable to remove proxy from local servers and delete remote servers
    execSync(`${pythonCmd} "${configFinderPath}" --disable --app all`, {
      cwd: projectRoot,
      stdio: 'pipe',
      timeout: 10000
    })
    console.log('[Electron] Config files restored successfully')
    console.log('[Electron] - Local servers: proxy removed')
    console.log('[Electron] - Remote servers: deleted')
  } catch (error) {
    console.log('[Electron] Failed to restore config files:', error)
  }
}

// Kill backend server function
function killBackendServer() {
  try {
    console.log('[Electron] Killing backend server on port 8282...')
    if (process.platform === 'win32') {
      // Windows
      execSync('FOR /F "tokens=5" %P IN (\'netstat -ano ^| findstr :8282 ^| findstr LISTENING\') DO taskkill /PID %P /F', {
        shell: 'cmd.exe',
        stdio: 'ignore'
      })
    } else {
      // macOS/Linux
      execSync('lsof -ti:8282 | xargs kill -9', { stdio: 'ignore' })
    }
    console.log('[Electron] Backend server killed successfully')
  } catch (error) {
    // Server might not be running, ignore error
    console.log('[Electron] No backend server to kill or already stopped')
  }
}

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: path.join(__dirname, '..', 'icons', 'dandan.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
    backgroundColor: '#f3f4f6',
    show: false,
    autoHideMenuBar: true,
  })

  // Remove menu bar
  mainWindow.setMenuBarVisibility(false)

  // 개발 모드와 프로덕션 모드 구분
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    // mainWindow.webContents.openDevTools() // 개발자 도구 자동 열기 비활성화
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // 윈도우가 로드되면 표시
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// Create blocking modal window
function createBlockingWindow(blockingData: any) {
  if (blockingWindow) {
    blockingWindow.focus()
    return
  }

  // Store data for the window to retrieve
  pendingBlockingData = blockingData

  blockingWindow = new BrowserWindow({
    width: 400,
    height: 350,
    minWidth: 350,
    minHeight: 300,
    show: false,
    frame: false,
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
    backgroundColor: '#ffffff',
  })

  // Load blocking modal page
  if (process.env.VITE_DEV_SERVER_URL) {
    blockingWindow.loadURL(`${process.env.VITE_DEV_SERVER_URL}#/blocking`)
  } else {
    blockingWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
      hash: '/blocking'
    })
  }

  blockingWindow.once('ready-to-show', () => {
    blockingWindow?.show()
  })

  blockingWindow.on('closed', () => {
    blockingWindow = null
    pendingBlockingData = null
  })
}

// 앱이 준비되면 윈도우 생성
app.whenReady().then(async () => {
  // Wait for backend server to be ready before initializing database
  const backendReady = await waitForBackend()

  if (backendReady) {
    // Initialize database
    initializeDatabase()

    // Connect to WebSocket server for real-time updates
    connectWebSocket()
  } else {
    console.error('[Electron] Starting app without backend connection - some features may not work')
  }

  createWindow()

  app.on('activate', () => {
    // macOS에서 독 아이콘 클릭 시 윈도우 재생성
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 모든 윈도우가 닫히면 앱 종료 (macOS 제외)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 앱이 완전히 종료될 때 - 백엔드 서버도 종료
app.on('will-quit', () => {
  isQuitting = true

  // Close WebSocket connection
  if (wsClient) {
    wsClient.close()
    wsClient = null
  }

  // Skip cleanup if restarting
  if (isRestarting) {
    console.log('[Electron] Restarting - skipping server cleanup')
    return
  }

  // Restore config files BEFORE killing server
  restoreConfigFiles()

  killBackendServer()
})

// Database setup
let db: BetterSqlite3.Database | null = null

// Wait for backend server to be ready
async function waitForBackend(): Promise<boolean> {
  const maxAttempts = 30
  const delayMs = 1000

  console.log('[Electron] Waiting for backend server to be ready...')

  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch('http://localhost:8282/health')
      if (response.ok) {
        console.log('[Electron] Backend server is ready')
        return true
      }
    } catch (error) {
      // Server not ready yet, continue waiting
      console.log(`[Electron] Backend not ready yet, attempt ${i + 1}/${maxAttempts}`)
    }

    // Wait before next attempt
    await new Promise(resolve => setTimeout(resolve, delayMs))
  }

  console.error('[Electron] Backend server failed to start within timeout')
  return false
}

// WebSocket connection for real-time updates
let isQuitting = false

function connectWebSocket() {
  const wsUrl = 'ws://localhost:8282/ws'
  console.log(`[WebSocket] Connecting to ${wsUrl}...`)

  wsClient = new WebSocket(wsUrl)

  wsClient.on('open', () => {
    console.log('[WebSocket] Connected to backend server')
  })

  wsClient.on('message', (data: any) => {
    try {
      const message = JSON.parse(data.toString())
      console.log('[WebSocket] Received:', message.type)

      // Handle blocking request - open separate window
      if (message.type === 'blocking_request') {
        console.log('[WebSocket] Opening blocking window')
        createBlockingWindow(message.data)
        return
      }

      // Forward WebSocket events to renderer process
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('websocket:update', message)
      }
    } catch (error) {
      console.error('[WebSocket] Error parsing message:', error)
    }
  })

  wsClient.on('error', (error: Error) => {
    console.error('[WebSocket] Connection error:', error)
  })

  wsClient.on('close', () => {
    console.log('[WebSocket] Connection closed, attempting to reconnect in 5s...')
    wsClient = null

    // Attempt to reconnect after 5 seconds
    setTimeout(() => {
      if (!wsClient && !isQuitting) {
        connectWebSocket()
      }
    }, 5000)
  })
}

function initializeDatabase() {
  try {
    // Use DB_PATH from environment variable or default path
    // In development: front/../data/mcp_observer.db
    // In production: can be set via DB_PATH env var
    let dbPath: string
    if (process.env.DB_PATH) {
      dbPath = process.env.DB_PATH
    } else {
      // Default: go up one directory from electron folder to project root
      const projectRoot = path.join(__dirname, '..', '..')
      dbPath = path.join(projectRoot, 'data', 'mcp_observer.db')
    }

    console.log(`[DB] Initializing database...`)
    console.log(`[DB] Database path: ${dbPath}`)
    console.log(`[DB] __dirname: ${__dirname}`)
    console.log(`[DB] app.getAppPath(): ${app.getAppPath()}`)

    db = new Database(dbPath, {
      readonly: true,
      fileMustExist: true,
      timeout: 5000
    })
    console.log(`[DB] Database connection opened successfully`)

    // Set pragmas for better concurrency handling
    db.pragma('query_only = ON')
    console.log(`[DB] Set query_only pragma`)

    const journalMode = db.pragma('journal_mode', { simple: true })
    console.log(`[DB] Journal mode: ${journalMode}`)

    // Test query to verify database is working
    const testQuery = db.prepare('SELECT COUNT(*) as count FROM sqlite_master')
    const testResult = testQuery.get() as any
    console.log(`[DB] Database schema tables count: ${testResult.count}`)

    console.log(`[DB] Database initialized successfully`)
    return true
  } catch (error: any) {
    console.error(`[DB] Error setting up database:`, error.message)
    console.error(`[DB] Error stack:`, error.stack)
    return false
  }
}

// Helper function to build mcpServers from database
function getMcpServersFromDB() {
  console.log(`[DB] getMcpServersFromDB called`)

  if (!db) {
    console.error(`[DB] Database not initialized`)
    return []
  }

  try {
    // First, get the app name (pname) and producer for each server from raw_events
    const appNameQuery = `
      SELECT DISTINCT mcpTag, pname, producer
      FROM raw_events
      WHERE mcpTag IS NOT NULL AND mcpTag != 'unknown'
    `
    const appNames = db.prepare(appNameQuery).all() as any[]
    const appNameMap = new Map()
    const producerMap = new Map()
    appNames.forEach(row => {
      appNameMap.set(row.mcpTag, row.pname || 'Unknown')
      producerMap.set(row.mcpTag, row.producer || 'local')
    })
    console.log(`[DB] Found app names for ${appNameMap.size} servers`)

    // Helper function to get icon based on app name
    const getIconForApp = (appName: string) => {
      const lowerAppName = (appName || '').toLowerCase()
      if (lowerAppName.includes('claude')) return 'claude.svg'
      if (lowerAppName.includes('cursor')) return 'cursor.svg'
      return 'default.svg'
    }

    // Group tools by mcpTag (server name)
    const serverMap = new Map()

    // First, add all servers from raw_events (so servers without tools/list also appear)
    appNames.forEach(row => {
      const serverName = row.mcpTag
      const appName = appNameMap.get(serverName) || 'Unknown'

      if (!serverMap.has(serverName)) {
        serverMap.set(serverName, {
          id: serverMap.size + 1,
          name: serverName,
          type: producerMap.get(serverName) || 'local',
          icon: getIconForApp(appName),
          appName: appName,
          tools: []
        })
        console.log(`[DB] Added server: ${serverName} (app: ${appName})`)
      }
    })

    // Get tools from mcpl table and add them to existing servers
    const query = `
      SELECT
        mcpTag,
        tool,
        tool_title,
        tool_description,
        safety
      FROM mcpl
      ORDER BY mcpTag, created_at
    `
    console.log(`[DB] Executing query for tools: ${query.trim()}`)

    const rows = db.prepare(query).all() as any[]
    console.log(`[DB] Query returned ${rows.length} tool rows`)

    rows.forEach(row => {
      const server = serverMap.get(row.mcpTag)
      if (server) {
        server.tools.push({
          name: row.tool,
          description: row.tool_description || '',
          safety: row.safety || 0  // 0: 검사 전, 1: 안전, 2: 조치권장, 3: 조치필요
        })
      }
    })

    // Calculate safety status for each server
    const servers = Array.from(serverMap.values()).map((server: any) => {
      const tools = server.tools as any[]
      const hasUnchecked = tools.some((t: any) => t.safety === 0)
      const hasActionRequired = tools.some((t: any) => t.safety === 3)  // 조치필요
      const hasActionRecommended = tools.some((t: any) => t.safety === 2)  // 조치권장

      return {
        ...server,
        isChecking: hasUnchecked,  // 검사 중인 도구가 있는가
        hasDanger: hasActionRequired,  // 조치필요 도구가 있는가
        hasWarning: hasActionRecommended  // 조치권장 도구가 있는가
      }
    })

    console.log(`[DB] Returning ${servers.length} servers`)
    servers.forEach(s => console.log(`[DB]   - ${s.name}: ${s.tools.length} tools, checking: ${s.isChecking}, danger: ${s.hasDanger}`))

    return servers
  } catch (error) {
    console.error('[DB] Error fetching MCP servers from database:', error)
    return []
  }
}

// IPC Handlers

// Get all MCP servers
ipcMain.handle('api:servers', () => {
  console.log(`[IPC] api:servers called`)
  const servers = getMcpServersFromDB()
  console.log(`[IPC] api:servers returning ${servers.length} servers`)
  return servers
})

// Get messages for a specific server
ipcMain.handle('api:servers:messages', (_event, serverId: number) => {
  console.log(`[IPC] api:servers:messages called with serverId: ${serverId}`)

  if (!db) {
    console.error(`[DB] Database not initialized`)
    return []
  }

  try {
    // First, get the server name from mcpServers
    const mcpServers = getMcpServersFromDB()
    const server = mcpServers.find((s: any) => s.id === serverId)

    if (!server) {
      console.error(`[DB] Server with id ${serverId} not found`)
      throw new Error('Server not found')
    }

    console.log(`[DB] Found server: ${server.name}`)

    // Query raw_events table for messages with matching mcpTag
    // Join with engine_results to get malicious scores
    const query = `
      SELECT
        re.id,
        re.ts,
        re.producer,
        re.pid,
        re.pname,
        re.event_type,
        re.mcpTag,
        re.data,
        re.created_at,
        COALESCE(MAX(er.score), 0) as max_score
      FROM raw_events re
      LEFT JOIN engine_results er ON re.id = er.raw_event_id
      WHERE re.mcpTag = ? AND re.event_type IN ('MCP', 'Proxy')
      GROUP BY re.id
      ORDER BY re.ts ASC
    `

    console.log(`[DB] Executing query for mcpTag: ${server.name}`)
    const rows = db.prepare(query).all(server.name) as any[]
    console.log(`[DB] Query returned ${rows.length} messages`)

    // Transform database rows to match frontend expected format
    const messages = rows.map(row => {
      let parsedData: any = {}
      try {
        parsedData = typeof row.data === 'string' ? JSON.parse(row.data) : row.data
      } catch (e) {
        console.error(`[DB] Error parsing data for event ${row.id}:`, e)
        parsedData = { raw: row.data }
      }

      // Determine message type from data
      let messageType = row.event_type
      if (parsedData.message && parsedData.message.method) {
        messageType = parsedData.message.method
      }

      // Determine sender from data (task field: send = client, recv = server)
      let sender = 'unknown'
      if (parsedData.task === 'SEND') {
        sender = 'client'
      } else if (parsedData.task === 'RECV') {
        sender = 'server'
      }

      // Get maliciousScore from engine_results (max_score from JOIN)
      const maliciousScore = row.max_score || 0

      // Convert ts to readable timestamp
      // Handle both string timestamps and numeric timestamps
      let timestamp: string
      try {
        if (typeof row.ts === 'string') {
          // If it's a string in ISO format or similar, try to parse directly
          // Format: "2025-11-12 16:53:17.613"
          const parsedDate = new Date(row.ts.replace(' ', 'T') + 'Z')
          if (!isNaN(parsedDate.getTime())) {
            timestamp = parsedDate.toISOString()
          } else {
            throw new Error('Invalid date string')
          }
        } else if (typeof row.ts === 'number') {
          // Check if ts is in nanoseconds (very large number)
          if (row.ts > 1e15) {
            // Nanoseconds to milliseconds
            const tsInMs = Math.floor(row.ts / 1000000)
            timestamp = new Date(tsInMs).toISOString()
          } else if (row.ts > 1e12) {
            // Already in milliseconds
            timestamp = new Date(row.ts).toISOString()
          } else {
            // Seconds to milliseconds
            timestamp = new Date(row.ts * 1000).toISOString()
          }
        } else {
          throw new Error('Unknown timestamp format')
        }
      } catch (e) {
        console.error(`[DB] Error converting timestamp for event ${row.id}, ts=${row.ts}, type=${typeof row.ts}:`, e)
        timestamp = new Date().toISOString() // Use current time as fallback
      }

      return {
        id: row.id,
        content: '',
        type: messageType,
        sender: sender,
        timestamp: timestamp,
        maliciousScore: maliciousScore,
        event_type: row.event_type,  // event_type 추가 (Proxy 또는 MCP)
        data: {
          message: parsedData.message || parsedData
        }
      }
    })

    console.log(`[IPC] api:servers:messages returning ${messages.length} messages`)
    return messages
  } catch (error) {
    console.error('[IPC] Error fetching messages:', error)
    return []
  }
})

// Get all engine results (for Dashboard Detected section)
ipcMain.handle('api:engine-results', () => {
  console.log(`[IPC] api:engine-results called`)

  if (!db) {
    console.error(`[DB] Database not initialized`)
    return []
  }

  try {
    const query = `
      SELECT
        er.id,
        er.raw_event_id,
        er.engine_name,
        er.serverName,
        er.severity,
        er.score,
        er.detail,
        er.created_at,
        re.ts,
        re.event_type,
        re.data
      FROM engine_results er
      LEFT JOIN raw_events re ON er.raw_event_id = re.id
      ORDER BY er.created_at DESC
    `
    console.log(`[DB] Executing query for engine results`)
    const results = db.prepare(query).all()
    console.log(`[DB] Query returned ${results.length} engine results`)
    console.log(`[IPC] api:engine-results returning ${results.length} results`)
    return results
  } catch (error) {
    console.error('[IPC] Error fetching engine results:', error)
    return []
  }
})

// Get engine results for a specific raw_event_id
ipcMain.handle('api:engine-results:by-event', (_event, rawEventId: number) => {
  console.log(`[IPC] api:engine-results:by-event called with rawEventId: ${rawEventId}`)

  if (!db) {
    console.error(`[DB] Database not initialized`)
    return []
  }

  try {
    const query = `
      SELECT
        id,
        raw_event_id,
        engine_name,
        serverName,
        producer,
        severity,
        score,
        detail,
        created_at
      FROM engine_results
      WHERE raw_event_id = ?
      ORDER BY score DESC
    `
    console.log(`[DB] Executing query for raw_event_id: ${rawEventId}`)
    const results = db.prepare(query).all(rawEventId)
    console.log(`[DB] Query returned ${results.length} engine results`)
    console.log(`[IPC] api:engine-results:by-event returning ${results.length} results`)
    return results
  } catch (error) {
    console.error('[IPC] Error fetching engine results by event:', error)
    return []
  }
})

// IPC 핸들러 예제
ipcMain.handle('ping', () => 'pong')

// 앱 관련 정보 제공
ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    name: app.getName(),
    platform: process.platform,
  }
})

// Handle blocking decision from renderer
ipcMain.handle('blocking:decision', (_event, requestId: string, decision: 'allow' | 'block') => {
  console.log(`[IPC] blocking:decision called: ${requestId} -> ${decision}`)

  if (wsClient && wsClient.readyState === WebSocket.OPEN) {
    const message = {
      type: 'blocking_decision',
      request_id: requestId,
      decision: decision
    }
    wsClient.send(JSON.stringify(message))
    console.log(`[WebSocket] Sent blocking decision: ${requestId} -> ${decision}`)
  } else {
    console.error('[WebSocket] Cannot send blocking decision - not connected')
  }

  // Close blocking window after decision
  if (blockingWindow && !blockingWindow.isDestroyed()) {
    blockingWindow.close()
  }
})

// Get blocking data for blocking window
ipcMain.handle('blocking:get-data', () => {
  console.log(`[IPC] blocking:get-data called`)
  return pendingBlockingData
})

// Close blocking window
ipcMain.handle('blocking:close', () => {
  console.log(`[IPC] blocking:close called`)
  if (blockingWindow && !blockingWindow.isDestroyed()) {
    blockingWindow.close()
  }
})

// Resize blocking window
ipcMain.handle('blocking:resize', (_event, width: number, height: number) => {
  console.log(`[IPC] blocking:resize called: ${width}x${height}`)
  if (blockingWindow && !blockingWindow.isDestroyed()) {
    blockingWindow.setSize(width, height)
    blockingWindow.center()
  }
})

// Config file path
function getConfigPath() {
  const projectRoot = path.join(__dirname, '..', '..')
  return path.join(projectRoot, 'config.conf')
}

// Parse config.conf file
function parseConfig(content: string) {
  const config: any = {
    Engine: {
      sensitive_file_enabled: true,
      tools_poisoning_enabled: true,
      command_injection_enabled: true,
      file_system_exposure_enabled: true
    },
    Log: {
      log_dir: './logs',
      max_log_file_size_mb: 100,
      max_log_files: 5
    }
  }

  let currentSection = ''
  const lines = content.split('\n')

  for (const line of lines) {
    const trimmed = line.trim()

    // Skip comments and empty lines
    if (trimmed.startsWith('#') || trimmed === '') continue

    // Section header
    const sectionMatch = trimmed.match(/^\[(\w+)\]$/)
    if (sectionMatch) {
      currentSection = sectionMatch[1]
      continue
    }

    // Key-value pair
    const kvMatch = trimmed.match(/^(\w+)\s*=\s*(.+)$/)
    if (kvMatch && currentSection) {
      const key = kvMatch[1]
      let value: any = kvMatch[2].trim()

      // Parse boolean values
      if (value === 'True' || value === 'true') {
        value = true
      } else if (value === 'False' || value === 'false') {
        value = false
      } else if (!isNaN(Number(value))) {
        value = Number(value)
      }

      if (config[currentSection]) {
        config[currentSection][key] = value
      }
    }
  }

  return config
}

// Generate config.conf content
function generateConfig(config: any) {
  const lines: string[] = [
    '# 82ch Unified Configuration',
    '# Observer + Engine integrated mode',
    '',
    '[Engine]',
    '# Detection engines to enable',
    `sensitive_file_enabled = ${config.Engine.sensitive_file_enabled ? 'True' : 'False'}`,
    `tools_poisoning_enabled = ${config.Engine.tools_poisoning_enabled ? 'True' : 'False'}`,
    `command_injection_enabled = ${config.Engine.command_injection_enabled ? 'True' : 'False'}`,
    `file_system_exposure_enabled = ${config.Engine.file_system_exposure_enabled ? 'True' : 'False'}`,
    '',
    '[Log]',
    '# Log directory (currently not used, but reserved for future)',
    `log_dir = ${config.Log.log_dir}`,
    '',
    '# Log file rotation settings',
    `max_log_file_size_mb = ${config.Log.max_log_file_size_mb}`,
    `max_log_files = ${config.Log.max_log_files}`
  ]

  return lines.join('\n')
}

// Get config
ipcMain.handle('config:get', () => {
  console.log(`[IPC] config:get called`)
  try {
    const configPath = getConfigPath()
    const content = fs.readFileSync(configPath, 'utf-8')
    const config = parseConfig(content)
    console.log(`[IPC] config:get returning config`)
    return config
  } catch (error) {
    console.error('[IPC] Error reading config:', error)
    throw error
  }
})

// Save config
ipcMain.handle('config:save', (_event, config: any) => {
  console.log(`[IPC] config:save called`)
  try {
    const configPath = getConfigPath()
    const content = generateConfig(config)
    fs.writeFileSync(configPath, content, 'utf-8')
    console.log(`[IPC] config:save completed`)
    return true
  } catch (error) {
    console.error('[IPC] Error saving config:', error)
    throw error
  }
})

// Get .env file path
function getEnvPath() {
  const projectRoot = path.join(__dirname, '..', '..')
  return path.join(projectRoot, '.env')
}

// Get env variables
ipcMain.handle('env:get', () => {
  console.log(`[IPC] env:get called`)
  try {
    const envPath = getEnvPath()
    if (!fs.existsSync(envPath)) {
      return { MISTRAL_API_KEY: '' }
    }
    const content = fs.readFileSync(envPath, 'utf-8')
    const env: any = {}
    const lines = content.split('\n')
    for (const line of lines) {
      const match = line.match(/^([^=]+)=(.*)$/)
      if (match) {
        env[match[1].trim()] = match[2].trim()
      }
    }
    console.log(`[IPC] env:get returning env`)
    return env
  } catch (error) {
    console.error('[IPC] Error reading env:', error)
    throw error
  }
})

// Save env variables
ipcMain.handle('env:save', (_event, env: any) => {
  console.log(`[IPC] env:save called`)
  try {
    const envPath = getEnvPath()
    const lines = Object.entries(env).map(([key, value]) => `${key}=${value}`)
    fs.writeFileSync(envPath, lines.join('\n'), 'utf-8')
    console.log(`[IPC] env:save completed`)
    return true
  } catch (error) {
    console.error('[IPC] Error saving env:', error)
    throw error
  }
})

// Restart app
ipcMain.handle('app:restart', () => {
  console.log(`[IPC] app:restart called`)
  isRestarting = true
  app.relaunch()
  app.exit(0)
})
