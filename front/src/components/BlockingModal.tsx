import { useState, useEffect } from 'react'

interface DetectionFinding {
  category: string
  pattern?: string
  matched_text?: string
  reason: string
  position?: [number, number]
  full_path?: string
}

interface DetectionResult {
  detector: string
  severity: string
  evaluation: number
  findings: DetectionFinding[]
  event_type: string
  analysis_text?: string
}

interface BlockingRequestData {
  request_id: string
  event_data: any
  detection_results: DetectionResult[]
  engine_name: string
  severity: string
  server_name: string
  tool_name: string
}

interface BlockingModalProps {
  blockingRequest: BlockingRequestData | null
  onDecision: (requestId: string, decision: 'allow' | 'block') => void
}

function BlockingModal({ blockingRequest, onDecision }: BlockingModalProps) {
  const [timeLeft, setTimeLeft] = useState(60)
  const [showDetails, setShowDetails] = useState(false)

  useEffect(() => {
    if (!blockingRequest) {
      setTimeLeft(60000)
      setShowDetails(false)
      return
    }

    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          onDecision(blockingRequest.request_id, 'block')
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [blockingRequest, onDecision])

  if (!blockingRequest) return null

  const { request_id, detection_results, engine_name, severity, server_name, tool_name, event_data } = blockingRequest
  const toolArgs = event_data?.data?.message?.params?.arguments || {}
  const toolCallReason = toolArgs?.tool_call_reason || ''

  // Remove tool_call_reason from toolArgs for display
  const displayArgs = { ...toolArgs }
  delete displayArgs.tool_call_reason

  // Simple view (default)
  if (!showDetails) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg shadow-2xl max-w-md w-full overflow-hidden flex flex-col animate-in fade-in zoom-in duration-200">
          {/* Header */}
          <div className="bg-gradient-to-r from-red-500 to-red-600 text-white px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white bg-opacity-20 rounded-lg">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-bold">Security Alert</h2>
                <p className="text-sm opacity-90">{timeLeft}s remaining</p>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            <div className="text-center mb-4">
              <div className="text-4xl mb-3">⚠️</div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">
                This MCP tool may be dangerous
              </h3>
              <p className="text-sm text-gray-600">
                <span className="font-semibold text-blue-600">{tool_name}</span> from <span className="font-semibold">{server_name}</span> has been flagged with <span className={`font-bold ${severity === 'high' ? 'text-red-600' : 'text-yellow-600'}`}>{severity.toUpperCase()}</span> severity.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="bg-gray-50 px-6 py-4 space-y-3 border-t">
            <div className="flex gap-3">
              <button
                onClick={() => onDecision(request_id, 'block')}
                className="flex-1 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-semibold py-2.5 px-4 rounded-lg transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
                Block
              </button>
              <button
                onClick={() => onDecision(request_id, 'allow')}
                className="flex-1 bg-white hover:bg-gray-100 text-gray-700 font-semibold py-2.5 px-4 rounded-lg transition-all border-2 border-gray-300 hover:border-gray-400 flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Allow
              </button>
            </div>
            <button
              onClick={() => setShowDetails(true)}
              className="w-full text-sm text-blue-600 hover:text-blue-800 font-medium py-2 transition-colors"
            >
              View Details →
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Detailed view
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 md:p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full h-full md:max-w-2xl md:max-h-[90vh] overflow-hidden flex flex-col animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="bg-gradient-to-r from-red-500 to-red-600 text-white px-3 py-2 md:px-4 md:py-3 shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 md:gap-3">
              <svg className="w-4 h-4 md:w-5 md:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <h2 className="text-xs md:text-sm font-bold leading-tight">Details</h2>
                <p className="text-[10px] md:text-xs opacity-90">{timeLeft}s</p>
              </div>
            </div>
            <button
              onClick={() => setShowDetails(false)}
              className="text-white hover:bg-white hover:bg-opacity-20 p-1 rounded transition-colors"
            >
              <svg className="w-4 h-4 md:w-5 md:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-2 md:p-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-1.5 md:gap-2 mb-3 md:mb-4">
            <div className="bg-gray-50 rounded p-1.5 md:p-2">
              <div className="text-[9px] md:text-xs text-gray-500">Server</div>
              <div className="font-medium text-[10px] md:text-sm truncate">{server_name}</div>
            </div>
            <div className="bg-gray-50 rounded p-1.5 md:p-2">
              <div className="text-[9px] md:text-xs text-gray-500">Tool</div>
              <div className="font-mono font-medium text-[10px] md:text-sm text-blue-600 truncate">{tool_name}</div>
            </div>
            <div className="bg-gray-50 rounded p-1.5 md:p-2">
              <div className="text-[9px] md:text-xs text-gray-500">Engine</div>
              <div className="font-medium text-[10px] md:text-sm">{engine_name}</div>
            </div>
            <div className="bg-gray-50 rounded p-1.5 md:p-2">
              <div className="text-[9px] md:text-xs text-gray-500">Severity</div>
              <div className={`font-bold text-[10px] md:text-sm ${severity === 'high' ? 'text-red-600' : 'text-yellow-600'}`}>
                {severity.toUpperCase()}
              </div>
            </div>
          </div>

          {/* MCP Tool Call Reason */}
          {toolCallReason && (
            <div className="mb-3 md:mb-4">
              <h3 className="text-[10px] md:text-xs font-semibold text-gray-700 mb-1.5 flex items-center gap-1">
                <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Reason
              </h3>
              <div className="bg-blue-50 border border-blue-200 rounded p-2 md:p-3">
                <p className="text-[10px] md:text-sm text-blue-900 leading-tight">{toolCallReason}</p>
              </div>
            </div>
          )}

          {/* Tool Arguments */}
          {Object.keys(displayArgs).length > 0 && (
            <div className="mb-3 md:mb-4">
              <h3 className="text-[10px] md:text-xs font-semibold text-gray-700 mb-1.5 flex items-center gap-1">
                <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                Arguments
              </h3>
              <pre className="bg-gray-900 text-green-400 p-2 md:p-3 rounded text-[9px] md:text-xs font-mono overflow-x-auto border border-gray-700 max-h-24 md:max-h-32 overflow-y-auto">
                {JSON.stringify(displayArgs, null, 2)}
              </pre>
            </div>
          )}

          {/* Detection Results */}
          <div className="mb-2">
            <h3 className="text-[10px] md:text-xs font-semibold text-gray-700 mb-1.5 flex items-center gap-1">
              <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Findings
            </h3>
            <div className="space-y-1.5 md:space-y-2">
              {detection_results.map((result, idx) => (
                <div key={idx} className="border border-red-200 rounded overflow-hidden">
                  <div className="bg-red-50 px-2 py-1 md:px-3 md:py-1.5 border-b border-red-200 flex items-center justify-between">
                    <span className="font-medium text-red-700 text-[10px] md:text-xs">{result.detector}</span>
                    <span className="text-[9px] md:text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full font-medium">
                      {result.evaluation}
                    </span>
                  </div>
                  <div className="p-1.5 md:p-2 space-y-1.5 md:space-y-2">
                    {result.findings.map((finding, fidx) => (
                      <div key={fidx} className="text-[10px] md:text-xs">
                        <div className="flex items-start gap-1.5">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] md:text-xs font-medium shrink-0 ${
                            finding.category === 'critical' ? 'bg-red-100 text-red-700' :
                            finding.category === 'high' ? 'bg-orange-100 text-orange-700' :
                            'bg-yellow-100 text-yellow-700'
                          }`}>
                            {finding.category}
                          </span>
                          <span className="text-gray-700 text-[9px] md:text-xs">{finding.reason}</span>
                        </div>
                        {finding.matched_text && (
                          <div className="mt-1 bg-gray-50 p-1.5 md:p-2 rounded border-l-2 border-red-400">
                            <code className="text-[9px] md:text-xs font-mono text-red-600 break-all">
                              {finding.matched_text}
                            </code>
                          </div>
                        )}
                        {finding.full_path && (
                          <div className="mt-1 bg-gray-50 p-1.5 md:p-2 rounded border-l-2 border-red-400">
                            <code className="text-[9px] md:text-xs font-mono text-red-600 break-all">
                              {finding.full_path}
                            </code>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="bg-gray-50 px-3 py-2 md:px-4 md:py-3 flex gap-2 md:gap-3 border-t shrink-0">
          <button
            onClick={() => onDecision(request_id, 'block')}
            className="flex-1 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-semibold py-2 px-3 md:py-2.5 md:px-4 rounded text-xs md:text-sm transition-all flex items-center justify-center gap-1.5"
          >
            <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
            Block
          </button>
          <button
            onClick={() => onDecision(request_id, 'allow')}
            className="flex-1 bg-white hover:bg-gray-100 text-gray-700 font-semibold py-2 px-3 md:py-2.5 md:px-4 rounded text-xs md:text-sm transition-all border border-gray-300 hover:border-gray-400 flex items-center justify-center gap-1.5"
          >
            <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Allow
          </button>
        </div>
      </div>
    </div>
  )
}

export default BlockingModal
