import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { itemList, jsonResponse, makeItem, mockFetch } from '../test/fixtures'
import { MAX_POLL_INTERVAL_MS, POLL_INTERVAL_MS, useItems } from './useItems'

/** Lets pending promises and (fake) timers run inside act(). */
async function advance(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('useItems', () => {
  it('loads the first page', async () => {
    vi.useFakeTimers()
    mockFetch(() => jsonResponse(itemList([makeItem({ id: 2 }), makeItem({ id: 1 })])))

    const { result } = renderHook(() => useItems())
    expect(result.current.loading).toBe(true)
    await advance()

    expect(result.current.loading).toBe(false)
    expect(result.current.items.map((item) => item.id)).toEqual([2, 1])
    expect(result.current.total).toBe(2)
    expect(result.current.hasMore).toBe(false)
  })

  it('polls while an item is pending and stops once it is ready', async () => {
    vi.useFakeTimers()
    const statuses = ['pending', 'pending', 'ready'] as const
    let call = 0
    const fetchMock = mockFetch(() =>
      jsonResponse(itemList([makeItem({ status: statuses[Math.min(call++, statuses.length - 1)] })])),
    )

    const { result } = renderHook(() => useItems())
    await advance()
    expect(result.current.items[0].status).toBe('pending')

    await advance(POLL_INTERVAL_MS)
    expect(result.current.items[0].status).toBe('pending')
    await advance(POLL_INTERVAL_MS * 2) // unchanged status → the next poll waits twice as long
    expect(result.current.items[0].status).toBe('ready')

    const callsWhenReady = fetchMock.mock.calls.length
    await advance(MAX_POLL_INTERVAL_MS * 2)
    expect(fetchMock.mock.calls.length).toBe(callsWhenReady)
  })

  it('backs off when a pending item never changes, up to the maximum interval', async () => {
    vi.useFakeTimers()
    const fetchMock = mockFetch(() => jsonResponse(itemList([makeItem({ status: 'pending' })])))
    renderHook(() => useItems())
    await advance()

    // Waits 2s, 4s, 8s, 16s, then is capped at 30s between polls.
    for (const [index, wait] of [2_000, 4_000, 8_000, 16_000].entries()) {
      await advance(wait - 1)
      expect(fetchMock).toHaveBeenCalledTimes(index + 1)
      await advance(1)
      expect(fetchMock).toHaveBeenCalledTimes(index + 2)
    }
    await advance(MAX_POLL_INTERVAL_MS - 1)
    expect(fetchMock).toHaveBeenCalledTimes(5)
    await advance(1)
    expect(fetchMock).toHaveBeenCalledTimes(6)
    await advance(MAX_POLL_INTERVAL_MS)
    expect(fetchMock).toHaveBeenCalledTimes(7)
  })

  it('addItem puts the new item on top without refetching', async () => {
    vi.useFakeTimers()
    const fetchMock = mockFetch(() => jsonResponse(itemList([makeItem({ id: 1 })])))
    const { result } = renderHook(() => useItems())
    await advance()

    act(() => result.current.addItem(makeItem({ id: 7, title: 'New' })))

    expect(result.current.items.map((item) => item.id)).toEqual([7, 1])
    expect(result.current.total).toBe(2)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('loadMore appends the next page using the current offset', async () => {
    vi.useFakeTimers()
    const fetchMock = mockFetch((url) =>
      url.searchParams.get('offset') === '0'
        ? jsonResponse(itemList([makeItem({ id: 3 }), makeItem({ id: 2 })], 3))
        : jsonResponse(itemList([makeItem({ id: 1 })], 3)),
    )
    const { result } = renderHook(() => useItems())
    await advance()
    expect(result.current.hasMore).toBe(true)

    act(() => result.current.loadMore())
    await advance()

    expect(new URL(String(fetchMock.mock.calls[1][0])).searchParams.get('offset')).toBe('2')
    expect(result.current.items.map((item) => item.id)).toEqual([3, 2, 1])
    expect(result.current.hasMore).toBe(false)
  })

  it('exposes errors and recovers on refresh', async () => {
    vi.useFakeTimers()
    let fail = true
    mockFetch(() => (fail ? jsonResponse({ error: { message: 'Database is locked' } }, 500) : jsonResponse(itemList([]))))
    const { result } = renderHook(() => useItems())
    await advance()
    expect(result.current.error).toBe('Database is locked')

    fail = false
    act(() => result.current.refresh())
    await advance()

    expect(result.current.error).toBeNull()
  })
})
