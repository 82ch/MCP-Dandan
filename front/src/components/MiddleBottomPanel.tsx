import { useEffect, useState } from 'react'
import type { ChatMessage } from '../types'

interface EngineResult {
  id: number
  raw_event_id: number
  engine_name: string
  serverName: string
  producer: string
  severity: string
  score: number
  detail: string
  created_at: string
}

interface MiddleBottomPanelProps {
  selectedMessage: ChatMessage | null
}

function MiddleBottomPanel({ selectedMessage }: MiddleBottomPanelProps) {
  const [engineResults, setEngineResults] = useState<EngineResult[]>([])

  useEffect(() => {
    if (selectedMessage && selectedMessage.id) {
      fetchEngineResults(selectedMessage.id)
    } else {
      setEngineResults([])
    }
  }, [selectedMessage])

  const fetchEngineResults = async (rawEventId: string | number) => {
    try {
      const results = await window.electronAPI.getEngineResultsByEvent(Number(rawEventId))
      setEngineResults(results)
    } catch (error) {
      console.error('Error fetching engine results:', error)
      setEngineResults([])
    }
  }

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
        {/* Message Type */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-2">Message Type</h3>
          <p className="text-lg font-mono font-medium text-gray-800">
            {selectedMessage.type}
          </p>
        </div>

        {/* Malicious Detect */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-2">Malicious Detect</h3>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Score:</span>
              <span className={`font-mono text-lg font-semibold ${
                selectedMessage.maliciousScore > 50 ? 'text-red-600' :
                selectedMessage.maliciousScore > 20 ? 'text-yellow-600' : 'text-green-600'
              }`}>
                {selectedMessage.maliciousScore !== undefined ? selectedMessage.maliciousScore : 'N/A'}
              </span>
              <span className="text-sm text-gray-500">/ 100</span>
            </div>
            <div className="mt-3 bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full transition-all ${
                  selectedMessage.maliciousScore > 50 ? 'bg-red-500' :
                  selectedMessage.maliciousScore > 20 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${(selectedMessage.maliciousScore || 0)}%` }}
              />
            </div>
            <div className="mt-2 text-xs text-gray-600">
              {selectedMessage.maliciousScore > 50 ? '⚠️ High Risk' :
               selectedMessage.maliciousScore > 20 ? '⚡ Medium Risk' : '✓ Safe'}
            </div>

            {/* Engine Detection Details */}
            {engineResults.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-300">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Detection Details</h4>
                <div className="space-y-3">
                  {engineResults.map((result) => (
                    <div key={result.id} className="bg-white border border-gray-300 rounded-lg p-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-mono text-sm font-semibold text-gray-800">
                              {result.engine_name}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              result.severity === 'high' ? 'bg-red-100 text-red-700' :
                              result.severity === 'medium' || result.severity === 'mid' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-green-100 text-green-700'
                            }`}>
                              {result.severity}
                            </span>
                          </div>
                          <p className="text-xs text-gray-600 mt-1">{result.detail}</p>
                        </div>
                        <div className="ml-3 flex flex-col items-end">
                          <span className={`font-mono text-lg font-bold ${
                            result.score > 50 ? 'text-red-600' :
                            result.score > 20 ? 'text-yellow-600' : 'text-green-600'
                          }`}>
                            {result.score}
                          </span>
                          <span className="text-xs text-gray-500">score</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {engineResults.length === 0 && selectedMessage.maliciousScore === 0 && (
              <div className="mt-4 pt-4 border-t border-gray-300">
                <p className="text-xs text-gray-500 text-center">No threats detected</p>
              </div>
            )}
          </div>
        </div>

        {/* Message Data */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 mb-2">Message Content</h3>
          <div className="bg-gray-50 rounded-lg p-4">
            <pre className="text-xs font-mono text-gray-700 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(selectedMessage.data.message, null, 2)}
            </pre>
          </div>
        </div>

        {/* Parameters */}
        {selectedMessage.data.message?.params && Object.keys(selectedMessage.data.message.params).length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-500 mb-2">Parameters</h3>
            <div className="bg-gray-50 rounded-lg p-4 space-y-3">
              {Object.entries(selectedMessage.data.message.params)
                .filter(([key]) => key !== 'arguments') // arguments는 제외
                .map(([key, value]) => (
                  <div key={key} className="flex flex-col gap-1">
                    <span className="font-mono text-sm font-semibold text-gray-600">{key}:</span>
                    <div className="bg-white border border-gray-300 rounded px-3 py-2 text-sm text-gray-700">
                      {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                    </div>
                  </div>
                ))}

              {/* Arguments를 Parameters 안에 포함 */}
              {selectedMessage.data.message?.params?.arguments && Object.keys(selectedMessage.data.message.params.arguments).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Arguments</h4>
                  <div className="space-y-2">
                    {Object.entries(selectedMessage.data.message.params.arguments).map(([key, value]) => (
                      <div key={key} className="flex flex-col gap-1">
                        <span className="font-mono text-sm font-semibold text-gray-600">{key}:</span>
                        <div className="bg-white border border-gray-300 rounded px-3 py-2 text-sm text-gray-900 font-mono">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MiddleBottomPanel
