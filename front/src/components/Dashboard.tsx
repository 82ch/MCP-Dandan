import { useEffect, useState } from 'react'
import { AlertTriangle, Shield, FileWarning, Database, UserX, LucideIcon } from 'lucide-react'
import type { MCPServer, DetectedEvent, ThreatStats, TimelineData, TopServer } from '../types'

interface ThreatDefinition {
  name: string
  description: string
  icon: LucideIcon
  color: string
  bgColor: string
  borderColor: string
}

const threatDefinitions: ThreatDefinition[] = [
  {
    name: 'Tool Poisoning',
    description: 'Malicious or tampered MCP tools are loaded, compromising normal operations.',
    icon: Shield,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200'
  },
  {
    name: 'Command Injection',
    description: 'Unvalidated user input allows execution of unintended system commands.',
    icon: AlertTriangle,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200'
  },
  {
    name: 'Filesystem Exposure',
    description: 'MCP servers access files or directories beyond their authorized scope.',
    icon: FileWarning,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200'
  },
  {
    name: 'PII Filter',
    description: 'Personally Identifiable Information (PII) detected in MCP tool requests.',
    icon: UserX,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200'
  },
  {
    name: 'Data Exfiltration',
    description: 'Sensitive information or credentials are exfiltrated to external destinations.',
    icon: Database,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200'
  }
]

interface DashboardProps {
  setSelectedServer: (server: MCPServer | null) => void
  servers: MCPServer[]
  setSelectedMessageId: (messageId: string | number | null) => void
}

function Dashboard({ setSelectedServer, servers, setSelectedMessageId }: DashboardProps) {
  const [detectedEvents, setDetectedEvents] = useState<DetectedEvent[]>([])
  const [topServers, setTopServers] = useState<TopServer[]>([])
  const [threatStats, setThreatStats] = useState<Record<string, ThreatStats>>({})
  const [timelineData, setTimelineData] = useState<TimelineData[]>([])

  useEffect(() => {
    fetchDashboardData()
  }, [])

  // Subscribe to WebSocket updates for real-time dashboard data
  useEffect(() => {
    const unsubscribe = window.electronAPI.onWebSocketUpdate((message: any) => {
      console.log('[Dashboard] WebSocket update received:', message.type)

      // Refresh dashboard data on relevant events
      if (message.type === 'server_update' ||
          message.type === 'detection_result' ||
          message.type === 'reload_all') {
        fetchDashboardData()
      }
    })

    return () => {
      unsubscribe()
    }
  }, [])

  const fetchDashboardData = async () => {
    try {
      const engineResults = await window.electronAPI.getEngineResults()

      // Process data for dashboard
      const events: DetectedEvent[] = []
      const serverDetectionCount: Record<string, number> = {}
      const threatCount: Record<string, number> = {}
      const threatAffectedServers: Record<string, Set<string>> = {}

      engineResults.forEach((result: any) => {
        const serverName = result.serverName || 'Unknown'

        // Count detections per server
        serverDetectionCount[serverName] = (serverDetectionCount[serverName] || 0) + 1

        // Determine threat type based on engine_name
        let threatType = 'Tool Poisoning' // default
        if (result.engine_name) {
          const name = result.engine_name.toLowerCase()
          console.log('Engine name:', result.engine_name, '-> lowercase:', name)

          if (name.includes('commandinjection')) {
            threatType = 'Command Injection'
            console.log('Matched: Command Injection')
          } else if (name.includes('filesystemexposure')) {
            threatType = 'Filesystem Exposure'
            console.log('Matched: Filesystem Exposure')
          } else if (name.includes('pii') || name.includes('filter')) {
            threatType = 'PII Filter'
            console.log('Matched: PII Filter')
          } else if (name.includes('data') || name.includes('exfiltration')) {
            threatType = 'Data Exfiltration'
            console.log('Matched: Data Exfiltration')
          } else if (name.includes('tool') || name.includes('poisoning')) {
            threatType = 'Tool Poisoning'
            console.log('Matched: Tool Poisoning')
          } else {
            console.log('No match found for:', name)
          }
        } else {
          console.log('No engine_name found in result:', result)
        }

        // Determine severity based on severity field or score
        let severity: 'low' | 'mid' | 'high' = result.severity || 'low'
        let severityColor = 'bg-yellow-400'

        if (severity.toLowerCase() === 'high' || result.score >= 8) {
          severity = 'high'
          severityColor = 'bg-red-500'
        } else if (severity.toLowerCase() === 'medium' || severity.toLowerCase() === 'mid' || result.score >= 5) {
          severity = 'mid'
          severityColor = 'bg-orange-400'
        } else {
          severity = 'low'
          severityColor = 'bg-yellow-400'
        }

        // Count threats
        threatCount[threatType] = (threatCount[threatType] || 0) + 1

        // Track affected servers per threat
        if (!threatAffectedServers[threatType]) {
          threatAffectedServers[threatType] = new Set()
        }
        threatAffectedServers[threatType].add(serverName)

        // Parse event data if available
        let description = result.detail || '—'
        try {
          if (result.data) {
            const eventData = JSON.parse(result.data)
            description = eventData.message?.params?.name || result.detail || '—'
          }
        } catch (e) {
          // Keep default description
        }

        // Format timestamp
        const timestamp = result.created_at || new Date(result.ts).toISOString()

        events.push({
          serverName,
          threatType,
          severity,
          severityColor,
          description,
          lastSeen: timestamp,
          engineResultId: result.id,
          rawEventId: result.raw_event_id
        })
      })

      // Sort servers by detection count
      const sortedServers = Object.entries(serverDetectionCount)
        .sort(([, a], [, b]) => (b as number) - (a as number))
        .slice(0, 5)
        .map(([name, count]) => ({ name, count: count as number }))

      // Build threat stats
      const stats: Record<string, ThreatStats> = {}
      threatDefinitions.forEach(threat => {
        stats[threat.name] = {
          detections: threatCount[threat.name] || 0,
          affectedServers: threatAffectedServers[threat.name]?.size || 0
        }
      })

      // Process timeline data (group by date)
      const timelineMap: Record<string, number> = {}
      engineResults.forEach((result: any) => {
        // Extract date from timestamp (e.g., "2025-11-07 04:01:18" -> "2025-11-07")
        let date
        if (result.created_at) {
          date = result.created_at.split(' ')[0]
        } else if (result.ts) {
          const d = new Date(result.ts)
          date = d.toISOString().split('T')[0]
        }

        if (date) {
          timelineMap[date] = (timelineMap[date] || 0) + 1
        }
      })

      // Convert to array and sort by date
      const timeline = Object.entries(timelineMap)
        .sort(([dateA], [dateB]) => dateA.localeCompare(dateB))
        .map(([date, count]) => ({ date, count: count as number }))

      setTopServers(sortedServers)
      setDetectedEvents(events)
      setThreatStats(stats)
      setTimelineData(timeline)
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    }
  }

  const handleGoToServer = (serverName: string, rawEventId: string | number) => {
    const server = servers.find(s => s.name === serverName)
    if (server) {
      setSelectedServer(server)
      // Set the message ID to auto-select it
      setSelectedMessageId(rawEventId)
    }
  }

  return (
    <div className="h-full overflow-auto bg-gray-50 p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>

      {/* Top Section: Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Top Affected Servers */}
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-base font-semibold text-gray-800 mb-3">Top Affected Servers</h2>
          {topServers.length === 0 ? (
            <p className="text-gray-500 text-center py-3 text-sm">No detections found</p>
          ) : (
            <div className="flex items-end justify-around gap-3 h-64">
              {topServers.map((server, index) => {
                const maxCount = topServers[0]?.count || 1
                const barHeightPx = Math.max(20, (server.count / maxCount) * 240)

                return (
                  <div key={index} className="flex flex-col items-center gap-1 flex-1 h-full justify-end">
                    <div className="text-xs text-gray-600 font-medium">{server.count}</div>
                    <div
                      className="w-full rounded-t transition-all duration-300"
                      style={{ height: `${barHeightPx}px`, backgroundColor: '#D4EDFA' }}
                    />
                    <div className="text-xs text-gray-700 text-center wrap-words w-full mt-1">{server.name}</div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Time-Series View */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <h3 className="text-base font-semibold text-gray-800 mb-3">Time-Series View</h3>
            {timelineData.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-xs">No timeline data available</p>
            ) : (
              <div className="relative h-40">
                <svg className="w-full h-full" viewBox="0 0 800 160" preserveAspectRatio="none">
                  {/* Grid lines */}
                  <line x1="40" y1="10" x2="40" y2="140" stroke="#E5E7EB" strokeWidth="1" />
                  <line x1="40" y1="140" x2="780" y2="140" stroke="#E5E7EB" strokeWidth="1" />

                  {/* Y-axis labels - only show max value */}
                  {(() => {
                    const maxCount = Math.max(...timelineData.map(d => d.count), 1)
                    return (
                      <text x="35" y="14" textAnchor="end" fontSize="10" fill="#9CA3AF">
                        {maxCount}
                      </text>
                    )
                  })()}

                  {/* Line path */}
                  {(() => {
                    const maxCount = Math.max(...timelineData.map(d => d.count), 1)
                    const xStep = 740 / (timelineData.length - 1 || 1)

                    const points = timelineData.map((d, i) => {
                      const x = 40 + i * xStep
                      const y = 140 - (d.count / maxCount) * 130
                      return `${x},${y}`
                    }).join(' ')

                    return (
                      <>
                        {/* Line */}
                        <polyline
                          points={points}
                          fill="none"
                          stroke="#6366F1"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />

                        {/* Data points */}
                        {timelineData.map((d, i) => {
                          const x = 40 + i * xStep
                          const y = 140 - (d.count / maxCount) * 130
                          return (
                            <circle
                              key={i}
                              cx={x}
                              cy={y}
                              r="2.5"
                              fill="#6366F1"
                            />
                          )
                        })}
                      </>
                    )
                  })()}

                  {/* X-axis labels - show only first and last */}
                  {(() => {
                    if (timelineData.length === 0) return null
                    const first = timelineData[0]
                    const last = timelineData[timelineData.length - 1]
                    return (
                      <>
                        <text x="40" y="153" textAnchor="start" fontSize="9" fill="#9CA3AF">
                          {first.date.slice(5)}
                        </text>
                        <text x="780" y="153" textAnchor="end" fontSize="9" fill="#9CA3AF">
                          {last.date.slice(5)}
                        </text>
                      </>
                    )
                  })()}
                </svg>
              </div>
            )}
          </div>
        </div>

        {/* Threats */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Threats</h2>
          <div className="grid grid-cols-1 gap-3">
            {threatDefinitions.map((threat) => {
              const Icon = threat.icon
              const stats = threatStats[threat.name] || { detections: 0, affectedServers: 0 }

              return (
                <div
                  key={threat.name}
                  className={`border rounded-lg p-4 ${threat.bgColor} ${threat.borderColor}`}
                >
                  <div className="flex items-start gap-3">
                    <Icon className={`${threat.color} shrink-0`} size={20} />
                    <div className="flex-1 min-w-0">
                      <h3 className={`font-semibold ${threat.color} text-sm`}>{threat.name}</h3>
                      <p className="text-xs text-gray-600 mt-1 line-clamp-2">{threat.description}</p>
                      <div className="flex flex-col gap-1 mt-2 text-xs text-gray-700">
                        <span className="font-bold">Detections: {stats.detections}</span>
                        <span className="font-bold">Affected Servers: {stats.affectedServers}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Detected Events Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Detected</h2>
        </div>
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Server Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Threat Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Severity Level
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Last seen
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Go to
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {detectedEvents.map((event, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {event.serverName}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {event.threatType}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-700">{event.severity}</span>
                      <span className={`w-2 h-2 rounded-full ${event.severityColor}`}></span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700 max-w-xs truncate">
                    {event.description}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {event.lastSeen}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <button
                      onClick={() => handleGoToServer(event.serverName, event.rawEventId)}
                      className="px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
                    >
                      {event.serverName}
                    </button>
                  </td>
                </tr>
              ))}
              {detectedEvents.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    No security events detected
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Dashboard