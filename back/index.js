const express = require('express')
const cors = require('cors')

const app = express()
const PORT = 3001

app.use(cors())
app.use(express.json())

// Mock data for MCP Servers
const mcpServers = [
  {
    id: 1,
    name: 'filesystem',
    icon: '📁',
    type: 'File System Server',
    tools: [
      {
        name: 'read_file',
        description: 'Read the complete contents of a file as text. DEPRECATED: Use read_text_file instead.'
      },
      {
        name: 'read_text_file',
        description: 'Read the complete contents of a file from the file system as text. Handles various text file encodings and formats the content in a parsable way.'
      },
      {
        name: 'read_media_file',
        description: 'Read an image or audio file. Returns the base64 encoded data and MIME type.'
      },
      {
        name: 'file_search',
        description: 'Search for files using semantic and keyword-based search. Supports multiple search modes and filters.'
      }
    ]
  },
  {
    id: 2,
    name: 'Weather',
    icon: '🌤️',
    type: 'Weather API Server',
    tools: [
      {
        name: 'get_current_weather',
        description: 'Get the current weather for a specific location. Requires location parameter (city name or coordinates).'
      },
      {
        name: 'get_forecast',
        description: 'Get weather forecast for the next 7 days. Returns temperature, precipitation, and conditions.'
      },
      {
        name: 'get_alerts',
        description: 'Get weather alerts and warnings for a specific region.'
      }
    ]
  },
  {
    id: 3,
    name: 'NOTION',
    icon: '📝',
    type: 'Notion Integration Server',
    tools: [
      {
        name: 'create_page',
        description: 'Create a new page in a Notion database. Requires database_id and page content parameters.'
      },
      {
        name: 'update_page',
        description: 'Update an existing Notion page. Requires page_id and content to update.'
      },
      {
        name: 'search_pages',
        description: 'Search for pages in Notion workspace. Supports keyword search and filters.'
      },
      {
        name: 'get_database',
        description: 'Retrieve database schema and properties. Requires database_id parameter.'
      }
    ]
  },
  {
    id: 4,
    name: 'Gmail',
    icon: '📧',
    type: 'Gmail Integration Server',
    tools: [
      {
        name: 'send_email',
        description: 'Send an email through Gmail. Requires to, subject, and body parameters.'
      },
      {
        name: 'read_emails',
        description: 'Read emails from Gmail inbox. Supports filtering by date, sender, and labels.'
      },
      {
        name: 'search_emails',
        description: 'Search emails using Gmail search syntax.'
      }
    ]
  },
  {
    id: 5,
    name: 'malicious',
    icon: '⚠️',
    type: 'Security Analysis Server',
    tools: [
      {
        name: 'scan_file',
        description: 'Scan a file for malicious content. Returns threat level and detailed analysis.'
      },
      {
        name: 'check_url',
        description: 'Check if a URL is malicious or safe. Uses multiple security databases.'
      },
      {
        name: 'analyze_behavior',
        description: 'Analyze behavioral patterns to detect potential threats.'
      }
    ]
  }
]

// Mock data for chat messages by server
const chatMessagesByServer = {
  1: [ // filesystem
    {
      id: 1,
      type: 'tool_call',
      timestamp: '2/16',
      data: { tool: 'read_file', params: { path: '/home/user/document.txt' } },
      maliciousScore: 0
    },
    {
      id: 2,
      type: 'tool_response',
      timestamp: '2/16',
      data: { result: 'File content loaded successfully', status: 'success' }
    },
    {
      id: 3,
      type: 'tool_call',
      timestamp: '2/17',
      data: { tool: 'file_search', params: { path: 'C:\\Music', content: 'hello world' } },
      maliciousScore: 1
    },
    {
      id: 4,
      type: 'tool_response',
      timestamp: '2/17',
      data: { result: 'Found 5 matching files', status: 'success' }
    }
  ],
  2: [ // Weather
    {
      id: 1,
      type: 'tool_call',
      timestamp: '2/16',
      data: { tool: 'get_current_weather', params: { location: 'Seoul' } },
      maliciousScore: 0
    },
    {
      id: 2,
      type: 'tool_response',
      timestamp: '2/16',
      data: { result: 'Temperature: 15°C, Sunny', status: 'success' }
    },
    {
      id: 3,
      type: 'tool_call',
      timestamp: '2/17',
      data: { tool: 'get_forecast', params: { location: 'Seoul', days: 7 } },
      maliciousScore: 0
    },
    {
      id: 4,
      type: 'tool_response',
      timestamp: '2/17',
      data: { result: '7-day forecast retrieved', status: 'success' }
    }
  ],
  3: [ // NOTION
    {
      id: 1,
      type: 'tool_call',
      timestamp: '2/16',
      data: { tool: 'create_page', params: { database_id: 'abc123', title: 'New Task' } },
      maliciousScore: 0
    },
    {
      id: 2,
      type: 'tool_response',
      timestamp: '2/16',
      data: { result: 'Page created successfully', status: 'success' }
    },
    {
      id: 3,
      type: 'tool_call',
      timestamp: '2/17',
      data: { tool: 'search_pages', params: { query: 'meeting notes' } },
      maliciousScore: 0
    },
    {
      id: 4,
      type: 'tool_response',
      timestamp: '2/17',
      data: { result: 'Found 12 pages', status: 'success' }
    }
  ],
  4: [ // Gmail
    {
      id: 1,
      type: 'tool_call',
      timestamp: '2/16',
      data: { tool: 'send_email', params: { to: 'user@example.com', subject: 'Hello' } },
      maliciousScore: 0
    },
    {
      id: 2,
      type: 'tool_response',
      timestamp: '2/16',
      data: { result: 'Email sent successfully', status: 'success' }
    },
    {
      id: 3,
      type: 'tool_call',
      timestamp: '2/17',
      data: { tool: 'read_emails', params: { limit: 10 } },
      maliciousScore: 0
    },
    {
      id: 4,
      type: 'tool_response',
      timestamp: '2/17',
      data: { result: 'Retrieved 10 emails', status: 'success' }
    }
  ],
  5: [ // malicious
    {
      id: 1,
      type: 'tool_call',
      timestamp: '2/16',
      data: { tool: 'scan_file', params: { path: '/suspicious/file.exe' } },
      maliciousScore: 8
    },
    {
      id: 2,
      type: 'tool_response',
      timestamp: '2/16',
      data: { result: 'Threat detected: Trojan.Generic', status: 'error' }
    },
    {
      id: 3,
      type: 'tool_call',
      timestamp: '2/17',
      data: { tool: 'check_url', params: { url: 'http://malicious-site.com' } },
      maliciousScore: 9
    },
    {
      id: 4,
      type: 'tool_response',
      timestamp: '2/17',
      data: { result: 'URL flagged as phishing site', status: 'error' }
    }
  ]
}

// API Routes

// Get all MCP servers
app.get('/api/servers', (req, res) => {
  res.json(mcpServers)
})

// Get server by ID
app.get('/api/servers/:id', (req, res) => {
  const serverId = parseInt(req.params.id)
  const server = mcpServers.find(s => s.id === serverId)

  if (server) {
    res.json(server)
  } else {
    res.status(404).json({ error: 'Server not found' })
  }
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

app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`)
})
