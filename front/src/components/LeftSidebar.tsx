import { ChevronLeft, ChevronRight, MessageSquare, Settings, LayoutDashboard, ChevronDown, Clock, AlertTriangle, HelpCircle } from 'lucide-react'
import { useState } from 'react'
import type { MCPServer } from '../types'
import SettingsModal from './SettingsModal'

interface LeftSidebarProps {
  isOpen: boolean
  setIsOpen: (isOpen: boolean) => void
  servers: MCPServer[]
  selectedServer: MCPServer | null
  setSelectedServer: (server: MCPServer | null) => void
  onStartTutorial?: () => void
}

function LeftSidebar({ isOpen, setIsOpen, servers, selectedServer, setSelectedServer, onStartTutorial }: LeftSidebarProps) {
  const [isServersExpanded, setIsServersExpanded] = useState<boolean>(true)
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false)

  return (
    <>
      {/* Toggle Button - 항상 표시 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow-md hover:bg-gray-100 transition-colors"
      >
        {isOpen ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
      </button>

      {/* Overlay for mobile - 사이드바가 열렸을 때 배경 클릭하면 닫힘 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`bg-white border-r border-gray-300 transition-all duration-300 flex flex-col ${
          isOpen ? 'w-64' : 'w-0'
        } overflow-hidden shrink-0 relative z-40 md:relative md:z-auto ${
          isOpen ? 'md:static fixed left-0 top-0 bottom-0' : ''
        }`}
      >
        {/* Dashboard Button */}
        <div className="p-4 border-b border-gray-200 mt-12">
          <button
            onClick={() => setSelectedServer(null)}
            data-tutorial="dashboard-btn"
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              selectedServer === null ? 'bg-blue-50 text-blue-600 font-bold' : 'text-gray-700 hover:bg-gray-100 font-bold'
            }`}
          >
            <LayoutDashboard size={24} />
            <span className="text-base">Dashboard</span>
          </button>
        </div>

        {/* Header */}
        <button
          onClick={() => setIsServersExpanded(!isServersExpanded)}
          className="p-4 border-b border-gray-200 flex items-center justify-between hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <MessageSquare size={20} className="text-gray-600" />
            <h2 className="text-xs text-gray-600">MCP Servers</h2>
          </div>
          <ChevronDown
            size={16}
            className={`text-gray-600 transition-transform ${isServersExpanded ? 'rotate-0' : '-rotate-90'}`}
          />
        </button>

        {/* Server List with Spacer */}
        <div className="flex-1 overflow-y-auto transition-all duration-300" data-tutorial="server-list">
          {isServersExpanded && (
            <>
              {servers.map((server) => (
                <button
                  key={server.id}
                  onClick={() => setSelectedServer(server)}
                  className={`w-full pl-8 pr-4 py-3 text-left hover:bg-gray-100 transition-colors flex items-center gap-3 ${
                    selectedServer?.id === server.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <img
                    src={`/logos/${server.icon}`}
                    alt={server.appName || server.name}
                    className="w-6 h-6 rounded object-contain"
                    onError={(e) => {
                      // Fallback to default icon if image fails to load
                      e.currentTarget.src = '/logos/default.svg'
                    }}
                  />
                  <div className="flex flex-col flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-700 font-medium">{server.name}</span>
                      {/* 검사 중 아이콘 (회전하는 시계) */}
                      {server.isChecking && (
                        <Clock size={14} className="text-gray-500 animate-spin" />
                      )}
                      {/* 조치필요 아이콘 (빨강) */}
                      {server.hasDanger && (
                        <AlertTriangle size={14} className="text-red-500" />
                      )}
                      {/* 조치권장 아이콘 (주황) */}
                      {server.hasWarning && !server.hasDanger && (
                        <AlertTriangle size={14} className="text-orange-400" />
                      )}
                    </div>
                    {server.appName && (
                      <span className="text-xs text-gray-500">{server.appName}</span>
                    )}
                  </div>
                </button>
              ))}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 space-y-1">
          <button
            onClick={onStartTutorial}
            data-tutorial="settings-btn"
            className="w-full flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <HelpCircle size={20} />
            <span className="text-sm">Tutorial</span>
          </button>
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="w-full flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Settings size={20} />
            <span className="text-sm">Settings</span>
          </button>
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  )
}

export default LeftSidebar
