import { useState, useRef, useEffect } from 'react'
import LeftSidebar from './components/LeftSidebar'
import MiddleTopPanel from './components/MiddleTopPanel'
import MiddleBottomPanel from './components/MiddleBottomPanel'
import RightChatPanel from './components/RightChatPanel'
import Dashboard from './components/Dashboard'

const API_BASE_URL = 'http://localhost:3001/api'

function App() {
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true)
  const [selectedServer, setSelectedServer] = useState(null)
  const [selectedMessage, setSelectedMessage] = useState(null)

  // Data from backend
  const [mcpServers, setMcpServers] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [loading, setLoading] = useState(true)

  // Resizable states
  const [middleTopHeight, setMiddleTopHeight] = useState(50) // percentage
  const [rightPanelWidth, setRightPanelWidth] = useState(33) // percentage

  const isDraggingVertical = useRef(false)
  const isDraggingHorizontal = useRef(false)

  // Fetch servers on mount
  useEffect(() => {
    fetchServers()
  }, [])

  // Fetch messages when server is selected
  useEffect(() => {
    if (selectedServer) {
      fetchMessages(selectedServer.id)
    } else {
      setChatMessages([])
    }
  }, [selectedServer])

  const fetchServers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/servers`)
      const data = await response.json()
      setMcpServers(data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching servers:', error)
      setLoading(false)
    }
  }

  const fetchMessages = async (serverId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/servers/${serverId}/messages`)
      const data = await response.json()
      setChatMessages(data)
    } catch (error) {
      console.error('Error fetching messages:', error)
      setChatMessages([])
    }
  }

  const serverInfo = selectedServer ? {
    name: selectedServer.name,
    type: selectedServer.type,
    tools: selectedServer.tools
  } : null

  // Handle vertical resize (middle panels)
  const handleVerticalMouseDown = () => {
    isDraggingVertical.current = true
  }

  const handleVerticalMouseMove = (e) => {
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

  const handleHorizontalMouseMove = (e) => {
    if (!isDraggingHorizontal.current) return

    const windowWidth = window.innerWidth
    const newWidth = ((windowWidth - e.clientX) / windowWidth) * 100

    if (newWidth > 20 && newWidth < 60) {
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
          <Dashboard setSelectedServer={setSelectedServer} servers={mcpServers} />
        </div>
      ) : (
        <>
          {/* Middle Section */}
          <div
            className="flex-1 flex flex-col"
            style={{ width: `${100 - rightPanelWidth}%` }}
            onMouseMove={handleVerticalMouseMove}
            onMouseUp={handleVerticalMouseUp}
          >
            {/* Middle Top Panel */}
            <div
              className="border-b border-gray-300 relative"
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
            <div style={{ height: `${100 - middleTopHeight}%` }}>
              <MiddleBottomPanel selectedMessage={selectedMessage} />
            </div>
          </div>

          {/* Horizontal Resize Handle */}
          <div
            className="w-1 bg-gray-300 hover:bg-blue-400 cursor-ew-resize transition-colors"
            onMouseDown={handleHorizontalMouseDown}
          />

          {/* Right Chat Panel */}
          <div
            className="border-l border-gray-300"
            style={{ width: `${rightPanelWidth}%` }}
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
