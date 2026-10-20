// TypeScript mirrors of the backend's API schemas (backend/app/models/schemas.py).

export type SourceType = 'note' | 'url'
export type ItemStatus = 'pending' | 'ready' | 'failed'

export interface Item {
  id: number
  source_type: SourceType
  title: string
  url: string | null
  status: ItemStatus
  error: string | null
  created_at: string
  chunk_count: number
  preview: string
}

export interface ItemList {
  items: Item[]
  total: number
  limit: number
  offset: number
}

export type IngestRequest = { type: 'note'; content: string } | { type: 'url'; url: string }

// Keep in sync with MAX_NOTE_CHARS in backend/app/models/schemas.py.
export const MAX_NOTE_CHARS = 50_000

export interface QueryRequest {
  question: string
  top_k?: number
}

export interface QuerySource {
  id: number // the n in the answer's [n] citations
  cited: boolean
  item_id: number
  item_title: string
  item_url: string | null
  source_type: SourceType
  chunk_index: number
  snippet: string
  score: number // cosine similarity, -1..1
}

export interface QueryResponse {
  question: string
  answer: string
  sources: QuerySource[]
  model: string | null // null when nothing relevant was found (no LLM call)
  truncated: boolean
}

// Keep in sync with MAX_QUERY_CHARS in backend/app/models/schemas.py.
export const MAX_QUESTION_CHARS = 1_000
