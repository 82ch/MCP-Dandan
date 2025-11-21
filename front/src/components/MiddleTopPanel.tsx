import type { ServerInfo } from '../types'

interface MiddleTopPanelProps {
  serverInfo: ServerInfo | null
}

function MiddleTopPanel({ serverInfo }: MiddleTopPanelProps) {
  if (!serverInfo) {
    return (
      <div className="h-full bg-white flex items-center justify-center text-gray-500">
        <p>Select a server to view details</p>
      </div>
    )
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
              // Determine border color based on safety status
              // 0: 검사 전 (회색), 1: 안전 (파랑), 2: 위험 (빨강)
              const borderColor =
                tool.safety === 1 ? 'border-blue-400' :  // 안전 (ALLOW)
                tool.safety === 2 ? 'border-red-500' :    // 위험 (DENY)
                'border-gray-400'                         // 검사 전 또는 undefined

              // Split description into text and code parts
              // Look for common patterns: "text # Response Schema ```json..." or "text { type: ..."
              // Split at "# Response Schema", "# Schema", "Input schema:", "Output:", code blocks, or JSON-like structures
              const codeBlockMatch = tool.description.match(/([\s\S]*?)(?=#\s*(?:Response\s*)?Schema|```|Input\s*schema\s*:|Output\s*:|[{[][\s\S]*type:\s*['"](?:object|string|number))/i);
              const hasCodeBlock = /#\s*(?:Response\s*)?Schema|```[\s\S]*```|Input\s*schema\s*:|Output\s*:|([{[][\s\S]*type:\s*['"](?:object|string|number))/.test(tool.description);

              let textPart = '';
              let codePart = '';

              if (hasCodeBlock && codeBlockMatch) {
                textPart = codeBlockMatch[1]?.trim() || '';
                codePart = tool.description.substring(textPart.length).trim();
                // Add line breaks before "Input schema:" and "Output:" for better readability
                codePart = codePart.replace(/\s*(Input\s*schema\s*:)/gi, '\n$1');
                codePart = codePart.replace(/\s*(Output\s*:)/gi, '\n$1');
                codePart = codePart.trim();
              } else {
                textPart = tool.description;
              }

              return (
                <div key={index} className={`border-l-4 ${borderColor} pl-3 md:pl-4 py-2`}>
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
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MiddleTopPanel
