import { ChevronLeft, ChevronRight, MessageSquare, Settings } from 'lucide-react'

function LeftSidebar({ isOpen, setIsOpen, servers, selectedServer, setSelectedServer }) {
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
        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center gap-2 mt-12">
          <MessageSquare size={24} className="text-gray-600" />
          <h2 className="font-semibold text-gray-800">MCP Servers</h2>
        </div>

        {/* Server List */}
        <div className="flex-1 overflow-y-auto">
          {servers.map((server) => (
            <button
              key={server.id}
              onClick={() => setSelectedServer(server)}
              className={`w-full px-4 py-3 text-left hover:bg-gray-100 transition-colors flex items-center gap-3 ${
                selectedServer?.id === server.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
              }`}
            >
              <span className="text-xl">{server.icon}</span>
              <span className="text-sm text-gray-700">{server.name}</span>
            </button>
          ))}
        </div>

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
