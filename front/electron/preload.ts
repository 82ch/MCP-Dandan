import { contextBridge, ipcRenderer } from 'electron'

// Electron API를 안전하게 노출
contextBridge.exposeInMainWorld('electronAPI', {
  // IPC 통신
  ping: () => ipcRenderer.invoke('ping'),
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),

  // Database API
  getServers: () => ipcRenderer.invoke('api:servers'),
  getServerMessages: (serverId: number) => ipcRenderer.invoke('api:servers:messages', serverId),
  getEngineResults: () => ipcRenderer.invoke('api:engine-results'),
  getEngineResultsByEvent: (rawEventId: number) => ipcRenderer.invoke('api:engine-results:by-event', rawEventId),

  // WebSocket events - subscribe to real-time updates
  onWebSocketUpdate: (callback: (message: any) => void) => {
    const subscription = (_event: any, message: any) => callback(message)
    ipcRenderer.on('websocket:update', subscription)

    // Return unsubscribe function
    return () => {
      ipcRenderer.removeListener('websocket:update', subscription)
    }
  },

  // Blocking decision - send user's decision back to server
  sendBlockingDecision: (requestId: string, decision: 'allow' | 'block') =>
    ipcRenderer.invoke('blocking:decision', requestId, decision),

  // Blocking window APIs
  getBlockingData: () => ipcRenderer.invoke('blocking:get-data'),
  closeBlockingWindow: () => ipcRenderer.invoke('blocking:close'),
  resizeBlockingWindow: (width: number, height: number) => ipcRenderer.invoke('blocking:resize', width, height),

  // Config APIs
  getConfig: () => ipcRenderer.invoke('config:get'),
  saveConfig: (config: any) => ipcRenderer.invoke('config:save', config),

  // Env APIs
  getEnv: () => ipcRenderer.invoke('env:get'),
  saveEnv: (env: any) => ipcRenderer.invoke('env:save', env),

  // App control
  restartApp: () => ipcRenderer.invoke('app:restart'),

  // 필요에 따라 추가 API 노출
  platform: process.platform,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron,
  },
})

// TypeScript 타입 정의를 위한 전역 인터페이스
declare global {
  interface Window {
    electronAPI: {
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
      getConfig: () => Promise<any>
      saveConfig: (config: any) => Promise<boolean>
      getEnv: () => Promise<any>
      saveEnv: (env: any) => Promise<boolean>
      restartApp: () => Promise<void>
      platform: string
      versions: {
        node: string
        chrome: string
        electron: string
      }
    }
  }
}

export {}
