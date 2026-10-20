import type { HealthResponse, IngestRequest, Item, ItemList, QueryRequest, QueryResponse } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Error thrown for any failed API call; `status` is 0 when the backend could not be reached. */
export class ApiError extends Error {
  readonly status: number
  readonly requestId: string | null

  constructor(status: number, message: string, requestId: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.requestId = requestId
  }
}

/** Single entry point for all backend calls: JSON in, JSON out, readable errors. */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(0, 'Backend unreachable')
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(
      response.status,
      extractErrorMessage(body) ?? `Request failed with status ${response.status}`,
      response.headers.get('X-Request-ID'),
    )
  }
  return body as T
}

/** Reads FastAPI's `{detail}` or our `{error: {message}}` shape, whichever is present. */
function extractErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  const { detail, error } = body as { detail?: unknown; error?: { message?: unknown } }
  if (typeof error?.message === 'string') return error.message
  if (typeof detail === 'string') return detail
  return null
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal })
}

export function getItems(page: { limit: number; offset: number }, signal?: AbortSignal): Promise<ItemList> {
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) })
  return request<ItemList>(`/items?${query}`, { signal })
}

export function ingest(body: IngestRequest): Promise<Item> {
  return request<Item>('/ingest', { method: 'POST', body: JSON.stringify(body) })
}

/** Resolves once the item is gone (the API answers 204 with no body). */
export async function deleteItem(id: number): Promise<void> {
  await request<null>(`/items/${id}`, { method: 'DELETE' })
}

/** A user-facing message for any error thrown by the API layer. */
export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
}

export function askQuestion(body: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> {
  return request<QueryResponse>('/query', { method: 'POST', body: JSON.stringify(body), signal })
}
