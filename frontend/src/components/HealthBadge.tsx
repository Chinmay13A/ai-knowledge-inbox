import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../api/client'

type HealthState = 'checking' | 'ok' | 'down'

const LABELS: Record<HealthState, { text: string; dot: string }> = {
  checking: { text: 'checking…', dot: 'bg-gray-400' },
  ok: { text: 'backend ok', dot: 'bg-green-500' },
  down: { text: 'backend unreachable', dot: 'bg-red-500' },
}

export function HealthBadge() {
  const [state, setState] = useState<HealthState>('checking')

  const check = useCallback((signal?: AbortSignal) => {
    setState('checking')
    getHealth(signal)
      .then(() => setState('ok'))
      .catch((error: unknown) => {
        if (signal?.aborted) return
        console.error('Health check failed', error)
        setState('down')
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    check(controller.signal)
    return () => controller.abort()
  }, [check])

  const { text, dot } = LABELS[state]
  return (
    <div className="flex items-center gap-2 text-sm text-gray-700">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden />
      <span>{text}</span>
      {state === 'down' && (
        <button
          type="button"
          onClick={() => check()}
          className="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100"
        >
          retry
        </button>
      )}
    </div>
  )
}
