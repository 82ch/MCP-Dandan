const express = require('express')
const cors = require('cors')
const Database = require('better-sqlite3')
const path = require('path')
const { mcpServers, chatMessagesByServer } = require('./mockData')

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

// API Routes

// Get all MCP servers
app.get('/api/servers', (req, res) => {
  res.json(mcpServers)
})

// Get a single server by ID
app.get('/api/servers/:id', (req, res) => {
  const serverId = parseInt(req.params.id)
  const server = mcpServers.find(s => s.id === serverId)

  if (!server) {
    return res.status(404).json({ error: 'Server not found' })
  }

  res.json(server)
})

// Get messages for a specific server
app.get('/api/servers/:id/messages', (req, res) => {
  const serverId = parseInt(req.params.id)
  const messages = chatMessagesByServer[serverId] || []
  res.json(messages)
})

// Get all messages (for all servers)
app.get('/api/messages', (req, res) => {
  res.json(chatMessagesByServer)
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