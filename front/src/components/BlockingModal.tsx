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

  useEffect(() => {
    if (!blockingRequest) {
      setTimeLeft(60)
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
  const userIntent = toolArgs?.user_intent || ''

  // Remove user_intent from toolArgs for display
  const displayArgs = { ...toolArgs }
  delete displayArgs.user_intent

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="bg-linear-to-r from-red-500 to-red-600 text-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white bg-opacity-20 rounded-lg">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-bold">Security Alert</h2>
              <p className="text-sm opacity-90">Threat detected - Action required</p>
            </div>
          </div>
          <div className="text-right bg-white bg-opacity-20 px-3 py-2 rounded-lg">
            <div className="text-2xl font-mono font-bold">{timeLeft}s</div>
            <div className="text-xs opacity-75">Auto-block</div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Server</div>
              <div className="font-medium text-sm truncate">{server_name}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Tool</div>
              <div className="font-mono font-medium text-sm text-blue-600 truncate">{tool_name}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Engine</div>
              <div className="font-medium text-sm">{engine_name}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Severity</div>
              <div className={`font-bold text-sm ${severity === 'high' ? 'text-red-600' : 'text-yellow-600'}`}>
                {severity.toUpperCase()}
              </div>
            </div>
          </div>

          {/* MCP Tool Intent */}
          {userIntent && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                MCP Tool Intent
              </h3>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-900 leading-relaxed">{userIntent}</p>
              </div>
            </div>
          )}

          {/* Tool Arguments */}
          {Object.keys(displayArgs).length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                Tool Arguments
              </h3>
              <pre className="bg-gray-900 text-green-400 p-3 rounded-lg text-xs font-mono overflow-x-auto border border-gray-700 max-h-32 overflow-y-auto">
                {JSON.stringify(displayArgs, null, 2)}
              </pre>
            </div>
          )}

          {/* Detection Results */}
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Detection Findings
            </h3>
            <div className="space-y-3">
              {detection_results.map((result, idx) => (
                <div key={idx} className="border border-red-200 rounded-lg overflow-hidden">
                  <div className="bg-red-50 px-4 py-2 border-b border-red-200 flex items-center justify-between">
                    <span className="font-medium text-red-700 text-sm">{result.detector}</span>
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full font-medium">
                      Score: {result.evaluation}
                    </span>
                  </div>
                  <div className="p-4 space-y-3">
                    {result.findings.map((finding, fidx) => (
                      <div key={fidx} className="text-sm">
                        <div className="flex items-start gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${
                            finding.category === 'critical' ? 'bg-red-100 text-red-700' :
                            finding.category === 'high' ? 'bg-orange-100 text-orange-700' :
                            'bg-yellow-100 text-yellow-700'
                          }`}>
                            {finding.category}
                          </span>
                          <span className="text-gray-700">{finding.reason}</span>
                        </div>
                        {finding.matched_text && (
                          <div className="mt-2 bg-gray-50 p-2 rounded border-l-2 border-red-400">
                            <span className="text-xs text-gray-500">Matched: </span>
                            <code className="text-xs font-mono text-red-600 break-all">
                              {finding.matched_text}
                            </code>
                          </div>
                        )}
                        {finding.full_path && (
                          <div className="mt-2 bg-gray-50 p-2 rounded border-l-2 border-red-400">
                            <span className="text-xs text-gray-500">Path: </span>
                            <code className="text-xs font-mono text-red-600 break-all">
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
        <div className="bg-gray-50 px-6 py-4 flex gap-4 border-t">
          <button
            onClick={() => onDecision(request_id, 'block')}
            className="flex-1 bg-linear-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-semibold py-3 px-6 rounded-lg transition-all shadow-lg hover:shadow-xl flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
            Block
          </button>
          <button
            onClick={() => onDecision(request_id, 'allow')}
            className="flex-1 bg-white hover:bg-gray-100 text-gray-700 font-semibold py-3 px-6 rounded-lg transition-all border-2 border-gray-300 hover:border-gray-400 flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
