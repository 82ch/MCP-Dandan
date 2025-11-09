const express = require('express')
const cors = require('cors')
const Database = require('better-sqlite3')
const path = require('path')

const app = express()
const PORT = 3001

// Initialize SQLite database
// Use DB_PATH from environment variable (for Docker) or default path (for local dev)
const dbPath = process.env.DB_PATH || path.join(__dirname, '..', '82ch.db')
console.log(`Using database at: ${dbPath}`)

// Better-sqlite3 options for read-only access with WAL mode support
const db = new Database(dbPath, {
  readonly: true,
  fileMustExist: true,
  timeout: 5000  // 5 second timeout for lock acquisition
})

// Set pragmas for better concurrency handling
try {
  // These pragmas help with concurrent read access
  db.pragma('query_only = ON')  // Extra safety for read-only mode
  const journalMode = db.pragma('journal_mode', { simple: true })
  console.log(`Database journal mode: ${journalMode}`)
} catch (error) {
  console.error('Error setting up database:', error.message)
}

// Middleware
app.use(cors())
app.use(express.json())

// Helper function to build mcpServers from database
function getMcpServersFromDB() {
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
    const rows = db.prepare(query).all()

    // Group tools by mcpTag (server name)
    const serverMap = new Map()

    rows.forEach(row => {
      const serverName = row.mcpTag

      if (!serverMap.has(serverName)) {
        serverMap.set(serverName, {
          id: serverMap.size + 1,
          name: serverName,
          type: row.producer || 'local',
          tools: []
        })
      }

      const server = serverMap.get(serverName)
      server.tools.push({
        name: row.tool,
        description: row.tool_description || ''
      })
    })

    return Array.from(serverMap.values())
  } catch (error) {
    console.error('Error fetching MCP servers from database:', error)
    return []
  }
}

// API Routes

// Get all MCP servers
app.get('/api/servers', (req, res) => {
  const mcpServers = getMcpServersFromDB()
  res.json(mcpServers)
})

// Get a single server by ID
app.get('/api/servers/:id', (req, res) => {
  const serverId = parseInt(req.params.id)
  const mcpServers = getMcpServersFromDB()
  const server = mcpServers.find(s => s.id === serverId)

  if (!server) {
    return res.status(404).json({ error: 'Server not found' })
  }

  res.json(server)
})

// Get messages for a specific server
app.get('/api/servers/:id/messages', (req, res) => {
  try {
    const serverId = parseInt(req.params.id)

    // First, get the server name from mcpServers
    const mcpServers = getMcpServersFromDB()
    const server = mcpServers.find(s => s.id === serverId)

    if (!server) {
      return res.status(404).json({ error: 'Server not found' })
    }

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

    const rows = db.prepare(query).all(server.name)

    // Transform database rows to match frontend expected format
    const messages = rows.map(row => {
      let parsedData = {}
      try {
        parsedData = typeof row.data === 'string' ? JSON.parse(row.data) : row.data
      } catch (e) {
        console.error('Error parsing data for event:', row.id, e)
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

      // Convert ts (nanoseconds) to readable timestamp
      // ts is in nanoseconds, convert to milliseconds by dividing by 1,000,000
      const tsInMs = Math.floor(row.ts / 1000000)
      const timestamp = new Date(tsInMs).toISOString()

      return {
        id: row.id,
        type: messageType,
        sender: sender,
        timestamp: timestamp,
        maliciousScore: maliciousScore,
        data: {
          message: parsedData.message || parsedData
        }
      }
    })

    res.json(messages)
  } catch (error) {
    console.error('Error fetching messages:', error)
    res.status(500).json({ error: 'Failed to fetch messages' })
  }
})

// Get all messages (for all servers)
app.get('/api/messages', (req, res) => {
  try {
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
      WHERE event_type = 'MCP'
      ORDER BY ts ASC
    `

    const rows = db.prepare(query).all()

    // Transform database rows to match frontend expected format
    const messages = rows.map(row => {
      let parsedData = {}
      try {
        parsedData = typeof row.data === 'string' ? JSON.parse(row.data) : row.data
      } catch (e) {
        console.error('Error parsing data for event:', row.id, e)
        parsedData = { raw: row.data }
      }

      // Determine message type from data
      let messageType = row.event_type
      if (parsedData.message && parsedData.message.method) {
        messageType = parsedData.message.method
      }

      // Determine sender from data (task field: send = client, recv = server)
      let sender = 'unknown'
      if (parsedData.task === 'send') {
        sender = 'client'
      } else if (parsedData.task === 'recv') {
        sender = 'server'
      }

      // Calculate maliciousScore (placeholder - should come from analysis)
      const maliciousScore = 0

      // Convert ts (nanoseconds) to readable timestamp
      // ts is in nanoseconds, convert to milliseconds by dividing by 1,000,000
      const tsInMs = Math.floor(row.ts / 1000000)
      const timestamp = new Date(tsInMs).toISOString()

      return {
        id: row.id,
        type: messageType,
        sender: sender,
        timestamp: timestamp,
        maliciousScore: maliciousScore,
        mcpTag: row.mcpTag,
        data: {
          message: parsedData.message || parsedData
        }
      }
    })

    res.json(messages)
  } catch (error) {
    console.error('Error fetching all messages:', error)
    res.status(500).json({ error: 'Failed to fetch all messages' })
  }
})

// Get all engine results (for Dashboard Detected section)
app.get('/api/engine-results', (req, res) => {
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
    const results = db.prepare(query).all()
    res.json(results)
  } catch (error) {
    console.error('Error fetching engine results:', error)
    res.status(500).json({ error: 'Failed to fetch engine results' })
  }
})

app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`)
})