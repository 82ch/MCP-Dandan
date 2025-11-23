import type { Step } from 'react-joyride'
import { AlertTriangle, Clock } from 'lucide-react'

// MCP Servers 설명용 컴포넌트
const ServerListContent = () => (
  <div>
    <p>모니터링 중인 MCP 서버 목록입니다. 각 서버의 상태와 위험도를 아이콘으로 확인할 수 있습니다.</p>
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className="text-red-500" />
        <span>조치필요</span>
      </div>
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className="text-orange-400" />
        <span>조치권장</span>
      </div>
      <div className="flex items-center gap-2">
        <Clock size={14} className="text-gray-500 animate-spin" />
        <span>검사 중</span>
      </div>
    </div>
  </div>
)

// Available Tools 설명용 컴포넌트
const ToolsListContent = () => (
  <div>
    <p>서버에서 제공하는 도구 목록입니다.</p>
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 bg-green-500 rounded-sm" />
        <span>안전</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 bg-yellow-400 rounded-sm" />
        <span>조치권장</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 bg-red-500 rounded-sm" />
        <span>조치필요</span>
      </div>
    </div>
    <p className="mt-3 text-sm text-gray-600">색상 바를 클릭하여 위험도를 수동으로 변경할 수 있습니다.</p>
  </div>
)

// Chat Messages 설명용 컴포넌트
const ChatPanelContent = () => (
  <div>
    <p>MCP 서버와의 통신 내역입니다.</p>
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 bg-blue-100 rounded-full" />
        <span>클라이언트 요청</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 bg-gray-200 rounded-full" />
        <span>서버 응답</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 bg-yellow-100 rounded-full" />
        <span>프록시 이벤트</span>
      </div>
    </div>
    <p className="mt-3 text-sm text-gray-600">각 메시지 하단의 점 색상으로 위험도를 확인할 수 있습니다.</p>
  </div>
)

// 대시보드 화면 튜토리얼 단계
export const dashboardSteps: Step[] = [
  {
    target: '[data-tutorial="dashboard-btn"]',
    content: '대시보드에서 전체 보안 현황을 한눈에 확인할 수 있습니다. 탐지된 위협과 영향받은 서버 통계를 볼 수 있습니다.',
    title: 'Dashboard',
    disableBeacon: true,
    placement: 'right',
  },
  {
    target: '[data-tutorial="server-list"]',
    content: <ServerListContent />,
    title: 'MCP Servers',
    placement: 'right',
  },
  {
    target: '[data-tutorial="top-servers"]',
    content: '가장 많은 보안 이벤트가 탐지된 서버 순위와 시간별 추이를 그래프로 확인할 수 있습니다.',
    title: 'Top Affected Servers',
    placement: 'right',
  },
  {
    target: '[data-tutorial="threats-panel"]',
    content: 'Tool Poisoning, Command Injection, Filesystem Exposure 등 위협 유형별 탐지 현황을 보여줍니다.',
    title: 'Threats',
    placement: 'left',
  },
  {
    target: '[data-tutorial="detected-table"]',
    content: '탐지된 보안 이벤트의 상세 내역입니다. 서버명, 위협 유형, 심각도를 확인하고 해당 서버로 이동할 수 있습니다.\n\n다음 단계에서 MCP 서버 상세 화면을 살펴봅니다.',
    title: 'Detected Events',
    placement: 'top',
  },
]

// MCP 서버 상세 화면 튜토리얼 단계
export const serverViewSteps: Step[] = [
  {
    target: '[data-tutorial="server-info"]',
    content: '선택한 MCP 서버의 상세 정보입니다. 서버 이름과 연결 타입(stdio/sse)을 확인할 수 있습니다.',
    title: 'Server Info',
    disableBeacon: true,
    placement: 'bottom',
  },
  {
    target: '[data-tutorial="tools-list"]',
    content: <ToolsListContent />,
    title: 'Available Tools',
    placement: 'bottom',
  },
  {
    target: '[data-tutorial="chat-panel"]',
    content: <ChatPanelContent />,
    title: 'Chat Messages',
    placement: 'left',
  },
  {
    target: '[data-tutorial="message-detail"]',
    content: '선택한 메시지의 상세 정보입니다. 악성 점수, 탐지 엔진 결과, 파라미터 등을 확인할 수 있습니다.',
    title: 'Message Details',
    placement: 'top',
  },
  {
    target: '[data-tutorial="settings-btn"]',
    content: '튜토리얼을 다시 보려면 이 버튼을 클릭하세요!',
    title: 'Tutorial',
    placement: 'top',
  },
]

export const TUTORIAL_STORAGE_KEY = '82ch-tutorial-completed'
export const TUTORIAL_SERVER_VIEW_KEY = '82ch-tutorial-server-completed'
