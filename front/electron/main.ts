import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'path'
import { fileURLToPath } from 'url'
import { createRequire } from 'module'
import { execSync } from 'child_process'
import type BetterSqlite3 from 'better-sqlite3'

const require = createRequire(import.meta.url)
const Database = require('better-sqlite3') as typeof BetterSqlite3

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Electron 보안 경고 비활성화 (개발 중)
process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true'

let mainWindow: BrowserWindow | null = null

// Kill backend server function
function killBackendServer() {
  try {
    console.log('[Electron] Killing backend server on port 28173...')
    if (process.platform === 'win32') {
      // Windows
      execSync('FOR /F "tokens=5" %P IN (\'netstat -ano ^| findstr :28173 ^| findstr LISTENING\') DO taskkill /PID %P /F', {
        shell: 'cmd.exe',
        stdio: 'ignore'
      })
    } else {
      // macOS/Linux
      execSync('lsof -ti:28173 | xargs kill -9', { stdio: 'ignore' })
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
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
    backgroundColor: '#f3f4f6',
    show: false,
  })

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

// 앱이 준비되면 윈도우 생성
app.whenReady().then(async () => {
  // Wait for backend server to be ready before initializing database
  const backendReady = await waitForBackend()

  if (backendReady) {
    // Initialize database
    initializeDatabase()
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
      const response = await fetch('http://localhost:28173/health')
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
    const query = `
      SELECT
        mcpTag,
        producer,
        tool,
        tool_title,
        tool_description,
        tool_parameter,
        annotations,
        created_at
      FROM mcpl
      ORDER BY mcpTag, created_at
    `
    console.log(`[DB] Executing query: ${query.trim()}`)

    const rows = db.prepare(query).all() as any[]
    console.log(`[DB] Query returned ${rows.length} rows`)

    // Group tools by mcpTag (server name)
    const serverMap = new Map()

    rows.forEach(row => {
      const serverName = row.mcpTag

      if (!serverMap.has(serverName)) {
        serverMap.set(serverName, {
          id: serverMap.size + 1,
          name: serverName,
          type: row.producer || 'local',
          icon: '🔧',
          tools: []
        })
        console.log(`[DB] Added new server: ${serverName}`)
      }

      const server = serverMap.get(serverName)
      server.tools.push({
        name: row.tool,
        description: row.tool_description || ''
      })
    })

    const servers = Array.from(serverMap.values())
    console.log(`[DB] Returning ${servers.length} servers`)
    servers.forEach(s => console.log(`[DB]   - ${s.name}: ${s.tools.length} tools`))

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
    const query = `
      SELECT
        id,
        ts,
        producer,
        pid,
        pname,
        event_type,
        mcpTag,
        data,
        created_at
      FROM raw_events
      WHERE mcpTag = ? AND event_type = 'MCP'
      ORDER BY ts ASC
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

      // Calculate maliciousScore (placeholder - should come from analysis)
      const maliciousScore = 0

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
