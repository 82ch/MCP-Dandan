import { Settings } from 'lucide-react'

function RightChatPanel({ messages, selectedMessage, setSelectedMessage }) {
  if (!messages || messages.length === 0) {
    return (
      <div className="h-full bg-white flex flex-col">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Chat</h2>
          <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
            <Settings size={20} className="text-gray-600" />
          </button>
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
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="font-semibold text-gray-800">Chat</h2>
        <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <Settings size={20} className="text-gray-600" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((message) => {
          const isToolCall = message.type === 'tool_call'
          const isSelected = selectedMessage?.id === message.id

          return (
            <div
              key={message.id}
              onClick={() => setSelectedMessage(message)}
              className={`flex ${isToolCall ? 'justify-start' : 'justify-end'} cursor-pointer`}
            >
              <div className="flex flex-col items-end max-w-[80%]">
                {/* Chat Bubble */}
                <div
                  className={`relative bg-gray-200 rounded-2xl px-4 py-3 ${
                    isSelected ? 'ring-2 ring-blue-400' : ''
                  }`}
                  style={{
                    borderBottomLeftRadius: isToolCall ? '4px' : '16px',
                    borderBottomRightRadius: isToolCall ? '16px' : '4px',
                  }}
                >
                  <div className="font-mono text-sm text-gray-900">
                    {isToolCall ? message.data.tool : message.data.result}
                  </div>
                </div>

                {/* Timestamp with dot indicator */}
                <div className="flex items-center gap-1 mt-1 px-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      isToolCall ? 'bg-green-500' :
                      message.data.status === 'success' ? 'bg-green-500' : 'bg-red-500'
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
