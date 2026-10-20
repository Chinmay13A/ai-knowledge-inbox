import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion, errorMessage, isAbortError } from '../api/client'
import type { QueryResponse } from '../api/types'

export interface AskState {
  result: QueryResponse | null
  asking: boolean
  error: string | null
  ask: (question: string) => Promise<void>
  reset: () => void
}

/**
 * Asks questions against POST /query. Only the latest question counts: asking again aborts the
 * previous request, so a slow earlier answer can never replace a newer one. The last answer stays
 * available while a new one loads or if the new one fails.
 */
export function useAsk(): AskState {
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const ask = useCallback(async (question: string) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setAsking(true)
    setError(null)
    try {
      setResult(await askQuestion({ question }, controller.signal))
    } catch (caught) {
      if (isAbortError(caught)) return
      setError(errorMessage(caught))
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null
        setAsking(false)
      }
    }
  }, [])

  const reset = useCallback(() => {
    inFlight.current?.abort()
    inFlight.current = null
    setResult(null)
    setError(null)
    setAsking(false)
  }, [])

  useEffect(() => () => inFlight.current?.abort(), [])

  return { result, asking, error, ask, reset }
}
