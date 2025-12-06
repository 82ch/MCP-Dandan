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
      <div className="h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500 mx-auto mb-2" />
          <p className="text-gray-600 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (!blockingData) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <p className="text-gray-600">No blocking data available</p>
          <button
            onClick={() => window.electronAPI.closeBlockingWindow()}
            className="mt-4 px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
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
      <div className="w-screen h-screen flex flex-col bg-white overflow-hidden">
        {/* Header - Draggable */}
        <div
          className="bg-gradient-to-r from-red-500 to-red-600 text-white px-3 py-2 md:px-4 md:py-3 shrink-0"
          style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
        >
          <div className="flex items-center gap-2 md:gap-3">
            <svg className="w-4 h-10 md:w-5 md:h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <h2 className="text-xs md:text-sm font-bold leading-tight">Security Alert</h2>
              <p className="text-[10px] md:text-xs opacity-90">{timeLeft}s</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col bg-red-50">
          {/* 상단 우측 View Details 버튼 영역 */}
          <div className="w-full flex justify-end px-3 md:px-4 pt-3">
            <button
              onClick={() => setShowDetails(true)}
              className="px-3 py-1.5 text-xs md:text-sm rounded-md border border-red-300 
                        text-red-700 bg-white hover:bg-red-50 transition-colors shadow-sm"
            >
              View Details →
            </button>
          </div>

          {/* Severity 박스 */}
          <div className="mt-4 px-4 py-2 w-2/4 mx-auto bg-red-100 border border-red-300 rounded-xl text-center text-red-700">
            <p className="text-sm font-semibold leading-tight">
              Severity:{' '}
              <span className={severity === 'high' ? 'text-red-600' : 'text-yellow-600'}>
                {severity.toUpperCase()}
              </span>
            </p>
          </div>

          {/* 중앙 내용 영역 */}
          <div className="flex-1 flex flex-col items-center justify-start px-3">
            {/* 아이콘 + 타이틀 가로 정렬 */}
            <div className="flex flex-row items-center justify-center gap-3 mb-3">
              {/* 경고 아이콘 */}
              <img src="../icons/warning.png" alt="Warning" className="w-30 h-30 object-contain" />

              {/* 타이틀 */}
              <h3 className="text-4xl md:text-2xl font-bold text-red-900 text-center">Threat Detected</h3>
            </div>

            <p className="text-base font-medium">
              <span className="font-semibold text-red-800">reason: {server_name}</span> server&apos;s{' '}
              <span className="font-semibold text-red-800">{tool_name}</span> tool triggered this request.
            </p>
          </div>
        </div>
        <div className="w-full max-w-xl mx-auto bg-red-100 rounded-full h-2 overflow-hidden">
          <div
            className="h-2 bg-red-500 transition-[width] duration-1000 ease-linear"
            style={{
              width: `${Math.max(0, Math.min(100, (timeLeft / TOTAL_TIME) * 100))}%`,
            }}
          />
        </div>

        {/* Actions */}
        <div className="bg-gray-50 px-3 py-4 md:px-4 md:py-3 flex gap-2 md:gap-3 border-t shrink-0">
          <button
            onClick={() => handleDecision('block')}
            className="flex-1 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700
                      text-white font-semibold py-2 rounded transition-all shadow-sm hover:shadow-md
                      flex items-center justify-center gap-1 text-xs md:text-sm"
          >
            Block
          </button>
          <button
            onClick={() => handleDecision('allow')}
            className="flex-1 bg-white hover:bg-gray-100 text-gray-700 font-semibold py-2 rounded
                      transition-all border border-gray-300 hover:border-gray-400
                      flex items-center justify-center gap-1 text-xs md:text-sm"
          >
            Allow
          </button>
        </div>
      </div>
    )
  }

  // Detailed view
  return (
    <div className="w-screen h-screen flex flex-col bg-white overflow-hidden">
      {/* Header - Draggable */}
      <div
        className="bg-gradient-to-r from-red-500 to-red-600 text-white px-2 py-1.5 md:px-4 md:py-3 shrink-0"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 md:gap-3">
            <svg className="w-4 h-12 md:w-5 md:h-14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <h2 className="text-[10px] md:text-sm font-bold leading-tight">Details</h2>
              <p className="text-[8px] md:text-xs opacity-90">{timeLeft}s</p>
            </div>
          </div>
          {/* <button
            onClick={() => setShowDetails(false)}
            className="text-white hover:text-red-200 p-0.5 rounded transition-colors"
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          >
            <svg className="w-3 h-3 md:w-5 md:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button> */}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-1.5 md:p-4 overflow-x-hidden">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1">Server</div>
            <div className="font-medium text-xs truncate" title={server_name}>
              {server_name}
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1">Tool</div>
            <div className="font-mono font-medium text-xs text-blue-600 truncate" title={tool_name}>
              {tool_name}
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1">Engine</div>
            <div className="font-medium text-xs truncate">{engine_name}</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1">Severity</div>
            <div className={`font-bold text-xs ${severity === 'high' ? 'text-red-600' : 'text-yellow-600'}`}>
              {severity.toUpperCase()}
            </div>
          </div>
        </div>

        {/* MCP Tool Call Reason */}
        {toolCallReason && (
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                />
              </svg>
              Reason
            </h3>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-xs text-blue-900 leading-relaxed">{toolCallReason}</p>
            </div>
          </div>
        )}

        {/* Tool Arguments */}
        {Object.keys(displayArgs).length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                />
              </svg>
              Arguments
            </h3>
            <pre className="bg-gray-900 text-green-400 p-2 rounded-lg text-xs font-mono overflow-x-auto border border-gray-700 max-h-24 overflow-y-auto break-all whitespace-pre-wrap">
              {JSON.stringify(displayArgs, null, 2)}
            </pre>
          </div>
        )}

        {/* Detection Results */}
        <div className="mb-2">
          <h3 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            Findings
          </h3>
          <div className="space-y-1 md:space-y-2">
            {detection_results.map((result, idx) => (
              <div key={idx} className="border border-red-200 rounded-lg overflow-hidden">
                <div className="bg-red-50 px-4 py-2 border-b border-red-200 flex items-center justify-between">
                  <span className="font-medium text-red-700 text-sm">{result.detector}</span>
                  <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full font-medium">
                    Score: {result.evaluation}
                  </span>
                </div>
                <div className="p-1 md:p-2 space-y-1 md:space-y-2">
                  {result.findings.map((finding, fidx) => (
                    <div key={fidx} className="text-sm">
                      <div className="flex items-start gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${
                            finding.category === 'critical'
                              ? 'bg-red-100 text-red-700'
                              : finding.category === 'high'
                              ? 'bg-orange-100 text-orange-700'
                              : 'bg-yellow-100 text-yellow-700'
                          }`}
                        >
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

      {/* Timer Bar */}
      <div className="w-full bg-red-100 h-2 overflow-hidden">
        <div
          className="h-2 bg-red-500 transition-[width] duration-1000 ease-linear"
          style={{
            width: `${Math.max(0, Math.min(100, (timeLeft / TOTAL_TIME) * 100))}%`,
          }}
        />
      </div>

      {/* Actions */}
      <div className="bg-gray-50 px-2 py-1.5 md:px-4 md:py-3 flex gap-1.5 md:gap-3 border-t shrink-0">
        <button
          onClick={() => handleDecision('block')}
          className="flex-1 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-semibold py-2.5 px-2 md:py-2.5 md:px-4 rounded transition-all flex items-center justify-center gap-1 text-[11px] md:text-sm"
        >
          <svg className="w-2.5 h-2.5 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
          Block
        </button>
        <button
          onClick={() => handleDecision('allow')}
          className="flex-1 bg-white hover:bg-gray-100 text-gray-700 font-semibold py-1.5 px-2 md:py-2.5 md:px-4 rounded transition-all border border-gray-300 hover:border-gray-400 flex items-center justify-center gap-1 text-[11px] md:text-sm"
        >
          <svg className="w-2.5 h-2.5 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Allow
        </button>
      </div>
    </div>
  )
}

export default BlockingPage
