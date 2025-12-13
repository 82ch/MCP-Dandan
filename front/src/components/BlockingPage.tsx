import { useState, useEffect, useCallback } from 'react'

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

// 전체 타임(초 단위) – 기존 값에 맞춰 60으로 둠
const TOTAL_TIME = 60

function BlockingPage() {
  const [blockingData, setBlockingData] = useState<BlockingRequestData | null>(null)
  const [timeLeft, setTimeLeft] = useState(TOTAL_TIME)
  const [loading, setLoading] = useState(true)
  const [showDetails, setShowDetails] = useState(false)

  // Resize window when switching views
  useEffect(() => {
    if (showDetails) {
      window.electronAPI.resizeBlockingWindow(600, 600)
    } else {
      window.electronAPI.resizeBlockingWindow(400, 350)
    }
  }, [showDetails])

  // Fetch blocking data from main process
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await window.electronAPI.getBlockingData()
        if (data) {
          setBlockingData(data)
        } else {
          console.error('[BlockingPage] No blocking data available')
        }
      } catch (error) {
        console.error('[BlockingPage] Error fetching blocking data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // Handle decision
  const handleDecision = useCallback(
    async (decision: 'allow' | 'block') => {
      if (!blockingData) return

      try {
        await window.electronAPI.sendBlockingDecision(blockingData.request_id, decision)
        // Window will be closed by main process
      } catch (error) {
        console.error('[BlockingPage] Error sending decision:', error)
      }
    },
    [blockingData],
  )

  // Timer countdown
  useEffect(() => {
    if (!blockingData) return

    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          handleDecision('block')
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [blockingData, handleDecision])

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50" style={{ borderRadius: '12px', overflow: 'hidden' }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500 mx-auto mb-2" />
          <p className="text-gray-600 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (!blockingData) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50" style={{ borderRadius: '12px', overflow: 'hidden' }}>
        <div className="text-center">
          <p className="text-gray-600">No blocking data available</p>
          <button
            onClick={() => window.electronAPI.closeBlockingWindow()}
            className="mt-4 px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300"
          >
            Close
          </button>
        </div>
      </div>
    )
  }

  const { detection_results, engine_name, severity, server_name, tool_name, event_data } = blockingData
  const toolArgs = event_data?.data?.message?.params?.arguments || {}
  const toolCallReason = toolArgs?.tool_call_reason || ''

  // Remove tool_call_reason from toolArgs for display
  const displayArgs = { ...toolArgs }
  delete displayArgs.tool_call_reason

  // Simple view (default)
  if (!showDetails) {
    return (
      <div
        className="w-screen h-screen flex flex-col bg-gray-50 overflow-hidden"
        style={{
          borderRadius: '12px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)'
        }}
      >
        {/* Header - Draggable */}
        <div
          className="bg-white border-b border-gray-200 px-4 py-3 shrink-0"
          style={{
            WebkitAppRegion: 'drag'
          } as React.CSSProperties}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-50 rounded-lg">
                <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <div>
                <h2 className="text-sm font-semibold text-gray-900">Security Alert</h2>
                <p className="text-xs text-gray-500">Auto-block in {timeLeft}s</p>
              </div>
            </div>
            <button
              onClick={() => setShowDetails(true)}
              className="px-3 py-1.5 text-xs rounded-lg border border-gray-300
                        text-gray-700 bg-white hover:bg-gray-50 transition-colors"
              style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
            >
              View Details →
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-8">
          {/* Warning Icon */}
          <div className="mb-6 p-4 bg-red-50 rounded-full">
            <img src="../icons/warning.png" alt="Warning" className="w-16 h-16 object-contain" />
          </div>

          {/* Title */}
          <h3 className="text-2xl font-bold text-gray-900 text-center mb-3">Threat Detected</h3>

          {/* Severity Badge */}
          <div className="mb-4">
            <span className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold ${
              severity === 'high'
                ? 'bg-red-100 text-red-700 border border-red-200'
                : 'bg-yellow-100 text-yellow-700 border border-yellow-200'
            }`}>
              {severity.toUpperCase()} SEVERITY
            </span>
          </div>

          {/* Description */}
          <div className="text-center max-w-md">
            <p className="text-sm text-gray-600 mb-2">
              <span className="font-semibold text-gray-900">{server_name}</span> server&apos;s{' '}
              <span className="font-semibold text-gray-900">{tool_name}</span> tool triggered a security alert.
            </p>
            <p className="text-xs text-gray-500">
              Engine: {engine_name}
            </p>
          </div>

          {/* Timer Bar */}
          <div className="w-full max-w-sm mt-8">
            <div className="w-full bg-gray-200 rounded-lg h-1.5 overflow-hidden">
              <div
                className="h-1.5 bg-red-500 transition-[width] duration-1000 ease-linear"
                style={{
                  width: `${Math.max(0, Math.min(100, (timeLeft / TOTAL_TIME) * 100))}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="bg-white border-t border-gray-200 px-4 py-3 flex gap-3 shrink-0">
          <button
            onClick={() => handleDecision('block')}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg
                      transition-colors flex items-center justify-center gap-2 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 75.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
            Block
          </button>
          <button
            onClick={() => handleDecision('allow')}
            className="flex-1 bg-white hover:bg-gray-50 text-gray-700 font-medium py-2.5 px-4 rounded-lg
                      transition-colors border border-gray-300 hover:border-gray-400
                      flex items-center justify-center gap-2 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Allow
          </button>
        </div>
      </div>
    )
  }

  // Detailed view
  return (
    <div
      className="w-screen h-screen flex flex-col bg-gray-50 overflow-hidden"
      style={{
        borderRadius: '12px',
        boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)'
      }}
    >
      {/* Header - Draggable */}
      <div
        className="bg-white border-b border-gray-200 px-4 py-3 shrink-0"
        style={{
          WebkitAppRegion: 'drag'
        } as React.CSSProperties}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-50 rounded-lg">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Threat Details</h2>
              <p className="text-xs text-gray-500">Auto-block in {timeLeft}s</p>
            </div>
          </div>
          <button
            onClick={() => setShowDetails(false)}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          >
            <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 overflow-x-hidden">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">Server</div>
            <div className="font-medium text-sm truncate" title={server_name}>
              {server_name}
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">Tool</div>
            <div className="font-mono font-medium text-sm text-blue-600 truncate" title={tool_name}>
              {tool_name}
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">Engine</div>
            <div className="font-medium text-sm truncate">{engine_name}</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">Severity</div>
            <div>
              <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${
                severity === 'high'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-yellow-100 text-yellow-700'
              }`}>
                {severity.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        {/* MCP Tool Call Reason */}
        {toolCallReason && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                />
              </svg>
              Tool Call Reason
            </h3>
            <div className="bg-white border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-gray-700 leading-relaxed">{toolCallReason}</p>
            </div>
          </div>
        )}

        {/* Tool Arguments */}
        {Object.keys(displayArgs).length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                />
              </svg>
              Tool Arguments
            </h3>
            <pre className="bg-gray-900 text-green-400 p-3 rounded-lg text-xs font-mono overflow-x-auto border border-gray-700 max-h-32 overflow-y-auto whitespace-pre-wrap">
{JSON.stringify(displayArgs, null, 2)}
            </pre>
          </div>
        )}

        {/* Detection Results */}
        <div className="mb-2">
          <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            Detection Findings
          </h3>
          <div className="space-y-3">
            {detection_results.map((result, idx) => (
              <div key={idx} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
                  <span className="font-medium text-gray-900 text-sm">{result.detector}</span>
                  <span className="text-xs bg-red-100 text-red-700 px-2.5 py-1 rounded-full font-semibold">
                    Score: {result.evaluation}
                  </span>
                </div>
                <div className="p-3 space-y-2">
                  {result.findings.map((finding, fidx) => (
                    <div key={fidx} className="text-sm">
                      <div className="flex items-start gap-2 mb-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${
                            finding.category === 'critical'
                              ? 'bg-red-100 text-red-700'
                              : finding.category === 'high'
                              ? 'bg-orange-100 text-orange-700'
                              : 'bg-yellow-100 text-yellow-700'
                          }`}
                        >
                          {finding.category}
                        </span>
                        <span className="text-gray-700 text-sm">{finding.reason}</span>
                      </div>
                      {finding.matched_text && (
                        <div className="mt-2 bg-red-50 p-2.5 rounded-lg border-l-4 border-red-500">
                          <span className="text-xs font-medium text-gray-700">Matched Text: </span>
                          <code className="text-xs font-mono text-red-700 break-all block mt-1">
                            {finding.matched_text}
                          </code>
                        </div>
                      )}
                      {finding.full_path && (
                        <div className="mt-2 bg-blue-50 p-2.5 rounded-lg border-l-4 border-blue-500">
                          <span className="text-xs font-medium text-gray-700">File Path: </span>
                          <code className="text-xs font-mono text-blue-700 break-all block mt-1">
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

      {/* Timer Bar */}
      <div className="w-full bg-gray-200 h-1.5 overflow-hidden">
        <div
          className="h-1.5 bg-red-500 transition-[width] duration-1000 ease-linear"
          style={{
            width: `${Math.max(0, Math.min(100, (timeLeft / TOTAL_TIME) * 100))}%`,
          }}
        />
      </div>

      {/* Actions */}
      <div className="bg-white border-t border-gray-200 px-4 py-3 flex gap-3 shrink-0">
        <button
          onClick={() => handleDecision('block')}
          className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg
                    transition-colors flex items-center justify-center gap-2 text-sm"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
          Block
        </button>
        <button
          onClick={() => handleDecision('allow')}
          className="flex-1 bg-white hover:bg-gray-50 text-gray-700 font-medium py-2.5 px-4 rounded-lg
                    transition-colors border border-gray-300 hover:border-gray-400
                    flex items-center justify-center gap-2 text-sm"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Allow
        </button>
      </div>
    </div>
  )
}

export default BlockingPage
