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
    if (error instanceof DOMException && error.name === 'AbortError') throw error
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

export interface HealthResponse {
  status: string
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal })
}
