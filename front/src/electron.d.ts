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
