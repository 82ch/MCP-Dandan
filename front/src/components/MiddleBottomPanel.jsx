function MiddleBottomPanel({ selectedMessage }) {
  if (!selectedMessage) {
    return (
      <div className="h-full bg-white flex items-center justify-center text-gray-500">
        <p>Select a message to view details</p>
      </div>
    )
  }

  return (
    <div className="h-full bg-white overflow-y-auto">
      <div className="p-6">
        {/* Tool Name */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-2">tool name</h3>
          <p className="text-lg font-mono font-medium text-gray-800">
            {selectedMessage.data.tool || selectedMessage.data.result}
          </p>
        </div>

        {/* Parameters */}
        {selectedMessage.data.params && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-500 mb-2">Parameters</h3>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              {Object.entries(selectedMessage.data.params).map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <span className="font-mono text-sm text-gray-600">{key}:</span>
                  <input
                    type="text"
                    value={value}
                    readOnly
                    className="flex-1 bg-white border border-gray-300 rounded px-3 py-1 text-sm text-gray-700"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Malicious Detect */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-2">Malicious Detect</h3>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Score:</span>
              <span className="font-mono text-lg font-semibold text-gray-800">
                {selectedMessage.maliciousScore || '악성 점수'}
              </span>
            </div>
            <div className="mt-3 bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-500 h-full transition-all"
                style={{ width: `${(selectedMessage.maliciousScore || 0) * 10}%` }}
              />
            </div>
          </div>
        </div>

        {/* Analysis Result */}
        {selectedMessage.data.status && (
          <div>
            <h3 className="text-sm font-semibold text-gray-500 mb-2">Analysis Result</h3>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-sm text-green-800">
                Status: <span className="font-semibold">{selectedMessage.data.status}</span>
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MiddleBottomPanel
