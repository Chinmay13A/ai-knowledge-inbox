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
