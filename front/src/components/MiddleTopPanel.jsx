function MiddleTopPanel({ serverInfo }) {
  if (!serverInfo) {
    return (
      <div className="h-full bg-white flex items-center justify-center text-gray-500">
        <p>Select a server to view details</p>
      </div>
    )
  }

  return (
    <div className="h-full bg-white overflow-y-auto">
      <div className="p-6">
        {/* Server Name */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-1">Server name</h3>
          <p className="text-lg font-medium text-gray-800">{serverInfo.name}</p>
        </div>

        {/* Server Type */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-1">Server type</h3>
          <p className="text-gray-700">{serverInfo.type}</p>
        </div>

        {/* Tools List */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 mb-3">Available Tools</h3>
          <div className="space-y-4">
            {serverInfo.tools.map((tool, index) => (
              <div key={index} className="border-l-4 border-blue-400 pl-4 py-2">
                <h4 className="font-mono text-sm font-semibold text-gray-800 mb-1">
                  {tool.name}
                </h4>
                <p className="text-xs text-gray-600 leading-relaxed">
                  {tool.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MiddleTopPanel
