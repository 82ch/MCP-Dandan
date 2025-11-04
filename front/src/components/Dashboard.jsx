import { useEffect, useState } from 'react'
import { AlertTriangle, Shield, FileWarning, Database } from 'lucide-react'

const API_BASE_URL = 'http://localhost:3001/api'

const threatDefinitions = [
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
    name: 'Data Exfiltration',
    description: 'Sensitive information or credentials are exfiltrated to external destinations.',
    icon: Database,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200'
  }
]

function Dashboard({ setSelectedServer, servers }) {
  const [detectedEvents, setDetectedEvents] = useState([])
  const [topServers, setTopServers] = useState([])
  const [threatStats, setThreatStats] = useState({})

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/messages`)
      const allMessages = await response.json()

      // Process data for dashboard
      const events = []
      const serverDetectionCount = {}
      const threatCount = {}
      const threatAffectedServers = {}

      Object.entries(allMessages).forEach(([serverId, messages]) => {
        const server = servers.find(s => s.id === parseInt(serverId))
        if (!server) return

        serverDetectionCount[server.name] = 0

        messages.forEach(msg => {
          if (msg.maliciousScore > 0) {
            // Count detections per server
            serverDetectionCount[server.name] = (serverDetectionCount[server.name] || 0) + 1

            // Determine threat type based on message type or score
            let threatType = 'Tool Poisoning'
            let severity = 'Low'
            let severityColor = 'bg-yellow-400'

            if (msg.maliciousScore >= 8) {
              severity = 'High'
              severityColor = 'bg-red-500'
              threatType = msg.type.includes('tool') ? 'Tool Poisoning' : 'Data Exfiltration'
            } else if (msg.maliciousScore >= 5) {
              severity = 'Mid'
              severityColor = 'bg-orange-400'
              threatType = 'Command Injection'
            } else {
              severity = 'Low'
              severityColor = 'bg-yellow-400'
              threatType = 'Filesystem Exposure'
            }

            // Count threats
            threatCount[threatType] = (threatCount[threatType] || 0) + 1

            // Track affected servers per threat
            if (!threatAffectedServers[threatType]) {
              threatAffectedServers[threatType] = new Set()
            }
            threatAffectedServers[threatType].add(server.name)

            events.push({
              serverName: server.name,
              serverId: server.id,
              threatType,
              severity,
              severityColor,
              description: msg.data?.message?.params?.name || '—',
              lastSeen: msg.timestamp,
              messageId: msg.id
            })
          }
        })
      })

      // Sort servers by detection count
      const sortedServers = Object.entries(serverDetectionCount)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([name, count]) => ({ name, count }))

      // Build threat stats
      const stats = {}
      threatDefinitions.forEach(threat => {
        stats[threat.name] = {
          detections: threatCount[threat.name] || 0,
          affectedServers: threatAffectedServers[threat.name]?.size || 0
        }
      })

      setTopServers(sortedServers)
      setDetectedEvents(events)
      setThreatStats(stats)
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    }
  }

  const handleGoToServer = (serverId) => {
    const server = servers.find(s => s.id === serverId)
    if (server) {
      setSelectedServer(server)
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
            <div className="flex items-end justify-around gap-3 h-40">
              {topServers.map((server, index) => {
                const maxCount = topServers[0]?.count || 1
                const barHeightPx = Math.max(20, (server.count / maxCount) * 140)

                return (
                  <div key={index} className="flex flex-col items-center gap-1 flex-1 h-full justify-end">
                    <div className="text-xs text-gray-600 font-medium">{server.count}</div>
                    <div
                      className="w-full rounded-t transition-all duration-300"
                      style={{ height: `${barHeightPx}px`, backgroundColor: '#D4EDFA' }}
                    />
                    <div className="text-xs text-gray-700 text-center break-words w-full mt-1">{server.name}</div>
                  </div>
                )
              })}
            </div>
          )}
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
                    <Icon className={`${threat.color} flex-shrink-0`} size={20} />
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
                      onClick={() => handleGoToServer(event.serverId)}
                      className="px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
                    >
                      {event.serverName}
                    </button>
                  </td>
                </tr>
              ))}
              {detectedEvents.length === 0 && (
                <tr>
                  <td colSpan="6" className="px-6 py-8 text-center text-gray-500">
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