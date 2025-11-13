import type { ChatMessage } from '../types'

interface RightChatPanelProps {
  messages: ChatMessage[]
  selectedMessage: ChatMessage | null
  setSelectedMessage: (message: ChatMessage | null) => void
}

function RightChatPanel({ messages, selectedMessage, setSelectedMessage }: RightChatPanelProps) {
  if (!messages || messages.length === 0) {
    return (
      <div className="h-full bg-white flex flex-col">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Chat</h2>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <p>Select a server to view messages</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full bg-white flex flex-col">
      {/* Header */}
      <div className="p-3 md:p-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
        <h2 className="font-semibold text-sm md:text-base text-gray-800">Chat</h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 md:p-6 space-y-3 md:space-y-4 min-h-0">
        {messages.map((message) => {
          // Client messages go LEFT, Server messages go RIGHT
          const isClientMessage = message.sender === 'client'
          const isSelected = selectedMessage?.id === message.id
          const isProxyEvent = message.event_type === 'Proxy'

          // Extract display text from message
          let displayText = message.type || 'Unknown'

          // For tools/call messages, show the tool name
          if (message.type === 'tools/call' && message.data?.message?.params?.name) {
            displayText = `${message.type}\n${message.data.message.params.name}`
          }

          // For server messages with id, find the corresponding client message
          if (!isClientMessage && message.data?.message?.id !== undefined) {
            const requestId = message.data.message.id
            // Find the most recent client message with matching id
            const clientMessage = messages
              .filter(m => m.sender === 'client' && m.data?.message?.id === requestId)
              .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0]

            if (clientMessage) {
              let clientText = clientMessage.type || 'Unknown'
              if (clientMessage.type === 'tools/call' && clientMessage.data?.message?.params?.name) {
                clientText = clientMessage.data.message.params.name
              }
              displayText = `${clientText} response`
            }
          }

          // Determine background color
          let bubbleColor = isClientMessage ? 'bg-blue-100' : 'bg-gray-200'
          if (isProxyEvent) {
            bubbleColor = 'bg-yellow-100'  // Proxy 이벤트는 노란색
          }

          return (
            <div
              key={message.id}
              onClick={() => setSelectedMessage(message)}
              className={`flex ${isClientMessage ? 'justify-start' : 'justify-end'} cursor-pointer`}
            >
              <div className={`flex flex-col ${isClientMessage ? 'items-start' : 'items-end'} max-w-[85%] md:max-w-[80%]`}>
                {/* Chat Bubble */}
                <div
                  className={`relative rounded-2xl px-3 py-2 md:px-4 md:py-3 ${
                    isSelected ? 'ring-2 ring-blue-400' : ''
                  } ${bubbleColor}`}
                  style={{
                    borderBottomLeftRadius: isClientMessage ? '4px' : '16px',
                    borderBottomRightRadius: isClientMessage ? '16px' : '4px',
                  }}
                >
                  <div className="font-mono text-sm text-gray-900 whitespace-pre-line">
                    {displayText}
                  </div>
                </div>

                {/* Timestamp with dot indicator */}
                <div className="flex items-center gap-1 mt-1 px-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      (message.maliciousScore ?? 0) > 5 ? 'bg-red-500' :
                      (message.maliciousScore ?? 0) > 2 ? 'bg-yellow-500' : 'bg-green-500'
                    }`}
                  />
                  <span className="text-xs text-gray-500 font-mono">{message.timestamp}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default RightChatPanel
