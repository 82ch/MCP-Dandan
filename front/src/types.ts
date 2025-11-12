// TypeScript 타입 정의

export interface MCPTool {
  name: string
  description: string
}

export interface MCPServer {
  id: string | number
  name: string
  type: string
  icon: string
  appName?: string
  tools: MCPTool[]
}

export interface ChatMessage {
  id: string | number
  content: string
  timestamp: string
  sender: 'user' | 'assistant' | 'client' | 'server'
  serverId?: string | number
  type?: string
  maliciousScore?: number
  data?: {
    message?: {
      id?: string | number
      params?: {
        name?: string
        arguments?: Record<string, any>
        [key: string]: any
      }
      [key: string]: any
    }
    [key: string]: any
  }
}

export interface ServerInfo {
  name: string
  type: string
  tools: MCPTool[]
}

export interface DetectedEvent {
  serverName: string
  threatType: string
  severity: 'low' | 'mid' | 'high'
  severityColor: string
  description: string
  lastSeen: string
  engineResultId: string | number
}

export interface ThreatStats {
  detections: number
  affectedServers: number
}

export interface TimelineData {
  date: string
  count: number
}

export interface TopServer {
  name: string
  count: number
}
