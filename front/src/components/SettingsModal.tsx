import { useState, useEffect } from 'react'
import { X, Save } from 'lucide-react'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

interface ConfigData {
  Engine: {
    sensitive_file_enabled: boolean
    tools_poisoning_enabled: boolean
    command_injection_enabled: boolean
    file_system_exposure_enabled: boolean
  }
  Log: {
    log_dir: string
    max_log_file_size_mb: number
    max_log_files: number
  }
}

function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [config, setConfig] = useState<ConfigData | null>(null)
  const [apiKey, setApiKey] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadConfig()
    }
  }, [isOpen])

  const loadConfig = async () => {
    setLoading(true)
    setError(null)
    try {
      const [configData, envData] = await Promise.all([
        window.electronAPI.getConfig(),
        window.electronAPI.getEnv()
      ])
      setConfig(configData)
      setApiKey(envData.MISTRAL_API_KEY || '')
    } catch (err) {
      setError('Failed to load configuration')
      console.error('Error loading config:', err)
    } finally {
      setLoading(false)
    }
  }

  const saveConfig = async () => {
    if (!config) return

    setSaving(true)
    setError(null)
    try {
      await Promise.all([
        window.electronAPI.saveConfig(config),
        window.electronAPI.saveEnv({ MISTRAL_API_KEY: apiKey })
      ])
      onClose()
      alert('Please restart the program for the changes to take effect.')
    } catch (err) {
      setError('Failed to save configuration')
      console.error('Error saving config:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleEngineToggle = (key: keyof ConfigData['Engine']) => {
    if (!config) return
    setConfig({
      ...config,
      Engine: {
        ...config.Engine,
        [key]: !config.Engine[key]
      }
    })
  }

  const handleLogChange = (key: keyof ConfigData['Log'], value: string | number) => {
    if (!config) return
    setConfig({
      ...config,
      Log: {
        ...config.Log,
        [key]: value
      }
    })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 backdrop-blur-sm bg-white/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Settings</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : error ? (
            <div className="text-red-500 text-center py-4">{error}</div>
          ) : config ? (
            <div className="space-y-6">
              {/* Engine Section */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Detection Engines</h3>
                <div className="space-y-3">
                  <label className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Sensitive File Detection</span>
                    <input
                      type="checkbox"
                      checked={config.Engine.sensitive_file_enabled}
                      onChange={() => handleEngineToggle('sensitive_file_enabled')}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Tools Poisoning Detection</span>
                    <input
                      type="checkbox"
                      checked={config.Engine.tools_poisoning_enabled}
                      onChange={() => handleEngineToggle('tools_poisoning_enabled')}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Command Injection Detection</span>
                    <input
                      type="checkbox"
                      checked={config.Engine.command_injection_enabled}
                      onChange={() => handleEngineToggle('command_injection_enabled')}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">File System Exposure Detection</span>
                    <input
                      type="checkbox"
                      checked={config.Engine.file_system_exposure_enabled}
                      onChange={() => handleEngineToggle('file_system_exposure_enabled')}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </label>
                </div>
              </div>

              {/* Log Section */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Log Settings</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Log Directory</label>
                    <input
                      type="text"
                      value={config.Log.log_dir}
                      onChange={(e) => handleLogChange('log_dir', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Max Log File Size (MB)</label>
                    <input
                      type="number"
                      value={config.Log.max_log_file_size_mb}
                      onChange={(e) => handleLogChange('max_log_file_size_mb', parseInt(e.target.value) || 0)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Max Log Files</label>
                    <input
                      type="number"
                      value={config.Log.max_log_files}
                      onChange={(e) => handleLogChange('max_log_files', parseInt(e.target.value) || 0)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* API Key Section */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">API Keys</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Mistral API Key</label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter your Mistral API key"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={saveConfig}
            disabled={saving || !config}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save size={16} />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SettingsModal
