import { useCallback, useEffect, useState } from 'react'
import { ApiError, getHealth } from '../api/client'
import type { HealthResponse } from '../api/types'

type HealthState = 'checking' | 'ok' | 'ai_not_configured' | 'degraded' | 'down'

const LABELS: Record<HealthState, { text: string; dot: string; hint?: string }> = {
  checking: { text: 'checking…', dot: 'bg-gray-400' },
  ok: { text: 'backend ok', dot: 'bg-green-500' },
  ai_not_configured: {
    text: 'AI not configured',
    dot: 'bg-amber-500',
    hint: 'Set EMBEDDING_API_KEY (and optionally LLM_API_KEY) in backend/.env, then restart the backend.',
  },
  degraded: { text: 'database unavailable', dot: 'bg-red-500' },
  down: { text: 'backend unreachable', dot: 'bg-red-500' },
}

function stateFrom(health: HealthResponse): HealthState {
  if (health.database !== 'ok') return 'degraded'
  if (health.embeddings !== 'ready' || health.llm !== 'ready') return 'ai_not_configured'
  return 'ok'
}

export function HealthBadge() {
  const [state, setState] = useState<HealthState>('checking')

  const check = useCallback((signal?: AbortSignal) => {
    setState('checking')
    getHealth(signal)
      .then((health) => setState(stateFrom(health)))
      .catch((error: unknown) => {
        if (signal?.aborted) return
        console.error('Health check failed', error)
        setState(error instanceof ApiError && error.status === 503 ? 'degraded' : 'down')
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    check(controller.signal)
    return () => controller.abort()
  }, [check])

  const { text, dot, hint } = LABELS[state]
  return (
    <div className="flex items-center gap-2 text-sm text-gray-700" title={hint}>
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden />
      <span>{text}</span>
      {(state === 'down' || state === 'degraded') && (
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
