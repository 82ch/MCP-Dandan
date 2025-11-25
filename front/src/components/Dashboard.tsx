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
    name: 'PII Leak',
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
          } else if (name.includes('pii') || name.includes('leak')) {
            threatType = 'PII Leak'
            console.log('Matched: PII Leak')
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

      // Process timeline data (group by minute)
      const timelineMap: Record<string, number> = {}
      engineResults.forEach((result: any) => {
        // Extract timestamp down to the minute (e.g., "2025-11-07 04:01:18" -> "2025-11-07 04:01")
        let minuteTimestamp
        if (result.created_at) {
          // Format: "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DD HH:MM"
          const parts = result.created_at.split(' ')
          if (parts.length === 2) {
            const timeParts = parts[1].split(':')
            minuteTimestamp = `${parts[0]} ${timeParts[0]}:${timeParts[1]}`
          }
        } else if (result.ts) {
          const d = new Date(result.ts)
          const year = d.getFullYear()
          const month = String(d.getMonth() + 1).padStart(2, '0')
          const day = String(d.getDate()).padStart(2, '0')
          const hours = String(d.getHours()).padStart(2, '0')
          const minutes = String(d.getMinutes()).padStart(2, '0')
          minuteTimestamp = `${year}-${month}-${day} ${hours}:${minutes}`
        }

        if (minuteTimestamp) {
          timelineMap[minuteTimestamp] = (timelineMap[minuteTimestamp] || 0) + 1
        }
      })

      // Convert to array and sort by timestamp
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

      {/* Detected Events Table - Full Width */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Detected Threats</h2>
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

      {/* Bottom Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Threat Categories */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Threat Categories</h2>
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

        {/* Top Affected Servers and Time-Series View */}
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-base font-semibold text-gray-800 mb-3">Top Affected Servers</h2>
          {topServers.length === 0 ? (
            <p className="text-gray-500 text-center py-3 text-sm">No detections found</p>
          ) : (
            <div className="h-64 flex items-center justify-center">
              <svg width="280" height="280" viewBox="0 0 280 280">
                {(() => {
                  const total = topServers.reduce((sum, s) => sum + s.count, 0)
                  const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
                  const centerX = 140
                  const centerY = 140
                  const radius = 100
                  let currentAngle = -90 // Start from top

                  return (
                    <>
                      {topServers.map((server, index) => {
                        const percentage = (server.count / total) * 100
                        const angle = (server.count / total) * 360
                        const startAngle = currentAngle
                        const endAngle = currentAngle + angle

                        // Convert to radians
                        const startRad = (startAngle * Math.PI) / 180
                        const endRad = (endAngle * Math.PI) / 180

                        // Calculate arc points
                        const x1 = centerX + radius * Math.cos(startRad)
                        const y1 = centerY + radius * Math.sin(startRad)
                        const x2 = centerX + radius * Math.cos(endRad)
                        const y2 = centerY + radius * Math.sin(endRad)

                        const largeArcFlag = angle > 180 ? 1 : 0

                        const pathData = [
                          `M ${centerX} ${centerY}`,
                          `L ${x1} ${y1}`,
                          `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
                          'Z'
                        ].join(' ')

                        currentAngle = endAngle

                        return (
                          <path
                            key={index}
                            d={pathData}
                            fill={colors[index % colors.length]}
                            opacity="0.9"
                            stroke="white"
                            strokeWidth="2"
                          />
                        )
                      })}
                      {/* Center circle for donut effect */}
                      <circle cx={centerX} cy={centerY} r="60" fill="white" />
                      {/* Center text */}
                      <text x={centerX} y={centerY - 5} textAnchor="middle" fontSize="20" fontWeight="bold" fill="#374151">
                        {total}
                      </text>
                      <text x={centerX} y={centerY + 15} textAnchor="middle" fontSize="12" fill="#6B7280">
                        Total
                      </text>
                    </>
                  )
                })()}
              </svg>
              {/* Legend */}
              <div className="ml-6 flex flex-col gap-2">
                {topServers.map((server, index) => {
                  const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
                  const total = topServers.reduce((sum, s) => sum + s.count, 0)
                  const percentage = ((server.count / total) * 100).toFixed(1)

                  return (
                    <div key={index} className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-sm"
                        style={{ backgroundColor: colors[index % colors.length] }}
                      />
                      <div className="text-xs">
                        <div className="font-medium text-gray-700 truncate max-w-[120px]" title={server.name}>
                          {server.name}
                        </div>
                        <div className="text-gray-500">
                          {server.count} ({percentage}%)
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
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
                    // Extract time portion (HH:MM) from "YYYY-MM-DD HH:MM"
                    const formatTime = (timestamp: string) => {
                      const parts = timestamp.split(' ')
                      return parts.length === 2 ? parts[1] : timestamp
                    }
                    return (
                      <>
                        <text x="40" y="153" textAnchor="start" fontSize="9" fill="#9CA3AF">
                          {formatTime(first.date)}
                        </text>
                        <text x="780" y="153" textAnchor="end" fontSize="9" fill="#9CA3AF">
                          {formatTime(last.date)}
                        </text>
                      </>
                    )
                  })()}
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard