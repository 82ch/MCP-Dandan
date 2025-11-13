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
