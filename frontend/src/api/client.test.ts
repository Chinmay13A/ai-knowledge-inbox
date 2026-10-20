import { describe, expect, it, vi } from 'vitest'
import { jsonResponse, mockFetch } from '../test/fixtures'
import { ApiError, getItems, ingest, request } from './client'

describe('request', () => {
  it('returns parsed JSON on success', async () => {
    mockFetch(() => jsonResponse({ status: 'ok' }))

    await expect(request('/health')).resolves.toEqual({ status: 'ok' })
  })

  it('uses the backend error message and request id', async () => {
    mockFetch(() =>
      jsonResponse({ error: { code: 'url_not_allowed', message: 'Private address' } }, 422, { 'X-Request-ID': 'req-1' }),
    )

    const error = await request('/ingest').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, message: 'Private address', requestId: 'req-1' })
  })

  it('reports an unreachable backend as status 0', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))

    await expect(request('/items')).rejects.toMatchObject({ status: 0, message: 'Backend unreachable' })
  })
})

describe('endpoints', () => {
  it('getItems sends paging parameters', async () => {
    const fetchMock = mockFetch(() => jsonResponse({ items: [], total: 0, limit: 50, offset: 100 }))

    await getItems({ limit: 50, offset: 100 })

    const url = new URL(String(fetchMock.mock.calls[0][0]))
    expect(url.pathname).toBe('/items')
    expect(url.searchParams.get('limit')).toBe('50')
    expect(url.searchParams.get('offset')).toBe('100')
  })

  it('ingest posts the JSON body', async () => {
    const fetchMock = mockFetch(() => jsonResponse({ id: 1 }, 201))

    await ingest({ type: 'url', url: 'https://example.com' })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ type: 'url', url: 'https://example.com' })
  })
})
