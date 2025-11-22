import { useState, useRef, useEffect, useCallback } from 'react'
import LeftSidebar from './components/LeftSidebar'
import MiddleTopPanel from './components/MiddleTopPanel'
import MiddleBottomPanel from './components/MiddleBottomPanel'
import RightChatPanel from './components/RightChatPanel'
import Dashboard from './components/Dashboard'
import type { MCPServer, ChatMessage } from './types'

function App() {
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState<boolean>(true)
  const [selectedServer, setSelectedServer] = useState<MCPServer | null>(null)
  const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null)
  const [pendingMessageId, setPendingMessageId] = useState<string | number | null>(null)

  // Data from backend
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState<boolean>(true)

  // Resizable states
  const [middleTopHeight, setMiddleTopHeight] = useState(50) // percentage
  const [rightPanelWidth, setRightPanelWidth] = useState(400) // pixels instead of percentage

  const isDraggingVertical = useRef(false)
  const isDraggingHorizontal = useRef(false)

  // Memoize fetch functions to avoid recreating on every render
  const fetchServers = useCallback(async () => {
    try {
      const data = await window.electronAPI.getServers()
      setMcpServers(data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching servers:', error)
      setLoading(false)
    }
  }, [])

  const fetchMessages = useCallback(async (serverId: string | number) => {
    try {
      const data = await window.electronAPI.getServerMessages(Number(serverId))
      setChatMessages(data)
    } catch (error) {
      console.error('Error fetching messages:', error)
      setChatMessages([])
    }
  }, [])

  // Fetch servers on mount
  useEffect(() => {
    fetchServers()
  }, [fetchServers])

  // Subscribe to WebSocket updates for real-time data
  useEffect(() => {
    const unsubscribe = window.electronAPI.onWebSocketUpdate((message: any) => {
      console.log('[App] WebSocket update received:', message.type)

      switch (message.type) {
        case 'server_update':
          // Refresh server list when servers change
          console.log('[App] Refreshing servers due to server_update')
          fetchServers()
          break

        case 'message_update':
          // Refresh messages if the current server matches
          console.log('[App] Message update for:', message.data.server_name)
          if (selectedServer && message.data.server_name === selectedServer.name) {
            console.log('[App] Refreshing messages for current server')
            fetchMessages(selectedServer.id)
          }
          // Also refresh servers to update indicators
          fetchServers()
          break

        case 'detection_result':
          // Refresh both servers and messages to update malicious scores
          console.log('[App] Detection result received, refreshing all data')
          fetchServers()
          if (selectedServer) {
            fetchMessages(selectedServer.id)
          }
          break

        case 'reload_all':
          // Full reload of all data
          console.log('[App] Full reload requested')
          fetchServers()
          if (selectedServer) {
            fetchMessages(selectedServer.id)
          }
          break

        case 'connection':
          console.log('[App] WebSocket connection established')
          // Fetch initial data on connection
          fetchServers()
          break

        default:
          console.log('[App] Unknown WebSocket message type:', message.type)
      }
    })

    // Cleanup on unmount
    return () => {
      unsubscribe()
    }
  }, [selectedServer, fetchServers, fetchMessages])

  // Fetch messages when server is selected
  useEffect(() => {
    if (selectedServer) {
      fetchMessages(selectedServer.id)
      // Reset selected message when server changes
      setSelectedMessage(null)
    } else {
      setChatMessages([])
      setSelectedMessage(null)
    }
  }, [selectedServer])

  // Auto-select message when pendingMessageId is set and messages are loaded
  useEffect(() => {
    if (pendingMessageId !== null && chatMessages.length > 0) {
      const message = chatMessages.find(m => m.id === pendingMessageId)
      if (message) {
        setSelectedMessage(message)
        setPendingMessageId(null)
      }
    }
  }, [pendingMessageId, chatMessages])

  const serverInfo = selectedServer ? {
    name: selectedServer.name,
    type: selectedServer.type,
    tools: selectedServer.tools
  } : null

  // Handle vertical resize (middle panels)
  const handleVerticalMouseDown = () => {
    isDraggingVertical.current = true
  }

  const handleVerticalMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDraggingVertical.current) return

    const container = e.currentTarget
    const rect = container.getBoundingClientRect()
    const newHeight = ((e.clientY - rect.top) / rect.height) * 100

    if (newHeight > 20 && newHeight < 80) {
      setMiddleTopHeight(newHeight)
    }
  }

  const handleVerticalMouseUp = () => {
    isDraggingVertical.current = false
  }

  // Handle horizontal resize (right panel)
  const handleHorizontalMouseDown = () => {
    isDraggingHorizontal.current = true
  }

  const handleHorizontalMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDraggingHorizontal.current) return

    const windowWidth = window.innerWidth
    const newWidth = windowWidth - e.clientX

    // Min 300px, max 60% of window width
    const minWidth = 300
    const maxWidth = windowWidth * 0.6

    if (newWidth >= minWidth && newWidth <= maxWidth) {
      setRightPanelWidth(newWidth)
    }
  }

  const handleHorizontalMouseUp = () => {
    isDraggingHorizontal.current = false
  }

  if (loading) {
    return (
      <div className="flex h-screen bg-gray-100 items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading servers...</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex h-screen bg-gray-100"
      onMouseMove={handleHorizontalMouseMove}
      onMouseUp={handleHorizontalMouseUp}
    >
      {/* Left Sidebar */}
      <LeftSidebar
        isOpen={isLeftSidebarOpen}
        setIsOpen={setIsLeftSidebarOpen}
        servers={mcpServers}
        selectedServer={selectedServer}
        setSelectedServer={setSelectedServer}
      />

      {/* Main Content Area */}
      {selectedServer === null ? (
        /* Dashboard View */
        <div className="flex-1">
          <Dashboard
            setSelectedServer={setSelectedServer}
            servers={mcpServers}
            setSelectedMessageId={setPendingMessageId}
          />
        </div>
      ) : (
        <>
          {/* Middle Section */}
          <div
            className="flex-1 flex flex-col min-w-0"
            style={{ width: `calc(100% - ${rightPanelWidth}px)` }}
            onMouseMove={handleVerticalMouseMove}
            onMouseUp={handleVerticalMouseUp}
          >
            {/* Middle Top Panel */}
            <div
              className="border-b border-gray-300 relative min-h-0"
              style={{ height: `${middleTopHeight}%` }}
            >
              <MiddleTopPanel serverInfo={serverInfo} />

              {/* Vertical Resize Handle */}
              <div
                className="absolute bottom-0 left-0 right-0 h-1 bg-gray-300 hover:bg-blue-400 cursor-ns-resize transition-colors"
                onMouseDown={handleVerticalMouseDown}
              />
            </div>

            {/* Middle Bottom Panel */}
            <div className="min-h-0" style={{ height: `${100 - middleTopHeight}%` }}>
              <MiddleBottomPanel selectedMessage={selectedMessage} />
            </div>
          </div>

          {/* Horizontal Resize Handle */}
          <div
            className="w-1 bg-gray-300 hover:bg-blue-400 cursor-ew-resize transition-colors shrink-0"
            onMouseDown={handleHorizontalMouseDown}
          />

          {/* Right Chat Panel */}
          <div
            className="border-l border-gray-300 -shrink-0"
            style={{ width: `${rightPanelWidth}px`, minWidth: '300px', maxWidth: '60vw' }}
          >
            <RightChatPanel
              messages={chatMessages}
              selectedMessage={selectedMessage}
              setSelectedMessage={setSelectedMessage}
            />
          </div>
        </>
      )}
    </div>
  )
}

export default App
