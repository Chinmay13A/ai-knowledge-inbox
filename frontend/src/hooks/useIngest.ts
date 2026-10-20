import { useCallback, useState } from 'react'
import { errorMessage, ingest } from '../api/client'
import type { IngestRequest, Item } from '../api/types'

export interface IngestState {
  submit: (request: IngestRequest) => Promise<Item | null>
  submitting: boolean
  error: string | null
  clearError: () => void
}

/** Saves one note or URL. Returns the created item, or null (with `error` set) on failure. */
export function useIngest(): IngestState {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = useCallback(async (request: IngestRequest) => {
    setSubmitting(true)
    setError(null)
    try {
      return await ingest(request)
    } catch (caught) {
      setError(errorMessage(caught))
      return null
    } finally {
      setSubmitting(false)
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return { submit, submitting, error, clearError }
}
