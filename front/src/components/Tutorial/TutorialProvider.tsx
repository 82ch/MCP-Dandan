import { useState, useEffect } from 'react'
import Joyride, { CallBackProps, STATUS, Step } from 'react-joyride'
import { dashboardSteps, serverViewSteps, TUTORIAL_STORAGE_KEY, TUTORIAL_SERVER_VIEW_KEY } from './tutorialSteps.tsx'

export type TutorialType = 'dashboard' | 'server'

interface TutorialProviderProps {
  run: boolean
  type: TutorialType
  onComplete: () => void
}

const joyrideStyles = {
  options: {
    primaryColor: '#3B82F6',
    zIndex: 10000,
  },
  tooltip: {
    borderRadius: 8,
    padding: 16,
  },
  tooltipTitle: {
    fontSize: 16,
    fontWeight: 600,
    marginBottom: 8,
  },
  tooltipContent: {
    fontSize: 14,
    lineHeight: 1.6,
    whiteSpace: 'pre-line' as const,
  },
  buttonNext: {
    backgroundColor: '#3B82F6',
    borderRadius: 6,
    padding: '8px 16px',
  },
  buttonBack: {
    color: '#6B7280',
    marginRight: 8,
  },
  buttonSkip: {
    color: '#9CA3AF',
  },
}

const joyrideLocale = {
  back: '이전',
  close: '닫기',
  last: '완료',
  next: '다음',
  skip: '건너뛰기',
}

function TutorialProvider({ run, type, onComplete }: TutorialProviderProps) {
  const [stepIndex, setStepIndex] = useState(0)
  const [joyrideKey, setJoyrideKey] = useState(0)

  const steps: Step[] = type === 'dashboard' ? dashboardSteps : serverViewSteps
  const storageKey = type === 'dashboard' ? TUTORIAL_STORAGE_KEY : TUTORIAL_SERVER_VIEW_KEY

  // run이 true로 바뀔 때 stepIndex를 리셋하고 Joyride 인스턴스를 재생성
  useEffect(() => {
    if (run) {
      setStepIndex(0)
      setJoyrideKey(prev => prev + 1)
    }
  }, [run])

  const handleCallback = (data: CallBackProps) => {
    const { status, index, action, type: callbackType } = data
    const finishedStatuses: string[] = [STATUS.FINISHED, STATUS.SKIPPED]

    console.log('[Tutorial] Callback:', { status, index, action, callbackType })

    // step 변경 추적
    if (callbackType === 'step:after' && action === 'next') {
      setStepIndex(index + 1)
    } else if (callbackType === 'step:after' && action === 'prev') {
      setStepIndex(index - 1)
    }

    // 에러 발생 시 튜토리얼 종료
    if (status === STATUS.ERROR) {
      console.error('[Tutorial] Error occurred, ending tutorial')
      onComplete()
      return
    }

    if (finishedStatuses.includes(status)) {
      localStorage.setItem(storageKey, 'true')
      onComplete()
    }
  }

  return (
    <Joyride
      key={joyrideKey}
      steps={steps}
      stepIndex={stepIndex}
      run={run}
      continuous
      showSkipButton
      showProgress
      scrollToFirstStep={false}
      disableScrolling={false}
      disableOverlayClose={false}
      disableCloseOnEsc={false}
      spotlightClicks={false}
      callback={handleCallback}
      styles={joyrideStyles}
      locale={joyrideLocale}
      floaterProps={{
        disableAnimation: true,
      }}
    />
  )
}

export default TutorialProvider
