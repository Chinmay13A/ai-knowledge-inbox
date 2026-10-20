import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { QueryResponse } from '../api/types'
import { jsonResponse, mockFetch } from '../test/fixtures'
import { useAsk } from './useAsk'

function answer(question: string): QueryResponse {
  return { question, answer: `About ${question} [1].`, sources: [], model: 'fake:chat', truncated: false }
}

describe('useAsk', () => {
  it('stores the answer', async () => {
    mockFetch(async (_url, init) => jsonResponse(answer(JSON.parse(String(init.body)).question)))
    const { result } = renderHook(() => useAsk())

    await act(() => result.current.ask('RAG'))

    expect(result.current.result?.answer).toBe('About RAG [1].')
    expect(result.current.asking).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('keeps the previous answer when a new question fails', async () => {
    let fail = false
    mockFetch(() =>
      fail
        ? jsonResponse({ error: { code: 'llm_failed', message: 'Gemini rate limit reached, try again shortly' } }, 502)
        : jsonResponse(answer('first')),
    )
    const { result } = renderHook(() => useAsk())
    await act(() => result.current.ask('first'))

    fail = true
    await act(() => result.current.ask('second'))

    expect(result.current.error).toBe('Gemini rate limit reached, try again shortly')
    expect(result.current.result?.question).toBe('first')
  })

  it('only the latest question wins: earlier requests are aborted', async () => {
    const signals: AbortSignal[] = []
    const fetchMock = mockFetch(
      (_url, init) =>
        new Promise<Response>((resolve, reject) => {
          signals.push(init.signal as AbortSignal)
          const question = JSON.parse(String(init.body)).question
          init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
          // The first question is slow, the second fast.
          setTimeout(() => resolve(jsonResponse(answer(question))), question === 'slow' ? 50 : 5)
        }),
    )
    const { result } = renderHook(() => useAsk())

    await act(async () => {
      const first = result.current.ask('slow')
      const second = result.current.ask('fast')
      await Promise.all([first, second])
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(signals[0].aborted).toBe(true)
    expect(result.current.result?.question).toBe('fast')
    expect(result.current.asking).toBe(false)
  })
})
