import { useState } from 'react'
import type { ServerInfo } from '../types'

interface MiddleTopPanelProps {
  serverInfo: ServerInfo | null
  onToolSafetyUpdate?: (toolName: string, newSafety: number) => void
}

function MiddleTopPanel({ serverInfo, onToolSafetyUpdate }: MiddleTopPanelProps) {
  // Local state to track safety updates for immediate UI feedback
  const [localSafetyUpdates, setLocalSafetyUpdates] = useState<Record<string, number>>({})
  const [updatingTools, setUpdatingTools] = useState<Record<string, boolean>>({})

  if (!serverInfo) {
    return (
      <div className="h-full bg-white flex items-center justify-center text-gray-500">
        <p>Select a server to view details</p>
      </div>
    )
  }

  // 클릭 시 safety 순환: 1(초록) -> 2(주황) -> 3(빨강) -> 1(초록)
  const handleSafetyClick = async (toolName: string, currentSafety: number | undefined) => {
    // 0(회색)은 클릭 기능 제공하지 않음
    if (currentSafety === 0 || currentSafety === undefined) {
      return
    }

    // 이미 업데이트 중이면 무시
    if (updatingTools[toolName]) {
      return
    }

    // 다음 safety 값 계산: 1 -> 2 -> 3 -> 1
    const nextSafety = currentSafety === 3 ? 1 : currentSafety + 1

    setUpdatingTools(prev => ({ ...prev, [toolName]: true }))
    try {
      const success = await window.electronAPI.updateToolSafety(serverInfo.name, toolName, nextSafety)
      if (success) {
        setLocalSafetyUpdates(prev => ({ ...prev, [toolName]: nextSafety }))
        onToolSafetyUpdate?.(toolName, nextSafety)
      }
    } catch (error) {
      console.error('Failed to update safety:', error)
    } finally {
      setUpdatingTools(prev => ({ ...prev, [toolName]: false }))
    }
  }

  return (
    <div className="h-full bg-white overflow-y-auto">
      <div className="p-4 md:p-6">
        {/* Server Name */}
        <div className="mb-4 md:mb-6">
          <h3 className="text-xs md:text-sm font-semibold text-gray-500 mb-1">Server name</h3>
          <p className="text-base md:text-lg font-medium text-gray-800 wrap-break-words">{serverInfo.name}</p>
        </div>

        {/* Server Type */}
        <div className="mb-4 md:mb-6">
          <h3 className="text-xs md:text-sm font-semibold text-gray-500 mb-1">Server type</h3>
          <p className="text-sm md:text-base text-gray-700">{serverInfo.type}</p>
        </div>

        {/* Tools List */}
        <div>
          <h3 className="text-xs md:text-sm font-semibold text-gray-500 mb-3">Available Tools</h3>
          <div className="space-y-3 md:space-y-4">
            {serverInfo.tools.map((tool, index) => {
              // Use local update if available, otherwise use original safety
              const effectiveSafety = localSafetyUpdates[tool.name] ?? tool.safety
              const isUpdating = updatingTools[tool.name]

              // Determine background color based on safety status
              // 0: 검사 전 (회색), 1: 안전 (초록), 2: 조치권장 (노랑), 3: 조치필요 (빨강)
              const bgColor =
                effectiveSafety === 1 ? 'bg-green-500' :
                effectiveSafety === 2 ? 'bg-yellow-400' :
                effectiveSafety === 3 ? 'bg-red-500' :
                'bg-gray-400'

              // 클릭 가능 여부 (0이 아닌 경우에만)
              const isClickable = effectiveSafety !== 0 && effectiveSafety !== undefined

              // Split description into text and code parts
              const codeBlockMatch = tool.description.match(/([\s\S]*?)(?=#\s*(?:Response\s*)?Schema|```|Input\s*schema\s*:|Output\s*:|[{[][\s\S]*type:\s*['"](?:object|string|number))/i);
              const hasCodeBlock = /#\s*(?:Response\s*)?Schema|```[\s\S]*```|Input\s*schema\s*:|Output\s*:|([{[][\s\S]*type:\s*['"](?:object|string|number))/.test(tool.description);

              let textPart = '';
              let codePart = '';

              if (hasCodeBlock && codeBlockMatch) {
                textPart = codeBlockMatch[1]?.trim() || '';
                codePart = tool.description.substring(textPart.length).trim();
                codePart = codePart.replace(/\s*(Input\s*schema\s*:)/gi, '\n$1');
                codePart = codePart.replace(/\s*(Output\s*:)/gi, '\n$1');
                codePart = codePart.trim();
              } else {
                textPart = tool.description;
              }

              return (
                <div key={index} className="flex">
                  {/* Clickable Border - 투명한 클릭 영역 + 보이는 바 */}
                  <div className="relative flex-shrink-0">
                    <div className={`w-1 h-full ${bgColor}`} />
                    <button
                      onClick={() => handleSafetyClick(tool.name, effectiveSafety)}
                      disabled={!isClickable || isUpdating}
                      className={`absolute inset-0 -left-2 -right-2 w-auto
                        ${isClickable && !isUpdating ? 'hover:opacity-70 cursor-pointer' : ''}
                        ${isUpdating ? 'opacity-50 cursor-wait' : ''}
                        ${!isClickable ? 'cursor-default' : ''}
                      `}
                      style={{ width: 'calc(100% + 16px)', left: '-8px' }}
                      title={isClickable ? '클릭하여 위험도 변경' : '검사 전'}
                    />
                  </div>
                  {/* Tool Content */}
                  <div className="flex-1 pl-3 md:pl-4 py-2">
                    <h4 className="font-mono text-xs md:text-sm font-semibold text-gray-800 mb-1 wrap-break-words">
                      {tool.name}
                    </h4>
                    {textPart && (
                      <p className="text-xs text-gray-600 leading-relaxed wrap-break-words mb-2">
                        {textPart}
                      </p>
                    )}
                    {codePart && (
                      <pre className="text-xs text-gray-600 bg-gray-50 p-2 rounded overflow-x-auto max-h-60 overflow-y-auto border border-gray-200">
                        <code className="font-mono">{codePart}</code>
                      </pre>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MiddleTopPanel
