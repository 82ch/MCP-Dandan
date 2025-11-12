import { ChevronLeft, ChevronRight, MessageSquare, Settings, LayoutDashboard, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import type { MCPServer } from '../types'

interface LeftSidebarProps {
  isOpen: boolean
  setIsOpen: (isOpen: boolean) => void
  servers: MCPServer[]
  selectedServer: MCPServer | null
  setSelectedServer: (server: MCPServer | null) => void
}

function LeftSidebar({ isOpen, setIsOpen, servers, selectedServer, setSelectedServer }: LeftSidebarProps) {
  const [isServersExpanded, setIsServersExpanded] = useState<boolean>(true)

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow-md hover:bg-gray-100 transition-colors"
      >
        {isOpen ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
      </button>

      {/* Sidebar */}
      <div
        className={`bg-white border-r border-gray-300 transition-all duration-300 flex flex-col ${
          isOpen ? 'w-64' : 'w-0'
        } overflow-hidden`}
      >
        {/* Dashboard Button */}
        <div className="p-4 border-b border-gray-200 mt-12">
          <button
            onClick={() => setSelectedServer(null)}
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

        {/* Server List */}
        {isServersExpanded && (
          <div className="flex-1 overflow-y-auto transition-all duration-300">
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
                <div className="flex flex-col">
                  <span className="text-sm text-gray-700 font-medium">{server.name}</span>
                  {server.appName && (
                    <span className="text-xs text-gray-500">{server.appName}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1"></div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200">
          <button className="w-full flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            <Settings size={20} />
            <span className="text-sm">Settings</span>
          </button>
        </div>
      </div>
    </>
  )
}

export default LeftSidebar
