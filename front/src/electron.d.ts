// Electron API 타입 정의

interface ElectronAPI {
  ping: () => Promise<string>
  getAppInfo: () => Promise<{
    version: string
    name: string
    platform: string
  }>
  getServers: () => Promise<any[]>
  getServerMessages: (serverId: number) => Promise<any[]>
  getEngineResults: () => Promise<any[]>
  getEngineResultsByEvent: (rawEventId: number) => Promise<any[]>
  onWebSocketUpdate: (callback: (message: any) => void) => () => void
  sendBlockingDecision: (requestId: string, decision: 'allow' | 'block') => Promise<void>
  getBlockingData: () => Promise<any>
  closeBlockingWindow: () => Promise<void>
  resizeBlockingWindow: (width: number, height: number) => Promise<void>
  updateToolSafety: (mcpTag: string, toolName: string, safety: number) => Promise<boolean>
  getConfig: () => Promise<any>
  saveConfig: (config: any) => Promise<boolean>
  getEnv: () => Promise<any>
  saveEnv: (env: any) => Promise<boolean>
  restartApp: () => Promise<void>
  exportDatabase: () => Promise<{ success: boolean; filePath?: string; canceled?: boolean; error?: string }>
  deleteDatabase: () => Promise<{ success: boolean; message?: string; error?: string }>
  platform: string
  versions: {
    node: string
    chrome: string
    electron: string
  }
}

interface Window {
  electronAPI: ElectronAPI
}
