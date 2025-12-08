import '@testing-library/jest-dom';
import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock Electron API
global.window = global.window || ({} as any);

(global.window as any).electronAPI = {
  ping: vi.fn().mockResolvedValue('pong'),
  getAppInfo: vi.fn().mockResolvedValue({
    version: '1.0.0',
    name: 'Test App',
    platform: 'test',
  }),
  getServers: vi.fn().mockResolvedValue([]),
  getServerMessages: vi.fn().mockResolvedValue([]),
  getEngineResults: vi.fn().mockResolvedValue([]),
  getEngineResultsByEvent: vi.fn().mockResolvedValue([]),
  onWebSocketUpdate: vi.fn().mockReturnValue(() => {}),
  sendBlockingDecision: vi.fn().mockResolvedValue(undefined),
  getBlockingData: vi.fn().mockResolvedValue(null),
  closeBlockingWindow: vi.fn().mockResolvedValue(undefined),
  resizeBlockingWindow: vi.fn().mockResolvedValue(undefined),
  getConfig: vi.fn().mockResolvedValue({}),
  saveConfig: vi.fn().mockResolvedValue(true),
  getEnv: vi.fn().mockResolvedValue({}),
  saveEnv: vi.fn().mockResolvedValue(true),
  restartApp: vi.fn().mockResolvedValue(undefined),
  platform: 'test',
  versions: {
    node: '18.0.0',
    chrome: '100.0.0',
    electron: '20.0.0',
  },
};
