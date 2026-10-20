import { vi } from 'vitest'
import type { Item, ItemList } from '../api/types'

export function makeItem(overrides: Partial<Item> = {}): Item {
  return {
    id: 1,
    source_type: 'note',
    title: 'A note',
    url: null,
    status: 'ready',
    error: null,
    created_at: new Date().toISOString(),
    chunk_count: 1,
    preview: 'A note about something.',
    ...overrides,
  }
}

export function itemList(items: Item[], total = items.length): ItemList {
  return { items, total, limit: 50, offset: 0 }
}

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })
}

type Handler = (url: URL, init: RequestInit) => Response | Promise<Response>

/** Replaces global fetch; every call is recorded so tests can assert on requests. */
export function mockFetch(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    if (init.signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
    return Promise.resolve(handler(new URL(String(input)), init))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
